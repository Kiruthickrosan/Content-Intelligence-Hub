# YouTube Q&A System

A Python FastAPI service that ingests YouTube channels, transcribes every video, stores semantic embeddings, and answers plain-English questions with cited sources (video title + timestamp deep-link).

## Run & Operate

- **YouTube Q&A API** workflow — runs `python3 -m uvicorn youtube_qa.main:app --host 0.0.0.0 --port 8000 --reload` on port 8000
- Swagger UI: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`
- Required env: `OPENAI_API_KEY` (set as Replit secret)

## Stack

- Python 3.11, FastAPI, uvicorn
- Auth: PyJWT (HS256), passlib/bcrypt
- DB: SQLite via SQLAlchemy 2.0
- Vector store: ChromaDB (local persistent)
- YouTube: yt-dlp (download + metadata), youtube-transcript-api (captions)
- Transcription: OpenAI Whisper API (fallback when no captions)
- Embeddings: OpenAI text-embedding-3-small
- LLM: gpt-4o-mini (grounded RAG answers)
- Rate limiting: SlowAPI (20 req/min per IP)

## Where things live

```
youtube_qa/
├── main.py               App entry point, lifespan, middleware wiring
├── config.py             All settings (pydantic-settings, reads env vars)
├── database.py           SQLAlchemy engine + session factory
├── models.py             ORM models: User, Channel, Video
├── schemas.py            Pydantic schemas (request/response)
├── auth.py               JWT helpers, password hashing, FastAPI deps
├── services/             Business logic (youtube, transcription, chunking, embeddings, vector store, qa, processing)
├── routers/              FastAPI routers: auth, channels, videos, qa
└── middleware/           SlowAPI rate limiter
```

## Architecture decisions

- **PyJWT over python-jose** — python-jose is blocked by Replit's package firewall; PyJWT is the maintained successor.
- **SQLite over PostgreSQL** — no external DB needed; the system is self-contained and SQLite handles the metadata load easily.
- **YouTube captions first, Whisper fallback** — ~70% of YouTube videos have auto-captions; using them is instant and free. Whisper only runs when captions are unavailable.
- **Single ChromaDB collection with metadata filters** — simpler than per-channel collections; channel_id and video_id stored as metadata allow precise filtering.
- **Prompt injection defense** — system prompt explicitly instructs the model to treat transcript text as *data to read*, never as *instructions to follow*.

## Product

Users register → admins add YouTube channels → the system processes every video in the background (download audio → transcribe → chunk → embed → store) → any user asks plain-English questions → the system returns a grounded answer with clickable source links to the exact video moment.

## User preferences

_Populate as you build._

## Gotchas

- `OPENAI_API_KEY` must be set — transcription (Whisper), embeddings, and Q&A all use it.
- The first registered user automatically becomes admin. Lock down `/auth/register` in production after that.
- Whisper API has a 25 MB file limit; `transcription.py` auto-splits longer audio into 10-minute segments.
- `SECRET_KEY` is auto-generated per process start if not set in env — set it explicitly in production or tokens will be invalidated on every restart.
- ChromaDB telemetry errors in logs are harmless — telemetry is disabled but the client still tries to send a startup event.

## Pointers

- Full API docs and usage guide: `youtube_qa/README.md`
- See the `pnpm-workspace` skill for the existing Node.js workspace structure
