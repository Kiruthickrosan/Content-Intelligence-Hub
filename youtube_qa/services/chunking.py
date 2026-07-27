"""
Transcript → overlapping text chunks with source metadata.

Each chunk records which video it came from and the timestamp of its
first word so users can jump straight to the relevant moment.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List


def _seconds_to_label(seconds: float) -> str:
    """Convert 3723.5 → '1h 2m 3s'."""
    s = int(seconds)
    h, remainder = divmod(s, 3600)
    m, sec = divmod(remainder, 60)
    if h:
        return f"{h}h {m}m {sec}s"
    if m:
        return f"{m}m {sec}s"
    return f"{sec}s"


def chunk_transcript(
    segments: List[Dict[str, Any]],
    video_id: str,
    video_title: str,
    channel_id: int,
    channel_name: str,
    chunk_size: int = 400,
    chunk_overlap: int = 60,
) -> List[Dict[str, Any]]:
    """
    Split a list of transcript segments into overlapping word-level chunks.

    Each segment is: {text: str, start: float, end: float}.

    Returns a list of chunk dicts:
    {
        "text":             str,   # the chunk content
        "video_id":         str,
        "video_title":      str,
        "channel_id":       int,
        "channel_name":     str,
        "timestamp_seconds": int,  # start time of the first word in this chunk
        "timestamp_label":  str,   # human-readable e.g. "1h 2m 3s"
        "youtube_url":      str,   # deep-link with &t= parameter
    }
    """
    if not segments:
        return []

    # ── 1. Flatten to a sequence of (word, start_time) pairs ─────────────────
    words: List[tuple[str, float]] = []          # (word, timestamp)
    for seg in segments:
        text = seg.get("text", "").strip()
        start = float(seg.get("start", 0))
        end = float(seg.get("end", start))

        seg_words = text.split()
        if not seg_words:
            continue

        # Distribute the segment's time range evenly across its words
        duration = max(end - start, 0)
        step = duration / len(seg_words) if len(seg_words) > 1 else 0
        for i, w in enumerate(seg_words):
            words.append((w, start + i * step))

    if not words:
        return []

    # ── 2. Slide a window of `chunk_size` words with `chunk_overlap` step ────
    chunks = []
    step = max(chunk_size - chunk_overlap, 1)
    i = 0
    while i < len(words):
        window = words[i : i + chunk_size]
        text = " ".join(w for w, _ in window)
        ts = int(window[0][1])                    # timestamp of the first word

        chunks.append({
            "text":              text,
            "video_id":          video_id,
            "video_title":       video_title,
            "channel_id":        channel_id,
            "channel_name":      channel_name,
            "timestamp_seconds": ts,
            "timestamp_label":   _seconds_to_label(ts),
            "youtube_url":       f"https://www.youtube.com/watch?v={video_id}&t={ts}",
        })
        i += step

    return chunks
