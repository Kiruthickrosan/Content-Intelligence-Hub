"""
Background video-processing pipeline.

process_video(video_id)
    Caption check → (audio download if needed) → transcribe →
    chunk → embed → ChromaDB → mark completed

process_channel(channel_id)
    Fetch video list → save new videos → process pending/failed videos.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import SessionLocal
from ..models import Channel, ChannelStatus, Video, VideoStatus
from .chunking import chunk_transcript
from .transcription import get_english_captions, transcribe_with_whisper
from .vector_store import add_chunks
from .youtube_service import download_audio, get_channel_videos

logger = logging.getLogger(__name__)
settings = get_settings()

_sem = asyncio.Semaphore(settings.max_concurrent_downloads)


# ─────────────────────────────────────────────────────────────────────────────
# SINGLE VIDEO PROCESSING — public entry point
# ─────────────────────────────────────────────────────────────────────────────

async def process_video(
    video_id: int,
    db: Optional[Session] = None,
) -> None:
    """Process one video row (by its SQLite primary key)."""

    own_session = db is None
    if own_session:
        db = SessionLocal()

    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            logger.error("process_video: video row %d not found", video_id)
            return

        channel = db.query(Channel).filter(Channel.id == video.channel_id).first()
        if not channel:
            logger.error("process_video: channel not found for video %d", video_id)
            return

        logger.info("Starting pipeline: %s (%s)", video.title, video.video_id)

        async with _sem:
            await _run_pipeline(video, channel, db)

    except Exception:
        logger.exception("Unexpected error processing video row %d", video_id)
    finally:
        if own_session:
            db.close()


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

async def _run_pipeline(
    video: Video,
    channel: Channel,
    db: Session,
) -> None:
    """
    Caption-first pipeline:

        1. Try English YouTube captions          (no audio download)
        2. If captions missing → download audio → Whisper translate
        3. Deduplicate + chunk transcript
        4. Embed + store in ChromaDB
        5. Mark video completed
    """

    audio_path: Optional[str] = None

    def _set_status(status: VideoStatus, error: Optional[str] = None) -> None:
        video.status = status
        if error:
            video.error_message = error
            logger.error("Video %s → %s: %s", video.video_id, status.value, error)
        video.updated_at = datetime.now(timezone.utc)
        db.commit()

    try:
        # ── STEP 1 ─ Try English captions first ──────────────────────────────
        logger.info("Video %s → checking English captions", video.video_id)
        _set_status(VideoStatus.transcribing)

        segments = await get_english_captions(video.video_id)

        if segments:
            logger.info(
                "Video %s → English captions found (%d segments) — skipping audio download",
                video.video_id, len(segments),
            )

        else:
            # ── STEP 2 ─ No captions → download audio + Whisper ──────────────
            logger.info(
                "Video %s → no English captions — downloading audio",
                video.video_id,
            )
            _set_status(VideoStatus.downloading)

            audio_path = await download_audio(
                video.url,
                settings.audio_temp_dir,
            )
            logger.info("Video %s → audio: %s", video.video_id, audio_path)

            _set_status(VideoStatus.transcribing)
            logger.info("Video %s → running Whisper (translate)", video.video_id)

            segments = await transcribe_with_whisper(audio_path)
            logger.info(
                "Video %s → Whisper produced %d segments",
                video.video_id, len(segments),
            )

            # Clean up audio immediately after transcription
            _cleanup_audio(audio_path)
            audio_path = None

        # ── Validate transcript ───────────────────────────────────────────────
        if not segments:
            _set_status(VideoStatus.failed, "Transcription produced no segments")
            return

        # ── STEP 3 ─ Chunk ────────────────────────────────────────────────────
        _set_status(VideoStatus.indexing)
        logger.info("Video %s → chunking transcript", video.video_id)

        chunks = chunk_transcript(
            segments=segments,
            video_id=video.video_id,
            video_title=video.title,
            channel_id=channel.id,
            channel_name=channel.name,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
        logger.info("Video %s → %d chunks created", video.video_id, len(chunks))

        if not chunks:
            _set_status(VideoStatus.failed, "Chunking produced no chunks")
            return

        # ── STEP 4 ─ Embed + ChromaDB ─────────────────────────────────────────
        logger.info("Video %s → embedding and storing %d chunks", video.video_id, len(chunks))
        await add_chunks(chunks)
        logger.info("Video %s → ChromaDB upsert done", video.video_id)

        # ── STEP 5 ─ Mark completed ───────────────────────────────────────────
        video.status = VideoStatus.completed
        video.chunk_count = len(chunks)
        video.processed_at = datetime.now(timezone.utc)
        video.updated_at = datetime.now(timezone.utc)
        video.error_message = None
        db.commit()

        logger.info(
            "Video %s completed — %d chunks indexed",
            video.video_id, len(chunks),
        )

    except Exception as exc:
        _cleanup_audio(audio_path)
        try:
            _set_status(VideoStatus.failed, str(exc))
        except Exception:
            logger.exception("Could not save failed status for %s", video.video_id)
        logger.exception("Pipeline failed for %s", video.video_id)


def _cleanup_audio(path: Optional[str]) -> None:
    if path and os.path.exists(path):
        try:
            os.remove(path)
            logger.info("Temporary audio removed: %s", path)
        except OSError as exc:
            logger.warning("Could not remove audio %s: %s", path, exc)


# ─────────────────────────────────────────────────────────────────────────────
# CHANNEL PROCESSING  (unchanged logic, kept for existing /channels routes)
# ─────────────────────────────────────────────────────────────────────────────

async def process_channel(channel_id: int) -> None:
    """
    Fetch the latest video list for a channel, save any new videos,
    then process all pending/failed videos one by one.

    NOTE: This is NOT the primary production flow.
    The primary flow is: user pastes a single video URL → process_video().
    This function exists only to support the /channels/{id}/sync admin endpoint.
    """
    db = SessionLocal()
    try:
        channel = db.query(Channel).filter(Channel.id == channel_id).first()
        if not channel:
            logger.error("process_channel: channel %d not found", channel_id)
            return

        logger.info("Syncing channel: %s (%s)", channel.name, channel.channel_id)
        channel.status = ChannelStatus.processing
        db.commit()

        # Fetch video list
        try:
            yt_videos = await get_channel_videos(channel.url)
        except Exception as exc:
            logger.error("Could not fetch video list for channel %d: %s", channel_id, exc)
            channel.status = ChannelStatus.error
            db.commit()
            return

        # Save new videos
        new_count = 0
        for v in yt_videos:
            exists = db.query(Video).filter(Video.video_id == v["video_id"]).first()
            if not exists:
                db.add(Video(
                    video_id=v["video_id"],
                    channel_id=channel_id,
                    title=v["title"],
                    url=v["url"],
                    duration=v.get("duration"),
                    upload_date=v.get("upload_date"),
                    thumbnail_url=v.get("thumbnail_url"),
                    status=VideoStatus.pending,
                ))
                new_count += 1

        db.commit()
        logger.info("Channel %d: %d new videos saved", channel_id, new_count)

        # Process pending / failed videos
        to_process = (
            db.query(Video)
            .filter(
                Video.channel_id == channel_id,
                Video.status.in_([VideoStatus.pending, VideoStatus.failed]),
            )
            .all()
        )

        logger.info(
            "Channel %d: processing %d videos", channel_id, len(to_process)
        )

        for video in to_process:
            await process_video(video.id, db)

        channel.status = ChannelStatus.active
        db.commit()
        logger.info("Channel %d sync complete", channel_id)

    except Exception:
        logger.exception("process_channel failed for channel %d", channel_id)
        try:
            Channel.status = ChannelStatus.error
            db.commit()
        except Exception:
            pass
    finally:
        db.close()