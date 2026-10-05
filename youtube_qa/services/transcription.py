"""
Transcript extraction pipeline.

Primary  : YouTube English captions via yt-dlp
Fallback : Local Faster-Whisper with task="translate"

No OpenAI transcription credits required.
"""

from __future__ import annotations

import asyncio
import html
import logging
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── VTT timestamp parser ──────────────────────────────────────────────────────

_TIMESTAMP_RE = re.compile(
    r"(?P<start>\d{2}:\d{2}(?::\d{2})?\.\d{3})\s+-->\s+"
    r"(?P<end>\d{2}:\d{2}(?::\d{2})?\.\d{3})"
)


def _timestamp_to_seconds(ts: str) -> float:
    parts = ts.split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    raise ValueError(f"Invalid VTT timestamp: {ts}")


def _clean_caption_text(text: str) -> str:
    """Strip VTT/HTML markup, decode entities, normalise whitespace."""
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ── VTT parser ────────────────────────────────────────────────────────────────


def _parse_vtt(vtt_path: Path) -> List[Dict[str, Any]]:
    """Parse a WebVTT file into [{text, start, end}, ...]."""
    content = vtt_path.read_text(encoding="utf-8", errors="ignore")
    lines = content.splitlines()
    segments: List[Dict[str, Any]] = []
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        match = _TIMESTAMP_RE.match(line)
        if not match:
            i += 1
            continue

        start = _timestamp_to_seconds(match.group("start"))
        end = _timestamp_to_seconds(match.group("end"))
        i += 1

        text_lines: List[str] = []
        while i < len(lines):
            tl = lines[i].strip()
            if not tl:
                break
            if _TIMESTAMP_RE.match(tl):
                i -= 1
                break
            text_lines.append(tl)
            i += 1

        text = _clean_caption_text(" ".join(text_lines))
        if text:
            segments.append({"text": text, "start": start, "end": end})
        i += 1

    return segments


# ── Rolling-cue deduplication ─────────────────────────────────────────────────


