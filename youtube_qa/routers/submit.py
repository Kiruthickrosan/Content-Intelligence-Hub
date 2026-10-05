"""
POST /submit-url

Single entry point for the frontend.

The user pastes any YouTube URL. This endpoint:
  - Classifies it as VIDEO or CHANNEL
  - VIDEO  → creates DB records + starts background processing
  - CHANNEL → returns channel name + one-line AI description
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Channel, ChannelStatus, User, Video, VideoStatus
from ..services import processing as proc
from ..services.url_classifier import classify_youtube_url, get_video_id
from ..services.youtube_service import get_channel_info, get_video_info

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/submit-url", tags=["submit"])


# ── Request / Response schemas ────────────────────────────────────────────────

class SubmitRequest(BaseModel):
    url: str


class SubmitResponse(BaseModel):
    url_type: str                   # "video" | "channel" | "unknown"

    # Video fields (populated when url_type == "video")
    video_id: Optional[str] = None
    video_title: Optional[str] = None
    db_video_id: Optional[int] = None
    status: Optional[str] = None    # "processing" | "already_indexed"

    # Channel fields (populated when url_type == "channel")
    channel_name: Optional[str] = None
    channel_description: Optional[str] = None


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("", response_model=SubmitResponse)
async def submit_url(
    body: SubmitRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubmitResponse:
    """
    Accept a raw YouTube URL and route it appropriately.

    - VIDEO URL   → index the video for Q&A (background task)
    - CHANNEL URL → return channel metadata + one-line description
    - UNKNOWN     → 422 error
    """
    url = body.url.strip()
    url_type = classify_youtube_url(url)

    # ── Unknown URL ───────────────────────────────────────────────────────────
    if url_type == "unknown":
        raise HTTPException(
            status_code=422,
            detail=(
                "Could not recognise this as a YouTube video or channel URL. "
                "Please paste a direct YouTube video link "
                "(e.g. https://www.youtube.com/watch?v=...) "
                "or a channel URL (e.g. https://www.youtube.com/@ChannelName)."
            ),
        )

    # ── Channel URL ───────────────────────────────────────────────────────────
    if url_type == "channel":
        return await _handle_channel(url, db, current_user)

    # ── Video URL ─────────────────────────────────────────────────────────────
    return await _handle_video(url, db, current_user, background_tasks)


# ─────────────────────────────────────────────────────────────────────────────
# Channel handler
# ─────────────────────────────────────────────────────────────────────────────

async def _handle_channel(
    url: str,
    db: Session,
    current_user: User,
) -> SubmitResponse:
    """
    Fetch channel metadata and generate a one-line AI description.
    Does NOT process individual videos.
    """
    try:
        info = await get_channel_info(url)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Could not fetch channel info: {exc}",
        )

    description = await _generate_channel_description(info)

    logger.info(
        "Channel URL submitted by user %d: %s → %s",
        current_user.id, url, info.get("name"),
    )

    return SubmitResponse(
        url_type="channel",
        channel_name=info.get("name"),
        channel_description=description,
    )


async def _generate_channel_description(
    info: Dict[str, Any],
) -> str:
    """
    Generate a single-sentence channel description using Gemini.

    Falls back to the raw YouTube description if Gemini is unavailable.
    """

    from ..config import get_settings
    from google import genai

    settings = get_settings()

    name = info.get("name", "Unknown")
    raw_desc = (info.get("description") or "").strip()[:1500]

    if not raw_desc:
        return f"A YouTube channel named '{name}'."

    if not settings.gemini_api_key:
        return raw_desc[:200] + (
            "…" if len(raw_desc) > 200 else ""
        )

    prompt = (
        f"YouTube channel name: {name}\n\n"
        f"Channel description:\n{raw_desc}\n\n"
        "Write exactly ONE sentence, under 30 words, describing "
        "what type of channel this is and the main topics it covers. "
        "Answer in English only. "
        "Do not start with 'This is a'. "
        "Start directly with the channel type."
    )

    try:
        client = genai.Client(
            api_key=settings.gemini_api_key
        )

        response = await client.aio.models.generate_content(
            model=settings.chat_model,
            contents=prompt,
        )

        answer = (response.text or "").strip()

        if answer:
            return answer

    except Exception as exc:
        logger.warning(
            "Could not generate channel description via Gemini: %s",
            exc,
        )

    return raw_desc[:200] + (
        "…" if len(raw_desc) > 200 else ""
    )


# ─────────────────────────────────────────────────────────────────────────────
# Video handler
# ─────────────────────────────────────────────────────────────────────────────

async def _handle_video(
    url: str,
    db: Session,
    current_user: User,
    background_tasks: BackgroundTasks,
) -> SubmitResponse:
    """
    Register a video and start background processing.

    If the video has already been indexed successfully, returns
    status="already_indexed" so the frontend can go straight to /ask.
    """
    video_id = get_video_id(url)
    if not video_id:
        raise HTTPException(status_code=422, detail="Could not extract video ID from URL.")

    # Check if this video is already in the DB
    existing_video = db.query(Video).filter(Video.video_id == video_id).first()
    if existing_video and existing_video.status == VideoStatus.completed:
        logger.info("Video %s already indexed — skipping reprocessing", video_id)
        return SubmitResponse(
            url_type="video",
            video_id=video_id,
            video_title=existing_video.title,
            db_video_id=existing_video.id,
            status="already_indexed",
        )

    # If it exists but failed/stuck, reset and reprocess
    if existing_video:
        existing_video.status = VideoStatus.pending
        existing_video.error_message = None
        db.commit()
        background_tasks.add_task(proc.process_video, existing_video.id)
        logger.info("Re-queued video %s (row %d)", video_id, existing_video.id)
        return SubmitResponse(
            url_type="video",
            video_id=video_id,
            video_title=existing_video.title,
            db_video_id=existing_video.id,
            status="processing",
        )

    # New video — fetch metadata from YouTube
    try:
        meta = await get_video_info(url)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Could not fetch video metadata: {exc}",
        )

    # Ensure the channel record exists
    channel = db.query(Channel).filter(
        Channel.channel_id == meta["channel_id"]
    ).first()

    if not channel:
        channel = Channel(
            channel_id=meta["channel_id"],
            name=meta["channel_name"],
            url=meta.get("channel_url", ""),
            description=meta.get("channel_description"),
            thumbnail_url=meta.get("channel_thumbnail"),
            video_count=0,
            status=ChannelStatus.active,
            added_by=current_user.id,
        )
        db.add(channel)
        db.commit()
        db.refresh(channel)
        logger.info("Auto-created channel record: %s", channel.name)

    # Create video record
    video = Video(
        video_id=video_id,
        channel_id=channel.id,
        title=meta["title"],
        url=url,
        duration=meta.get("duration"),
        upload_date=meta.get("upload_date"),
        thumbnail_url=meta.get("thumbnail_url"),
        status=VideoStatus.pending,
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    # Kick off background processing
    background_tasks.add_task(proc.process_video, video.id)

    logger.info(
        "Video %s (row %d) queued for processing by user %d",
        video_id, video.id, current_user.id,
    )

    return SubmitResponse(
        url_type="video",
        video_id=video_id,
        video_title=meta["title"],
        db_video_id=video.id,
        status="processing",
    )