from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class RolePreset(StrEnum):
    ENGINEERING = "engineering"
    PRODUCT = "product"
    OPERATIONS = "operations"
    GENERIC = "generic"


class ReadinessBand(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvidenceItem(BaseModel):
    source: Literal["resume", "jd", "inference"]
    text: str


class GapItem(BaseModel):
    title: str
    severity: Literal["high", "medium", "low"]
    evidence: list[EvidenceItem]
    gap_reason: str
    suggested_action: str


class SprintPlanDay(BaseModel):
    day: int
    focus: str
    minutes: int
    tasks: list[str]
    linked_gap: str
    done_criteria: str


class InterviewQuestion(BaseModel):
    question: str
    why_it_matters: str
    linked_gap: str


class SprintReport(BaseModel):
    role: RolePreset
    readiness_score: int = Field(ge=0, le=100)
    readiness_band: ReadinessBand
    evidence_coverage: float = Field(ge=0, le=1)
    confidence: Literal["high", "medium", "low"]
    summary: str
    top_gaps: list[GapItem]
    sprint_plan: list[SprintPlanDay]
    interview_questions: list[InterviewQuestion]
    markdown: str = ""


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class SessionState(BaseModel):
    session_id: str
    status: Literal["collecting_context", "needs_role_confirmation", "ready_to_report", "report_ready"] = (
        "collecting_context"
    )
    messages: list[ChatMessage] = Field(default_factory=list)
    resume_text: str = ""
    jd_text: str = ""
    constraints_text: str = ""
    role: RolePreset | None = None
    role_confidence: float = 0
    followup_count: int = 0
    report: SprintReport | None = None


class CreateSessionResponse(BaseModel):
    session_id: str
    status: str
    message: str
    missing: list[str]


class SseEvent(BaseModel):
    event: Literal["status", "assistant_delta", "state", "report", "error", "done"]
    data: dict[str, Any]


class HealthResponse(BaseModel):
    ok: bool
    service: str


class LLMProviderConfig(BaseModel):
    id: str
    name: str
    api_key_env: str
    model_env: str
    base_url_env: str
    configured: bool
    api_key_mask: str
    model: str
    base_url: str


class LLMConfigResponse(BaseModel):
    active_provider: str
    providers: list[LLMProviderConfig]
