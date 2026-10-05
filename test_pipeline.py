"""
Full pipeline smoke test using the downloaded English VTT.

Tests:
parse → dedup → chunk → embed (local)
→ ChromaDB → RAG search → Gemini answer
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, r"D:\Project\Video-Transcript-AI")

ROOT     = Path(r"D:\Project\Video-Transcript-AI")
VTT_FILE = ROOT / "test_caps_EVByF-I3usA.en.vtt"
VIDEO_ID    = "EVByF-I3usA"
VIDEO_TITLE = "Cloud, EC2, S3, RDS Explained | Interview Ready Tamil"

assert VTT_FILE.exists(), f"VTT file not found: {VTT_FILE}\nRun the yt-dlp download command first."
print(f"[1/7] English VTT found: {VTT_FILE.name}  ({VTT_FILE.stat().st_size // 1024} KB)")


# ── Step 2: Parse + deduplicate ───────────────────────────────────────────────
from youtube_qa.services.transcription import _parse_vtt, _deduplicate_captions

raw_segments   = _parse_vtt(VTT_FILE)
clean_segments = _deduplicate_captions(raw_segments)

print(f"[2/7] Raw cues: {len(raw_segments)}  →  Clean segments: {len(clean_segments)}")
assert len(clean_segments) > 0, "Deduplication wiped all segments"
print(f"      Sample: [{clean_segments[0]['start']:.1f}s] {clean_segments[0]['text'][:80]}")


# ── Step 3: Chunk ─────────────────────────────────────────────────────────────
from youtube_qa.services.chunking import chunk_transcript

chunks = chunk_transcript(
    segments=clean_segments,
    video_id=VIDEO_ID,
    video_title=VIDEO_TITLE,
    channel_id=1,
    channel_name="Hareesh Rajendran",
    chunk_size=400,
    chunk_overlap=60,
)
print(f"[3/7] Chunks: {len(chunks)}")
assert len(chunks) > 0, "Chunking returned 0 chunks"
total_words = sum(len(c["text"].split()) for c in chunks)
print(f"      Total words across chunks: {total_words}")
print(f"      First chunk ({chunks[0]['timestamp_label']}): {chunks[0]['text'][:80]}...")


# ── Step 4: Local embeddings ──────────────────────────────────────────────────
async def test_embeddings():
    from youtube_qa.services.embeddings import embed_texts

    print(f"[4/7] Embedding 3 sample chunks (model loads on first call) ...")
    sample = [c["text"] for c in chunks[:3]]
    embeddings = await embed_texts(sample)

    assert len(embeddings) == 3,           f"Expected 3 embeddings, got {len(embeddings)}"
    assert len(embeddings[0]) > 100,       "Embedding vector is too short"
    print(f"[4/7] Embedding OK — vector dim: {len(embeddings[0])}")

asyncio.run(test_embeddings())


# ── Step 5: Store all chunks in ChromaDB ─────────────────────────────────────
async def test_chromadb():
    from youtube_qa.services.vector_store import add_chunks, collection_count, delete_video_chunks

    delete_video_chunks(VIDEO_ID)
    before = collection_count()
    print(f"[5/7] ChromaDB before insert: {before} docs")

    print(f"[5/7] Storing {len(chunks)} chunks ...")
    await add_chunks(chunks)

    after = collection_count()
    print(f"[5/7] ChromaDB after insert:  {after} docs")
    assert after > before, f"Count did not increase: {before} → {after}"
    print(f"[5/7] ChromaDB OK — {after - before} chunks stored")

asyncio.run(test_chromadb())


# ── Step 6: RAG retrieval ─────────────────────────────────────────────────────
async def test_search():
    from youtube_qa.services.vector_store import search

    question = "What does the speaker explain about EC2?"
    print(f"[6/7] Semantic search: '{question}'")
    hits = await search(query=question, n_results=3)

    assert len(hits) > 0, "Search returned 0 results"
    print(f"[6/7] Retrieved {len(hits)} chunks:")
    for i, h in enumerate(hits, 1):
        print(f"      [{i}] {h['timestamp_label']}  dist={h['distance']:.3f}")
        print(f"           {h['text'][:100]}...")

asyncio.run(test_search())


# ── Step 7: LLM answer via Gemini ────────────────────────────────────────────
async def test_llm():
    from youtube_qa.services.qa_service import answer_question
    from youtube_qa.config import get_settings

    settings = get_settings()

    if not settings.gemini_api_key:
        print("[7/7] FAILED — GEMINI_API_KEY not set in .env")
        return

    question = "What does the speaker explain about EC2?"

    print(
        f"[7/7] Asking Gemini ({settings.chat_model}): "
        f"'{question}'"
    )

    response = await answer_question(
        question=question
    )

    assert response.answer, "Gemini returned an empty answer"

    print(
        f"[7/7] Answer ({len(response.answer)} chars):"
    )
    print()
    print(response.answer)
    print()

    print(
        f"      Model: {response.model}"
    )

    print(
        f"      Sources: {len(response.sources)}"
    )

    for source in response.sources:
        print(
            f"        - {source.video_title} "
            f"@ {source.timestamp_label} "
            f"{source.youtube_url}"
        )
asyncio.run(test_llm())

# ── Summary ───────────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("PIPELINE COMPLETE")
print(f"  Raw cues      : {len(raw_segments)}")
print(f"  Clean segments: {len(clean_segments)}")
print(f"  Chunks        : {len(chunks)}")
print(f"  Embed dim     : 384 (sentence-transformers)")
print(f"  ChromaDB      : {len(chunks)} docs stored")
print(f"  RAG + LLM     : working")
print("=" * 60)