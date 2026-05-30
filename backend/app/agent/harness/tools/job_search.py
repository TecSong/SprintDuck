from __future__ import annotations

import re
from typing import Any

from ....models import RolePreset
from ....role_presets import infer_role, rubric_for
from ..registry import ToolResult, ToolSpec


class JdParseTool:
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="jd.parse",
            description="Parse a pasted JD into local job facts and role signals.",
            input_schema={"type": "object", "properties": {"jd_text": {"type": "string"}}},
            output_schema={"type": "object"},
            data_access=("jd",),
        )

    async def run(self, payload: dict[str, Any]) -> ToolResult:
        jd_text = str(payload.get("jd_text") or "")
        role, confidence = infer_role(jd_text)
        title = _extract_job_title(jd_text)
        chunks = _chunks(jd_text)
        return ToolResult(
            ok=True,
            data={
                "title": title,
                "role": role.value,
                "role_confidence": confidence,
                "requirements": chunks[:8],
            },
            evidence_refs=("jd",),
        )


class EvidenceExtractTool:
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="evidence.extract",
            description="Map resume evidence snippets to local JD requirements.",
            input_schema={
                "type": "object",
                "properties": {
                    "resume_text": {"type": "string"},
                    "jd_text": {"type": "string"},
                    "role": {"type": "string"},
                },
            },
            output_schema={"type": "object"},
            data_access=("resume", "jd"),
        )

    async def run(self, payload: dict[str, Any]) -> ToolResult:
        role = RolePreset(payload.get("role") or RolePreset.GENERIC)
        resume_chunks = _chunks(str(payload.get("resume_text") or ""))
        jd_chunks = _chunks(str(payload.get("jd_text") or ""))
        rows = []
        for criterion in rubric_for(role):
            resume_evidence = _matching_chunks(resume_chunks, criterion.keywords)[:2]
            jd_evidence = _matching_chunks(jd_chunks, criterion.keywords)[:2]
            rows.append(
                {
                    "requirement": criterion.title,
                    "matched": bool(resume_evidence),
                    "resume_evidence": resume_evidence,
                    "jd_evidence": jd_evidence,
                    "suggested_action": criterion.action,
                }
            )
        return ToolResult(ok=True, data={"evidence_map": rows}, evidence_refs=("resume", "jd"))


class FitScoreTool:
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="fit.score",
            description="Compute explainable local fit score and application priority.",
            input_schema={"type": "object", "properties": {"evidence_map": {"type": "array"}}},
            output_schema={"type": "object"},
        )

    async def run(self, payload: dict[str, Any]) -> ToolResult:
        evidence_map = list(payload.get("evidence_map") or [])
        total = len(evidence_map) or 1
        matched = [row for row in evidence_map if row.get("matched")]
        gaps = [row for row in evidence_map if not row.get("matched")]
        coverage = round(len(matched) / total, 2)
        score = max(0, min(100, round(35 + coverage * 55)))
        priority = "建议投递" if score >= 70 else ("谨慎投递" if score >= 50 else "低优先级")
        return ToolResult(
            ok=True,
            data={
                "score": score,
                "coverage": coverage,
                "priority": priority,
                "strengths": matched[:3],
                "gaps": gaps[:3],
            },
            evidence_refs=("resume", "jd"),
        )


class MessageComposeTool:
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="message.compose",
            description="Compose a concise Chinese recruiter opening draft from verified evidence.",
            input_schema={
                "type": "object",
                "properties": {
                    "job_title": {"type": "string"},
                    "fit": {"type": "object"},
                },
            },
            output_schema={"type": "object"},
            risk_level="local_write",
            data_access=("resume", "jd"),
        )

    async def run(self, payload: dict[str, Any]) -> ToolResult:
        fit = dict(payload.get("fit") or {})
        strengths = list(fit.get("strengths") or [])
        gaps = list(fit.get("gaps") or [])
        job_title = str(payload.get("job_title") or "这个岗位")
        strength_text = _first_resume_evidence(strengths) or "我的过往经历和岗位要求有直接相关部分"
        ask_text = gaps[0]["requirement"] if gaps else "团队当前最看重的能力"
        draft = (
            f"你好，我关注到{job_title}，我过往有相关经历：{strength_text}。"
            f"我想进一步了解岗位对「{ask_text}」的要求，也希望有机会投递并沟通。"
        )
        return ToolResult(ok=True, data={"draft": draft, "channel": "Boss 直聘/招聘者私聊"}, evidence_refs=("resume", "jd"))


def _chunks(text: str) -> list[str]:
    return [
        chunk.strip()
        for chunk in re.split(r"[\n。；;.!?？]+", text)
        if len(chunk.strip()) >= 3
    ]


def _matching_chunks(chunks: list[str], keywords: tuple[str, ...]) -> list[str]:
    rows = []
    for chunk in chunks:
        lower = chunk.lower()
        if any(keyword.lower() in lower for keyword in keywords):
            rows.append(chunk)
    return rows


def _extract_job_title(jd_text: str) -> str:
    patterns = (
        r"(?:岗位|职位|Job Title|Title)\s*[:：]\s*([^\n。；;]+)",
        r"([A-Za-z ]*(?:Engineer|Manager|Operations|运营|工程师|产品经理)[A-Za-z\u4e00-\u9fff ]*)",
    )
    for pattern in patterns:
        match = re.search(pattern, jd_text, flags=re.I)
        if match:
            return match.group(1).strip()[:60]
    return "目标岗位"


def _first_resume_evidence(strengths: list[dict[str, Any]]) -> str:
    for strength in strengths:
        evidence = list(strength.get("resume_evidence") or [])
        if evidence:
            return str(evidence[0])[:80]
    return ""
