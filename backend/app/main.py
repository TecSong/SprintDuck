from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .agent import SprintDuckAgent
from .models import (
    CreateSessionResponse,
    HealthResponse,
    LLMConfigResponse,
    SessionState,
    SseEvent,
    UpdateLLMConfigRequest,
)
from .providers import build_provider_from_env, llm_config_payload, save_llm_config
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
agent = SprintDuckAgent(provider=build_provider_from_env())


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(ok=True, service="sprintduck-agent")


@app.get("/api/llm/config", response_model=LLMConfigResponse)
async def get_llm_config() -> dict[str, object]:
    return llm_config_payload()


@app.put("/api/llm/config", response_model=LLMConfigResponse)
async def update_llm_config(payload: UpdateLLMConfigRequest) -> dict[str, object]:
    try:
        config = save_llm_config(payload.provider, payload.api_key, payload.model, payload.base_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    agent.provider = build_provider_from_env()
    return config


@app.post("/api/chat/sessions", response_model=CreateSessionResponse)
async def create_session() -> CreateSessionResponse:
    session = store.create()
    llm_warning = _llm_warning()
    message = "请发送简历、目标 JD、关键日期、每天可投入时间和当前求职阶段。支持粘贴文本或上传 .txt/.md。"
    return CreateSessionResponse(
        session_id=session.session_id,
        status=session.status,
        message=f"{llm_warning}\n\n{message}" if llm_warning else message,
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
            llm_warning = _llm_warning()
            if llm_warning:
                yield _format_sse(SseEvent(event="status", data={"message": llm_warning}))
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
        text = raw.decode("utf-8", errors="ignore").strip()
        label = _label_for_upload(name)
        chunks.append(f"{label}：\n{text}" if label else text)
    return "\n\n".join(chunk for chunk in chunks if chunk)


def _label_for_upload(filename: str) -> str | None:
    if any(token in filename for token in ("resume", "cv", "简历")):
        return "简历"
    if any(token in filename for token in ("jd", "job", "岗位", "职位")):
        return "JD"
    if any(token in filename for token in ("constraint", "deadline", "约束", "时间")):
        return "约束"
    return None


def _format_sse(event: SseEvent) -> str:
    return f"event: {event.event}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"


def _llm_warning() -> str | None:
    config = llm_config_payload()
    active = next(
        (provider for provider in config["providers"] if provider["id"] == config["active_provider"]),
        None,
    )
    if not active or active["configured"]:
        return None
    return f"当前 {active['name']} 尚未配置 API Key。请点击右上角齿轮填写 {active['api_key_env']}。"
