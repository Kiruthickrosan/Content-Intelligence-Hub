"""
Audio → timestamped transcript.

Primary path : YouTube automatic/manual captions via yt-dlp.
Fallback path: Local Faster-Whisper transcription.

No OpenAI API credits are required for transcription.
"""

import asyncio
import html
import logging
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


# ── VTT helpers ──────────────────────────────────────────────────────────────

_TIMESTAMP_RE = re.compile(
    r"(?P<start>\d{2}:\d{2}(?::\d{2})?\.\d{3})\s+-->\s+"
    r"(?P<end>\d{2}:\d{2}(?::\d{2})?\.\d{3})"
)


def _timestamp_to_seconds(timestamp: str) -> float:
    """
    Convert VTT timestamp into seconds.

    Supports:
        MM:SS.mmm
        HH:MM:SS.mmm
    """

    parts = timestamp.split(":")

    if len(parts) == 2:
        minutes, seconds = parts
        return (
            int(minutes) * 60
            + float(seconds)
        )

    if len(parts) == 3:
        hours, minutes, seconds = parts
        return (
            int(hours) * 3600
            + int(minutes) * 60
            + float(seconds)
        )

    raise ValueError(f"Invalid VTT timestamp: {timestamp}")


def _clean_caption_text(text: str) -> str:
    """Clean VTT/HTML markup and normalize whitespace."""

    # Remove HTML/VTT tags such as <c>, </c>, <00:...>
    text = re.sub(r"<[^>]+>", "", text)

    # Decode entities such as &amp;
    text = html.unescape(text)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def _parse_vtt(vtt_path: Path) -> List[Dict[str, Any]]:
    """
    Parse a WebVTT file into:

    {
        "text": "...",
        "start": 0.0,
        "end": 3.2
    }
    """

    content = vtt_path.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    lines = content.splitlines()

    segments: List[Dict[str, Any]] = []

    i = 0

    while i < len(lines):
        line = lines[i].strip()

        match = _TIMESTAMP_RE.match(line)

        if not match:
            i += 1
            continue

        start = _timestamp_to_seconds(
            match.group("start")
        )

        end = _timestamp_to_seconds(
            match.group("end")
        )

        i += 1

        text_lines: List[str] = []

        while i < len(lines):
            text_line = lines[i].strip()

            if not text_line:
                break

            # Stop if another timestamp block begins.
            if _TIMESTAMP_RE.match(text_line):
                i -= 1
                break

            text_lines.append(text_line)
            i += 1

        text = _clean_caption_text(
            " ".join(text_lines)
        )

        if text:
            segments.append({
                "text": text,
                "start": start,
                "end": end,
            })

        i += 1

    return segments


# ── Primary: YouTube captions via yt-dlp ─────────────────────────────────────

async def _try_youtube_transcript(
    video_id: str,
) -> Optional[List[Dict[str, Any]]]:
    """
    Fetch YouTube automatic captions using yt-dlp.

    Language priority:
        1. ta-orig
        2. ta

    Each language is requested separately so that a failure
    for one language does not prevent another language from working.

    Returns:
        List of {text, start, end} dictionaries, or None.
    """

    def _fetch() -> Optional[List[Dict[str, Any]]]:

        url = f"https://www.youtube.com/watch?v={video_id}"

        for language in ("ta-orig", "ta"):

            with tempfile.TemporaryDirectory(
                prefix=f"ytcaps_{video_id}_"
            ) as temp_dir:

                temp_path = Path(temp_dir)

                output_template = str(
                    temp_path / "%(id)s.%(language)s.%(ext)s"
                )

                command = [
                    sys.executable,
                    "-m",
                    "yt_dlp",

                    "--write-auto-subs",

                    "--sub-langs",
                    language,

                    "--sub-format",
                    "vtt",

                    "--skip-download",
                    "--no-playlist",

                    "--output",
                    output_template,

                    url,
                ]

                logger.info(
                    "Trying YouTube automatic captions: "
                    "video=%s language=%s",
                    video_id,
                    language,
                )

                process = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="ignore",
                )

                caption_files = list(
                    temp_path.glob("*.vtt")
                )

                # A caption file is enough to consider the attempt successful,
                # even if yt-dlp also emitted warnings.
                if caption_files:

                    caption_file = caption_files[0]

                    logger.info(
                        "Caption downloaded successfully: %s",
                        caption_file.name,
                    )

                    segments = _parse_vtt(
                        caption_file
                    )

                    if segments:

                        logger.info(
                            "Using YouTube %s captions for %s "
                            "(%d segments)",
                            language,
                            video_id,
                            len(segments),
                        )

                        return segments

                # No usable caption file for this language.
                logger.warning(
                    "No usable %s captions for %s. "
                    "yt-dlp exit code=%s stderr=%s",
                    language,
                    video_id,
                    process.returncode,
                    process.stderr.strip() or "none",
                )

        logger.info(
            "No usable YouTube captions found for %s",
            video_id,
        )

        return None

    try:
        return await asyncio.to_thread(_fetch)

    except Exception as exc:
        logger.warning(
            "Caption fetch failed for %s: %s",
            video_id,
            exc,
        )
        return None