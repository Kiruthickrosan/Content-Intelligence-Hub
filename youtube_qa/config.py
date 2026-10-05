"""
Central configuration — reads from environment variables and .env file.
"""

import secrets
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Gemini ────────────────────────────────────────────────────────────────
    gemini_api_key: str = ""

    # Gemini model used for:
    # - RAG answers
    # - Channel one-line descriptions
    chat_model: str = "gemini-3.8-flash"

    # ── Embeddings ────────────────────────────────────────────────────────────
    # Local sentence-transformers model.
    #
    # all-MiniLM-L6-v2 → 384-dimensional vectors, fast and free.
    embedding_model: str = "all-MiniLM-L6-v2"

    # ── Authentication ────────────────────────────────────────────────────────
    secret_key: str = secrets.token_hex(32)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    # ── Processing ────────────────────────────────────────────────────────────
    chunk_size: int = 400
    chunk_overlap: int = 60
    top_k_results: int = 8
    max_concurrent_downloads: int = 3

    # ── Storage ───────────────────────────────────────────────────────────────
    db_path: str = "youtube_qa.db"
    chroma_path: str = "./chroma_db"
    audio_temp_dir: str = "./temp_audio"

    # ── YouTube cookies ───────────────────────────────────────────────────────
    youtube_cookies_file: str = "./youtube_cookies.txt"

    # ── Rate limiting ─────────────────────────────────────────────────────────
    rate_limit: str = "20/minute"


@lru_cache()
def get_settings() -> Settings:
    return Settings()