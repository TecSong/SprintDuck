# SprintDuckAgent Architecture

## System Overview

```text
React Workbench
  | create session / send message or text files
  v
FastAPI SSE API
  | session orchestration
  v
Agent State Machine
  |- intake completeness
  |- role inference
  |- evidence extraction
  |- readiness report
  |- Markdown export
  v
Provider + Harness Ports
  |- DeepSeek provider
  |- Fake provider for tests
  |- Tool/skill registry stubs
```

## Backend Modules

- `app.main`: FastAPI app, CORS, health endpoint, session/chat routes.
- `app.models`: public Pydantic contracts for sessions, messages, report, plan, evidence, and SSE events.
- `app.session_store`: in-memory session store.
- `app.agent`: lightweight state machine and report orchestration.
- `app.role_presets`: engineering/product/operations inference and criteria.
- `app.providers`: LLM provider interface, fake provider, DeepSeek provider.
- `app.markdown`: deterministic Markdown report rendering.
- `app.harness`: future-facing tool and skill interfaces, registry, and no-op adapters.

## Frontend Modules

- `src/App.tsx`: two-column workbench shell.
- `src/api.ts`: session creation, SSE message sending, file text extraction.
- `src/types.ts`: frontend copies of the backend response contracts.
- `src/components`: chat panel, report panel, evidence list, plan view, export button.

## Agent State Machine

```text
collecting_context
  -> needs_role_confirmation
  -> ready_to_report
  -> report_ready
```

The state machine is intentionally small. It tracks:

- resume text
- JD text
- deadline or key date
- daily available minutes
- current stage
- inferred or confirmed role
- follow-up count
- generated report

If required context is missing, the agent asks a focused follow-up. If role inference is low-confidence, it asks for role confirmation once. After two missing-information rounds, it may generate a low-confidence report with explicit missing evidence.

## Report Contract

The final report includes:

- `role`: inferred role preset
- `readiness_score`: 0-100
- `readiness_band`: high, medium, low
- `evidence_coverage`: 0-1
- `summary`: concise candidate-facing explanation
- `top_gaps`: evidence-backed gap items
- `sprint_plan`: 1-7 day plan items
- `interview_questions`: likely follow-up questions
- `markdown`: rendered user export

## API Contract

- `GET /api/health`
- `GET /api/llm/config`
- `PUT /api/llm/config`
- `POST /api/chat/sessions`
- `POST /api/chat/sessions/{session_id}/messages`

Chat messages use `multipart/form-data` so the frontend can send text plus text files. The response is `text/event-stream`.

SSE event names:

- `status`
- `assistant_delta`
- `state`
- `report`
- `error`
- `done`

## Environment

Supported variables:

- `LLM_PROVIDER`, default `wanjie_ark`
- DeepSeek: `DEEPSEEK_API_KEY` or `deepseek_api_key`, `DEEPSEEK_MODEL`, `DEEPSEEK_BASE_URL`
- 万界方舟: `WANJIE_ARK_API_KEY` or `wjark_api_key` or `WJARK_API_KEY`, `WANJIE_ARK_MODEL`, `WANJIE_ARK_BASE_URL`

The web app's model configuration panel writes these provider values to the local `.env` file. API keys are only returned to the browser as masked status strings.

## Privacy

Phase 1 keeps user job-search data in server memory only. It does not write resume/JD/report content to disk unless the user exports Markdown from the browser.
