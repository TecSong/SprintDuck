# Job Search Agent Harness Design

## Design Goal

The harness is the execution boundary that turns SprintDuckAgent from a prompt wrapper into a job-search agent. It should let the agent understand user intent, reason over the current job-search state, call tools or skills through explicit permissions, and complete real candidate tasks without hiding evidence or privacy tradeoffs.

The design follows the PRD scope:

- Support the complete local-first job-search workflow: candidate profile, JD matching, resume optimization, company research, application messages, interview preparation, debrief, offer negotiation, and pipeline tracking.
- Keep the MVP focused on local workbench tasks. Platform submission and recruiter message sending are not automatic MVP behavior.
- Make every external call and high-impact action auditable and interruptible by the user.
- Preserve the existing interview sprint report as one skill inside the broader harness.

## Assumptions

- The first implementation should be testable without network calls, real recruiting platforms, or real MCP servers.
- Local deterministic tools should run before LLM or connector tools whenever they can produce useful structure.
- The agent may autonomously read and transform user-provided local context. It must ask for approval before sending data outside the local process or before any high-impact platform action.
- Missing evidence is not the same as candidate weakness. Harness outputs must preserve that distinction.

## Non-Goals

- No full automatic batch application.
- No hidden recruiter message sending.
- No platform automation that bypasses recruiting platform rules.
- No cloud persistence of resumes, credentials, pipeline state, or audit logs.
- No claim that data never leaves the machine when external LLM, search, MCP, or platform connectors are enabled.

## Core Loop

```text
User input
  -> intake and state update
  -> intent parsing
  -> task frame selection
  -> plan construction
  -> consent and risk gate
  -> tool or skill execution
  -> evidence and policy validation
  -> user-facing artifact plus next action
```

### 1. Intake And State Update

The harness receives text, uploaded files, imported job data, connector data, and user edits. It updates local state before planning:

- Candidate profile facts.
- Resume evidence snippets.
- JD facts and requirements.
- Company or team research notes.
- Opportunity pipeline records.
- Existing artifacts, such as tailored resumes, messages, reports, and negotiation scripts.
- Privacy mode and consent preferences.

### 2. Intent Parsing

The intent parser maps user language to one or more job-search tasks. It should support mixed requests, because real users often ask for outcome-level help.

Example:

```text
帮我看看这个岗位值不值得投，顺便写一段 Boss 开场白
```

Expected parsed frame:

- Primary intent: `jd_match`
- Secondary intent: `application_message`
- Required context: resume evidence, JD text, user constraints
- Possible missing context: target tone, salary or city constraints
- Risk level: local by default, external only if company research is requested

Supported MVP intent families:

| Intent | User language examples | Expected artifact |
| --- | --- | --- |
| `privacy_intake` | "我想纯本地使用", "调用模型前给我看数据" | privacy mode and consent policy |
| `profile_build` | "这是我的简历", "帮我整理候选人档案" | structured profile and evidence map |
| `jd_match` | "这个岗位匹配吗", "要不要投" | fit score, reasons, gaps, priority |
| `resume_optimize` | "按这个 JD 改简历", "帮我优化 bullet" | evidence-backed rewrite suggestions |
| `company_research` | "帮我背调这家公司" | sourced company brief and unknowns |
| `application_message` | "写 Boss 开场白", "帮我写内推请求" | concise Chinese message drafts |
| `interview_sprint` | "5 天后面试怎么准备" | readiness report and 1-7 day plan |
| `interview_debrief` | "这是面试复盘，下一步怎么办" | debrief, follow-up message, new gaps |
| `offer_negotiation` | "这个 offer 怎么谈" | comparison, strategy, scripts |
| `pipeline_update` | "把这个机会标记成二面" | local pipeline mutation and next action |

### 3. Task Frame Selection

The harness converts parsed intent into a task frame. A task frame defines the expected inputs, required tools, artifact contract, risk policy, and completion criteria.

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

Task frames make ambiguous work explicit. If required context is missing, the agent asks a focused follow-up. If optional context is missing, the agent can continue and mark assumptions.

### 4. Plan Construction

The planner builds a short executable plan from the task frame and current state.

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

Rules:

- Prefer local tools first, such as parsing, redaction, evidence extraction, scoring, rendering, and pipeline writes.
- Use LLM generation only for natural language synthesis, ranking explanations, or drafts that benefit from language quality.
- Use web or MCP tools only when the user asks for research, imports, calendar, document parsing, or platform data.
- Split high-impact actions into draft, preview, final confirmation, execute, and audit steps.

### 5. Consent And Risk Gate

