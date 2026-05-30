from __future__ import annotations

from .models import SprintReport


def render_report_markdown(report: SprintReport) -> str:
    lines: list[str] = [
        "# SprintDuckAgent 求职冲刺报告",
        "",
        f"- 岗位模板: `{report.role}`",
        f"- 准备度: **{report.readiness_score}/100** ({report.readiness_band})",
        f"- 证据覆盖率: **{report.evidence_coverage:.0%}**",
        f"- 置信度: **{report.confidence}**",
        "",
        "## 总结",
        "",
        report.summary,
        "",
        "## Top Gaps",
    ]

    for index, gap in enumerate(report.top_gaps, start=1):
        evidence = "；".join(item.text for item in gap.evidence) or "未发现证据"
        lines.extend(
            [
                "",
                f"### {index}. {gap.title}",
                "",
                f"- 严重程度: {gap.severity}",
                f"- 证据: {evidence}",
                f"- 原因: {gap.gap_reason}",
                f"- 建议: {gap.suggested_action}",
            ]
        )

    lines.extend(["", "## 冲刺计划"])
    for day in report.sprint_plan:
        lines.extend(
            [
                "",
                f"### Day {day.day}: {day.focus}",
                "",
                f"- 预计投入: {day.minutes} 分钟",
                f"- 关联 Gap: {day.linked_gap}",
                "- 任务:",
                *[f"  - {task}" for task in day.tasks],
                f"- 完成标准: {day.done_criteria}",
            ]
        )

    lines.extend(["", "## 高频追问"])
    for index, question in enumerate(report.interview_questions, start=1):
        lines.extend(
            [
                "",
                f"{index}. {question.question}",
                f"   - 为什么会问: {question.why_it_matters}",
                f"   - 关联 Gap: {question.linked_gap}",
            ]
        )

    return "\n".join(lines).strip() + "\n"

