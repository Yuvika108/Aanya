"""
AANYA — FastAPI backend

Run locally with:
    python app.py   (or: uvicorn app:app --reload --port 8000)

Interactive API docs: http://localhost:8000/docs
"""

import asyncio
import io
import json
import os
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from engine import AanyaEngine
from models import ChatRequest, ChatResponse, TaskCreateRequest, TaskListResponse

load_dotenv()
import config

GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or getattr(config, "gemini_key", "")).strip()
if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is not set. Create a .env file or set it in your "
        "hosting provider's environment variables."
    )

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(title="Aanya API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dedicated thread-pool for blocking I/O (Gemini SDK + gTTS HTTP calls).
# Using a bounded pool prevents runaway threads under load.
_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="aanya-worker")

# ── Session store ─────────────────────────────────────────────────────────────
_sessions: dict[str, AanyaEngine] = {}


def _get_engine(session_id: str) -> AanyaEngine:
    if session_id not in _sessions:
        _sessions[session_id] = AanyaEngine(
            session_id=session_id, api_key=GEMINI_API_KEY
        )
    return _sessions[session_id]


# ── Static assets ─────────────────────────────────────────────────────────────
_static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(_static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=_static_dir), name="static")


@app.get("/")
def serve_ui():
    index_file = os.path.join(_static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"status": "ok", "message": "Aanya API is running"}


@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "Aanya API is running"}


# ── Chat endpoints ────────────────────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a message to Aanya with optional attachments. Runs in thread pool."""
    if not request.message.strip() and not request.attachments:
        raise HTTPException(status_code=400, detail="message or attachment is required")

    engine = _get_engine(request.session_id)

    try:
        loop = asyncio.get_running_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(_executor, engine.execute_command, request.message, request.attachments),
            timeout=35.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="Aanya took too long to respond. Please try again.",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return ChatResponse(**result)


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Real-time token streaming via Server-Sent Events (SSE)."""
    if not request.message.strip() and not request.attachments:
        raise HTTPException(status_code=400, detail="message or attachment is required")

    engine = _get_engine(request.session_id)

    async def event_generator():
        loop = asyncio.get_running_loop()
        queue = asyncio.Queue()

        def producer():
            try:
                for packet in engine.execute_command_stream(request.message, request.attachments):
                    loop.call_soon_threadsafe(queue.put_nowait, packet)
            except Exception as exc:
                loop.call_soon_threadsafe(queue.put_nowait, {"type": "error", "error": str(exc)})
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        _executor.submit(producer)

        while True:
            packet = await queue.get()
            if packet is None:
                break
            yield f"data: {json.dumps(packet)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Task endpoints ────────────────────────────────────────────────────────────
@app.get("/tasks/{session_id}", response_model=TaskListResponse)
def get_tasks(session_id: str):
    engine = _get_engine(session_id)
    return TaskListResponse(tasks=engine.load_tasks())


@app.post("/tasks/{session_id}", response_model=TaskListResponse)
def add_task(session_id: str, request: TaskCreateRequest):
    engine = _get_engine(session_id)
    engine.save_task(request.task)
    return TaskListResponse(tasks=engine.load_tasks())


@app.delete("/tasks/{session_id}/{task_number}", response_model=TaskListResponse)
def delete_task(session_id: str, task_number: int):
    engine = _get_engine(session_id)
    removed = engine.delete_task(task_number)
    if removed is None:
        raise HTTPException(status_code=404, detail="No task at that number")
    return TaskListResponse(tasks=engine.load_tasks())


# ── Custom Links & Shortcuts endpoints ────────────────────────────────────────
class LinkCreateRequest(BaseModel):
    name: str
    url: str
    session_id: str = "default"


@app.get("/links")
@app.get("/links/{session_id}")
def get_links(session_id: str = "default"):
    """Get all custom shortcuts/links for a given session."""
    engine = _get_engine(session_id)
    return {"links": engine.get_links()}


@app.post("/links")
def add_link(request: LinkCreateRequest):
    """Save a new custom link that Aanya can open directly."""
    if not request.name.strip() or not request.url.strip():
        raise HTTPException(status_code=400, detail="Name and URL are required")
    engine = _get_engine(request.session_id)
    link = engine.add_link(request.name, request.url)
    return {"link": link, "links": engine.get_links()}


@app.delete("/links/{link_id}")
def delete_link(link_id: str, session_id: str = "default"):
    """Delete a custom link by ID or name."""
    engine = _get_engine(session_id)
    removed = engine.delete_link(link_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Link not found")
    return {"status": "ok", "links": engine.get_links()}


# ── Feedback & Learning endpoints ─────────────────────────────────────────────
class FeedbackRequest(BaseModel):
    session_id: str = "default"
    positive: bool
    last_reply: str = ""
    correction: str = ""  # optional correction when thumbs_down


@app.post("/feedback")
async def submit_feedback(request: FeedbackRequest):
    """Record 👍/👎 feedback. On thumbs-down with a correction, immediately
    updates Aanya's memory so she improves for the rest of the session."""
    engine = _get_engine(request.session_id)
    loop = asyncio.get_running_loop()
    reply = await loop.run_in_executor(
        _executor,
        engine.apply_feedback,
        request.positive,
        request.last_reply,
        request.correction,
    )
    return {"reply": reply, "status": "ok"}


