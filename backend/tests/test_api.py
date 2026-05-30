from __future__ import annotations

import json
from pathlib import Path

import httpx

from app.main import app

ROOT = Path(__file__).resolve().parents[2]


def parse_sse(raw: str):
    events = []
    for part in raw.split("\n\n"):
        lines = [line for line in part.splitlines() if line.strip()]
        if not lines:
            continue
        event = next((line.replace("event:", "").strip() for line in lines if line.startswith("event:")), "")
        data = next((line.replace("data:", "").strip() for line in lines if line.startswith("data:")), "{}")
        events.append((event, json.loads(data)))
    return events


async def test_chat_api_streams_state_and_report():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        created = await client.post("/api/chat/sessions")
        assert created.status_code == 200
        session_id = created.json()["session_id"]

        messages = [
            "简历：我有 2 年内容运营经验，负责公众号、社群和活动复盘。曾策划 3 场线上活动，累计报名 1800 人，活动后社群留存约 42%。熟悉内容排期、社群答疑、基础数据复盘。",
            "JD：岗位：用户运营。要求：负责用户分层、社群活跃、活动策划、数据复盘和转化提升。需要能独立设计运营节奏，和产品、销售协同推进转化。加分项：CRM 自动化、付费投放、生命周期运营。",
            "约束：面试日期是明天，每天可以投入 120 分钟，目前阶段是面试前最后准备。",
        ]

        final_events = []
        for message in messages:
            response = await client.post(f"/api/chat/sessions/{session_id}/messages", data={"message": message})
            assert response.status_code == 200
            final_events = parse_sse(response.text)

        names = [event for event, _data in final_events]
        assert "report" in names
        report = next(data for event, data in final_events if event == "report")
        assert report["role"] == "operations"
        assert len(report["sprint_plan"]) == 1
        assert "## 高频追问" in report["markdown"]


async def test_chat_api_keeps_message_jd_when_resume_file_uploaded():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        created = await client.post("/api/chat/sessions")
        assert created.status_code == 200
        session_id = created.json()["session_id"]

        jd = (
            "岗位职责：负责用户增长活动策划、用户分层运营、社群活跃和转化提升，"
            "基于数据复盘优化活动效果。任职要求：熟悉 CRM、生命周期运营、跨团队协作，"
            "有活动策划、用户增长和数据分析经验。"
        )
        resume = (
            "简历：我有 3 年用户运营经验，负责公众号、社群和活动复盘。曾策划 3 场线上活动，"
            "累计报名 1800 人，活动后社群留存约 42%。熟悉内容排期、社群答疑、基础数据复盘。"
        )

        response = await client.post(
            f"/api/chat/sessions/{session_id}/messages",
            data={"message": jd},
            files=[("files", ("resume.md", resume, "text/markdown"))],
        )
        assert response.status_code == 200

        events = parse_sse(response.text)
        state = next(data for event, data in events if event == "state")
        assistant_reply = "".join(str(data["text"]) for event, data in events if event == "assistant_delta")
        assert "目标岗位 JD" not in state["missing"]
        assert "目标岗位 JD" not in assistant_reply
        assert "关键日期" in state["missing"]


async def test_chat_api_accepts_md_and_txt_file_uploads_without_message():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        created = await client.post("/api/chat/sessions")
        assert created.status_code == 200
        session_id = created.json()["session_id"]

        resume = (ROOT / "samples" / "test_resume.md").read_text()
        jd = (ROOT / "samples" / "test_jd.md").read_text()
        constraints = (ROOT / "samples" / "test_constraints.txt").read_text()

        response = await client.post(
            f"/api/chat/sessions/{session_id}/messages",
            data={"message": ""},
            files=[
                ("files", ("test_resume.md", resume, "text/markdown")),
                ("files", ("test_jd.md", jd, "text/markdown")),
                ("files", ("test_constraints.txt", constraints, "text/plain")),
            ],
        )
        assert response.status_code == 200

        events = parse_sse(response.text)
        report = next(data for event, data in events if event == "report")
        assert report["role"] == "engineering"
        assert len(report["sprint_plan"]) == 5
        assert "## Top Gaps" in report["markdown"]


async def test_chat_api_txt_upload_contributes_constraints():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        created = await client.post("/api/chat/sessions")
        assert created.status_code == 200
        session_id = created.json()["session_id"]
        constraints = (ROOT / "samples" / "test_constraints.txt").read_text()

        response = await client.post(
            f"/api/chat/sessions/{session_id}/messages",
            data={"message": ""},
            files=[("files", ("test_constraints.txt", constraints, "text/plain"))],
        )
        assert response.status_code == 200

        events = parse_sse(response.text)
        state = next(data for event, data in events if event == "state")
        assert "简历材料" in state["missing"]
        assert "目标岗位 JD" in state["missing"]
        assert "关键日期" not in state["missing"]
        assert "每天可投入时间" not in state["missing"]
        assert "当前求职阶段" not in state["missing"]


