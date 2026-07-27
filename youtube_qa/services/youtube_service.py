"""
YouTube integration — fetch channel metadata, list videos, download audio.

Uses yt-dlp under the hood. Only the audio track is kept on disk; the
video file is deleted immediately after extraction to conserve space.
"""
import asyncio
import logging
import os
import re
import tempfile
from typing import Any, Dict, List, Optional

import yt_dlp

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _quiet_opts(extra: dict | None = None) -> dict:
    """Base yt-dlp options — silent unless an error occurs."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "logger": _YTDLPLogger(),
    }
    if extra:
        opts.update(extra)
    return opts


class _YTDLPLogger:
    """Redirect yt-dlp internal messages to Python logging."""

    def debug(self, msg: str) -> None:
        if msg.startswith("[debug]"):
            logger.debug(msg)

    def info(self, msg: str) -> None:
        logger.info(msg)

    def warning(self, msg: str) -> None:
        logger.warning(msg)

    def error(self, msg: str) -> None:
        logger.error(msg)


def _normalise_channel_url(url: str) -> str:
    """Accept handles, /channel/, /user/, /c/ — return as-is; yt-dlp resolves all."""
    return url.strip().rstrip("/")


# ── Channel info ──────────────────────────────────────────────────────────────

async def get_channel_info(url: str) -> Dict[str, Any]:
    """
    Fetch basic channel metadata without downloading anything.

    Returns a dict with keys: channel_id, name, description, thumbnail_url, video_count.
    Raises ValueError if the URL cannot be resolved.
    """
    url = _normalise_channel_url(url)

    def _fetch() -> Dict[str, Any]:
        opts = _quiet_opts({
            "extract_flat": "in_playlist",
            "playlist_items": "1",      # just enough to resolve the channel
            "skip_download": True,
        })
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if info is None:
            raise ValueError("Could not retrieve channel information")

        # yt-dlp returns a playlist-like object for channels
        channel_id = info.get("channel_id") or info.get("id", "")
        name = info.get("channel") or info.get("uploader") or info.get("title", "Unknown")
        description = info.get("description", "")
        thumbnails = info.get("thumbnails") or []
        thumbnail_url = thumbnails[-1]["url"] if thumbnails else info.get("thumbnail")
        entries = info.get("entries") or []
        video_count = info.get("playlist_count") or len(entries)

        return {
            "channel_id": channel_id,
            "name": name,
            "url": url,
            "description": description,
            "thumbnail_url": thumbnail_url,
            "video_count": video_count,
        }

    return await asyncio.to_thread(_fetch)


# ── Video listing ─────────────────────────────────────────────────────────────

async def get_channel_videos(channel_url: str) -> List[Dict[str, Any]]:
    """
    Return a list of all video metadata for the channel.

    Each item contains: video_id, title, url, duration, upload_date, thumbnail_url.
    """
    url = _normalise_channel_url(channel_url)

    def _fetch() -> List[Dict[str, Any]]:
        opts = _quiet_opts({
            "extract_flat": True,
            "skip_download": True,
        })
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if info is None:
            return []

        entries = info.get("entries") or []
        videos = []
        for entry in entries:
            if not entry:
                continue
            vid_id = entry.get("id") or entry.get("video_id", "")
            if not vid_id:
                continue
            thumbnails = entry.get("thumbnails") or []
            thumb = thumbnails[-1]["url"] if thumbnails else entry.get("thumbnail")
            videos.append({
                "video_id": vid_id,
                "title": entry.get("title", "Untitled"),
                "url": entry.get("webpage_url") or f"https://www.youtube.com/watch?v={vid_id}",
                "duration": entry.get("duration"),
                "upload_date": entry.get("upload_date"),
                "thumbnail_url": thumb,
            })
        return videos

    return await asyncio.to_thread(_fetch)


# ── Audio download ────────────────────────────────────────────────────────────

async def download_audio(video_url: str, output_dir: str) -> str:
    """
    Download and extract audio from a YouTube video.

    Returns the path to the resulting audio file (opus/webm, ~32 kbps).
    The caller is responsible for deleting the file when done.

    Raises RuntimeError on download failure.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Extract video ID for a stable filename
    vid_id_match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", video_url)
    stem = vid_id_match.group(1) if vid_id_match else "audio"
    template = os.path.join(output_dir, f"{stem}.%(ext)s")

    def _download() -> str:
        opts = _quiet_opts({
            "format": "bestaudio[abr<=64]/bestaudio/best",
            "outtmpl": template,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "opus",
                "preferredquality": "32",
            }],
        })
        with yt_dlp.YoutubeDL(opts) as ydl:
            result = ydl.extract_info(video_url, download=True)

        if result is None:
            raise RuntimeError(f"yt-dlp returned no info for {video_url}")

        # Find the output file (extension may vary)
        for candidate in [
            os.path.join(output_dir, f"{stem}.opus"),
            os.path.join(output_dir, f"{stem}.webm"),
            os.path.join(output_dir, f"{stem}.ogg"),
            os.path.join(output_dir, f"{stem}.m4a"),
            os.path.join(output_dir, f"{stem}.mp3"),
        ]:
            if os.path.exists(candidate):
                logger.info("Audio downloaded: %s", candidate)
                return candidate

        # Fallback: find any file starting with stem
        for fname in os.listdir(output_dir):
            if fname.startswith(stem):
                return os.path.join(output_dir, fname)

        raise RuntimeError(f"Could not locate downloaded audio file for {video_url}")

    try:
        return await asyncio.to_thread(_download)
    except yt_dlp.utils.DownloadError as exc:
        raise RuntimeError(f"Download failed: {exc}") from exc
