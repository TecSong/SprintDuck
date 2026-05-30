# 求职 Agent Harness 设计

## 设计目标

Harness 是 SprintDuckAgent 从 prompt wrapper 走向求职 Agent 的执行边界。它需要让 Agent 能够解析用户意图、基于当前求职状态自主推理、在明确权限下调用 tools 或 skills，并在真实求职任务中交付可验证结果，同时不隐藏证据来源和隐私代价。

本设计对齐 PRD 范围：

- 支持完整的 local-first 求职工作流：候选人档案、JD 匹配、简历优化、公司背调、投递消息、面试准备、面试复盘、Offer 谈判和 pipeline 跟踪。
- MVP 聚焦本地工作台任务。平台投递和招聘者消息发送不是 MVP 自动行为。
- 每一次外部调用和高影响动作都必须可审计、可打断、可由用户确认。
- 保留现有面试冲刺报告能力，并把它收敛为更大 harness 里的一个 skill。

## 关键假设

- 第一版实现必须可以在没有网络、真实招聘平台、真实 MCP server 的情况下测试。
- 能用本地确定性工具产出结构化结果时，应优先使用本地工具，再考虑 LLM 或 connector。
- Agent 可以自主读取和转换用户提供的本地上下文；但只要数据要离开本地进程，或动作会影响外部平台，就必须先获得用户授权。
- 缺少证据不等于候选人能力不足。Harness 输出必须保留这个区分。

## 非目标

- 不做全自动批量投递。
- 不做隐藏式招聘者消息发送。
- 不做绕过招聘平台规则的平台自动化。
- 不在云端持久化简历、凭证、pipeline 状态或审计日志。
- 启用外部 LLM、搜索、MCP 或平台 connector 时，不声称“数据永不离开本机”。

## 核心循环

```text
用户输入
  -> intake 和状态更新
  -> 意图解析
  -> 选择任务 frame
  -> 构造执行 plan
  -> consent 和风险门禁
  -> tool 或 skill 执行
  -> 证据与策略校验
  -> 返回用户可用 artifact 和下一步动作
```

### 1. Intake 和状态更新

Harness 接收聊天文本、上传文件、导入岗位数据、connector 数据和用户编辑结果。进入规划前，先更新本地状态：

- 候选人档案事实。
- 简历证据片段。
- JD 事实和岗位要求。
- 公司或团队背调笔记。
- 机会 pipeline 记录。
- 已生成 artifact，例如定制简历、消息草稿、报告和谈判脚本。
- 隐私模式和用户授权偏好。

### 2. 意图解析

意图解析器把用户自然语言映射到一个或多个求职任务。它必须支持混合请求，因为真实用户经常直接描述目标结果，而不是拆成单步指令。

示例：

```text
帮我看看这个岗位值不值得投，顺便写一段 Boss 开场白
```

期望解析结果：

- 主意图：`jd_match`
- 次意图：`application_message`
- 必需上下文：简历证据、JD 文本、用户约束
- 可能缺失上下文：消息语气、薪资或城市约束
- 风险等级：默认本地执行；只有用户要求公司背调时才需要外部能力

MVP 支持的意图族：

| Intent | 用户表达示例 | 期望 artifact |
| --- | --- | --- |
| `privacy_intake` | “我想纯本地使用”，“调用模型前给我看数据” | 隐私模式和授权策略 |
| `profile_build` | “这是我的简历”，“帮我整理候选人档案” | 结构化档案和证据地图 |
| `jd_match` | “这个岗位匹配吗”，“要不要投” | 匹配分、解释、gap、优先级 |
| `resume_optimize` | “按这个 JD 改简历”，“帮我优化 bullet” | 带证据约束的改写建议 |
| `company_research` | “帮我背调这家公司” | 带来源的公司简报和未知项 |
| `application_message` | “写 Boss 开场白”，“帮我写内推请求” | 简洁可信的中文消息草稿 |
| `interview_sprint` | “5 天后面试怎么准备” | 准备度报告和 1-7 天冲刺计划 |
| `interview_debrief` | “这是面试复盘，下一步怎么办” | 复盘、跟进消息、新 gap |
| `offer_negotiation` | “这个 offer 怎么谈” | 对比、策略、沟通脚本 |
| `pipeline_update` | “把这个机会标记成二面” | 本地 pipeline 更新和下一步动作 |

