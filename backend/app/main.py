from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .agent import SprintDuckAgent
from .models import CreateSessionResponse, HealthResponse, SessionState, SseEvent
from .providers import DeepSeekProvider
from .session_store import InMemorySessionStore

app = FastAPI(title="SprintDuckAgent API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

store = InMemorySessionStore()
agent = SprintDuckAgent(provider=DeepSeekProvider())


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(ok=True, service="sprintduck-agent")


@app.post("/api/chat/sessions", response_model=CreateSessionResponse)
async def create_session() -> CreateSessionResponse:
    session = store.create()
    return CreateSessionResponse(
        session_id=session.session_id,
        status=session.status,
        message="请发送简历、目标 JD、关键日期、每天可投入时间和当前求职阶段。支持粘贴文本或上传 .txt/.md。",
        missing=agent.initial_missing(),
    )


@app.get("/api/chat/sessions/{session_id}", response_model=SessionState)
async def get_session(session_id: str) -> SessionState:
    session = store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.post("/api/chat/sessions/{session_id}/messages")
async def post_message(
    session_id: str,
    message: str = Form(default=""),
    files: list[UploadFile] | None = File(default=None),
) -> StreamingResponse:
    session = store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    file_text = await _read_text_files(files or [])
    merged = "\n\n".join(part for part in [message.strip(), file_text] if part)
    if not merged:
        raise HTTPException(status_code=400, detail="Message or text file is required")

    async def stream() -> AsyncIterator[str]:
        try:
            async for event in agent.handle_user_message(session, merged):
                store.save(session)
                yield _format_sse(event)
        except Exception as exc:
            yield _format_sse(SseEvent(event="error", data={"message": str(exc)}))

    return StreamingResponse(stream(), media_type="text/event-stream")


async def _read_text_files(files: list[UploadFile]) -> str:
    chunks: list[str] = []
    for file in files:
        name = (file.filename or "").lower()
        if not (name.endswith(".txt") or name.endswith(".md") or name.endswith(".markdown")):
            continue
        raw = await file.read()
        chunks.append(raw.decode("utf-8", errors="ignore").strip())
    return "\n\n".join(chunk for chunk in chunks if chunk)


def _format_sse(event: SseEvent) -> str:
    return f"event: {event.event}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"