Every step passes through a gate before execution.

Risk levels:

| Level | Examples | Harness behavior |
| --- | --- | --- |
| `local_read` | parse resume, parse JD, score fit | execute automatically |
| `local_write` | save pipeline note, render Markdown | execute automatically, show result |
| `external_read` | web search, public page fetch | require task-level consent if disabled |
| `external_model` | LLM rewrite or analysis | show payload scope and require consent by privacy mode |
| `connector_read` | import job from platform | require connector authorization |
| `connector_write_draft` | create platform draft | require preview and audit |
| `connector_submit` | send message, submit application | require final explicit confirmation |

Consent request contract:

```text
ConsentRequest
  purpose
  target_service
  data_scope
  redaction_summary
  retention_notice
  choices: allow_once | allow_session | edit_payload | deny
```

The gate must be testable with fake consent decisions.

### 6. Tool And Skill Execution

The harness owns registries for tools, skills, and MCP adapters.

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

Tools are narrow capabilities. Skills compose tools into job-search behavior. MCP adapters look like tools to the planner, but carry additional capability declarations:

```text
McpAdapterSpec
  server_name
  readable_data
  writable_data
  external_targets
  high_impact_actions
  auth_required
```

### 7. Evidence And Policy Validation

Before returning a result, the harness validates:

- Claims cite resume, JD, user note, company source, connector record, or explicit inference.
- Resume rewrites do not introduce unverified facts.
- Fit scores distinguish evidence gaps from candidate gaps.
- Company research includes sources or marks claims as unverified.
- Application messages do not overstate experience.
- External calls have audit entries.
- High-impact connector actions have final confirmation.

Validation result:

```text
ValidationReport
  passed
  blocking_errors
  warnings
  missing_evidence
  unsupported_claims
```

Blocking errors stop execution and ask the agent to repair the artifact or ask the user for more context.

## Harness State

The harness state should be local and serializable:

```text
JobWorkspaceState
  candidate_profile
  evidence_map
  opportunities
  artifacts
  consent_policy
  audit_log
```

Opportunity records:

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

Artifact records:

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

The MVP can keep this in memory, but the interfaces should not assume memory-only state. Pipeline tracking will need local persistence later.

## Built-In MVP Tools

| Tool | Type | Purpose |
| --- | --- | --- |
| `profile.parse` | local | parse resume and personal material into candidate facts |
| `pii.redact` | local | redact direct identity fields and user-configured sensitive fields |
| `jd.parse` | local | extract role, level, requirements, location, salary clues, and interview signals |
| `evidence.extract` | local | map resume evidence to JD requirements |
| `fit.score` | local | compute explainable fit, confidence, and priority |
| `resume.rewrite` | local or model-backed | generate evidence-constrained rewrite candidates |
| `message.compose` | local or model-backed | draft recruiter messages, referral requests, and application answers |
| `report.render` | local | render Markdown artifacts |
| `pipeline.store` | local | save opportunities, stages, notes, and next actions |
| `audit.log` | local | record external calls, connector actions, and consent decisions |
| `consent.check` | local | decide whether a step is allowed, blocked, or needs user approval |
| `web.search` | external | retrieve public company or role context when approved |
| `web.fetch` | external | fetch approved public pages for research |
| `llm.generate` | external model | synthesize explanations, drafts, and rewrites after payload review |

## Built-In Skills

| Skill | Main intents | Required tools | Output |
| --- | --- | --- | --- |
| `privacy_intake` | `privacy_intake` | `pii.redact`, `consent.check`, `audit.log` | privacy mode and redaction policy |
| `candidate_profile_builder` | `profile_build` | `profile.parse`, `evidence.extract` | profile, evidence map, missing facts |
| `jd_match_analyst` | `jd_match` | `jd.parse`, `evidence.extract`, `fit.score` | fit report, priority, gaps |
| `resume_optimizer` | `resume_optimize` | `evidence.extract`, `resume.rewrite`, `report.render` | before/after bullets and truth checks |
| `company_researcher` | `company_research` | `web.search`, `web.fetch`, `report.render` | sourced brief, risks, questions |
| `application_assistant` | `application_message` | `message.compose`, `pii.redact` | recruiter, referral, or form-answer drafts |
| `interview_sprint_coach` | `interview_sprint` | existing readiness logic, `report.render` | readiness report and sprint plan |
| `interview_debrief_assistant` | `interview_debrief` | `evidence.extract`, `message.compose`, `pipeline.store` | debrief, follow-up, next plan |
| `offer_negotiation_coach` | `offer_negotiation` | `report.render`, optional salary data | offer comparison and negotiation scripts |
| `pipeline_manager` | `pipeline_update` | `pipeline.store`, `audit.log` | updated opportunity and next action |

