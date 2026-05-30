.PHONY: install test test-real dev backend frontend

install:
	uv sync
	pnpm --dir frontend install

test:
	uv run pytest backend/tests

test-real:
	uv run python backend/scripts/run_real_conversations.py

backend:
	uv run uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload

frontend:
	pnpm --dir frontend dev --host 127.0.0.1 --port 5173

dev:
	uv run python backend/scripts/dev.py

