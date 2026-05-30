from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import AsyncIterator

from .harness import ToolRegistry, default_registry
from .markdown import render_report_markdown
from .models import (
    ChatMessage,
    EvidenceItem,
    GapItem,
    InterviewQuestion,
    ReadinessBand,
    RolePreset,
    SessionState,
    SprintPlanDay,
    SprintReport,
    SseEvent,
)
from .providers import LLMProvider
from .role_presets import Criterion, infer_role, rubric_for


MISSING_LABELS = {
    "resume": "简历材料",
    "jd": "目标岗位 JD",
    "deadline": "关键日期",
    "daily_minutes": "每天可投入时间",
    "stage": "当前求职阶段",
}

SECTION_LABELS = {
    "resume": r"(?:简历|候选人|candidate|resume)\s*[:：]",
    "jd": r"(?:jd|目标\s*jd|岗位职责|职位描述|job description)\s*[:：]",
    "constraints": r"(?:约束|限制|关键日期|面试日期|投递日期|constraints)\s*[:：]",
}

JD_SIGNAL_TOKENS = ("jd", "岗位", "职位", "职责", "要求", "任职", "job description")
RESUME_SIGNAL_TOKENS = ("简历", "经历", "项目", "负责", "我是一名", "我有")


@dataclass(frozen=True)
class ContextQuality:
    missing: list[str]
    low_confidence: bool


