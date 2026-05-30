# Minimal Agent Refactor Plan

## 目标

把当前手写 agent harness 重构成一个最小化、可交付的求职 agent。第一阶段采用 Pydantic AI 替换自研 LLM/tool glue，但保留显式业务路由、确定性本地工具和 consent gate。LangGraph 暂不进入黑客松前置路径，等需要可恢复长流程、跨轮审批和 connector 图编排时再引入。

本方案的成功标准：

- 保留当前 FastAPI SSE 和 React workbench API 形态。
- 保留现有面试冲刺报告能力，并把它纳入 `interview_sprint_coach` skill。
- 最小 agent 可以完成本地闭环：隐私模式、简历/JD 导入、JD 匹配、简历优化建议、面试冲刺计划、投递话术、pipeline 下一步。
- 纯本地模式不能因为未配置模型而失败。
- 外部模型、web、MCP 或 connector 动作必须先经过 payload preview、脱敏和 consent。
- 平台发送、投递、删除、更新线上资料等高影响动作不属于最小 agent。

## 当前实现盘点

当前代码已经实现了一个手写 mini harness：

- `backend/app/agent/core.py`
  - 负责会话入口、文本 intake、上下文完整度判断、SSE 事件输出。
  - 仍内置传统面试冲刺报告生成逻辑。
  - 现在只要生成真实回答就会调用配置的大模型，不满足纯本地模式。
- `backend/app/agent/harness/runtime.py`
  - 手写 `IntentAnalysis`、`PlanStep`、`HarnessRun`。
  - 规则识别 `jd_match` 和 `application_message`。
  - 顺序调用 skill，并拼装本地 artifact。
- `backend/app/agent/harness/registry.py`
  - 手写 `ToolSpec`、`ToolResult`、`ToolRegistry`。
  - 已包含 risk/data/evidence 字段雏形，但还没有真正的 consent enforcement。
- `backend/app/agent/harness/tools/`
  - 已有 `jd.parse`、`evidence.extract`、`fit.score`、`message.compose`。
  - 已有 `role_rubric.load`、`evidence.normalize`，但没有被核心流程充分使用。
- `backend/app/agent/harness/skills/`
  - 已有 `jd_match_analyst` 和 `application_assistant`。
- `backend/tests/test_agent.py`
  - 已覆盖当前 harness 的 intent、plan、tool order、missing context。
  - 还缺 privacy gate、pure local、scenario fixture、forbidden action 测试。

结论：不应继续把 `runtime.py` 扩成完整自研框架。应保留其中的业务规则和本地 tool 实现，把模型交互、结构化输出、工具 schema、流式事件和 approval 机制迁到 Pydantic AI。

## 框架取舍

### Pydantic AI 作为第一阶段 runtime

适合当前项目，因为：

- 当前后端已经使用 Pydantic/FastAPI，模型输出可以直接用 `BaseModel` contract。
- 支持 typed `Agent` output、function tools、deps、streaming event、deferred tool approval、MCP toolsets。
- 可以把本地确定性工具作为普通 Python 函数保留，不要求把业务流程交给模型自由规划。
- 可用 OpenAI-compatible provider 包装 DeepSeek、万界方舟等现有 provider。

### LangGraph 作为第二阶段 orchestration

暂不作为黑客松前置依赖。它适合后续：

- 长流程 durable execution。
- human-in-the-loop interrupt/resume。
- connector draft/submit 分阶段审批。
- 公司背调、文档解析、平台导入等跨节点 workflow。

## 最小 Agent 边界

最小 agent 不是全量 PRD agent，只覆盖 demo 和 MVP 第一闭环。

### In Scope

- 隐私模式 intake：纯本地、脱敏后外部模型、完整上下文外部模型。
- 简历和 JD 文本 intake。
- 候选人档案和证据片段的本地解析。
- JD 匹配分析和投递优先级。
- 简历优化建议，不做完整自动改写。
- 面试冲刺报告和 1-7 天计划。
- 招聘者开场白/跟进话术草稿。
- 本地 pipeline 下一步动作。
- Markdown artifact 渲染。
- 外部模型调用审计记录。

### Out of Scope

- 真实 Boss 直聘/脉脉登录和自动化。
- 自动投递或发送消息。
- PDF/DOCX 高质量解析。
- 公司联网背调。
- Offer 谈判完整流程。
- 长期记忆、向量库、云同步。

## 必须 Skills

