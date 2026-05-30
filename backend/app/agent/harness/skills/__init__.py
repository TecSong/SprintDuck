from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ..registry import ToolRegistry, ToolResult


@dataclass(frozen=True)
class SkillResult:
    ok: bool
    artifact: dict[str, Any]
    tool_results: list[dict[str, Any]]
    error: str | None = None


class AgentSkill(Protocol):
    name: str
    description: str
    supported_intents: tuple[str, ...]

    def required_tools(self, context: dict[str, Any]) -> list[str]: ...

    async def run(
        self,
        context: dict[str, Any],
        tools: ToolRegistry,
        artifact: dict[str, Any],
    ) -> SkillResult: ...


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, AgentSkill] = {}

    def register(self, skill: AgentSkill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> AgentSkill | None:
        return self._skills.get(name)


class JdMatchAnalystSkill:
    name = "jd_match_analyst"
    description = "解析 JD、映射简历证据，并计算本地投递优先级。"
    supported_intents = ("jd_match",)

    def required_tools(self, context: dict[str, Any]) -> list[str]:
        return ["jd.parse", "evidence.extract", "fit.score"]

    async def run(
        self,
        context: dict[str, Any],
        tools: ToolRegistry,
        artifact: dict[str, Any],
    ) -> SkillResult:
        tool_results: list[dict[str, Any]] = []

        jd_result = await tools.run("jd.parse", {"jd_text": context["jd_text"]})
        _append_tool_result(tool_results, "jd.parse", jd_result)
        if not jd_result.ok:
            return _failed(tool_results, jd_result.error or "JD 解析失败")

        evidence_result = await tools.run(
            "evidence.extract",
            {
                "resume_text": context["resume_text"],
                "jd_text": context["jd_text"],
                "role": jd_result.data["role"],
            },
        )
        _append_tool_result(tool_results, "evidence.extract", evidence_result)
        if not evidence_result.ok:
            return _failed(tool_results, evidence_result.error or "证据抽取失败")

        fit_result = await tools.run("fit.score", evidence_result.data)
        _append_tool_result(tool_results, "fit.score", fit_result)
        if not fit_result.ok:
            return _failed(tool_results, fit_result.error or "匹配评分失败")

        return SkillResult(
            ok=True,
            artifact={
                "job": jd_result.data,
                "fit": fit_result.data,
                "evidence_map": evidence_result.data["evidence_map"],
            },
            tool_results=tool_results,
        )


class ApplicationAssistantSkill:
    name = "application_assistant"
    description = "基于已验证匹配结果生成招聘者开场白草稿。"
    supported_intents = ("application_message",)

    def required_tools(self, context: dict[str, Any]) -> list[str]:
        return ["message.compose"]

    async def run(
        self,
        context: dict[str, Any],
        tools: ToolRegistry,
        artifact: dict[str, Any],
    ) -> SkillResult:
        message_result = await tools.run(
            "message.compose",
            {
                "job_title": artifact["job"]["title"],
                "fit": artifact["fit"],
            },
        )
        tool_results: list[dict[str, Any]] = []
        _append_tool_result(tool_results, "message.compose", message_result)
        if not message_result.ok:
            return _failed(tool_results, message_result.error or "消息生成失败")
        return SkillResult(ok=True, artifact={"message": message_result.data}, tool_results=tool_results)


def default_skill_registry() -> SkillRegistry:
    registry = SkillRegistry()
    registry.register(JdMatchAnalystSkill())
    registry.register(ApplicationAssistantSkill())
    return registry


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


def _failed(tool_results: list[dict[str, Any]], error: str) -> SkillResult:
    return SkillResult(ok=False, artifact={}, tool_results=tool_results, error=error)


__all__ = [
    "AgentSkill",
    "ApplicationAssistantSkill",
    "JdMatchAnalystSkill",
    "SkillRegistry",
    "SkillResult",
    "default_skill_registry",
]