class SprintDuckAgent:
    def __init__(self, provider: LLMProvider, registry: ToolRegistry | None = None) -> None:
        self.provider = provider
        self.registry = registry or default_registry()

    def initial_missing(self) -> list[str]:
        return list(MISSING_LABELS.values())

    async def handle_user_message(self, session: SessionState, text: str) -> AsyncIterator[SseEvent]:
        text = text.strip()
        session.messages.append(ChatMessage(role="user", content=text))
        self._ingest_text(session, text)

        yield SseEvent(event="status", data={"message": "已收到信息，正在检查上下文完整度。"})
        await asyncio.sleep(0)

        quality = self._quality(session)
        if quality.missing and session.followup_count < 2:
            session.followup_count += 1
            session.status = "collecting_context"
            reply = self._followup_question(quality.missing)
            session.messages.append(ChatMessage(role="assistant", content=reply))
            yield SseEvent(event="assistant_delta", data={"text": reply})
            yield SseEvent(event="state", data=self._state_payload(session, quality.missing))
            yield SseEvent(event="done", data={"status": session.status})
            return

        if session.jd_text and not session.role:
            role, confidence = infer_role(session.jd_text)
            session.role = role
            session.role_confidence = confidence

        if quality.low_confidence and session.followup_count < 2:
            session.followup_count += 1
            session.status = "needs_role_confirmation"
            reply = "我对岗位类型判断不够确定。请直接告诉我这是工程、产品、运营，还是其他岗位？"
            session.messages.append(ChatMessage(role="assistant", content=reply))
            yield SseEvent(event="assistant_delta", data={"text": reply})
            yield SseEvent(event="state", data=self._state_payload(session, quality.missing))
            yield SseEvent(event="done", data={"status": session.status})
            return

        session.status = "ready_to_report"
        yield SseEvent(event="status", data={"message": "上下文足够，正在生成证据化冲刺报告。"})
        report = await self._generate_report(session, low_confidence=bool(quality.missing or quality.low_confidence))
        session.report = report
        session.status = "report_ready"
        reply = "报告已生成。右侧可以查看准备度、证据化 Gap、冲刺计划和高频追问，也可以下载 Markdown。"
        session.messages.append(ChatMessage(role="assistant", content=reply))
        yield SseEvent(event="assistant_delta", data={"text": reply})
        yield SseEvent(event="report", data=report.model_dump(mode="json"))
        yield SseEvent(event="state", data=self._state_payload(session, []))
        yield SseEvent(event="done", data={"status": session.status})

    def _ingest_text(self, session: SessionState, text: str) -> None:
        role = _extract_role_confirmation(text, session.status)
        if role:
            session.role = role
            session.role_confidence = 0.95

        sections = _extract_labeled_sections(text)
        if sections.get("resume"):
            session.resume_text = _append(session.resume_text, sections["resume"])
        if sections.get("jd"):
            session.jd_text = _append(session.jd_text, sections["jd"])
        if sections.get("constraints"):
            session.constraints_text = _append(session.constraints_text, sections["constraints"])

        has_jd_signal = _has_jd_signal(text)
        has_resume_signal = _has_resume_signal(text)
        has_constraint_signal = _has_deadline(text) or _daily_minutes(text) or _stage(text)

        if not sections and has_jd_signal:
            session.jd_text = _append(session.jd_text, text)
        if not sections and (has_resume_signal or not session.resume_text):
            session.resume_text = _append(session.resume_text, text)
        if sections:
            for prefix in _unlabeled_prefixes(text):
                if _has_jd_signal(prefix):
                    session.jd_text = _append(session.jd_text, prefix)
        if has_constraint_signal:
            session.constraints_text = _append(session.constraints_text, text)

        if session.jd_text and (not session.role or session.role_confidence < 0.55):
            inferred, confidence = infer_role(session.jd_text)
            session.role = inferred
            session.role_confidence = confidence

    def _quality(self, session: SessionState) -> ContextQuality:
        missing: list[str] = []
        if len(session.resume_text) < 80:
            missing.append("resume")
        if len(session.jd_text) < 80:
            missing.append("jd")
        if not _has_deadline(session.constraints_text):
            missing.append("deadline")
        if not _daily_minutes(session.constraints_text):
            missing.append("daily_minutes")
        if not _stage(session.constraints_text):
            missing.append("stage")
        low_confidence = bool(session.jd_text and session.role_confidence < 0.55)
        return ContextQuality(missing=missing, low_confidence=low_confidence)

    def _followup_question(self, missing: list[str]) -> str:
        labels = [MISSING_LABELS[key] for key in missing[:3]]
        return "我还缺少这些关键信息：" + "、".join(labels) + "。请补充后我再生成报告。"

    def _state_payload(self, session: SessionState, missing: list[str]) -> dict[str, object]:
        return {
            "session_id": session.session_id,
            "status": session.status,
            "missing": [MISSING_LABELS[key] for key in missing],
            "role": session.role,
            "role_confidence": session.role_confidence,
            "followup_count": session.followup_count,
        }

    async def _generate_report(self, session: SessionState, low_confidence: bool) -> SprintReport:
        role = session.role or RolePreset.GENERIC
        criteria = rubric_for(role)
        gaps = self._build_gaps(criteria, session.resume_text, session.jd_text)
        coverage = _evidence_coverage(gaps)
        score = _score_from_coverage(coverage, low_confidence)
        band = _band_for(score)
        days = _plan_days(session.constraints_text)
        daily_minutes = _daily_minutes(session.constraints_text) or 60
        plan = _build_plan(days, daily_minutes, gaps)
        questions = _build_questions(criteria, gaps)
        summary = (
            f"基于当前简历和 JD，系统按 {role.value} 模板评估。"
            f"你的材料准备度为 {score}/100，证据覆盖率约 {coverage:.0%}。"
            "这不是 offer 概率，而是当前材料相对目标岗位的准备度。"
        )

        report = SprintReport(
            role=role,
            readiness_score=score,
            readiness_band=band,
            evidence_coverage=coverage,
            confidence="low" if low_confidence else ("high" if coverage >= 0.75 else "medium"),
            summary=summary,
            top_gaps=gaps[:4],
            sprint_plan=plan,
            interview_questions=questions,
        )

        report = await self._maybe_enrich_with_llm(report, session)
        report.markdown = render_report_markdown(report)
        return report

    def _build_gaps(self, criteria: tuple[Criterion, ...], resume_text: str, jd_text: str) -> list[GapItem]:
        resume_chunks = _chunks(resume_text)
        jd_chunks = _chunks(jd_text)
        rows: list[GapItem] = []
        for criterion in criteria:
            resume_evidence = _matching_chunks(resume_chunks, criterion.keywords)
            jd_evidence = _matching_chunks(jd_chunks, criterion.keywords)
            if resume_evidence:
                severity = "low"
                reason = "简历中已有相关证据，但仍需要前置表达并贴合 JD 语言。"
                evidence = [EvidenceItem(source="resume", text=item) for item in resume_evidence[:2]]
            else:
                severity = "high" if jd_evidence else "medium"
                reason = "JD 提到相关要求，但简历中未发现足够证据。" if jd_evidence else "当前材料中未发现稳定证据，需要补齐表达。"
                evidence = [EvidenceItem(source="jd", text=item) for item in jd_evidence[:2]]
                if not evidence:
                    evidence = [EvidenceItem(source="inference", text="未发现证据")]

            rows.append(
                GapItem(
                    title=criterion.title,
                    severity=severity,
                    evidence=evidence,
                    gap_reason=reason,
                    suggested_action=criterion.action,
                )
            )

        return sorted(rows, key=lambda item: {"high": 0, "medium": 1, "low": 2}[item.severity])

    async def _maybe_enrich_with_llm(self, report: SprintReport, session: SessionState) -> SprintReport:
        system = (
            "你是求职冲刺教练，只能基于已给简历/JD证据改写总结和追问。"
            "返回 JSON，字段为 summary 和 interview_questions。不要编造经历。"
        )
        user = json.dumps(
            {
                "resume": session.resume_text[:4000],
                "jd": session.jd_text[:4000],
                "current_report": report.model_dump(mode="json", exclude={"markdown"}),
            },
            ensure_ascii=False,
        )
        try:
            enriched = await self.provider.generate_json(system, user)
        except Exception:
            return report
        if not enriched:
            return report
        if isinstance(enriched.get("summary"), str) and enriched["summary"].strip():
            report.summary = enriched["summary"].strip()
        raw_questions = enriched.get("interview_questions")
        if isinstance(raw_questions, list):
            parsed: list[InterviewQuestion] = []
            for item in raw_questions[:8]:
                if isinstance(item, dict) and item.get("question"):
                    parsed.append(
                        InterviewQuestion(
                            question=str(item["question"]),
                            why_it_matters=str(item.get("why_it_matters") or "验证关键岗位要求。"),
                            linked_gap=str(item.get("linked_gap") or report.top_gaps[0].title),
                        )
                    )
            if len(parsed) >= 5:
                report.interview_questions = parsed
        return report


