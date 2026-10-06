"""
Pydantic request/response schemas — the public API surface.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, HttpUrl, field_validator

from .models import ChannelStatus, UserRole, VideoStatus


# ── Auth ──────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    role: UserRole
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Channels ──────────────────────────────────────────────────────────────────

class ChannelAddRequest(BaseModel):
    url: str = Field(..., description="YouTube channel URL or handle, e.g. https://youtube.com/@handle")

    @field_validator("url")
    @classmethod
    def sanitise_url(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        # Block any javascript: or data: schemes hiding in substrings
        if any(bad in v.lower() for bad in ["javascript:", "data:", "<", ">"]):
            raise ValueError("URL contains disallowed characters")
        return v


class ChannelOut(BaseModel):
    id: int
    channel_id: str
    name: str
    url: str
    description: Optional[str]
    thumbnail_url: Optional[str]
    video_count: int
    status: ChannelStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class ChannelListResponse(BaseModel):
    channels: List[ChannelOut]
    total: int


# ── Videos ────────────────────────────────────────────────────────────────────

class VideoOut(BaseModel):
    id: int
    video_id: str
    channel_id: int
    title: str
    url: str
    duration: Optional[int]
    upload_date: Optional[str]
    thumbnail_url: Optional[str]
    status: VideoStatus
    error_message: Optional[str]
    chunk_count: int
    processed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class VideoListResponse(BaseModel):
    videos: List[VideoOut]
    total: int


# ── Q&A ───────────────────────────────────────────────────────────────────────

class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)
    channel_id: Optional[int] = Field(
        None,
        description="Restrict search to a specific channel. Omit to search all channels.",
    )

    @field_validator("question")
    @classmethod
    def sanitise_question(cls, v: str) -> str:
        v = v.strip()
        # Strip any angle-bracket HTML/injection attempts
        if any(bad in v for bad in ["<script", "<!--", "<iframe"]):
            raise ValueError("Question contains disallowed content")
        return v


class Source(BaseModel):
    video_id: str
    video_title: str
    channel_name: str
    timestamp_seconds: int
    timestamp_label: str   # "1h 23m 45s"
    youtube_url: str       # deep-link with &t= parameter
    excerpt: str           # the actual chunk text shown to the user


class AskResponse(BaseModel):
    answer: str
    sources: List[Source]
    model: str


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    database: str
    vector_store: str
    version: str = "1.0.0"