| Skill | Intent | 第一阶段行为 | 必需 tools |
| --- | --- | --- | --- |
| `privacy_intake` | `privacy_intake` | 保存隐私模式，生成外发规则说明 | `pii.redact`, `consent.check`, `audit.log` |
| `candidate_profile_builder` | `profile_build` | 从简历文本提取候选人事实和证据片段 | `profile.parse`, `evidence.normalize` |
| `jd_match_analyst` | `jd_match` | 解析 JD，映射简历证据，计算匹配分和优先级 | `jd.parse`, `evidence.extract`, `fit.score` |
| `resume_optimizer` | `resume_optimize` | 生成事实约束的优化建议，不直接编造新 bullet | `evidence.extract`, `resume.suggest`, `report.render` |
| `interview_sprint_coach` | `interview_sprint` | 包装现有 readiness/gaps/sprint plan/report 逻辑 | `role_rubric.load`, `evidence.extract`, `report.render` |
| `application_assistant` | `application_message` | 基于已验证证据生成中文招聘者消息草稿 | `message.compose`, `pii.redact` |
| `pipeline_manager` | `pipeline_update` | 保存岗位阶段、下一步动作和 artifact refs | `pipeline.store`, `audit.log` |

### 暂缓 Skills

- `company_researcher`：需要 web/search consent 和来源管理，放到第二阶段。
- `platform_application_operator`：涉及高影响 connector，放到 LangGraph 阶段。
- `interview_debrief_assistant`、`offer_negotiation_coach`、`mock_interview_coach`：不是黑客松最小闭环。

## 必须 Tools

| Tool | 风险等级 | 第一阶段要求 |
| --- | --- | --- |
| `profile.parse` | `local_read` | 文本规则 + 可选模型抽取；纯本地时必须可用 |
| `pii.redact` | `local_read` | 默认脱敏手机号、邮箱、微信、地址等直接身份信息 |
| `jd.parse` | `local_read` | 保留现有规则解析，输出 title、role、requirements |
| `evidence.normalize` | `local_read` | 统一证据片段和缺失证据标签 |
| `evidence.extract` | `local_read` | 保留现有 rubric keyword 匹配，输出 evidence map |
| `fit.score` | `local_read` | 保留当前可解释分数和优先级 |
| `resume.suggest` | `local_write` | 基于 evidence map 生成优化建议；不能新增未经验证事实 |
| `message.compose` | `local_write` | 保留当前模板化 Boss/招聘者消息草稿 |
| `report.render` | `local_write` | 渲染 Markdown artifact |
| `pipeline.store` | `local_write` | MVP 可先内存保存，但接口不要绑定内存 |
| `consent.check` | `local_read` | 外部工具前置 gate，返回 allow/block/needs_user |
| `audit.log` | `local_write` | 记录目标服务、目的、数据范围、授权方式、payload 摘要 |
| `llm.generate` | `external_model` | 只能在 consent 后调用；Pydantic AI agent 封装现有 provider |

第一阶段不实现 `web.search`、`web.fetch`、`job_platform.*`。这些可以先保留为 blocked tool specs，用测试证明默认不能执行。

## 目标目录结构

```text
backend/app/agent/
  core.py                  # FastAPI-facing session/SSE facade, kept stable
  state.py                 # JobWorkspaceState, ConsentPolicy, Artifact, Opportunity
  router.py                # rule-first intent parser and task-frame selector
  runtime.py               # MinimalAgentRuntime orchestration facade
  pydantic_runtime.py      # Pydantic AI agent builders and structured outputs
  tools/
    local.py               # profile, pii, jd, evidence, scoring, report, pipeline
    external.py            # llm.generate wrapper, default blocked web/connector specs
  skills/
    job_search.py          # skill workflows as small Python functions
  validation.py            # evidence/unsupported-claim/high-impact-action checks
```

现有 `backend/app/agent/harness/` 可以先保留兼容层，逐步把实现迁入新结构。不要一次性大改 import surface。

## 执行流程

```text
user input
  -> core.py updates SessionState / JobWorkspaceState
  -> router.py returns IntentAnalysis + TaskFrame
  -> runtime.py builds short PlanStep list
  -> consent.check gates external/high-impact steps
  -> local skill workflow executes deterministic tools
  -> pydantic_runtime.py optionally generates summary/draft with typed output
  -> validation.py blocks unsupported claims and unconfirmed actions
  -> core.py streams artifact/state/report over existing SSE contract
```

关键规则：

- Router 先用规则和 task frame，不把高影响 planning 交给模型自由决定。
- Local tools 永远优先。LLM 只负责自然语言质量、结构化抽取补强和草稿润色。
- `llm.generate` 本身也必须作为受控 tool，经 `consent.check` 后才能执行。
- 纯本地模式下，agent 返回本地 deterministic artifact，而不是抛出模型未配置错误。
- Connector submit 类动作在第一阶段不存在；即使用户要求，也只能返回草稿和确认说明。

## Pydantic AI 迁移切入点

### 1. 结构化输出替换 `generate_json`

把当前 `LLMProvider.generate_json(system, user)` 的调用点替换为 Pydantic AI typed output：