async def test_chat_api_resume_upload_does_not_satisfy_constraints():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        created = await client.post("/api/chat/sessions")
        assert created.status_code == 200
        session_id = created.json()["session_id"]
        resume = (ROOT / "samples" / "test_resume.md").read_text()

        response = await client.post(
            f"/api/chat/sessions/{session_id}/messages",
            data={"message": ""},
            files=[("files", ("test_resume.md", resume, "text/markdown"))],
        )
        assert response.status_code == 200

        events = parse_sse(response.text)
        state = next(data for event, data in events if event == "state")
        assert "简历材料" not in state["missing"]
        assert "目标岗位 JD" in state["missing"]
        assert "关键日期" in state["missing"]
        assert "每天可投入时间" in state["missing"]
        assert "当前求职阶段" in state["missing"]


async def test_chat_api_resume_file_with_jd_message_still_requires_constraints():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        created = await client.post("/api/chat/sessions")
        assert created.status_code == 200
        session_id = created.json()["session_id"]
        resume = (ROOT / "samples" / "test_resume.md").read_text()
        jd = (ROOT / "samples" / "test_jd.md").read_text()

        response = await client.post(
            f"/api/chat/sessions/{session_id}/messages",
            data={"message": jd},
            files=[("files", ("test_resume.md", resume, "text/markdown"))],
        )
        assert response.status_code == 200

        events = parse_sse(response.text)
        state = next(data for event, data in events if event == "state")
        assistant_reply = "".join(str(data["text"]) for event, data in events if event == "assistant_delta")
        assert "简历材料" not in state["missing"]
        assert "目标岗位 JD" not in state["missing"]
        assert "关键日期" in state["missing"]
        assert "每天可投入时间" in state["missing"]
        assert "当前求职阶段" in state["missing"]
        assert "当前求职阶段" in assistant_reply


async def test_chat_api_resume_file_with_jd_and_constraints_message_generates_report():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        created = await client.post("/api/chat/sessions")
        assert created.status_code == 200
        session_id = created.json()["session_id"]
        resume = (ROOT / "samples" / "test_resume.md").read_text()
        jd = (ROOT / "samples" / "test_jd.md").read_text()
        constraints = (ROOT / "samples" / "test_constraints.txt").read_text()

        response = await client.post(
            f"/api/chat/sessions/{session_id}/messages",
            data={"message": f"{jd}\n\n{constraints}"},
            files=[("files", ("test_resume.md", resume, "text/markdown"))],
        )
        assert response.status_code == 200

        events = parse_sse(response.text)
        report = next(data for event, data in events if event == "report")
        assert report["role"] == "engineering"
        assert len(report["sprint_plan"]) == 5
        assert "## 高频追问" in report["markdown"]


async def test_chat_api_jd_file_with_resume_and_constraints_message_generates_report():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        created = await client.post("/api/chat/sessions")
        assert created.status_code == 200
        session_id = created.json()["session_id"]
        resume = (ROOT / "samples" / "test_resume.md").read_text()
        jd = (ROOT / "samples" / "test_jd.md").read_text()
        constraints = (ROOT / "samples" / "test_constraints.txt").read_text()

        response = await client.post(
            f"/api/chat/sessions/{session_id}/messages",
            data={"message": f"{resume}\n\n{constraints}"},
            files=[("files", ("test_jd.md", jd, "text/markdown"))],
        )
        assert response.status_code == 200

        events = parse_sse(response.text)
        report = next(data for event, data in events if event == "report")
        assert report["role"] == "engineering"
        assert len(report["sprint_plan"]) == 5
        assert "## 高频追问" in report["markdown"]


async def test_chat_api_complete_unlabeled_markdown_message_generates_report():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        created = await client.post("/api/chat/sessions")
        assert created.status_code == 200
        session_id = created.json()["session_id"]
        resume = (ROOT / "samples" / "test_resume.md").read_text()
        jd = (ROOT / "samples" / "test_jd.md").read_text()
        constraints = (ROOT / "samples" / "test_constraints.txt").read_text()

        response = await client.post(
            f"/api/chat/sessions/{session_id}/messages",
            data={"message": f"{resume}\n\n{jd}\n\n{constraints}"},
        )
        assert response.status_code == 200

        events = parse_sse(response.text)
        report = next(data for event, data in events if event == "report")
        assert report["role"] == "engineering"
        assert len(report["sprint_plan"]) == 5
        assert "## 高频追问" in report["markdown"]