def _deduplicate_captions(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    YouTube auto-captions are cumulative / rolling.

    Example raw cues:
        "A B C"
        "A B C D E"   <- extends previous
        "D E F G"     <- drops A B C

    We keep only the *new* words introduced in each cue so the final
    transcript contains each word exactly once.
    """
    if not segments:
        return []

    result: List[Dict[str, Any]] = []
    prev_words: List[str] = []

    for seg in segments:
        curr_words = seg["text"].split()
        if not curr_words:
            continue

        # Find longest suffix of prev_words that matches a prefix of curr_words
        overlap = 0
        limit = min(len(prev_words), len(curr_words))
        for k in range(limit, 0, -1):
            if prev_words[-k:] == curr_words[:k]:
                overlap = k
                break

        new_words = curr_words[overlap:]
        if new_words:
            result.append(
                {
                    "text": " ".join(new_words),
                    "start": seg["start"],
                    "end": seg["end"],
                }
            )

        prev_words = curr_words

    logger.info(
        "Deduplication: %d raw cues → %d clean segments",
        len(segments),
        len(result),
    )
    return result


# ── Primary: English YouTube captions via yt-dlp ──────────────────────────────


async def get_english_captions(video_id: str) -> Optional[List[Dict[str, Any]]]:
    """
    Download English YouTube captions with yt-dlp.

    Tries subtitle code "en" for manual/automatic English captions.

    Returns deduplicated [{text, start, end}], or None when unavailable.
    """

    def _fetch() -> Optional[List[Dict[str, Any]]]:
        url = f"https://www.youtube.com/watch?v={video_id}"

        with tempfile.TemporaryDirectory(prefix=f"ytcaps_{video_id}_") as tmp:
            tmp_path = Path(tmp)
            output_template = str(tmp_path / "%(id)s.%(ext)s")

            cmd = [
                sys.executable,
                "-m",
                "yt_dlp",
                "--write-auto-subs",
                "--sub-langs",
                "en",
                "--sub-format",
                "vtt",
                # Important: YouTube may return 429 without this delay
                "--sleep-subtitles",
                "60",
                "--skip-download",
                "--no-playlist",
                "--output",
                output_template,
                url,
            ]

            logger.info("Fetching English captions for %s", video_id)

            proc = __import__("subprocess").run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=180,
            )

            output = (proc.stdout or "") + (proc.stderr or "")

            if "429" in output:
                logger.warning(
                    "YouTube returned HTTP 429 while fetching English captions for %s",
                    video_id,
                )
                return None

            vtt_files = list(tmp_path.glob("*.vtt"))

            if not vtt_files:
                logger.warning(
                    "No English VTT for %s. yt-dlp exit=%d stderr=%s",
                    video_id,
                    proc.returncode,
                    (proc.stderr or "").strip()[:300] or "none",
                )
                return None

            vtt_file = vtt_files[0]

            logger.info(
                "English VTT downloaded: %s",
                vtt_file.name,
            )

            raw_segments = _parse_vtt(vtt_file)

            if not raw_segments:
                logger.warning(
                    "VTT parsed but produced 0 segments for %s",
                    video_id,
                )
                return None

            clean = _deduplicate_captions(raw_segments)

            if not clean:
                logger.warning(
                    "Deduplication wiped all segments for %s",
                    video_id,
                )
                return None

            logger.info(
                "English captions ready for %s: %d segments",
                video_id,
                len(clean),
            )

            return clean

    try:
        return await asyncio.to_thread(_fetch)

    except Exception as exc:
        logger.warning(
            "Caption fetch exception for %s: %s",
            video_id,
            exc,
        )
        return None


# ── Fallback: Faster-Whisper with translation ─────────────────────────────────


async def transcribe_with_whisper(audio_path: str) -> List[Dict[str, Any]]:
    """
    Transcribe an audio file using local Faster-Whisper.

    Uses task="translate" so output is always English regardless of
    the source language.

    The audio is decoded with faster_whisper.audio.decode_audio() which
    avoids the PyAV path-based bug observed in this environment.

    Returns [{text, start, end}, ...].
    """

    def _run() -> List[Dict[str, Any]]:
        try:
            from faster_whisper import WhisperModel
            from faster_whisper.audio import decode_audio
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper is not installed. " "Run: pip install faster-whisper"
            ) from exc

        logger.info("Loading Whisper model (base) ...")
        model = WhisperModel(
            "base",
            device="cpu",
            compute_type="int8",
        )

        logger.info("Decoding audio: %s", audio_path)

        import numpy as np

        decoded_audio = decode_audio(audio_path)

        if isinstance(decoded_audio, tuple):
            audio_array = decoded_audio[0]
        else:
            audio_array = decoded_audio

        audio_array = np.asarray(audio_array, dtype=np.float32)

        logger.info("Running Whisper transcription (task=translate) ...")

        raw_segments, info = model.transcribe(
            audio_array,
            task="translate",
            language=None,
            beam_size=5,
            condition_on_previous_text=False,
            vad_filter=True,
        )

        logger.info(
            "Whisper detected language: %s (%.0f%% confidence)",
            info.language,
            info.language_probability * 100,
        )

        segments: List[Dict[str, Any]] = []
        for seg in raw_segments:
            text = seg.text.strip()
            if text:
                segments.append(
                    {
                        "text": text,
                        "start": float(seg.start),
                        "end": float(seg.end),
                    }
                )

        logger.info("Whisper produced %d segments", len(segments))
        return segments

    return await asyncio.to_thread(_run)


# ── Public entry point ────────────────────────────────────────────────────────


async def transcribe(
    video_id: str,
    audio_path: Optional[str] = None,
) -> List[Dict[str, Any]]:

    segments = await get_english_captions(video_id)

    if segments:
        logger.info(
            "Using YouTube English captions for %s (%d segments)",
            video_id,
            len(segments),
        )
        return segments

    logger.info(
        "No English captions for %s — falling back to Faster-Whisper",
        video_id,
    )

    if not audio_path:
        raise RuntimeError(
            f"No English captions found for {video_id} "
            "and no audio_path provided for Whisper fallback."
        )

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    segments = await transcribe_with_whisper(audio_path)

    if not segments:
        raise RuntimeError(f"Whisper produced no segments for {video_id}.")

    return segments
