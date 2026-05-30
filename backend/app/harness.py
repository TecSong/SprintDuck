from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Protocol

from .models import RolePreset
from .role_presets import infer_role, rubric_for


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    category: str = "local"
    output_schema: dict[str, Any] | None = None
    risk_level: str = "local_read"
    data_access: tuple[str, ...] = ()
    persists_data: bool = False


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    data: Any = None
    evidence_refs: tuple[str, ...] = ()
    audit_refs: tuple[str, ...] = ()
    error: str | None = None


@dataclass(frozen=True)
class IntentAnalysis:
    primary_intent: str
    secondary_intents: list[str]
    required_context: list[str]
    missing_context: list[str]
    risk_level: str
    rationale: str


@dataclass(frozen=True)
class PlanStep:
    id: str
    purpose: str
    tool_name: str
    risk_level: str = "local_read"
    requires_consent: bool = False


@dataclass(frozen=True)
class HarnessRun:
    intent: IntentAnalysis
    plan: list[PlanStep]
    tool_results: list[dict[str, Any]]
    artifact: dict[str, Any]
    summary: str


class AgentTool(Protocol):
    def spec(self) -> ToolSpec: ...

    async def run(self, payload: dict[str, Any]) -> ToolResult: ...


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, AgentTool] = {}

    def register(self, tool: AgentTool) -> None:
        self._tools[tool.spec().name] = tool

    async def run(self, name: str, payload: dict[str, Any]) -> ToolResult:
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(ok=False, error=f"Tool not found: {name}")
        return await tool.run(payload)

    def list_specs(self) -> list[ToolSpec]:
        return [tool.spec() for tool in self._tools.values()]


class RoleRubricTool:
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="role_rubric.load",
            description="Load local evaluation criteria for a role preset.",
            input_schema={"type": "object", "properties": {"role": {"type": "string"}}},
        )

    async def run(self, payload: dict[str, Any]) -> ToolResult:
        role = RolePreset(payload.get("role", RolePreset.GENERIC))
        return ToolResult(ok=True, data=[criterion.__dict__ for criterion in rubric_for(role)])


class EvidenceNormalizeTool:
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="evidence.normalize",
            description="Normalize evidence snippets and explicit missing-evidence labels.",
            input_schema={"type": "object", "properties": {"items": {"type": "array"}}},
        )

    async def run(self, payload: dict[str, Any]) -> ToolResult:
        items = payload.get("items") or []
        normalized = [str(item).strip() for item in items if str(item).strip()]
        return ToolResult(ok=True, data=normalized or ["未发现证据"])


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


