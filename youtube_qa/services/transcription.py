"""
Audio → timestamped transcript via OpenAI Whisper API.

Primary path : YouTube's own captions (via youtube-transcript-api) — free, instant.
Fallback path: OpenAI Whisper API — for videos without captions.

The Whisper API accepts files up to 25 MB.  For longer audio the file is
split into 10-minute segments before uploading.
"""
import asyncio
import logging
import math
import os
import subprocess
import tempfile
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Primary: YouTube captions ─────────────────────────────────────────────────

async def _try_youtube_transcript(video_id: str) -> Optional[List[Dict[str, Any]]]:
    """
    Attempt to fetch auto-generated or manually uploaded captions.

    Returns a list of {text, start, end} dicts, or None if unavailable.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

        def _fetch():
            try:
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                # Prefer manual English, then auto-generated English, then any
                for lang in ("en", "en-US", "en-GB"):
                    try:
                        t = transcript_list.find_transcript([lang])
                        return t.fetch()
                    except Exception:
                        pass
                # Fall back to auto-generated in any language
                try:
                    t = transcript_list.find_generated_transcript(
                        [t.language_code for t in transcript_list]
                    )
                    return t.fetch()
                except Exception:
                    pass
                return None
            except (TranscriptsDisabled, NoTranscriptFound):
                return None

        raw = await asyncio.to_thread(_fetch)
        if not raw:
            return None

        # Normalise to {text, start, end}
        segments = []
        for item in raw:
            segments.append({
                "text": item["text"].strip(),
                "start": float(item["start"]),
                "end": float(item["start"]) + float(item.get("duration", 0)),
            })
        logger.info("Fetched YouTube captions for %s (%d segments)", video_id, len(segments))
        return segments

    except ImportError:
        logger.warning("youtube-transcript-api not installed; skipping caption fetch")
        return None
    except Exception as exc:
        logger.warning("Caption fetch failed for %s: %s", video_id, exc)
        return None


# ── Fallback: Whisper API ─────────────────────────────────────────────────────

_MAX_WHISPER_BYTES = 24 * 1024 * 1024   # 24 MB — leave margin below 25 MB
_SEGMENT_DURATION  = 600                 # 10 minutes per chunk


def _split_audio(audio_path: str, segment_sec: int = _SEGMENT_DURATION) -> List[tuple]:
    """
    Use ffprobe + ffmpeg to split an audio file into fixed-length segments.

    Returns a list of (path, offset_seconds) tuples; caller must clean up temp files.
    """
    # Get duration
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
        capture_output=True, text=True,
    )
    try:
        total_sec = float(probe.stdout.strip())
    except ValueError:
        return [(audio_path, 0)]  # can't probe — try whole file

    if total_sec <= segment_sec:
        return [(audio_path, 0)]

    n_parts = math.ceil(total_sec / segment_sec)
    parts = []
    for i in range(n_parts):
        fd, part_path = tempfile.mkstemp(suffix=".ogg")
        os.close(fd)
        subprocess.run(
            ["ffmpeg", "-y", "-i", audio_path,
             "-ss", str(i * segment_sec),
             "-t",  str(segment_sec),
             "-c", "copy", part_path],
            capture_output=True, check=True,
        )
        parts.append((part_path, i * segment_sec))   # (path, offset_seconds)
    return parts


async def _transcribe_with_whisper(audio_path: str) -> List[Dict[str, Any]]:
    """
    Send audio to OpenAI Whisper and return timestamped segments.

    Splits large files automatically.
    """
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    file_size = os.path.getsize(audio_path)

    # If file fits, send it directly
    if file_size <= _MAX_WHISPER_BYTES:
        parts_with_offsets = [(audio_path, 0)]
    else:
        logger.info("Audio (%d MB) exceeds Whisper limit — splitting", file_size // (1024**2))
        parts_with_offsets = await asyncio.to_thread(_split_audio, audio_path)

    all_segments: List[Dict[str, Any]] = []

    for part_path, offset in parts_with_offsets:
        try:
            with open(part_path, "rb") as f:
                response = await client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"],
                )
            for seg in (response.segments or []):
                all_segments.append({
                    "text":  seg.text.strip(),
                    "start": seg.start + offset,
                    "end":   seg.end   + offset,
                })
        finally:
            # Remove temp split files (not the original)
            if part_path != audio_path and os.path.exists(part_path):
                os.remove(part_path)

    logger.info("Whisper transcribed %d segments from %s", len(all_segments), audio_path)
    return all_segments


# ── Public API ────────────────────────────────────────────────────────────────

async def transcribe(video_id: str, audio_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Return a list of transcript segments: [{text, start, end}, ...].

    1. Tries YouTube's own captions (fast, free).
    2. Falls back to OpenAI Whisper on the downloaded audio file.

    Raises RuntimeError if both methods fail or audio_path is required but missing.
    """
    # Try captions first
    segments = await _try_youtube_transcript(video_id)
    if segments:
        return segments

    # Whisper fallback
    if not audio_path:
        raise RuntimeError(
            f"No captions available for video {video_id} and no audio file was provided."
        )
    if not os.path.exists(audio_path):
        raise RuntimeError(f"Audio file not found: {audio_path}")

    return await _transcribe_with_whisper(audio_path)