def _append(current: str, addition: str) -> str:
    addition = addition.strip()
    if not addition:
        return current
    return f"{current}\n\n{addition}".strip() if current else addition


def _extract_labeled_sections(text: str) -> dict[str, str]:
    matches = _section_matches(text)
    sections: dict[str, str] = {}
    for index, (name, _start, end) in enumerate(matches):
        next_start = matches[index + 1][1] if index + 1 < len(matches) else len(text)
        sections[name] = text[end:next_start].strip()
    return {key: value for key, value in sections.items() if value}


def _section_matches(text: str) -> list[tuple[str, int, int]]:
    matches: list[tuple[str, int, int]] = []
    for name, pattern in SECTION_LABELS.items():
        for match in re.finditer(pattern, text, flags=re.I):
            matches.append((name, match.start(), match.end()))
    matches.sort(key=lambda item: item[1])
    return matches


def _unlabeled_prefixes(text: str) -> list[str]:
    matches = _section_matches(text)
    if not matches:
        return []
    prefix = text[: matches[0][1]].strip()
    return [prefix] if prefix else []


def _has_jd_signal(text: str) -> bool:
    lower = text.lower()
    return any(token in lower for token in JD_SIGNAL_TOKENS)


def _has_resume_signal(text: str) -> bool:
    return any(token in text for token in RESUME_SIGNAL_TOKENS)


