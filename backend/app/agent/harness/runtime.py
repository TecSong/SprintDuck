from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from .registry import ToolRegistry
from .skills import SkillRegistry, default_skill_registry
from .tools import default_registry


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
    skill_name: str
    risk_level: str = "local_read"
    requires_consent: bool = False


@dataclass(frozen=True)
class HarnessRun:
    intent: IntentAnalysis
    plan: list[PlanStep]
    tool_results: list[dict[str, Any]]
    artifact: dict[str, Any]
    summary: str


@dataclass(frozen=True)
class HarnessProgress:
    phase: str
    message: str
    plan: list[PlanStep] | None = None
    run: HarnessRun | None = None


class JobSearchHarness:
    def __init__(
        self,
        tools: ToolRegistry | None = None,
        skills: SkillRegistry | None = None,
    ) -> None:
        self.tools = tools or default_registry()
        self.skills = skills or default_skill_registry()

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
        final_run: HarnessRun | None = None
        async for progress in self.run_stream(intent, context):
            if progress.run:
                final_run = progress.run
        if final_run:
            return final_run
        return _failed_run(intent, [], [], {}, "Harness 未产生执行结果")

    async def run_stream(self, intent: IntentAnalysis, context: dict[str, Any]):
        skill_names = self._skill_names_for(intent)
        plan = self._build_plan(skill_names, context)
        yield HarnessProgress(
            phase="plan_generated",
            message="Plan 生成：" + " -> ".join(f"{step.skill_name}.{step.tool_name}" for step in plan) + "。",
            plan=plan,
        )
        tool_results: list[dict[str, Any]] = []
        artifact: dict[str, Any] = {}
        for skill_name in skill_names:
            skill = self.skills.get(skill_name)
            if not skill:
                yield HarnessProgress(
                    phase="completed",
                    message=f"计划执行：{skill_name} 不存在，任务中止。",
                    run=_failed_run(intent, plan, tool_results, artifact, f"Skill not found: {skill_name}"),
                )
                return
            yield HarnessProgress(
                phase="skill_started",
                message=(
                    f"计划执行：开始 {skill_name}，调用 "
                    + "、".join(skill.required_tools(context))
                    + "。"
                ),
            )
            result = await skill.run(context, self.tools, artifact)
            tool_results.extend(result.tool_results)
            if not result.ok:
                yield HarnessProgress(
                    phase="completed",
                    message=f"计划执行：{skill_name} 失败，正在返回可审计结果。",
                    run=_failed_run(intent, plan, tool_results, artifact, result.error or f"{skill_name} 执行失败"),
                )
                return
            artifact.update(result.artifact)
            yield HarnessProgress(
                phase="skill_completed",
                message=(
                    f"计划执行：完成 {skill_name}，得到 "
                    + "、".join(item["tool"] for item in result.tool_results)
                    + " 结果。"
                ),
            )

        run = HarnessRun(
            intent=intent,
            plan=plan,
            tool_results=tool_results,
            artifact=artifact,
            summary=_render_summary(intent, plan, artifact),
        )
        yield HarnessProgress(phase="completed", message="计划执行：全部步骤完成，正在生成最终回答。", run=run)

    def _skill_names_for(self, intent: IntentAnalysis) -> list[str]:
        skill_names = ["jd_match_analyst"]
        if "application_message" in intent.secondary_intents:
            skill_names.append("application_assistant")
        return skill_names

    def _build_plan(self, skill_names: list[str], context: dict[str, Any]) -> list[PlanStep]:
        plan: list[PlanStep] = []
        for skill_name in skill_names:
            skill = self.skills.get(skill_name)
            if not skill:
                continue
            for tool_name in skill.required_tools(context):
                plan.append(
                    PlanStep(
                        id=f"{skill_name}:{tool_name}",
                        purpose=f"{skill.description} / {tool_name}",
                        tool_name=tool_name,
                        skill_name=skill_name,
                        risk_level="local_write" if tool_name == "message.compose" else "local_read",
                    )
                )
        return plan


def _failed_run(
    intent: IntentAnalysis,
    plan: list[PlanStep],
    tool_results: list[dict[str, Any]],
    artifact: dict[str, Any],
    error: str,
) -> HarnessRun:
    failed_artifact = {**artifact, "error": error}
    return HarnessRun(
        intent=intent,
        plan=plan,
        tool_results=tool_results,
        artifact=failed_artifact,
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
        "推理执行：" + " -> ".join(f"{step.skill_name}.{step.tool_name}" for step in plan) + "。",
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
