"""
Background video-processing pipeline.

process_video(video_id, db)  — full pipeline for a single video:
    downloading → transcribing → chunking → embedding → indexing

process_channel(channel_id, db) — enqueue all pending videos for a channel.

A module-level asyncio.Semaphore caps concurrent downloads so the system
does not hammer YouTube or the OpenAI API simultaneously.
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
from .transcription import transcribe
from .vector_store import add_chunks
from .youtube_service import download_audio, get_channel_videos

logger = logging.getLogger(__name__)
settings = get_settings()

# Limit concurrent downloads/transcriptions
_sem = asyncio.Semaphore(settings.max_concurrent_downloads)


# ── Single-video pipeline ─────────────────────────────────────────────────────

async def process_video(video_id: int, db: Optional[Session] = None) -> None:
    """
    Run the full processing pipeline for one video (by DB primary key).

    Opens its own DB session if none is provided so it can be safely
    called from a background task.
    """
    own_session = db is None
    if own_session:
        db = SessionLocal()

    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            logger.error("process_video: video %d not found", video_id)
            return

        channel = db.query(Channel).filter(Channel.id == video.channel_id).first()
        if not channel:
            logger.error("process_video: channel not found for video %d", video_id)
            return

        async with _sem:
            await _run_pipeline(video, channel, db)
    finally:
        if own_session:
            db.close()


async def _run_pipeline(video: Video, channel: Channel, db: Session) -> None:
    audio_path: Optional[str] = None

    def _set_status(status: VideoStatus, error: Optional[str] = None):
        video.status = status
        if error:
            video.error_message = error
            logger.error("Video %s failed at %s: %s", video.video_id, status.value, error)
        video.updated_at = datetime.now(timezone.utc)
        db.commit()

    try:
        # ── Step 1: Download audio ────────────────────────────────────────────
        _set_status(VideoStatus.downloading)
        audio_path = await download_audio(video.url, settings.audio_temp_dir)

        # ── Step 2: Transcribe ────────────────────────────────────────────────
        _set_status(VideoStatus.transcribing)
        segments = await transcribe(video.video_id, audio_path)

        # Delete audio immediately — we only needed what was said
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
            audio_path = None

        if not segments:
            _set_status(VideoStatus.failed, "Transcription produced no segments")
            return

        # ── Step 3: Chunk ─────────────────────────────────────────────────────
        _set_status(VideoStatus.indexing)
        chunks = chunk_transcript(
            segments=segments,
            video_id=video.video_id,
            video_title=video.title,
            channel_id=channel.id,
            channel_name=channel.name,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )

        # ── Step 4: Embed + store ─────────────────────────────────────────────
        await add_chunks(chunks)

        # ── Step 5: Mark complete ─────────────────────────────────────────────
        video.status       = VideoStatus.completed
        video.chunk_count  = len(chunks)
        video.processed_at = datetime.now(timezone.utc)
        video.updated_at   = datetime.now(timezone.utc)
        video.error_message = None
        db.commit()
        logger.info("Video %s processed successfully (%d chunks)", video.video_id, len(chunks))

    except Exception as exc:
        # Clean up audio on any failure
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except OSError:
                pass
        _set_status(VideoStatus.failed, str(exc))


# ── Channel-level trigger ─────────────────────────────────────────────────────

async def process_channel(channel_id: int) -> None:
    """
    Fetch video list from YouTube, persist new videos, and enqueue processing.

    Skips videos that are already completed or currently in-flight.
    """
    db = SessionLocal()
    try:
        channel = db.query(Channel).filter(Channel.id == channel_id).first()
        if not channel:
            logger.error("process_channel: channel %d not found", channel_id)
            return

        channel.status = ChannelStatus.processing
        db.commit()

        # Fetch latest video list from YouTube
        try:
            yt_videos = await get_channel_videos(channel.url)
        except Exception as exc:
            logger.error("Could not fetch videos for channel %d: %s", channel_id, exc)
            channel.status = ChannelStatus.error
            db.commit()
            return

        # Persist any new videos
        existing_ids = {v.video_id for v in db.query(Video).filter(Video.channel_id == channel.id).all()}
        new_videos = []
        for v in yt_videos:
            if v["video_id"] in existing_ids:
                continue
            db_video = Video(
                video_id    = v["video_id"],
                channel_id  = channel.id,
                title       = v["title"],
                url         = v["url"],
                duration    = v.get("duration"),
                upload_date = v.get("upload_date"),
                thumbnail_url = v.get("thumbnail_url"),
                status      = VideoStatus.pending,
            )
            db.add(db_video)
            new_videos.append(db_video)

        channel.video_count = len(existing_ids) + len(new_videos)
        channel.status = ChannelStatus.active
        db.commit()

        # Refresh to get IDs
        for v in new_videos:
            db.refresh(v)

        logger.info("Channel %d: %d new videos queued", channel_id, len(new_videos))

        # Also pick up any previously failed/pending videos
        all_pending = db.query(Video).filter(
            Video.channel_id == channel.id,
            Video.status.in_([VideoStatus.pending, VideoStatus.failed]),
        ).all()
        pending_ids = [v.id for v in all_pending]

    finally:
        db.close()

    # Fire-and-forget — process each video as a concurrent task
    tasks = [asyncio.create_task(process_video(vid_id)) for vid_id in pending_ids]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
