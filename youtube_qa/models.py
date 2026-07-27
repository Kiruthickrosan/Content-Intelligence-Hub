"""
SQLAlchemy ORM models — Channel, Video, User.
"""
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column, DateTime, Enum, ForeignKey, Integer, String, Text
)
from sqlalchemy.orm import relationship

from .database import Base


def _utcnow():
    return datetime.now(timezone.utc)


# ── Enums ─────────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    admin = "admin"
    user  = "user"


class ChannelStatus(str, enum.Enum):
    active     = "active"
    processing = "processing"
    error      = "error"


class VideoStatus(str, enum.Enum):
    pending      = "pending"
    downloading  = "downloading"
    transcribing = "transcribing"
    indexing     = "indexing"
    completed    = "completed"
    failed       = "failed"


# ── Models ────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    username        = Column(String(50),  unique=True, index=True, nullable=False)
    email           = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role            = Column(Enum(UserRole), default=UserRole.user, nullable=False)
    created_at      = Column(DateTime, default=_utcnow)

    channels = relationship("Channel", back_populates="owner")


class Channel(Base):
    __tablename__ = "channels"

    id            = Column(Integer, primary_key=True, index=True)
    channel_id    = Column(String(255), unique=True, index=True, nullable=False)  # YouTube ID
    name          = Column(String(255), nullable=False)
    url           = Column(String(500),  nullable=False)
    description   = Column(Text,         nullable=True)
    thumbnail_url = Column(String(500),  nullable=True)
    video_count   = Column(Integer,      default=0)
    status        = Column(Enum(ChannelStatus), default=ChannelStatus.active, nullable=False)
    added_by      = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at    = Column(DateTime, default=_utcnow)

    owner  = relationship("User",  back_populates="channels")
    videos = relationship("Video", back_populates="channel", cascade="all, delete-orphan")


class Video(Base):
    __tablename__ = "videos"

    id            = Column(Integer, primary_key=True, index=True)
    video_id      = Column(String(255), unique=True, index=True, nullable=False)  # YouTube ID
    channel_id    = Column(Integer, ForeignKey("channels.id"), nullable=False)
    title         = Column(String(500), nullable=False)
    url           = Column(String(500), nullable=False)
    duration      = Column(Integer,     nullable=True)   # seconds
    upload_date   = Column(String(20),  nullable=True)   # YYYYMMDD from yt-dlp
    thumbnail_url = Column(String(500), nullable=True)
    status        = Column(Enum(VideoStatus), default=VideoStatus.pending, nullable=False)
    error_message = Column(Text,    nullable=True)
    chunk_count   = Column(Integer, default=0)
    processed_at  = Column(DateTime, nullable=True)
    created_at    = Column(DateTime, default=_utcnow)
    updated_at    = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    channel = relationship("Channel", back_populates="videos")
