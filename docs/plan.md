# SprintDuckAgent Implementation Plan

## Summary

SprintDuckAgent is an open-source, locally runnable job-search agent for candidates. The first demo is a Chinese-first professional workbench where a user chats with an agent, provides resume/JD text or `.txt`/`.md` files, answers timing constraints, and receives an evidence-backed readiness report, adaptive 1-7 day sprint plan, and likely interview follow-up questions.

The project is rebuilt from scratch in `/Users/yikosong/myprojects/SprintDuckAgent`. Existing SprintDuck architecture and UI are intentionally not reused.

## Phase 1 Scope

- FastAPI backend with SSE chat API.
- React/Vite frontend with chat and report side-by-side workbench.
- DeepSeek provider using `deepseek-v4-flash` by default.
- In-memory sessions only; no account system or database.
- Markdown report export.
- Agent harness architecture for future tools/skills, with stubbed built-in tools.
- Synthetic real-conversation test cases for engineering, product, and operations roles.

## Out of Scope

- Commercial funnel, pricing, waitlist, earlybird, payment, and lead capture.
- Persistent storage, login, history, reminders, task tracking, or deployment.
- PDF parsing, image OCR, and broad file ingestion.
- Full mock interview, resume rewriting, or long-term coaching memory.

## Implementation Order

1. Write docs under `/docs`: PRD, architecture, prototype, harness design, and test cases.
2. Initialize project metadata, git repo, MIT license, `.gitignore`, root scripts, backend and frontend package files.
3. Implement backend domain contracts and fake-provider tests first.
4. Implement lightweight agent state machine, role inference, report generation, Markdown rendering, and SSE API.
5. Add DeepSeek provider and real conversation harness.
6. Build React workbench from the prototype spec.
7. Run unit/integration tests, run real DeepSeek sample if credentials work, then start backend and frontend locally.

## Acceptance Criteria

- `make test` passes backend tests.
- `make test-real` can run three synthetic real conversation cases when `DEEPSEEK_API_KEY` or `deepseek_api_key` is present.
- `make dev` starts backend and frontend.
- Web UI can complete a chat flow, render report panels, and download Markdown.
- The generated report includes readiness score/band, evidence coverage, top gaps, adaptive sprint plan, likely interview questions, and visible evidence references.