def _extract_role_confirmation(text: str, status: str) -> RolePreset | None:
    if status != "needs_role_confirmation" and len(text.strip()) > 24:
        return None
    lower = text.lower()
    if any(token in lower for token in ("工程", "研发", "前端", "后端", "engineering", "engineer")):
        return RolePreset.ENGINEERING
    if any(token in lower for token in ("产品", "product")):
        return RolePreset.PRODUCT
    if any(token in lower for token in ("运营", "operations", "operator")):
        return RolePreset.OPERATIONS
    return None


def _has_deadline(text: str) -> bool:
    return bool(
        re.search(
            r"(明天|后天|\d+\s*天后|(?<![\d-])\d{1,2}\s*[/-]\s*\d{1,2}(?![\d-])|\d{1,2}\s*月\s*\d{1,2}\s*日|面试日期|投递日期)",
            text,
        )
    )


def _daily_minutes(text: str) -> int | None:
    minute = re.search(r"每天.*?(\d{1,3})\s*分钟", text)
    if minute:
        return int(minute.group(1))
    hour = re.search(r"每天.*?(\d(?:\.\d)?)\s*小时", text)
    if hour:
        return int(float(hour.group(1)) * 60)
    return None


def _stage(text: str) -> str | None:
    for token in ("一面", "二面", "终面", "投递", "准备", "邀约", "邀请", "面试前", "作品集"):
        if token in text:
            return token
    return None


def _plan_days(text: str) -> int:
    if "明天" in text:
        return 1
    if "后天" in text:
        return 2
    match = re.search(r"(\d{1,2})\s*天后", text)
    if match:
        return max(1, min(7, int(match.group(1))))
    return 7


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


def _evidence_coverage(gaps: list[GapItem]) -> float:
    if not gaps:
        return 0
    matched = sum(1 for gap in gaps if any(item.source == "resume" for item in gap.evidence))
    return round(matched / len(gaps), 2)


def _score_from_coverage(coverage: float, low_confidence: bool) -> int:
    score = round(35 + coverage * 55)
    if low_confidence:
        score = min(score, 62)
    return max(0, min(100, score))


def _band_for(score: int) -> ReadinessBand:
    if score >= 75:
        return ReadinessBand.HIGH
    if score >= 50:
        return ReadinessBand.MEDIUM
    return ReadinessBand.LOW


def _build_plan(days: int, daily_minutes: int, gaps: list[GapItem]) -> list[SprintPlanDay]:
    plan: list[SprintPlanDay] = []
    for day in range(1, days + 1):
        gap = gaps[(day - 1) % len(gaps)]
        plan.append(
            SprintPlanDay(
                day=day,
                focus=gap.title,
                minutes=daily_minutes,
                tasks=[
                    f"整理「{gap.title}」相关经历，写出背景、动作、结果各 3 条。",
                    f"按 JD 语言重写一段 90 秒回答，并标出可量化证据。",
                    "用一遍模拟追问检查是否仍有未发现证据。",
                ],
                linked_gap=gap.title,
                done_criteria="能用 90 秒讲清楚证据、取舍、结果，并能回答至少 2 个追问。",
            )
        )
    return plan


def _build_questions(criteria: tuple[Criterion, ...], gaps: list[GapItem]) -> list[InterviewQuestion]:
    questions: list[InterviewQuestion] = []
    for criterion, gap in zip(criteria, gaps, strict=False):
        questions.append(
            InterviewQuestion(
                question=criterion.question_seed,
                why_it_matters=f"面试官会用这个问题验证「{gap.title}」是否有真实经历支撑。",
                linked_gap=gap.title,
            )
        )
    while len(questions) < 5:
        gap = gaps[len(questions) % len(gaps)]
        questions.append(
            InterviewQuestion(
                question=f"请用 STAR 结构讲一个能证明「{gap.title}」的案例。",
                why_it_matters="这是把简历证据转成面试表达的关键问题。",
                linked_gap=gap.title,
            )
        )
    return questions[:8]
