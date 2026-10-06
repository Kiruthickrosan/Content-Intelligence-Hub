# YouTube Q&A System

Turn any YouTube channel into a searchable, question-answerable knowledge base.
Point it at a channel, wait for processing to finish, then ask questions in plain English.
Every answer cites the exact video and timestamp it came from.

## Quick Start

### 1. Start the API

The server runs on port 8000.  Open `/docs` for the full interactive Swagger UI.

```
http://localhost:8000/docs
```

### 2. Create an account

```http
POST /auth/register
{
  "username": "alice",
  "email": "alice@example.com",
  "password": "supersecret123"
}
```

The **first account registered** is automatically made admin.  All subsequent
accounts are regular users.  Admins can add/delete channels; users can only
ask questions and browse video status.

### 3. Log in and get your token

```http
POST /auth/login
{
  "username": "alice",
  "password": "supersecret123"
}
```

Returns `{ "access_token": "eyJ...", "token_type": "bearer" }`.

Include it on every request:
```
Authorization: Bearer eyJ...
```

### 4. Add a YouTube channel (admin only)

```http
POST /channels
Authorization: Bearer eyJ...
{
  "url": "https://www.youtube.com/@YourChannel"
}
```

The system immediately:
1. Fetches channel metadata from YouTube
2. Queues all videos for background processing
3. Returns the channel record

Processing happens in the background — you can keep using the API while it runs.

### 5. Check processing status

```http
GET /videos?channel_id=1
```

Each video moves through: `pending → downloading → transcribing → indexing → completed`.

Videos with YouTube auto-captions skip the download+transcription step entirely
(much faster).  Others have their audio downloaded, transcribed via OpenAI
Whisper, then deleted.

### 6. Ask a question

```http
POST /ask
Authorization: Bearer eyJ...
{
  "question": "What did they say about pricing in the March video?",
  "channel_id": 1
}
```

Omit `channel_id` to search across all indexed channels.

Response:
```json
{
  "answer": "In the March 15th video at 23:41, they discussed...",
  "sources": [
    {
      "video_title": "March Update — Pricing Changes",
      "channel_name": "Example Channel",
      "timestamp_label": "23m 41s",
      "youtube_url": "https://youtube.com/watch?v=abc123&t=1421",
      "excerpt": "...the new pricing tiers will take effect..."
    }
  ],
  "model": "gpt-4o-mini"
}
```

---

## API Reference

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/auth/register` | — | Create account |
| `POST` | `/auth/login` | — | Get JWT token |
| `POST` | `/channels` | admin | Add a YouTube channel |
| `GET` | `/channels` | user | List all channels |
| `GET` | `/channels/{id}` | user | Channel detail |
| `DELETE` | `/channels/{id}` | admin | Remove channel + all its data |
| `POST` | `/channels/{id}/sync` | admin | Re-sync video list, requeue failures |
| `GET` | `/videos` | user | List videos (filter by channel/status) |
| `GET` | `/videos/{id}` | user | Single video detail |
| `POST` | `/videos/{id}/reprocess` | admin | Re-queue a failed video |
| `POST` | `/ask` | user | Ask a question |
| `GET` | `/health` | — | Health check |

---

## Architecture

```
youtube_qa/
├── main.py               FastAPI app, startup, middleware wiring
├── config.py             Settings (env vars / .env file)
├── database.py           SQLAlchemy + SQLite engine
├── models.py             ORM models: User, Channel, Video
├── schemas.py            Pydantic request/response schemas
├── auth.py               JWT creation/verification, password hashing
│
├── services/
│   ├── youtube_service.py   yt-dlp: channel metadata, video listing, audio download
│   ├── transcription.py     YouTube captions (primary) → Whisper API (fallback)
│   ├── chunking.py          Transcript → overlapping word-level chunks with timestamps
│   ├── embeddings.py        OpenAI text-embedding-3-small, batched
│   ├── vector_store.py      ChromaDB: store, search, delete chunks
│   ├── qa_service.py        RAG pipeline: retrieve → ground prompt → GPT-4o-mini
│   └── processing.py        Background pipeline: per-video and per-channel orchestration
│
├── routers/
│   ├── auth_router.py    /auth/*
│   ├── channels.py       /channels/*
│   ├── videos.py         /videos/*
│   └── qa.py             /ask
│
└── middleware/
    └── rate_limit.py     SlowAPI rate limiter (default: 20 req/min per IP)
```

### Data flow

```
YouTube URL
    │
    ▼
[youtube_service] ──► channel metadata + video list ──► SQLite (Channel, Video rows)
    │
    ▼ (background, per video)
[youtube_service] ──► download audio (yt-dlp) ──► temp file
    │
    ▼
[transcription]   ──► YouTube captions OR OpenAI Whisper ──► [{text, start, end}]
    │                  audio file deleted immediately after
    ▼
[chunking]        ──► overlapping word chunks (400 words, 60 overlap) + timestamps
    │
    ▼
[embeddings]      ──► OpenAI text-embedding-3-small ──► vectors
    │
    ▼
[vector_store]    ──► ChromaDB (persistent, local)

User question
    │
    ▼
[vector_store]    ──► top-8 semantic matches
    │
    ▼
[qa_service]      ──► grounded prompt → GPT-4o-mini ──► answer + citations
```

### Security design

- **Injection protection** — all DB access via SQLAlchemy ORM parameterized queries.
- **Prompt injection** — transcript text is marked as *data to read*, not instructions.
  The system prompt explicitly tells the model to ignore commands embedded in transcripts.
- **Auth** — JWT (PyJWT, HS256, 24-hour expiry).  Roles: `admin` / `user`.
- **Rate limiting** — SlowAPI, 20 requests/minute per IP (configurable).
- **Input sanitization** — Pydantic validators strip dangerous characters from URLs
  and questions before they reach any processing code.

---

## Configuration

All settings read from environment variables (or a `.env` file in the project root).

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | *(required)* | OpenAI API key |
| `SECRET_KEY` | auto-generated | JWT signing key — **set this in production** |
| `CHUNK_SIZE` | `400` | Words per transcript chunk |
| `CHUNK_OVERLAP` | `60` | Overlapping words between chunks |
| `TOP_K_RESULTS` | `8` | Chunks retrieved per question |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI embedding model |
| `CHAT_MODEL` | `gpt-4o-mini` | OpenAI chat model |
| `MAX_CONCURRENT_DOWNLOADS` | `3` | Parallel video downloads |
| `RATE_LIMIT` | `20/minute` | SlowAPI rate limit expression |
| `AUDIO_TEMP_DIR` | `./temp_audio` | Temporary audio storage |
| `CHROMA_PATH` | `./chroma_db` | ChromaDB persistent storage |

---

## Notes

- **Whisper file limit**: OpenAI Whisper API accepts files up to 25 MB.
  Long videos are automatically split into 10-minute segments before upload.
- **First admin**: The first registered user gets admin role automatically.
  Protect the `/auth/register` endpoint in production once your admin account exists.
- **Re-processing**: Failed videos can be re-queued via `POST /videos/{id}/reprocess`.
  Whole channels can be re-synced via `POST /channels/{id}/sync`.
