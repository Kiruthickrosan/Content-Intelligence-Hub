"""
ChromaDB vector store — add chunks, similarity search, delete by video/channel.

All chunks live in a single collection ("youtube_qa") with metadata fields
so queries can be filtered by channel_id or video_id without separate collections.
"""
import logging
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from ..config import get_settings
from .embeddings import embed_query, embed_texts

logger = logging.getLogger(__name__)
settings = get_settings()

_COLLECTION_NAME = "youtube_qa"
_client: Optional[chromadb.PersistentClient] = None
_collection: Optional[chromadb.Collection] = None


def _get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(
            path=settings.chroma_path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        _collection = _client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("ChromaDB collection '%s' ready (%d docs)", _COLLECTION_NAME, _collection.count())
    return _collection


def collection_count() -> int:
    """Return total number of stored chunks (for health checks)."""
    try:
        return _get_collection().count()
    except Exception:
        return -1


# ── Write ─────────────────────────────────────────────────────────────────────

async def add_chunks(chunks: List[Dict[str, Any]]) -> None:
    """
    Embed and persist a list of chunk dicts (as returned by chunking.chunk_transcript).

    Each chunk gets a unique ID: <video_id>_<chunk_index>.
    """
    if not chunks:
        return

    col = _get_collection()
    texts = [c["text"] for c in chunks]
    embeddings = await embed_texts(texts)

    ids       = [f"{c['video_id']}_{i}" for i, c in enumerate(chunks)]
    documents = texts
    metadatas = [
        {
            "video_id":          c["video_id"],
            "video_title":       c["video_title"],
            "channel_id":        str(c["channel_id"]),   # Chroma metadata must be str/int/float/bool
            "channel_name":      c["channel_name"],
            "timestamp_seconds": c["timestamp_seconds"],
            "timestamp_label":   c["timestamp_label"],
            "youtube_url":       c["youtube_url"],
        }
        for c in chunks
    ]

    # Upsert in batches of 500 (Chroma's recommended batch size)
    batch = 500
    for i in range(0, len(ids), batch):
        col.upsert(
            ids=ids[i:i+batch],
            embeddings=embeddings[i:i+batch],
            documents=documents[i:i+batch],
            metadatas=metadatas[i:i+batch],
        )

    logger.info("Stored %d chunks for video %s", len(chunks), chunks[0]["video_id"])


# ── Read ──────────────────────────────────────────────────────────────────────

async def search(
    query: str,
    n_results: int = 8,
    channel_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Semantic search over stored chunks.

    Returns up to n_results items, each with keys:
        text, video_id, video_title, channel_id, channel_name,
        timestamp_seconds, timestamp_label, youtube_url, distance.
    """
    col = _get_collection()
    if col.count() == 0:
        return []

    query_embedding = await embed_query(query)

    where: Optional[Dict] = None
    if channel_id is not None:
        where = {"channel_id": str(channel_id)}

    results = col.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, col.count()),
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        hits.append({
            "text":              doc,
            "video_id":          meta["video_id"],
            "video_title":       meta["video_title"],
            "channel_id":        int(meta["channel_id"]),
            "channel_name":      meta["channel_name"],
            "timestamp_seconds": int(meta["timestamp_seconds"]),
            "timestamp_label":   meta["timestamp_label"],
            "youtube_url":       meta["youtube_url"],
            "distance":          float(dist),
        })

    return hits


# ── Delete ────────────────────────────────────────────────────────────────────

def delete_video_chunks(video_id: str) -> None:
    """Remove all stored chunks belonging to a specific video."""
    col = _get_collection()
    col.delete(where={"video_id": video_id})
    logger.info("Deleted chunks for video %s", video_id)


def delete_channel_chunks(channel_id: int) -> None:
    """Remove all stored chunks belonging to a specific channel."""
    col = _get_collection()
    col.delete(where={"channel_id": str(channel_id)})
    logger.info("Deleted chunks for channel %d", channel_id)
