"""
SQLAlchemy ORM models — Channel, Video, User.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Enums ─────────────────────────────────────────────────────────────────────


class UserRole(str, enum.Enum):
    admin = "admin"
    user = "user"


class ChannelStatus(str, enum.Enum):
    active = "active"
    processing = "processing"
    error = "error"


class VideoStatus(str, enum.Enum):
    pending = "pending"
    downloading = "downloading"
    transcribing = "transcribing"
    indexing = "indexing"
    completed = "completed"
    failed = "failed"


# ── User ──────────────────────────────────────────────────────────────────────


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole),
        default=UserRole.user,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
    )

    channels: Mapped[list["Channel"]] = relationship(
        "Channel",
        back_populates="owner",
    )


# ── Channel ───────────────────────────────────────────────────────────────────


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    channel_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    thumbnail_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    video_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    status: Mapped[ChannelStatus] = mapped_column(
        Enum(ChannelStatus),
        default=ChannelStatus.active,
        nullable=False,
    )

    added_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
    )

    owner: Mapped["User | None"] = relationship(
        "User",
        back_populates="channels",
    )

    videos: Mapped[list["Video"]] = relationship(
        "Video",
        back_populates="channel",
        cascade="all, delete-orphan",
    )


# ── Video ─────────────────────────────────────────────────────────────────────


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    video_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    channel_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("channels.id"),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    duration: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    upload_date: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    thumbnail_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    status: Mapped[VideoStatus] = mapped_column(
        Enum(VideoStatus),
        default=VideoStatus.pending,
        nullable=False,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    chunk_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
        onupdate=_utcnow,
    )

    channel: Mapped["Channel"] = relationship(
        "Channel",
        back_populates="videos",
    )