"""
Channel management endpoints.

POST   /channels          (admin) — add a YouTube channel and trigger processing
GET    /channels          (any)   — list all channels
GET    /channels/{id}     (any)   — get one channel with its video summary
DELETE /channels/{id}     (admin) — remove a channel and all its indexed data
POST   /channels/{id}/sync (admin) — re-sync video list and process new/failed videos
"""
import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_admin
from ..database import get_db
from ..models import Channel, ChannelStatus, User, Video, VideoStatus
from ..schemas import ChannelAddRequest, ChannelListResponse, ChannelOut
from ..services import processing as proc
from ..services import vector_store
from ..services.youtube_service import get_channel_info

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/channels", tags=["channels"])


@router.post("", response_model=ChannelOut, status_code=201)
async def add_channel(
    body: ChannelAddRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Add a YouTube channel.  Fetches its metadata immediately, then
    kicks off video processing in the background.
    """
    # Fetch channel metadata from YouTube
    try:
        info = await get_channel_info(body.url)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not reach YouTube channel: {exc}")

    # Idempotency — return existing record if already added
    existing = db.query(Channel).filter(Channel.channel_id == info["channel_id"]).first()
    if existing:
        raise HTTPException(status_code=409, detail="Channel already added")

    channel = Channel(
        channel_id=info["channel_id"],
        name=info["name"],
        url=info["url"],
        description=info.get("description"),
        thumbnail_url=info.get("thumbnail_url"),
        video_count=info.get("video_count", 0),
        status=ChannelStatus.processing,
        added_by=admin.id,
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    # Process videos in the background
    channel_id = channel.id
    background_tasks.add_task(proc.process_channel, channel_id)
    logger.info("Channel %d (%s) added by user %d", channel_id, channel.name, admin.id)

    return channel


@router.get("", response_model=ChannelListResponse)
def list_channels(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    channels = db.query(Channel).order_by(Channel.created_at.desc()).all()
    return ChannelListResponse(channels=channels, total=len(channels))


@router.get("/{channel_id}", response_model=ChannelOut)
def get_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel


@router.delete("/{channel_id}", status_code=204)
def delete_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Remove a channel, all its videos, and all indexed vector data."""
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Remove from vector store
    vector_store.delete_channel_chunks(channel_id)

    db.delete(channel)
    db.commit()
    logger.info("Channel %d deleted", channel_id)


@router.post("/{channel_id}/sync", status_code=202)
async def sync_channel(
    channel_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Re-fetch the video list and process any new or previously failed videos."""
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    background_tasks.add_task(proc.process_channel, channel_id)
    return {"message": "Sync started", "channel_id": channel_id}
