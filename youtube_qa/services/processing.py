"""
Background video-processing pipeline.

process_video(video_id, db)
    Full pipeline for a single video:

    downloading
        ↓
    transcribing
        ↓
    chunking
        ↓
    embedding
        ↓
    indexing
        ↓
    completed

process_channel(channel_id)
    Fetch all videos from a YouTube channel, save new videos,
    and process pending/failed/stale videos.

Transcription uses YouTube captions first and falls back to
local Faster-Whisper. No OpenAI transcription credits are required.
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


# ─────────────────────────────────────────────────────────────────────────────
# Limit concurrent processing
# ─────────────────────────────────────────────────────────────────────────────

_sem = asyncio.Semaphore(settings.max_concurrent_downloads)


# ─────────────────────────────────────────────────────────────────────────────
# SINGLE VIDEO PROCESSING
# ─────────────────────────────────────────────────────────────────────────────

async def process_video(
    video_id: int,
    db: Optional[Session] = None,
) -> None:
    """
    Process one video using its database ID.

    Steps:

        1. Download audio
        2. Transcribe audio
        3. Chunk transcript
        4. Generate embeddings
        5. Store chunks in ChromaDB
        6. Mark video as completed

    If no DB session is provided, a new session is created.
    """

    own_session = db is None

    if own_session:
        db = SessionLocal()

    try:
        # ─────────────────────────────────────────────────────────────────────
        # Find video
        # ─────────────────────────────────────────────────────────────────────

        video = (
            db.query(Video)
            .filter(Video.id == video_id)
            .first()
        )

        if not video:
            logger.error(
                "process_video: video %d not found",
                video_id,
            )
            return

        # ─────────────────────────────────────────────────────────────────────
        # Find channel
        # ─────────────────────────────────────────────────────────────────────

        channel = (
            db.query(Channel)
            .filter(Channel.id == video.channel_id)
            .first()
        )

        if not channel:
            logger.error(
                "process_video: channel not found for video %d",
                video_id,
            )
            return

        logger.info(
            "Starting processing: %s (%s)",
            video.title,
            video.video_id,
        )

        # ─────────────────────────────────────────────────────────────────────
        # Limit concurrent processing
        # ─────────────────────────────────────────────────────────────────────

        async with _sem:
            await _run_pipeline(
                video,
                channel,
                db,
            )

    except Exception:
        logger.exception(
            "Unexpected error while processing video %d",
            video_id,
        )

    finally:
        if own_session:
            db.close()


# ─────────────────────────────────────────────────────────────────────────────
# VIDEO PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

async def _run_pipeline(
    video: Video,
    channel: Channel,
    db: Session,
) -> None:
    """
    Execute the complete processing pipeline for one video.
    """

    audio_path: Optional[str] = None

    def _set_status(
        status: VideoStatus,
        error: Optional[str] = None,
    ) -> None:
        """
        Update video status safely.
        """

        video.status = status

        if error:
            video.error_message = error

            logger.error(
                "Video %s failed at %s: %s",
                video.video_id,
                status.value,
                error,
            )

        video.updated_at = datetime.now(timezone.utc)

        db.commit()

    try:

        # ─────────────────────────────────────────────────────────────────────
        # STEP 1 — DOWNLOAD AUDIO
        # ─────────────────────────────────────────────────────────────────────

        logger.info(
            "Video %s → downloading audio",
            video.video_id,
        )

        _set_status(VideoStatus.downloading)

        audio_path = await download_audio(
            video.url,
            settings.audio_temp_dir,
        )

        logger.info(
            "Video %s → audio downloaded: %s",
            video.video_id,
            audio_path,
        )

        # ─────────────────────────────────────────────────────────────────────
        # STEP 2 — TRANSCRIPTION
        # ─────────────────────────────────────────────────────────────────────

        logger.info(
            "Video %s → transcribing",
            video.video_id,
        )

        _set_status(VideoStatus.transcribing)

        segments = await transcribe(
            video.video_id,
            audio_path,
        )

        logger.info(
            "Video %s → transcription returned %d segments",
            video.video_id,
            len(segments),
        )

        # ─────────────────────────────────────────────────────────────────────
        # Remove audio after transcription
        # ─────────────────────────────────────────────────────────────────────

        if audio_path and os.path.exists(audio_path):

            try:
                os.remove(audio_path)

                logger.info(
                    "Video %s → temporary audio removed",
                    video.video_id,
                )

            except OSError as exc:

                logger.warning(
                    "Could not remove audio file %s: %s",
                    audio_path,
                    exc,
                )

            audio_path = None

        # ─────────────────────────────────────────────────────────────────────
        # Validate transcript
        # ─────────────────────────────────────────────────────────────────────

        if not segments:

            _set_status(
                VideoStatus.failed,
                "Transcription produced no segments",
            )

            return

        # ─────────────────────────────────────────────────────────────────────
        # STEP 3 — CHUNK TRANSCRIPT
        # ─────────────────────────────────────────────────────────────────────

        logger.info(
            "Video %s → creating transcript chunks",
            video.video_id,
        )

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

        logger.info(
            "Video %s → created %d chunks",
            video.video_id,
            len(chunks),
        )

        if not chunks:

            _set_status(
                VideoStatus.failed,
                "Transcript chunking produced no chunks",
            )

            return

        # ─────────────────────────────────────────────────────────────────────
        # STEP 4 — EMBEDDINGS + CHROMADB
        # ─────────────────────────────────────────────────────────────────────

        logger.info(
            "Video %s → adding %d chunks to vector store",
            video.video_id,
            len(chunks),
        )

        await add_chunks(chunks)

        logger.info(
            "Video %s → chunks indexed successfully",
            video.video_id,
        )

        # ─────────────────────────────────────────────────────────────────────
        # STEP 5 — MARK COMPLETED
        # ─────────────────────────────────────────────────────────────────────

        video.status = VideoStatus.completed
        video.chunk_count = len(chunks)
        video.processed_at = datetime.now(timezone.utc)
        video.updated_at = datetime.now(timezone.utc)
        video.error_message = None

        db.commit()

        logger.info(
            "Video %s processed successfully (%d chunks)",
            video.video_id,
            len(chunks),
        )

    except Exception as exc:

        # ─────────────────────────────────────────────────────────────────────
        # Cleanup temporary audio
        # ─────────────────────────────────────────────────────────────────────

        if audio_path and os.path.exists(audio_path):

            try:
                os.remove(audio_path)

            except OSError:
                pass

        # ─────────────────────────────────────────────────────────────────────
        # Mark video as failed
        # ─────────────────────────────────────────────────────────────────────

        try:
            _set_status(
                VideoStatus.failed,
                str(exc),
            )

        except Exception:
            logger.exception(
                "Could not update failed status for video %s",
                video.video_id,
            )

        logger.exception(
            "Pipeline failed for video %s",
            video.video_id,
        )


# ─────────────────────────────────────────────────────────────────────────────
# CHANNEL PROCESSING
# ─────────────────────────────────────────────────────────────────────────────

async def process_channel(
    channel_id: int,
) -> None:
    """
    Fetch videos from YouTube, save new videos, and process videos
    that are pending, failed, or stuck in an intermediate state.
    """

    logger.info("=" * 70)
    logger.info(
        "process_channel START - channel_id=%d",
        channel_id,
    )
    logger.info("=" * 70)

    db = SessionLocal()

    pending_ids = []

    try:

        # ─────────────────────────────────────────────────────────────────────
        # GET CHANNEL
        # ─────────────────────────────────────────────────────────────────────

        channel = (
            db.query(Channel)
            .filter(Channel.id == channel_id)
            .first()
        )

        if not channel:

            logger.error(
                "Channel %d not found",
                channel_id,
            )

            return

        logger.info(
            "Channel found: %s",
            channel.name,
        )

        logger.info(
            "Channel URL: %s",
            channel.url,
        )

        channel.status = ChannelStatus.processing

        db.commit()

        # ─────────────────────────────────────────────────────────────────────
        # FETCH YOUTUBE VIDEOS
        # ─────────────────────────────────────────────────────────────────────

        logger.info(
            "Fetching videos from YouTube..."
        )

        try:

            yt_videos = await get_channel_videos(
                channel.url
            )

            logger.info(
                "Fetched %d videos from YouTube",
                len(yt_videos),
            )

        except Exception as exc:

            logger.exception(
                "Failed while fetching YouTube videos"
            )

            channel.status = ChannelStatus.error

            db.commit()

            return

        # ─────────────────────────────────────────────────────────────────────
        # EXISTING VIDEOS
        # ─────────────────────────────────────────────────────────────────────

        existing_ids = {
            video.video_id
            for video in (
                db.query(Video)
                .filter(Video.channel_id == channel.id)
                .all()
            )
        }

        logger.info(
            "Existing videos in DB: %d",
            len(existing_ids),
        )

        # ─────────────────────────────────────────────────────────────────────
        # INSERT NEW VIDEOS
        # ─────────────────────────────────────────────────────────────────────

        new_videos = []

        for v in yt_videos:

            video_id = v["video_id"]

            logger.info(
                "YouTube Video → %s (%s)",
                v["title"],
                video_id,
            )

            if video_id in existing_ids:

                logger.info(
                    "Already exists. Skipping."
                )

                continue

            db_video = Video(
                video_id=video_id,
                channel_id=channel.id,
                title=v["title"],
                url=v["url"],
                duration=v.get("duration"),
                upload_date=v.get("upload_date"),
                thumbnail_url=v.get("thumbnail_url"),
                status=VideoStatus.pending,
            )

            db.add(db_video)

            new_videos.append(db_video)

        # Commit new videos
        db.commit()

        logger.info(
            "Inserted %d new videos",
            len(new_videos),
        )

        # Refresh generated IDs
        for video in new_videos:
            db.refresh(video)

        # ─────────────────────────────────────────────────────────────────────
        # UPDATE CHANNEL
        # ─────────────────────────────────────────────────────────────────────

        channel.video_count = (
            len(existing_ids) + len(new_videos)
        )

        channel.status = ChannelStatus.active

        db.commit()

        # ─────────────────────────────────────────────────────────────────────
        # FIND VIDEOS THAT NEED PROCESSING
        # ─────────────────────────────────────────────────────────────────────

        pending_videos = (
            db.query(Video)
            .filter(
                Video.channel_id == channel.id,
                Video.status.in_(
                    [
                        VideoStatus.pending,
                        VideoStatus.failed,
                        VideoStatus.downloading,
                        VideoStatus.transcribing,
                        VideoStatus.indexing,
                    ]
                ),
            )
            .all()
        )

        pending_ids = [
            video.id
            for video in pending_videos
        ]

        logger.info(
            "Videos waiting for processing: %d",
            len(pending_ids),
        )

        logger.info(
            "Pending video IDs: %s",
            pending_ids,
        )

    except Exception:

        logger.exception(
            "Unexpected error inside process_channel"
        )
        if Channel is not None:
            try:
                Channel.status = ChannelStatus.error
                db.commit()
            except Exception:
                logger.exception(
                    "Could not update channel status to error"
                )

        raise

    finally:

        db.close()

    # ─────────────────────────────────────────────────────────────────────────
    # PROCESS VIDEOS
    # ─────────────────────────────────────────────────────────────────────────

    if not pending_ids:

        logger.warning(
            "No videos to process."
        )

        return

    logger.info(
        "Starting processing of %d videos...",
        len(pending_ids),
    )

    # Create processing tasks
    tasks = [
        asyncio.create_task(
            process_video(video_id)
        )
        for video_id in pending_ids
    ]

    # Wait for all videos
    results = await asyncio.gather(
        *tasks,
        return_exceptions=True,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # PROCESS RESULTS
    # ─────────────────────────────────────────────────────────────────────────

    for video_id, result in zip(
        pending_ids,
        results,
    ):

        if isinstance(result, Exception):

            logger.error(
                "Video %d processing failed: %s",
                video_id,
                result,
            )

        else:

            logger.info(
                "Video %d processing completed.",
                video_id,
            )

    logger.info("=" * 70)
    logger.info(
        "process_channel FINISHED - channel_id=%d",
        channel_id,
    )
    logger.info("=" * 70)