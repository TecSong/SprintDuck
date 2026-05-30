from __future__ import annotations

from typing import Any

from ....models import RolePreset
from ....role_presets import rubric_for
from ..registry import ToolResult, ToolSpec


class RoleRubricTool:
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="role_rubric.load",
            description="Load local evaluation criteria for a role preset.",
            input_schema={"type": "object", "properties": {"role": {"type": "string"}}},
            data_access=("role",),
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
