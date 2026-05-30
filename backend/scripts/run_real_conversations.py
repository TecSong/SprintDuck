from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.main import app


def parse_sse(raw: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for part in raw.split("\n\n"):
        lines = [line for line in part.splitlines() if line.strip()]
        if not lines:
            continue
        event = next((line.replace("event:", "").strip() for line in lines if line.startswith("event:")), "")
        data_line = next((line.replace("data:", "").strip() for line in lines if line.startswith("data:")), "{}")
        events.append({"event": event, "data": json.loads(data_line)})
    return events


async def run_case(client: httpx.AsyncClient, case: dict[str, Any]) -> dict[str, Any]:
    created = await client.post("/api/chat/sessions")
    created.raise_for_status()
    session_id = created.json()["session_id"]
    final_report: dict[str, Any] | None = None

    for message in case["messages"]:
        response = await client.post(f"/api/chat/sessions/{session_id}/messages", data={"message": message})
        response.raise_for_status()
        for event in parse_sse(response.text):
            if event["event"] == "report":
                final_report = event["data"]

    if not final_report:
        raise AssertionError(f"{case['name']} did not produce a report")
    assert final_report["role"] == case["expected_role"], final_report["role"]
    assert 0 <= final_report["readiness_score"] <= 100
    assert final_report["readiness_band"] in {"high", "medium", "low"}
    assert 0 <= final_report["evidence_coverage"] <= 1
    assert len(final_report["top_gaps"]) >= 3
    assert len(final_report["sprint_plan"]) >= 1
    assert len(final_report["sprint_plan"]) <= 7
    assert len(final_report["interview_questions"]) >= 5
    assert "## Top Gaps" in final_report["markdown"]
    return final_report


async def main() -> None:
    load_dotenv(ROOT / ".env")
    cases = json.loads((ROOT / "samples" / "real_conversations.json").read_text())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        for case in cases:
            report = await run_case(client, case)
            print(f"{case['name']}: {report['role']} {report['readiness_score']} {len(report['sprint_plan'])}d")


if __name__ == "__main__":
    asyncio.run(main())
