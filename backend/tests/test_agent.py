from __future__ import annotations

import json

import pytest

from app.agent import SprintDuckAgent
from app.agent.harness.skills import default_skill_registry
from app.agent.harness.tools import default_registry
from app.models import SessionState


class StubLLMProvider:
    async def generate_json(self, system: str, user: str) -> dict[str, object]:
        payload = json.loads(user)
        if payload.get("draft_summary"):
            return {"summary": f"大模型生成：{payload['draft_summary']}"}
        return {
            "summary": "大模型基于简历和 JD 生成的测试总结。",
            "interview_questions": [
                {
                    "question": f"请说明第 {index} 个关键经历。",
                    "why_it_matters": "验证岗位关键要求。",
                    "linked_gap": "岗位匹配证据",
                }
                for index in range(1, 6)
            ],
        }


class EmptyLLMProvider:
    async def generate_json(self, system: str, user: str) -> dict[str, object]:
        return {}


async def collect(agent: SprintDuckAgent, session: SessionState, text: str):
    return [event async for event in agent.handle_user_message(session, text)]


def event_names(events):
    return [event.event for event in events]


async def test_agent_asks_for_missing_context_before_reporting():
    agent = SprintDuckAgent(StubLLMProvider())
    session = SessionState(session_id="s1")

    events = await collect(agent, session, "简历：我做过 React 和 Node.js 项目。")

    assert "assistant_delta" in event_names(events)
    assert session.status == "collecting_context"
    assert session.report is None
    assert session.followup_count == 1


async def test_agent_keeps_unlabeled_jd_when_resume_file_is_merged_after_message():
    agent = SprintDuckAgent(StubLLMProvider())
    session = SessionState(session_id="s1b")

    events = await collect(
        agent,
        session,
        (
            "岗位职责：负责用户增长活动策划、用户分层运营、社群活跃和转化提升，"
            "基于数据复盘优化活动效果。任职要求：熟悉 CRM、生命周期运营、跨团队协作，"
            "有活动策划、用户增长和数据分析经验。\n\n"
            "简历：我有 3 年用户运营经验，负责公众号、社群和活动复盘。曾策划 3 场线上活动，"
            "累计报名 1800 人，活动后社群留存约 42%。熟悉内容排期、社群答疑、基础数据复盘。"
        ),
    )

    state = next(event.data for event in events if event.event == "state")
    assistant_reply = "".join(str(event.data["text"]) for event in events if event.event == "assistant_delta")
    assert "目标岗位 JD" not in state["missing"]
    assert "目标岗位 JD" not in assistant_reply
    assert "关键日期" in state["missing"]
    assert session.jd_text.startswith("负责用户增长活动策划")


async def test_agent_generates_evidence_backed_report_for_engineering_case():
    agent = SprintDuckAgent(StubLLMProvider())
    session = SessionState(session_id="s2")

    await collect(
        agent,
        session,
        "简历：我是一名 4 年经验的全栈工程师，主要使用 TypeScript、React、Node.js 和 PostgreSQL。负责过 B2B SaaS 的权限系统和报表模块。最近项目中我把页面加载时间从 4.2s 优化到 1.8s，并推动组件库重构。",
    )
    await collect(
        agent,
        session,
        "JD：岗位：Senior Fullstack Engineer。要求：5年以上经验，熟悉 React、Node.js、PostgreSQL，能够设计可扩展后端服务。需要性能优化经验、跨团队沟通能力。加分项：Kubernetes、系统设计、带领小团队。",
    )
    events = await collect(agent, session, "约束：面试日期是 5 天后，每天可以投入 90 分钟，目前阶段是已经拿到一面邀请。")

    assert "report" in event_names(events)
    assert session.report is not None
    assert session.report.role == "engineering"
    assert 0 <= session.report.readiness_score <= 100
    assert len(session.report.top_gaps) >= 3
    assert len(session.report.sprint_plan) == 5
    assert len(session.report.interview_questions) >= 5
    assert "未发现证据" in session.report.markdown or "证据:" in session.report.markdown


async def test_agent_limits_plan_to_seven_days_for_longer_deadline():
    agent = SprintDuckAgent(StubLLMProvider())
    session = SessionState(session_id="s3")

    await collect(agent, session, "简历：我做过 3 年 B2B 产品经理，负责客户后台、权限配置和数据看板。熟悉用户访谈、PRD、需求优先级排序和跨部门推进。上线数据看板模块，使运营团队每周手动统计时间减少约 6 小时。")
    await collect(agent, session, "JD：岗位：Product Manager - Growth。要求：负责增长漏斗分析、A/B 测试、用户分层、商业化转化策略。需要能写 PRD，与设计、研发、运营协作，并用数据评估上线效果。")
    await collect(agent, session, "约束：目标投递日期是 9 天后，每天可以投入 60 分钟，目前阶段是准备定制简历和作品集。")

    assert session.report is not None
    assert session.report.role == "product"
    assert len(session.report.sprint_plan) == 7


