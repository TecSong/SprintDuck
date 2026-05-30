# SprintDuckAgent PRD

## Problem Statement

求职者准备面试时常常不知道自己和目标岗位的真实差距在哪里，也很难把有限时间转成清晰、可执行的冲刺计划。通用聊天机器人可以给建议，但经常泛泛而谈，缺少对简历和 JD 的证据引用，用户无法判断哪些建议可信、哪些只是模型猜测。

用户需要一个开源、可本地运行、默认不长期保存隐私材料的求职冲刺 Agent：它能通过对话收集材料，用证据解释差距，并把差距转成接下来几天最该做的任务。

## Solution

SprintDuckAgent 提供一个中文优先的本地 Web 工作台。用户和 Agent 对话，上传或粘贴文本类简历/JD，补充关键日期、每日可投入时间、当前求职阶段。Agent 从 JD 推断岗位模板，在必要时追问确认，然后输出：

- 准备度分数、准备度区间、证据覆盖率
- 证据化 Top Gaps
- 1-7 天自适应冲刺计划
- 高频面试追问
- 可下载 Markdown 报告

第一版不做商业化与持久化，只保证核心求职诊断闭环可信、可演示、可扩展。

## User Stories

1. As a candidate, I want to paste my resume and JD into a chat, so that I can get started without learning a complex tool.
2. As a candidate, I want to upload `.txt` or `.md` resume/JD files, so that I do not need to manually reformat text.
3. As a candidate, I want the agent to ask for missing timing constraints, so that the sprint plan fits my real deadline.
4. As a candidate, I want the agent to infer whether the role is engineering, product, or operations, so that the diagnosis uses relevant criteria.
5. As a candidate, I want the agent to ask for confirmation when the role is ambiguous, so that the report is not built on the wrong template.
6. As a candidate, I want every major gap to cite resume/JD evidence, so that I can trust the diagnosis.
7. As a candidate, I want missing evidence to be labeled as missing evidence, so that the system does not accuse me of lacking a skill I may simply not have written down.
8. As a candidate, I want a readiness score and band, so that I can quickly understand my current preparation level.
9. As a candidate, I want the score to be explained as material readiness, not offer probability, so that I do not overinterpret it.
10. As a candidate, I want a 1-7 day plan based on my deadline, so that I can act immediately.
11. As a candidate, I want each plan item to connect back to a gap, so that I know why I am doing it.
12. As a candidate, I want likely interview follow-up questions, so that I can rehearse the areas most likely to be challenged.
13. As a candidate, I want to download the final report as Markdown, so that I can keep or edit it locally.
14. As an open-source user, I want the app to run locally, so that my job-search documents do not need to be stored by a hosted service.
15. As a developer, I want provider interfaces around LLM calls, so that DeepSeek can be replaced later.
16. As a developer, I want a harness interface for future tools and skills, so that the agent can later call interview question banks, resume parsers, or company research tools.
17. As a maintainer, I want fake-provider tests around the public agent behavior, so that the core contract is stable without paying for every test run.
18. As a maintainer, I want real model conversation cases, so that the demo is validated against actual LLM behavior.

## Implementation Decisions

- The app is a new FastAPI + React/Vite project, independent of previous SprintDuck code.
- The backend owns session state, role inference, report generation, Markdown rendering, provider calls, and harness interfaces.
- The frontend owns chat composition, SSE rendering, report visualization, file text upload, and Markdown download.
- Sessions are memory-only in Phase 1. Refreshing or restarting the server loses session state.
- Accepted files are text-like only: `.txt`, `.md`, `.markdown`.
- The default role presets are engineering, product, and operations. A generic role exists only as fallback after ambiguity.
- The agent may ask at most two missing-information follow-up rounds before producing a low-confidence report.
- The report must always distinguish evidence found from evidence not found.
- The API uses SSE for chat responses because the product is an agent, but final reports are still structured objects.
- DeepSeek `deepseek-v4-flash` is the default model. Provider and model are configurable via environment variables.
- Harness design is included now, but Phase 1 tools/skills are architecture stubs, not full external integrations.

## Testing Decisions

- Tests verify behavior through public service/API interfaces rather than prompt implementation details.
- Fake provider tests cover the agent state machine, role inference, missing-info follow-ups, report contract, Markdown rendering, and SSE event shape.
- Real provider tests are opt-in and use synthetic public samples for engineering, product, and operations.
- Real tests pass when the final report has required structure, evidence references or explicit missing-evidence labels, a valid adaptive plan, and role-relevant interview questions.
- Web smoke verification checks that backend and frontend can start locally and the main workbench loads.

## Out of Scope

- Payment, pricing, waitlist, earlybird, lead capture, or conversion analytics.
- Account system, persistent database, historical reports, reminder jobs, or daily task completion.
- PDF/image parsing, OCR, or cloud storage.
- Full mock interview, voice, video, or resume rewriting.
- Hosted deployment and CI/CD.

## Further Notes

Open-source positioning should be visible in README and product copy: local-first, privacy-aware, evidence-backed, and hackable. The UI should feel like a professional workbench, not a marketing landing page.
