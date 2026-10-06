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
from typing import Any, Dict, List, Optional, cast

import yt_dlp
from yt_dlp.utils import DownloadError

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
        opts = _quiet_opts(
            {
                "extract_flat": "in_playlist",
                "playlist_items": "1",  # just enough to resolve the channel
                "skip_download": True,
            }
        )
        with yt_dlp.YoutubeDL(cast(Any, opts)) as ydl:
            info = ydl.extract_info(url, download=False)

        if info is None:
            raise ValueError("Could not retrieve channel information")

        # yt-dlp returns a playlist-like object for channels
        channel_id = info.get("channel_id") or info.get("id", "")
        name = (
            info.get("channel") or info.get("uploader") or info.get("title", "Unknown")
        )
        description = info.get("description", "")
        thumbnails = info.get("thumbnails") or []
        thumbnail_url = thumbnails[-1]["url"] if thumbnails else info.get("thumbnail")
        entries = info.get("entries") or []
        video_count = info.get("playlist_count") or 0

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
    Return all uploaded videos from a YouTube channel.
    """

    url = _normalise_channel_url(channel_url)

    # Force yt-dlp to read the Uploads tab
    if "/videos" not in url:
        url = f"{url}/videos"

    def _fetch() -> List[Dict[str, Any]]:
        opts = _quiet_opts(
            {
                "extract_flat": "in_playlist",
                "playlistend": 1000,  # fetch up to 1000 uploads
                "skip_download": True,
            }
        )

        with yt_dlp.YoutubeDL(cast(Any, opts)) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            return []

        entries = info.get("entries") or []

        videos = []

        for entry in entries:

            if not entry:
                continue

            video_id = entry.get("id")

            if not video_id:
                continue

            thumbnails = entry.get("thumbnails") or []

            videos.append(
                {
                    "video_id": video_id,
                    "title": entry.get("title", "Untitled"),
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "duration": entry.get("duration"),
                    "upload_date": entry.get("upload_date"),
                    "thumbnail_url": (
                        thumbnails[-1]["url"] if thumbnails else entry.get("thumbnail")
                    ),
                }
            )

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
    vid_id_match = re.search(
        r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})",
        video_url,
    )

    stem = vid_id_match.group(1) if vid_id_match else "audio"

    template = os.path.join(
        output_dir,
        f"{stem}.%(ext)s",
    )

    def _download() -> str:

        opts = _quiet_opts(
            {
                "format": "bestaudio[abr<=64]/bestaudio/best",
                "outtmpl": template,
                "ffmpeg_location": (
                    r"C:\Users\Kiruthickrosan K\Downloads"
                    r"\ffmpeg-8.1.2-essentials_build"
                    r"\ffmpeg-8.1.2-essentials_build\bin"
                ),
                "retries": 5,
                "fragment_retries": 5,
                "sleep_interval": 2,
                "max_sleep_interval": 6,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "opus",
                        "preferredquality": "32",
                    }
                ],
            }
        )

        # Try browser cookies to reduce YouTube 429/auth issues.
        for browser in (
            "chrome",
            "edge",
            "firefox",
        ):
            try:

                test_opts = dict(opts)

                test_opts["cookiesfrombrowser"] = (browser,)

                with yt_dlp.YoutubeDL(cast(Any, test_opts)) as ydl:

                    result = ydl.extract_info(
                        video_url,
                        download=True,
                    )

                opts = test_opts

                logger.info(
                    "Audio download using %s cookies",
                    browser,
                )

                break

            except Exception:
                continue

        else:
            # No browser worked — try without cookies.
            with yt_dlp.YoutubeDL(cast(Any, opts)) as ydl:

                result = ydl.extract_info(
                    video_url,
                    download=True,
                )

        if result is None:
            raise RuntimeError(f"yt-dlp returned no info for {video_url}")

        # Check expected audio extensions first.
        for candidate in [
            os.path.join(
                output_dir,
                f"{stem}.opus",
            ),
            os.path.join(
                output_dir,
                f"{stem}.webm",
            ),
            os.path.join(
                output_dir,
                f"{stem}.ogg",
            ),
            os.path.join(
                output_dir,
                f"{stem}.m4a",
            ),
            os.path.join(
                output_dir,
                f"{stem}.mp3",
            ),
        ]:

            if os.path.exists(candidate):

                logger.info(
                    "Audio downloaded: %s",
                    candidate,
                )

                return candidate

        # Final fallback: find any file starting with the video ID.
        for fname in os.listdir(output_dir):

            if fname.startswith(stem):

                return os.path.join(
                    output_dir,
                    fname,
                )

        raise RuntimeError(
            f"Could not locate downloaded audio file " f"for {video_url}"
        )

    # Run blocking yt-dlp work in a worker thread.
    return await asyncio.to_thread(_download)


# ── Single video metadata ──────────────────────────────────────────────────────


async def get_video_info(video_url: str) -> Dict[str, Any]:
    """
    Fetch metadata for a single YouTube video without downloading it.

    Returns a dict with:
        video_id, title, duration, upload_date, thumbnail_url,
        channel_id, channel_name, channel_url, channel_description
    """

    def _fetch() -> Dict[str, Any]:
        opts = _quiet_opts(
            {
                "skip_download": True,
                "no_playlist": True,
            }
        )
        with yt_dlp.YoutubeDL(cast(Any, opts)) as ydl:
            info = ydl.extract_info(video_url, download=False)

        if info is None:
            raise ValueError(f"yt-dlp returned no info for {video_url}")

        thumbnails = info.get("thumbnails") or []
        thumbnail_url = thumbnails[-1]["url"] if thumbnails else info.get("thumbnail")

        return {
            "video_id": info.get("id", ""),
            "title": info.get("title", "Untitled"),
            "duration": info.get("duration"),
            "upload_date": info.get("upload_date"),
            "thumbnail_url": thumbnail_url,
            "channel_id": info.get("channel_id") or info.get("uploader_id", ""),
            "channel_name": info.get("channel") or info.get("uploader", "Unknown"),
            "channel_url": info.get("channel_url") or info.get("uploader_url", ""),
            "channel_description": info.get("description", ""),
        }

    return await asyncio.to_thread(_fetch)
