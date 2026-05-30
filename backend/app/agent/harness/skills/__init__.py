from __future__ import annotations

from .job_search import AgentSkill, ApplicationAssistantSkill, JdMatchAnalystSkill, SkillResult


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, AgentSkill] = {}

    def register(self, skill: AgentSkill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> AgentSkill | None:
        return self._skills.get(name)


def default_skill_registry() -> SkillRegistry:
    registry = SkillRegistry()
    registry.register(JdMatchAnalystSkill())
    registry.register(ApplicationAssistantSkill())
    return registry


__all__ = [
    "AgentSkill",
    "ApplicationAssistantSkill",
    "JdMatchAnalystSkill",
    "SkillRegistry",
    "SkillResult",
    "default_skill_registry",
]