- `HarnessSummaryOutput`
- `SprintReportOutput`
- `ResumeSuggestionOutput`
- `ApplicationMessageOutput`

保留现有 provider env 选择，但新增一个 OpenAI-compatible adapter 给 Pydantic AI 使用。

### 2. Tool schema 由 Pydantic AI 生成

当前 `ToolSpec.input_schema` 可以先保留用于 UI/audit，但 tool 对模型暴露时改为 Python function signature + Pydantic model。

本地业务 skill 可以继续直接调用 Python function，不要求每个 local tool 都由模型主动调用。

### 3. Approval 对齐 consent gate

用 Pydantic AI deferred tool approval 表达外部模型、web、MCP、connector 的暂停点。但产品层仍以自己的 `ConsentRequest` 为准：

- `allow_once`
- `allow_session`
- `edit_payload`
- `deny`

Approval 结果进入 `audit.log`，不能只存在模型消息历史里。

### 4. Streaming 对齐现有 SSE

Pydantic AI streaming event 映射到现有 SSE：

- tool start/result -> `status`
- text delta -> `assistant_delta`
- final structured output -> `state` 或 `report`
- blocked approval -> `state` with `consent_request`
- error -> `error`

前端可以先无改动消费旧事件，后续再展示更细的 plan/consent UI。

## 分阶段实施

### Phase 0: 合约冻结

Deliverables:

- 新增 `state.py` 和 typed contracts。
- 明确 `PrivacyMode`、`RiskLevel`、`ConsentRequest`、`PlanStep`、`Artifact`。
- 把当前 tool/skill 名称和本方案表格对齐。

Verification:

- `make test` 通过。
- 现有 `jd_match + application_message` 测试不改行为。

### Phase 1: 纯本地最小 agent

Deliverables:

- 实现 `privacy_intake`、`candidate_profile_builder`、`jd_match_analyst`、`resume_optimizer`、`interview_sprint_coach`、`application_assistant`、`pipeline_manager`。
- `interview_sprint_coach` 复用当前 `core.py` 的 report 逻辑，但移到 skill。
- 未配置 LLM 时仍能跑完整本地 demo。

Verification:

- 新增 pure-local test：未配置 provider 时仍返回 JD 匹配、优化建议、冲刺计划和消息草稿。
- 新增 forbidden action test：用户要求“帮我直接发送”时，不能产生 connector submit step。

### Phase 2: Pydantic AI 模型增强

Deliverables:

- 增加 `pydantic-ai` 依赖。
- 用 typed output 替换 `_enrich_harness_with_llm` 和 `_maybe_enrich_with_llm`。
- `llm.generate` 统一经过 `consent.check`、`pii.redact`、`audit.log`。

Verification:

- Fake model tests 校验 typed output 缺字段时失败可控。
- Privacy tests 校验 payload preview 包含目的、目标服务、数据范围、脱敏摘要。

### Phase 3: Scenario harness

Deliverables:

- 增加 scenario fixture runner。
- 覆盖至少 5 个最小闭环 scenario：
  - privacy mode + resume intake
  - JD match + application message
  - resume suggestion unsupported claim blocking
  - interview sprint report
  - pipeline update

Verification:

- scenario tests 不依赖网络。
- 每个 scenario 校验 expected intents、plan steps、artifacts、forbidden actions。

### Phase 4: LangGraph 预留，不实现

只有当 Phase 1-3 稳定后，再考虑：

- 公司背调的 web/search graph。
- connector draft/submit interrupt graph。
- 本地持久化 checkpoint。
- 多轮 debrief/offer workflow。

## 测试矩阵

| 测试 | 覆盖 |
| --- | --- |
| `test_minimal_agent_pure_local_demo_flow` | 无模型配置时完整本地闭环 |
| `test_external_model_requires_consent_preview` | 模型调用前必须生成 consent request |
| `test_pii_redact_before_external_payload` | 外发 payload 默认脱敏直接身份信息 |
| `test_forbidden_submit_action_without_confirmation` | 没有最终确认时不能发送/投递 |
| `test_resume_suggestion_blocks_unsupported_claim` | 简历建议不能新增未验证事实 |
| `test_pipeline_update_is_local_write_only` | pipeline 更新本地执行并审计 |
| `test_existing_report_flow_still_passes` | 保留当前面试冲刺能力 |

## 实施顺序建议

1. 先做 Phase 0 和 Phase 1，不引入 Pydantic AI 依赖。
2. 等本地闭环跑通后，再做 Phase 2 的 Pydantic AI typed output。
3. 最后加 scenario harness，避免一开始把测试框架和 runtime 重构绑在一起。

这个顺序可以把风险拆开：先保证业务闭环，再替换 agent framework glue，最后补评测。

