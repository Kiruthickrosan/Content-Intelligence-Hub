"""
FastAPI application entry point.

Startup:
  - Creates all SQLite tables if they don't exist
  - Ensures the temp audio directory exists
  - Warms up the ChromaDB collection

Routes:
  /auth/*     — register, login
  /channels/* — channel management
  /videos/*   — video status
  /ask        — Q&A
  /health     — health check
  /docs       — Swagger UI (auto-generated)
"""
import logging
import os
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .config import get_settings
from .database import Base, engine, SessionLocal
from .middleware.rate_limit import limiter
from .routers import auth_router, channels, qa, videos
from .schemas import HealthResponse
from .services import vector_store

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)
settings = get_settings()


# ── Startup / shutdown ────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create DB tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ready: %s", settings.db_path)

    # Temp audio dir
    os.makedirs(settings.audio_temp_dir, exist_ok=True)

    # Warm ChromaDB (creates collection if needed)
    count = vector_store.collection_count()
    logger.info("Vector store ready — %d chunks indexed", count)

    logger.info("YouTube Q&A API started  ·  docs at /docs")
    yield
    logger.info("YouTube Q&A API shutting down")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="YouTube Q&A API",
    description=(
        "Ingest YouTube channels, transcribe every video, index the content "
        "semantically, and answer questions with cited sources."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    lambda request, exc: JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Rate limit exceeded — please slow down your requests."},
    ),
)
app.add_middleware(SlowAPIMiddleware)

# CORS — tighten origins in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(auth_router.router)
app.include_router(channels.router)
app.include_router(videos.router)
app.include_router(qa.router)


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["system"])
def health():
    """
    Lightweight health check — confirms DB and vector store are reachable.
    Useful for load-balancer probes and monitoring dashboards.
    """
    db_status = "ok"
    try:
        db = SessionLocal()
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db.close()
    except Exception as exc:
        db_status = f"error: {exc}"

    vs_count = vector_store.collection_count()
    vs_status = "ok" if vs_count >= 0 else "error"

    return HealthResponse(
        status="ok" if db_status == "ok" and vs_status == "ok" else "degraded",
        database=db_status,
        vector_store=f"{vs_status} ({vs_count} chunks)" if vs_count >= 0 else vs_status,
    )


@app.get("/", include_in_schema=False)
def root():
    return {"message": "YouTube Q&A API — visit /docs for the interactive API reference."}


# ── Dev runner ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "youtube_qa.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info",
    )
