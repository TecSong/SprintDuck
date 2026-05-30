# SprintDuckAgent

SprintDuckAgent is an open-source, local-first interview sprint coach for candidates. It uses an agent conversation to collect resume/JD context, then produces an evidence-backed readiness report, adaptive 1-7 day sprint plan, and likely interview follow-up questions.

The first demo is Chinese-first and intentionally avoids accounts, databases, lead capture, payment, and persistent storage.

## Quick Start

```bash
make install
make dev
```

Backend: `http://127.0.0.1:8000`

Frontend: `http://127.0.0.1:5173`

## Environment

Copy `.env.example` to `.env` and set one of:

- `DEEPSEEK_API_KEY`
- `deepseek_api_key`

The default model is `deepseek-v4-flash`.

## Tests

```bash
make test
make test-real
```

`make test-real` uses DeepSeek and synthetic public test cases from `docs/test-cases.md`.

## Docs

- `docs/plan.md`
- `docs/prd.md`
- `docs/architecture.md`
- `docs/prototype-ui.md`
- `docs/harness-design.md`
- `docs/test-cases.md`

