# Agent Harness Design

## Purpose

SprintDuckAgent should behave like an agent, not only a prompt wrapper. Phase 1 includes the architecture hooks for future tools and skills while keeping implementations small and local.

## Concepts

- Tool: deterministic capability callable by the agent, such as parsing text, loading a role rubric, or rendering Markdown.
- Skill: higher-level behavior package that can combine tools, prompts, and policy, such as "generate behavioral interview questions".
- Harness: registry and execution boundary that lets the agent discover and call tools/skills through stable interfaces.

## Phase 1 Interfaces

```text
ToolSpec
  name
  description
  input_schema

ToolResult
  ok
  data
  error

AgentTool
  spec() -> ToolSpec
  run(input) -> ToolResult

AgentSkill
  name
  description
  required_tools
  run(context, registry) -> ToolResult
```

## Built-in Phase 1 Tools

- `role_rubric.load`: returns criteria for engineering, product, operations, or generic.
- `markdown_report.render`: renders the final report into Markdown.
- `evidence.normalize`: normalizes evidence snippets and missing-evidence labels.

These tools are local and deterministic. They exist to shape the architecture for later extension, not because the first demo needs external tool execution.

## Future Skills

- `resume_evidence_extractor`: improve evidence extraction from complex resumes.
- `company_research`: gather public company/JD context.
- `interview_question_bank`: combine community templates with generated questions.
- `mock_interview`: run a structured interview loop.
- `daily_sprint_adjuster`: update plans based on completed tasks.

## Guardrails

- Tools must not persist resume/JD content by default.
- Tool outputs must be included in report evidence or omitted; hidden claims are not allowed.
- Skills can suggest low-confidence conclusions only when the report says evidence is missing.
- The harness must be testable with fake tools and without network calls.