## Autonomy Policy

The agent can proceed without asking when:

- The action only reads or transforms local user-provided content.
- The artifact is a draft, report, score, or plan.
- Missing context is optional and the output clearly labels assumptions.

The agent must ask before continuing when:

- Required context is missing and cannot be inferred.
- The user asks for company research but external search is disabled.
- A model call would send resume, salary, employer, contact, or JD content outside local execution.
- A platform connector reads private account data.
- Any action sends, submits, deletes, updates online profile data, or writes to a recruiting platform.

## Scenario Harness For Real Job Search Tasks

The evaluation harness should run multi-turn scenarios that look like real candidate workflows, not only one-shot prompts.

Scenario fixture:

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

Each scenario should assert:

- Intent parser selected the right task family or asked a focused clarification.
- Planner chose local tools before external tools.
- Consent gates triggered for model, web, MCP, or platform calls.
- Final artifact satisfied the task contract.
- Claims were backed by evidence or marked as missing.
- Forbidden actions, such as submitting an application without confirmation, did not happen.

Priority scenarios:

1. Resume import to candidate profile.
2. JD paste to fit analysis and application priority.
3. JD-tailored resume rewrite with unsupported-claim rejection.
4. Company research with sourced brief and unknowns.
5. Recruiter opening message in Chinese from resume plus JD evidence.
6. Existing interview sprint report from resume, JD, deadline, and daily time.
7. Interview debrief to follow-up message and next-round plan.
8. Offer comparison and negotiation script.
9. Pipeline update across multiple opportunities.
10. Platform connector draft flow where final send is blocked until confirmation.

## Example End-To-End Plan

User request:

```text
这是一个高级全栈岗位，帮我判断值不值得投，并写一段 Boss 直聘开场白。
```

Harness behavior:

1. Parse intent as `jd_match` plus `application_message`.
2. Check state for resume evidence and JD text.
3. If resume or JD is missing, ask for the missing item.
4. Run `jd.parse`, `evidence.extract`, and `fit.score`.
5. Generate a fit report with priority, evidence-backed strengths, gaps, and questions to ask recruiter.
6. Draft a concise Chinese opening message from verified evidence.
7. Return both artifacts and mark the message as a draft.
8. Do not send the message, even if a platform connector exists, unless the user explicitly confirms after preview.

## Implementation Phases

### Phase 1: Contract And Local Execution

- Extend `ToolSpec`, `ToolResult`, and registry contracts with risk, data access, evidence refs, and audit refs.
- Add task frames and deterministic local tools for profile parsing, JD parsing, evidence extraction, fit scoring, report rendering, consent checks, and audit logging.
- Keep current interview sprint report as `interview_sprint_coach`.

Verification:

- Unit tests can run with fake tools and no network.
- Existing interview tests keep passing.
- Privacy gate tests prove external tools are blocked by default.

### Phase 2: Intent Router And Scenario Evaluations

- Add the intent parser and planner.
- Add real job-search scenario fixtures.
- Assert intent, plan, consent, artifact quality, and forbidden actions.

Verification:

- Scenario tests cover all MVP intent families.
- Mixed user requests produce multi-step plans.
- Unsupported claims are caught before user output.

### Phase 3: External Model And Research Adapters

- Put `llm.generate`, `web.search`, and `web.fetch` behind consent and audit.
- Add payload preview and redaction summary to model calls.
- Add source tracking to company research.

Verification:

- Fake external adapters can simulate approval, denial, and tool failure.
- Audit log records target, purpose, data scope, and consent mode.

### Phase 4: Connector-Ready Boundary

- Add read-only platform import adapters first.
- Add draft-only message support after connector auth exists.
- Keep final submit/send as a separate high-impact action with explicit confirmation.

Verification:

- Connector tests prove no submit action can run without final confirmation.
- Disabling a connector leaves local profile, JD matching, resume optimization, interview, and pipeline flows usable.

## MVP Acceptance Criteria

- A user can complete a realistic local workflow from resume import to JD match, tailored resume suggestions, interview sprint plan, application message, and pipeline next action.
- The harness can explain which intent it inferred, which steps it planned, and which evidence supports the output.
- External calls show target service, purpose, data scope, redaction summary, and consent options before execution.
- High-impact connector actions are impossible without explicit final confirmation.
- Scenario tests can evaluate agent autonomy and task completion without relying on live platforms or network access.
