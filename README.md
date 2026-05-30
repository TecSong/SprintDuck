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

Copy `.env.example` to `.env`, or use the model configuration panel in the web app. The panel writes API keys to the local `.env` file and does not send them to the browser after saving.

Select the active provider with `LLM_PROVIDER`; the default is `wanjie_ark`.

- `deepseek`: `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`, `DEEPSEEK_BASE_URL`
- `wanjie_ark`: `WANJIE_ARK_API_KEY`, `WANJIE_ARK_MODEL`, `WANJIE_ARK_BASE_URL`

`deepseek_api_key` remains supported as a legacy alias for DeepSeek. `wjark_api_key` and `WJARK_API_KEY` are supported as aliases for 万界方舟. The 万界方舟 base URL defaults to `https://maas-openapi.wanjiedata.com/api`.

## Tests

```bash
make test
make test-real
```

`make test-real` uses the active configured provider and synthetic public test cases from `docs/test-cases.md`.

## Docs

- `docs/plan.md`
- `docs/prd.md`
- `docs/architecture.md`
- `docs/prototype-ui.md`
- `docs/harness-design.md`
- `docs/test-cases.md`
