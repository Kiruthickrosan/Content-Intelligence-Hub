"""
Video status endpoints.

GET  /videos                     — list all videos (with optional filters)
GET  /videos/{id}                — single video detail
POST /videos/{id}/reprocess      — re-queue a failed video (admin)
"""
import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_admin
from ..database import get_db
from ..models import User, Video, VideoStatus
from ..schemas import VideoListResponse, VideoOut
from ..services import processing as proc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/videos", tags=["videos"])


@router.get("", response_model=VideoListResponse)
def list_videos(
    channel_id: Optional[int] = Query(None, description="Filter by channel"),
    status: Optional[VideoStatus] = Query(None, description="Filter by processing status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(Video)
    if channel_id is not None:
        q = q.filter(Video.channel_id == channel_id)
    if status is not None:
        q = q.filter(Video.status == status)

    total = q.count()
    videos = q.order_by(Video.created_at.desc()).offset(offset).limit(limit).all()
    return VideoListResponse(videos=videos, total=total)


@router.get("/{video_id}", response_model=VideoOut)
def get_video(
    video_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


@router.post("/{video_id}/reprocess", status_code=202)
async def reprocess_video(
    video_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Re-queue a failed or stuck video for processing."""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if video.status == VideoStatus.completed:
        return {"message": "Video already completed", "video_id": video_id}

    video.status = VideoStatus.pending
    video.error_message = None
    db.commit()

    background_tasks.add_task(proc.process_video, video.id)
    logger.info("Video %d queued for reprocessing", video_id)
    return {"message": "Reprocessing started", "video_id": video_id}