class JobSearchHarness:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def analyze_intent(self, user_text: str, context: dict[str, Any]) -> IntentAnalysis | None:
        lower = user_text.lower()
        wants_message = any(token in lower for token in ("开场白", "内推", "申请表", "投递消息", "沟通话术", "boss"))
        wants_match = any(token in lower for token in ("值不值得", "要不要投", "匹配吗", "投递优先级")) or bool(
            re.search(r"(帮我|请|看看|看下|分析).{0,16}(判断|匹配度|匹配|是否值得|投不投)", user_text)
        )
        if not wants_message and not wants_match:
            return None

        secondary = ["application_message"] if wants_message else []
        required = ["resume", "jd"]
        missing = [
            key
            for key in required
            if len(str(context.get(f"{key}_text") or "").strip()) < 80
        ]
        rationale = "识别到用户希望判断岗位投递价值"
        if wants_message:
            rationale += "，并生成招聘者沟通草稿"
        return IntentAnalysis(
            primary_intent="jd_match",
            secondary_intents=secondary,
            required_context=required,
            missing_context=missing,
            risk_level="local_read",
            rationale=rationale,
        )

    def followup_for(self, intent: IntentAnalysis) -> str:
        labels = {"resume": "简历材料", "jd": "目标岗位 JD"}
        missing = "、".join(labels[item] for item in intent.missing_context)
        return f"我已识别到任务：{_intent_label(intent)}。还缺少：{missing}。请补充后我再继续执行。"

    async def run(self, intent: IntentAnalysis, context: dict[str, Any]) -> HarnessRun:
        plan = [
            PlanStep("parse-jd", "解析 JD 岗位事实和角色类型", "jd.parse"),
            PlanStep("extract-evidence", "把简历证据映射到 JD 要求", "evidence.extract"),
            PlanStep("score-fit", "计算匹配分和投递优先级", "fit.score"),
        ]
        if "application_message" in intent.secondary_intents:
            plan.append(PlanStep("compose-message", "生成招聘者开场白草稿", "message.compose", "local_write"))

        tool_results: list[dict[str, Any]] = []
        jd_result = await self.registry.run("jd.parse", {"jd_text": context["jd_text"]})
        _append_tool_result(tool_results, "jd.parse", jd_result)
        if not jd_result.ok:
            return _failed_run(intent, plan, tool_results, jd_result.error or "JD 解析失败")

        evidence_result = await self.registry.run(
            "evidence.extract",
            {
                "resume_text": context["resume_text"],
                "jd_text": context["jd_text"],
                "role": jd_result.data["role"],
            },
        )
        _append_tool_result(tool_results, "evidence.extract", evidence_result)
        if not evidence_result.ok:
            return _failed_run(intent, plan, tool_results, evidence_result.error or "证据抽取失败")

        fit_result = await self.registry.run("fit.score", evidence_result.data)
        _append_tool_result(tool_results, "fit.score", fit_result)
        if not fit_result.ok:
            return _failed_run(intent, plan, tool_results, fit_result.error or "匹配评分失败")

        artifact: dict[str, Any] = {
            "job": jd_result.data,
            "fit": fit_result.data,
            "evidence_map": evidence_result.data["evidence_map"],
        }

        if "application_message" in intent.secondary_intents:
            message_result = await self.registry.run(
                "message.compose",
                {"job_title": jd_result.data["title"], "fit": fit_result.data},
            )
            _append_tool_result(tool_results, "message.compose", message_result)
            if message_result.ok:
                artifact["message"] = message_result.data

        return HarnessRun(
            intent=intent,
            plan=plan,
            tool_results=tool_results,
            artifact=artifact,
            summary=_render_summary(intent, plan, artifact),
        )


def default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(RoleRubricTool())
    registry.register(EvidenceNormalizeTool())
    registry.register(JdParseTool())
    registry.register(EvidenceExtractTool())
    registry.register(FitScoreTool())
    registry.register(MessageComposeTool())
    return registry


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


def _append_tool_result(rows: list[dict[str, Any]], name: str, result: ToolResult) -> None:
    rows.append(
        {
            "tool": name,
            "ok": result.ok,
            "evidence_refs": list(result.evidence_refs),
            "audit_refs": list(result.audit_refs),
            "error": result.error,
        }
    )


def _failed_run(
    intent: IntentAnalysis,
    plan: list[PlanStep],
    tool_results: list[dict[str, Any]],
    error: str,
) -> HarnessRun:
    return HarnessRun(
        intent=intent,
        plan=plan,
        tool_results=tool_results,
        artifact={"error": error},
        summary=f"任务执行失败：{error}",
    )


def _intent_label(intent: IntentAnalysis) -> str:
    labels = [intent.primary_intent, *intent.secondary_intents]
    return " + ".join(labels)


def _render_summary(intent: IntentAnalysis, plan: list[PlanStep], artifact: dict[str, Any]) -> str:
    fit = dict(artifact.get("fit") or {})
    strengths = list(fit.get("strengths") or [])
    gaps = list(fit.get("gaps") or [])
    strength_lines = [
        f"- {item['requirement']}：{', '.join(item.get('resume_evidence') or ['已有相关证据'])}"
        for item in strengths[:2]
    ]
    gap_lines = [
        f"- {item['requirement']}：当前简历证据不足，建议补齐「{item['suggested_action']}」"
        for item in gaps[:2]
    ]
    message = dict(artifact.get("message") or {})
    sections = [
        f"意图分析：{_intent_label(intent)}。{intent.rationale}。",
        "推理执行：" + " -> ".join(step.tool_name for step in plan) + "。",
        f"结论：匹配分 {fit.get('score')}/100，证据覆盖率 {fit.get('coverage'):.0%}，投递建议为「{fit.get('priority')}」。",
    ]
    if strength_lines:
        sections.append("主要证据：\n" + "\n".join(strength_lines))
    if gap_lines:
        sections.append("待补齐 Gap：\n" + "\n".join(gap_lines))
    if message:
        sections.append("开场白草稿：\n" + str(message["draft"]))
    sections.append("下一步：先让用户确认草稿和事实真实性；不会自动发送或投递。")
    return "\n\n".join(sections)
