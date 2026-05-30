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


async def run_harness_case(client: httpx.AsyncClient, case: dict[str, Any]) -> dict[str, Any]:
    created = await client.post("/api/chat/sessions")
    created.raise_for_status()
    session_id = created.json()["session_id"]
    final_state: dict[str, Any] | None = None
    assistant_text = ""

    for message in case["messages"]:
        response = await client.post(f"/api/chat/sessions/{session_id}/messages", data={"message": message})
        response.raise_for_status()
        for event in parse_sse(response.text):
            if event["event"] == "assistant_delta":
                assistant_text += str(event["data"].get("text") or "")
            if event["event"] == "state" and "intent" in event["data"]:
                final_state = event["data"]

    if not final_state:
        raise AssertionError(f"{case['name']} did not produce a harness state")

    intent = final_state["intent"]
    assert intent["primary_intent"] == case["expected_primary_intent"]
    assert intent["secondary_intents"] == case["expected_secondary_intents"]
    assert [step["tool"] for step in final_state["plan"]] == case["expected_tools"]
    assert [result["tool"] for result in final_state["tool_results"]] == case["expected_tools"]
    assert final_state["artifact"]["fit"]["priority"] in {"建议投递", "谨慎投递", "低优先级"}
    assert 0 <= final_state["artifact"]["fit"]["score"] <= 100
    assert "意图分析" in assistant_text
    assert "推理执行" in assistant_text
    assert "不会自动发送或投递" in assistant_text
    return final_state


async def main() -> None:
    load_dotenv(ROOT / ".env")
    cases = json.loads((ROOT / "samples" / "real_conversations.json").read_text())
    harness_cases = json.loads((ROOT / "samples" / "harness_real_cases.json").read_text())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        for case in cases:
            report = await run_case(client, case)
            print(f"{case['name']}: {report['role']} {report['readiness_score']} {len(report['sprint_plan'])}d")
        for case in harness_cases:
            state = await run_harness_case(client, case)
            print(
                f"{case['name']}: "
                f"{state['intent']['primary_intent']} {state['artifact']['fit']['score']}"
            )


if __name__ == "__main__":
    asyncio.run(main())