### 3. 任务 Frame 选择

Harness 把解析出的意图转换为任务 frame。任务 frame 定义期望输入、必需工具、artifact 合约、风险策略和完成标准。

```text
TaskFrame
  name
  required_context
  optional_context
  default_skill
  allowed_tools
  risk_policy
  output_contract
  completion_check
```

任务 frame 的作用是把模糊请求变成可执行任务。如果缺少必需上下文，Agent 应提出聚焦追问；如果缺少可选上下文，Agent 可以继续，但必须标明假设。

### 4. Plan 构造

Planner 根据任务 frame 和当前状态构造短小、可执行的 plan。

```text
PlanStep
  id
  purpose
  tool_or_skill
  input_refs
  output_refs
  risk_level
  requires_consent
  completion_signal
```

规划规则：

- 优先使用本地工具，例如解析、脱敏、证据抽取、评分、渲染和 pipeline 写入。
- 只有在自然语言质量、解释排序或草稿生成明显受益时，才使用 LLM。
- 只有用户要求研究、导入、日历、文档解析或平台数据时，才使用 web 或 MCP 工具。
- 高影响动作必须拆成草稿、预览、最终确认、执行和审计步骤。

### 5. Consent 和风险门禁

每个 plan step 执行前都要通过风险门禁。

风险等级：

| Level | 示例 | Harness 行为 |
| --- | --- | --- |
| `local_read` | 解析简历、解析 JD、计算匹配分 | 自动执行 |
| `local_write` | 保存 pipeline 笔记、渲染 Markdown | 自动执行，并展示结果 |
| `external_read` | web search、公开页面 fetch | 如果未启用对应权限，需要任务级授权 |
| `external_model` | LLM 改写或分析 | 按隐私模式展示 payload 范围并请求授权 |
| `connector_read` | 从招聘平台导入岗位 | 需要 connector 授权 |
| `connector_write_draft` | 在平台创建草稿 | 需要预览和审计 |
| `connector_submit` | 发送消息、投递申请 | 需要最终显式确认 |

授权请求合约：

```text
ConsentRequest
  purpose
  target_service
  data_scope
  redaction_summary
  retention_notice
  choices: allow_once | allow_session | edit_payload | deny
```

门禁必须能用 fake consent decision 测试，避免测试依赖真实用户点击。

### 6. Tool 和 Skill 执行

Harness 拥有 tool registry、skill registry 和 MCP adapter registry。

```text
ToolSpec
  name
  description
  category
  input_schema
  output_schema
  risk_level
  data_access
  persists_data

ToolResult
  ok
  data
  evidence_refs
  audit_refs
  error

AgentSkill
  name
  description
  supported_intents
  required_tools
  output_contract
  run(context, planner, registry) -> SkillResult
```

Tool 是边界清晰的窄能力。Skill 组合多个 tool，形成可完成求职任务的高层行为。MCP adapter 对 planner 来说也表现为 tool，但必须额外声明能力边界：

```text
McpAdapterSpec
  server_name
  readable_data
  writable_data
  external_targets
  high_impact_actions
  auth_required
```

### 7. 证据和策略校验

返回结果前，harness 必须校验：

- 结论引用简历、JD、用户笔记、公司来源、connector 记录，或明确标记为推断。
- 简历改写不能引入未经验证的新事实。
- 匹配分必须区分“证据缺口”和“候选人能力缺口”。
- 公司背调必须给出来源，或把相关判断标记为未验证。
- 投递消息不能夸大候选人经历。
- 外部调用必须有审计记录。
- 高影响 connector 动作必须有最终确认。

校验结果：

```text
ValidationReport
  passed
  blocking_errors
  warnings
  missing_evidence
  unsupported_claims
```

Blocking error 会阻止当前输出，要求 Agent 修复 artifact 或向用户补问。

## Harness 状态

Harness 状态应保持本地化，并且可以序列化：

```text
JobWorkspaceState
  candidate_profile
  evidence_map
  opportunities
  artifacts
  consent_policy
  audit_log
```

机会记录：

