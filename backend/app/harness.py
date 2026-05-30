from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .models import RolePreset
from .role_presets import rubric_for


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    data: Any = None
    error: str | None = None


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


def default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(RoleRubricTool())
    registry.register(EvidenceNormalizeTool())
    return registry

