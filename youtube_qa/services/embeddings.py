"""
Text → vector embeddings using local sentence-transformers.

Completely free — no API key, no credits, no network calls after
the first run (model is cached in ~/.cache/huggingface/).

Model: all-MiniLM-L6-v2
  - 384-dimensional vectors
  - ~90 MB download (once)
  - Fast CPU inference
  - Good semantic quality for RAG
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

# Module-level model cache — loaded once, reused for every request
_model = None
_model_name: Optional[str] = None


def _get_model():
    """Load and cache the sentence-transformers model."""
    global _model, _model_name

    from ..config import get_settings
    settings = get_settings()

    if _model is None or _model_name != settings.embedding_model:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise RuntimeError(
                "sentence-transformers is not installed. "
                "Run: pip install sentence-transformers"
            )

        logger.info(
            "Loading embedding model: %s (first run downloads ~90 MB) ...",
            settings.embedding_model,
        )
        _model = SentenceTransformer(settings.embedding_model)
        _model_name = settings.embedding_model
        logger.info("Embedding model loaded: %s", settings.embedding_model)

    return _model


def _embed_sync(texts: List[str]) -> List[List[float]]:
    """Synchronous embedding — runs in a thread pool via asyncio.to_thread."""
    model = _get_model()
    # encode() returns a numpy array of shape (n_texts, embedding_dim)
    embeddings = model.encode(
        texts,
        batch_size=64,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,   # unit vectors → cosine = dot product
    )
    # Convert numpy array rows to plain Python lists for ChromaDB
    return [row.tolist() for row in embeddings]


async def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Return one embedding vector per input text.

    Runs the CPU-bound model in a thread pool so the FastAPI event
    loop is not blocked.
    """
    if not texts:
        return []

    logger.debug("Embedding %d texts ...", len(texts))
    result = await asyncio.to_thread(_embed_sync, texts)
    logger.debug("Embedding complete: %d vectors of dim %d", len(result), len(result[0]))
    return result


async def embed_query(text: str) -> List[float]:
    """Embed a single query string. Returns one vector."""
    results = await embed_texts([text])
    return results[0]