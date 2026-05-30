from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


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