@app.get("/memory/{session_id}")
def get_memory(session_id: str):
    """Return everything Aanya has learned about this user."""
    engine = _get_engine(session_id)
    return engine.get_memory_summary()


@app.delete("/memory/{session_id}")
def clear_memory(session_id: str):
    """Wipe Aanya's learned memory for this session."""
    engine = _get_engine(session_id)
    engine.forget("all")
    return {"status": "ok", "message": "Memory cleared."}


# ── TTS endpoint ──────────────────────────────────────────────────────────────
class TTSRequest(BaseModel):
    text: str
    slow: bool = False


def _generate_tts_mp3(text: str, slow: bool) -> bytes:
    """Synchronous gTTS call — runs in thread pool."""
    from gtts import gTTS  # lazy import; avoids startup cost
    tts = gTTS(text=text, lang="en", tld="co.uk", slow=slow)
    buf = io.BytesIO()
    tts.write_to_fp(buf)
    return buf.getvalue()


@app.post("/tts")
async def text_to_speech(request: TTSRequest):
    """Convert text to British-English MP3 via Google TTS.

    gTTS makes an outbound HTTP call to Google — we run it in a thread so it
    never blocks the async event loop (which caused the 'server disconnected'
    error when called back-to-back with /chat).
    """
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text cannot be empty")

    # Truncate extremely long replies so TTS stays snappy
    if len(text) > 500:
        text = text[:500] + "..."

    try:
        loop = asyncio.get_running_loop()
        mp3_bytes = await asyncio.wait_for(
            loop.run_in_executor(_executor, _generate_tts_mp3, text, request.slow),
            timeout=15.0,  # gTTS should respond within 15 s even on slow connections
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504, detail="TTS generation timed out."
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"TTS generation failed: {exc}"
        )

    return StreamingResponse(
        io.BytesIO(mp3_bytes),
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-store", "Content-Length": str(len(mp3_bytes))},
    )


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    print(f"\n🚀 Aanya starting on http://localhost:{port}")
    print(f"📖 Docs: http://localhost:{port}/docs\n")
    reload_enabled = os.getenv("RELOAD", "false").lower() in ("true", "1", "yes")
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        reload=reload_enabled,
        reload_excludes=["*.json", "server/data/*", "*/server/data/*", "data/*", "*.log", ".pytest_cache/*", "__pycache__/*"],
        reload_dirs=["server", "static"] if reload_enabled else None,
        # Increase timeouts so long Gemini calls don't get cut off by uvicorn
        timeout_keep_alive=60,
    )