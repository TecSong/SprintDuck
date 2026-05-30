from __future__ import annotations

from ..registry import ToolRegistry
from .job_search import EvidenceExtractTool, FitScoreTool, JdParseTool, MessageComposeTool
from .local import EvidenceNormalizeTool, RoleRubricTool


def default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(RoleRubricTool())
    registry.register(EvidenceNormalizeTool())
    registry.register(JdParseTool())
    registry.register(EvidenceExtractTool())
    registry.register(FitScoreTool())
    registry.register(MessageComposeTool())
    return registry


__all__ = ["default_registry"]
