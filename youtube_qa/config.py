"""
Central configuration — reads from environment variables and .env file.
"""
import os
import secrets
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── OpenAI ────────────────────────────────────────────────────────────────
    openai_api_key: str = "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"

    # ── Authentication ────────────────────────────────────────────────────────
    # Override SECRET_KEY in .env or environment for production
    secret_key: str = secrets.token_hex(32)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    # ── Processing ────────────────────────────────────────────────────────────
    # Transcript chunking
    chunk_size: int = 400       # approximate words per chunk
    chunk_overlap: int = 60     # overlapping words between neighboring chunks

    # OpenAI models
    embedding_model: str = "text-embedding-3-small"
    chat_model: str = "gpt-4o-mini"

    # Retrieval
    top_k_results: int = 8

    # Concurrency
    max_concurrent_downloads: int = 3

    # ── Storage ───────────────────────────────────────────────────────────────
    db_path: str = "youtube_qa.db"
    chroma_path: str = "./chroma_db"
    audio_temp_dir: str = "./temp_audio"

    # ── Rate limiting ─────────────────────────────────────────────────────────
    rate_limit: str = "20/minute"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
