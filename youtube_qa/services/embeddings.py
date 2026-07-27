"""
Text → vector embeddings via OpenAI text-embedding-3-small.

Batches requests to stay within the API's token limits.
"""
import asyncio
import logging
from typing import List, Optional

from openai import AsyncOpenAI

from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_client: Optional[AsyncOpenAI] = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


_BATCH_SIZE = 100   # texts per API call


async def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Return one embedding vector per input text.

    Texts are sent in batches of 100 to stay within rate limits.
    The returned list preserves the original order.
    """
    client = _get_client()
    all_embeddings: List[List[float]] = []

    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]
        response = await client.embeddings.create(
            model=settings.embedding_model,
            input=batch,
        )
        # response.data is sorted by index
        batch_embeddings = [item.embedding for item in sorted(response.data, key=lambda x: x.index)]
        all_embeddings.extend(batch_embeddings)
        logger.debug("Embedded batch %d–%d", i, i + len(batch))

    return all_embeddings


async def embed_query(text: str) -> List[float]:
    """Embed a single query string. Returns one vector."""
    results = await embed_texts([text])
    return results[0]
