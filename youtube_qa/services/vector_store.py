"""
ChromaDB vector store — add chunks, similarity search, delete by video/channel.

All chunks live in a single collection ("youtube_qa") with metadata fields
so queries can be filtered by channel_id or video_id without separate collections.
"""

import logging
from typing import Any, Dict, List, Optional, cast


import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection
from chromadb.api.types import Embeddings, Include, Metadatas
from chromadb.config import Settings as ChromaSettings

from ..config import get_settings
from .embeddings import embed_query, embed_texts

logger = logging.getLogger(__name__)
settings = get_settings()

_COLLECTION_NAME = "youtube_qa"

# Correct Chroma types
_client: Optional[ClientAPI] = None
_collection: Optional[Collection] = None


def _get_collection() -> Collection:
    """Create and return the persistent ChromaDB collection."""
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

        logger.info(
            "ChromaDB collection '%s' ready (%d docs)",
            _COLLECTION_NAME,
            _collection.count(),
        )

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
    Embed and persist a list of chunk dicts.

    Each chunk gets a unique ID:
        <video_id>_<chunk_index>
    """
    if not chunks:
        return

    col = _get_collection()

    texts = [c["text"] for c in chunks]
    embeddings = cast(Embeddings, await embed_texts(texts))

    ids = [f"{c['video_id']}_{i}" for i, c in enumerate(chunks)]

    documents = texts

    metadatas = cast(
        Metadatas,
        [
            {
                "video_id": c["video_id"],
                "video_title": c["video_title"],
                "channel_id": str(c["channel_id"]),
                "channel_name": c["channel_name"],
                "timestamp_seconds": c["timestamp_seconds"],
                "timestamp_label": c["timestamp_label"],
                "youtube_url": c["youtube_url"],
            }
            for c in chunks
        ],
    )

    # Upsert in batches
    batch = 500

    for i in range(0, len(ids), batch):
        col.upsert(
            ids=ids[i : i + batch],
            embeddings=embeddings[i : i + batch],
            documents=documents[i : i + batch],
            metadatas=metadatas[i : i + batch],
        )

    logger.info(
        "Stored %d chunks for video %s",
        len(chunks),
        chunks[0]["video_id"],
    )


# ── Read ──────────────────────────────────────────────────────────────────────


async def search(
    query: str,
    n_results: int = 8,
    channel_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Semantic search over stored chunks.

    Returns up to n_results items, each containing:
        text, video_id, video_title, channel_id, channel_name,
        timestamp_seconds, timestamp_label, youtube_url, distance.
    """

    col = _get_collection()
    total_docs = col.count()

    if total_docs == 0:
        return []

    query_embedding = await embed_query(query)

    where: Optional[Dict[str, Any]] = None

    if channel_id is not None:
        where = {"channel_id": str(channel_id)}

    results = col.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, total_docs),
        where=where,
        include=cast(
            Include,
            [
                "documents",
                "metadatas",
                "distances",
            ],
        ),
    )

    documents = results.get("documents")
    metadatas = results.get("metadatas")
    distances = results.get("distances")

    # Chroma only returns these when requested and available.
    if not documents or not metadatas or not distances:
        return []

    docs = documents[0]
    metas = metadatas[0]
    dists = distances[0]

    hits: List[Dict[str, Any]] = []

    for doc, meta, dist in zip(docs, metas, dists):
        if meta is None:
            continue

        hits.append(
            {
                "text": doc,
                "video_id": str(meta["video_id"]),
                "video_title": str(meta["video_title"]),
                "channel_id": int(meta["channel_id"]),
                "channel_name": str(meta["channel_name"]),
                "timestamp_seconds": int(meta["timestamp_seconds"]),
                "timestamp_label": str(meta["timestamp_label"]),
                "youtube_url": str(meta["youtube_url"]),
                "distance": float(dist),
            }
        )

    return hits


# ── Delete ────────────────────────────────────────────────────────────────────


def delete_video_chunks(video_id: str) -> None:
    """Remove all stored chunks belonging to a specific video."""
    col = _get_collection()

    col.delete(where={"video_id": video_id})

    logger.info(
        "Deleted chunks for video %s",
        video_id,
    )


def delete_channel_chunks(channel_id: int) -> None:
    """Remove all stored chunks belonging to a specific channel."""
    col = _get_collection()

    col.delete(where={"channel_id": str(channel_id)})

    logger.info(
        "Deleted chunks for channel %d",
        channel_id,
    )