```text
Opportunity
  id
  company
  role
  source
  jd_ref
  stage
  priority
  next_action
  deadline
  notes
  artifact_refs
```

Artifact 记录：

```text
Artifact
  id
  type
  opportunity_id
  content
  evidence_refs
  created_at
  export_format
```

MVP 可以先保存在内存里，但接口不应假设只能内存存储。Pipeline 跟踪后续需要本地持久化。

## MVP 内置工具

| Tool | 类型 | 用途 |
| --- | --- | --- |
| `profile.parse` | 本地 | 把简历和个人材料解析成候选人事实 |
| `pii.redact` | 本地 | 脱敏直接身份信息和用户配置的敏感字段 |
| `jd.parse` | 本地 | 提取岗位、级别、要求、地点、薪资线索和面试信号 |
| `evidence.extract` | 本地 | 把简历证据映射到 JD 要求 |
| `fit.score` | 本地 | 计算可解释的匹配分、置信度和优先级 |
| `resume.rewrite` | 本地或模型支持 | 生成事实约束下的改写候选 |
| `message.compose` | 本地或模型支持 | 生成招聘者消息、内推请求和申请表回答 |
| `report.render` | 本地 | 渲染 Markdown artifact |
| `pipeline.store` | 本地 | 保存机会、阶段、笔记和下一步动作 |
| `audit.log` | 本地 | 记录外部调用、connector 动作和授权决策 |
| `consent.check` | 本地 | 判断步骤允许、阻塞或需要用户授权 |
| `web.search` | 外部 | 在授权后检索公开公司或岗位上下文 |
| `web.fetch` | 外部 | 抓取授权的公开页面用于背调 |
| `llm.generate` | 外部模型 | 在 payload 预览后合成解释、草稿和改写 |

## 内置 Skills

| Skill | 主要意图 | 必需工具 | 输出 |
| --- | --- | --- | --- |
| `privacy_intake` | `privacy_intake` | `pii.redact`, `consent.check`, `audit.log` | 隐私模式和脱敏策略 |
| `candidate_profile_builder` | `profile_build` | `profile.parse`, `evidence.extract` | 档案、证据地图、缺失事实 |
| `jd_match_analyst` | `jd_match` | `jd.parse`, `evidence.extract`, `fit.score` | 匹配报告、优先级、gap |
| `resume_optimizer` | `resume_optimize` | `evidence.extract`, `resume.rewrite`, `report.render` | bullet 前后对比和真实性确认 |
| `company_researcher` | `company_research` | `web.search`, `web.fetch`, `report.render` | 带来源简报、风险、追问 |
| `application_assistant` | `application_message` | `message.compose`, `pii.redact` | 招聘者、内推或申请表草稿 |
| `interview_sprint_coach` | `interview_sprint` | 现有准备度逻辑, `report.render` | 准备度报告和冲刺计划 |
| `interview_debrief_assistant` | `interview_debrief` | `evidence.extract`, `message.compose`, `pipeline.store` | 复盘、跟进消息、下一轮计划 |
| `offer_negotiation_coach` | `offer_negotiation` | `report.render`, 可选薪酬数据 | Offer 对比和谈判脚本 |
| `pipeline_manager` | `pipeline_update` | `pipeline.store`, `audit.log` | 更新后的机会和下一步动作 |

## 自主性策略

Agent 可以不追问而继续执行的情况：

- 动作只读取或转换用户提供的本地内容。
- 产出是草稿、报告、评分或计划。
- 缺失的是可选上下文，且输出会明确标注假设。

Agent 必须先询问用户的情况：

- 缺少必需上下文且无法可靠推断。
- 用户要求公司背调，但外部搜索未启用。
- 模型调用会把简历、薪资、雇主、联系方式或 JD 内容发送到本地执行之外。
- 平台 connector 会读取私有账号数据。
- 任何发送、投递、删除、更新线上资料，或写入招聘平台的动作。

## 面向真实求职任务的 Scenario Harness

评测 harness 应运行多轮 scenario，让测试像真实候选人工作流，而不是只测一次 prompt。

Scenario fixture：

```text
Scenario
  name
  persona
  privacy_mode
  initial_workspace
  turns
  fake_tool_responses
  expected_intents
  expected_plan_steps
  expected_artifacts
  forbidden_actions
  quality_assertions
```