async def test_agent_runs_minimal_harness_for_jd_match_and_message():
    agent = SprintDuckAgent(StubLLMProvider())
    session = SessionState(session_id="s4")

    events = await collect(
        agent,
        session,
        (
            "帮我判断这个岗位值不值得投，并写一段 Boss 开场白。\n\n"
            "简历：我是一名 4 年经验的全栈工程师，主要使用 TypeScript、React、Node.js 和 PostgreSQL。"
            "负责过 B2B SaaS 权限系统、报表模块和内部自动化平台。最近项目中我把页面加载时间从 4.2s 优化到 1.8s，"
            "并推动前端组件库重构。我有基础 Docker 使用经验，但没有主导过 Kubernetes 或大型系统设计评审。\n\n"
            "JD：岗位：Senior Fullstack Engineer。要求：5年以上经验，熟悉 React、Node.js、PostgreSQL，"
            "能够设计可扩展后端服务。需要性能优化经验、跨团队沟通能力、英文技术文档阅读能力。"
            "加分项：Kubernetes、系统设计、带领小团队。"
        ),
    )

    names = event_names(events)
    assert "report" not in names
    assert session.status == "report_ready"
    assert session.report is None

    state = next(event.data for event in events if event.event == "state")
    assistant_reply = "".join(str(event.data["text"]) for event in events if event.event == "assistant_delta")
    status_texts = [str(event.data["message"]) for event in events if event.event == "status"]
    assert state["intent"]["primary_intent"] == "jd_match"
    assert state["intent"]["secondary_intents"] == ["application_message"]
    assert [step["skill"] for step in state["plan"]] == [
        "jd_match_analyst",
        "jd_match_analyst",
        "jd_match_analyst",
        "application_assistant",
    ]
    assert [step["tool"] for step in state["plan"]] == ["jd.parse", "evidence.extract", "fit.score", "message.compose"]
    assert [result["tool"] for result in state["tool_results"]] == ["jd.parse", "evidence.extract", "fit.score", "message.compose"]
    assert state["artifact"]["fit"]["priority"] in {"建议投递", "谨慎投递", "低优先级"}
    assert any(text.startswith("意图分析：jd_match + application_message") for text in status_texts)
    assert any(text.startswith("Plan 生成：jd_match_analyst.jd.parse") for text in status_texts)
    assert any(text.startswith("计划执行：开始 jd_match_analyst") for text in status_texts)
    assert "意图分析" in assistant_reply
    assert "推理执行" in assistant_reply
    assert "开场白草稿" in assistant_reply
    assert "不会自动发送或投递" in assistant_reply
    first_assistant_index = names.index("assistant_delta")
    assert max(
        index
        for index, event in enumerate(events)
        if event.event == "status" and str(event.data["message"]).startswith(("意图分析：", "Plan 生成：", "计划执行："))
    ) < first_assistant_index


async def test_agent_harness_asks_for_missing_required_context():
    agent = SprintDuckAgent(StubLLMProvider())
    session = SessionState(session_id="s5")

    events = await collect(
        agent,
        session,
        (
            "帮我判断这个岗位要不要投。"
            "JD：岗位：增长产品经理。要求：负责增长漏斗分析、A/B 测试、用户分层和商业化转化策略。"
            "需要能写清楚 PRD，与设计、研发、运营协作，并用数据评估上线效果。"
        ),
    )

    state = next(event.data for event in events if event.event == "state")
    assistant_reply = "".join(str(event.data["text"]) for event in events if event.event == "assistant_delta")
    assert state["intent"]["primary_intent"] == "jd_match"
    assert state["intent"]["missing_context"] == ["resume"]
    assert "简历材料" in assistant_reply
    assert session.report is None


async def test_agent_requires_valid_llm_response_for_report_generation():
    agent = SprintDuckAgent(EmptyLLMProvider())
    session = SessionState(session_id="s6")

    await collect(agent, session, "简历：我有 3 年前端工程经验，负责 React、TypeScript、性能优化、组件库和跨团队协作。曾把核心页面首屏从 4 秒优化到 1.5 秒，并接入过 FastAPI SSE 大模型应用。")
    await collect(agent, session, "JD：岗位：AI 产品方向前端工程师。要求：负责 Agent Web 工作台、对话、报告、任务流和配置界面；熟悉 React、TypeScript、工程化、性能优化，并能接入大模型和工具调用。")

    with pytest.raises(RuntimeError, match="大模型响应缺少 summary"):
        await collect(agent, session, "约束：面试日期是 5 天后，每天可以投入 90 分钟，目前阶段是已经拿到一面邀请。")


def test_harness_keeps_tools_and_skills_separate():
    tools = {spec.name for spec in default_registry().list_specs()}
    skills = default_skill_registry()

    assert {"jd.parse", "evidence.extract", "fit.score", "message.compose"}.issubset(tools)
    assert "jd_match_analyst" not in tools
    assert "application_assistant" not in tools
    assert skills.get("jd_match_analyst") is not None
    assert skills.get("application_assistant") is not None
    assert skills.get("jd_match_analyst").required_tools({}) == ["jd.parse", "evidence.extract", "fit.score"]
    assert skills.get("application_assistant").required_tools({}) == ["message.compose"]
