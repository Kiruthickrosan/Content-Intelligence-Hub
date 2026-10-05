"""
YouTube URL classifier.

classify_youtube_url(url) → "video" | "channel" | "unknown"
get_video_id(url)         → "dQw4w9WgXcQ" | None
"""

from __future__ import annotations

import re
from typing import Literal, Optional

# Matches all standard YouTube video URL forms:
#   https://www.youtube.com/watch?v=VIDEO_ID
#   https://youtu.be/VIDEO_ID
#   https://www.youtube.com/shorts/VIDEO_ID
#   https://www.youtube.com/embed/VIDEO_ID
_VIDEO_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|embed/)|youtu\.be/)"
    r"(?P<video_id>[A-Za-z0-9_-]{11})"
)

# Channel URL patterns:
#   /channel/UC...
#   /c/SomeName
#   /user/SomeName
#   /@handle
_CHANNEL_RE = re.compile(
    r"youtube\.com/(?:channel/|c/|user/|@)"
)

UrlType = Literal["video", "channel", "unknown"]


def classify_youtube_url(url: str) -> UrlType:
    """
    Return "video", "channel", or "unknown".

    Checks video patterns first because some video URLs also contain
    channel-like segments in their query strings.
    """
    if _VIDEO_RE.search(url):
        return "video"
    if _CHANNEL_RE.search(url):
        return "channel"
    return "unknown"


def get_video_id(url: str) -> Optional[str]:
    """Extract the 11-character video ID from a YouTube URL, or return None."""
    match = _VIDEO_RE.search(url)
    return match.group("video_id") if match else None