每个 scenario 至少校验：

- 意图解析器选择了正确任务族，或提出了聚焦澄清问题。
- Planner 先选择本地工具，再选择外部工具。
- 模型、web、MCP 或平台调用触发了授权门禁。
- 最终 artifact 满足对应任务合约。
- 结论有证据支撑，或明确标记证据缺失。
- 禁止动作没有发生，例如未确认就投递申请。

优先 scenario：

1. 简历导入到候选人档案。
2. 粘贴 JD 后生成匹配分析和投递优先级。
3. 按 JD 定制简历，并拦截 unsupported claim。
4. 公司背调，生成带来源简报和未知项。
5. 基于简历和 JD 证据生成中文招聘者开场白。
6. 基于简历、JD、截止日期和每日时间生成现有面试冲刺报告。
7. 面试复盘转成跟进消息和下一轮计划。
8. Offer 对比和谈判脚本。
9. 多个机会的 pipeline 更新。
10. 平台 connector draft 流程，其中最终发送在确认前必须被阻塞。

## 端到端示例 Plan

用户请求：

```text
这是一个高级全栈岗位，帮我判断值不值得投，并写一段 Boss 直聘开场白。
```

Harness 行为：

1. 把意图解析为 `jd_match` 加 `application_message`。
2. 检查状态里是否已有简历证据和 JD 文本。
3. 如果缺少简历或 JD，向用户补问缺失项。
4. 执行 `jd.parse`、`evidence.extract` 和 `fit.score`。
5. 生成匹配报告，包含优先级、证据化优势、gap 和应该追问招聘者的问题。
6. 基于已验证证据生成简洁中文开场白。
7. 同时返回两个 artifact，并把消息标记为草稿。
8. 即使已有平台 connector，也不能发送消息；只有用户预览后显式确认，才能进入发送步骤。

## 实现阶段

### Phase 1：合约和本地执行

- 扩展 `ToolSpec`、`ToolResult` 和 registry 合约，加入风险等级、数据访问范围、证据引用和审计引用。
- 增加 task frame，以及本地确定性工具：profile parse、JD parse、evidence extract、fit score、report render、consent check 和 audit log。
- 保留当前面试冲刺报告，并包装为 `interview_sprint_coach`。

验证：

- 单元测试可以用 fake tools 运行，不依赖网络。
- 现有面试测试继续通过。
- 隐私门禁测试证明外部工具默认被阻塞。

### Phase 2：意图路由和 Scenario 评测

- 增加 intent parser 和 planner。
- 增加真实求职 scenario fixture。
- 校验意图、plan、授权、artifact 质量和禁止动作。

验证：

- Scenario tests 覆盖所有 MVP 意图族。
- 混合用户请求能生成多步 plan。
- Unsupported claim 会在返回用户前被拦截。

### Phase 3：外部模型和研究 Adapter

- 把 `llm.generate`、`web.search` 和 `web.fetch` 放到 consent 和 audit 后面。
- 给模型调用增加 payload 预览和脱敏摘要。
- 给公司背调增加来源追踪。

验证：

- Fake external adapters 可以模拟授权、拒绝和工具失败。
- Audit log 记录目标服务、调用目的、数据范围和授权方式。

### Phase 4：Connector-Ready 边界

- 先增加只读平台导入 adapter。
- Connector auth 存在后，再增加 draft-only 消息支持。
- 最终 submit/send 保持为独立高影响动作，必须显式确认。

验证：

- Connector tests 证明没有最终确认时，submit action 无法执行。
- 关闭 connector 后，本地档案、JD 匹配、简历优化、面试和 pipeline 流程仍可用。

## MVP 验收标准

- 用户可以完成真实本地流程：导入简历、JD 匹配、定制简历建议、面试冲刺计划、投递消息和 pipeline 下一步动作。
- Harness 能说明它推断了什么意图、规划了哪些步骤，以及输出由哪些证据支撑。
- 外部调用执行前展示目标服务、调用目的、数据范围、脱敏摘要和授权选项。
- 高影响 connector 动作在没有最终显式确认时不可能执行。
- Scenario tests 可以在不依赖真实平台或网络的情况下评测 Agent 自主性和任务完成质量。
