# Real Conversation Test Cases

## Quality Gate

Each real model case passes only if the final report has:

- readiness score between 0 and 100
- readiness band of `high`, `medium`, or `low`
- evidence coverage between 0 and 1
- at least 3 gap items, each with evidence or explicit `未发现证据`
- an adaptive 1-7 day sprint plan
- at least 5 likely interview questions
- Markdown export text containing score, gaps, plan, and questions

## Upload Flow Cases

These cases verify the browser upload path and the multipart API path, not only pasted text.

### Upload Case 1: Resume Markdown Only

- File: `samples/test_resume.md`
- User action: upload the file with an empty text box, then submit.
- Expected:
  - upload button shows `1 个文本文件` before submit
  - send button becomes enabled
  - assistant asks for missing JD and constraints instead of generating a report

### Upload Case 2: Resume Markdown + JD Markdown + Constraints Text

- Files:
  - `samples/test_resume.md`
  - `samples/test_jd.md`
  - `samples/test_constraints.txt`
- User action: upload all three files with an empty text box, then submit.
- Expected:
  - upload button shows `3 个文本文件` before submit
  - report is generated
  - role preset is engineering
  - sprint plan length is 5 days
  - report includes Top Gaps and interview questions

### Upload Case 3: Constraints Text Only

- File: `samples/test_constraints.txt`
- User action: upload the file with an empty text box, then submit.
- Expected:
  - upload button shows `1 个文本文件` before submit
  - assistant still asks for resume and JD
  - missing context no longer includes key date, daily minutes, or current stage

## Case 1: Software Engineering

Candidate:

```text
我是一名 4 年经验的全栈工程师，主要使用 TypeScript、React、Node.js 和 PostgreSQL。
负责过 B2B SaaS 的权限系统、报表模块和内部自动化平台。
最近项目中我把一个页面加载时间从 4.2s 优化到 1.8s，并推动了前端组件库重构。
我有基础的 Docker 使用经验，但没有主导过 Kubernetes 或大型系统设计评审。
```

JD:

```text
岗位：Senior Fullstack Engineer
要求：5年以上经验，熟悉 React、Node.js、PostgreSQL，能够设计可扩展后端服务。
需要有性能优化经验、跨团队沟通能力、英文技术文档阅读能力。
加分项：Kubernetes、系统设计、带领小团队。
```

Constraints:

```text
面试日期是 5 天后，每天可以投入 90 分钟，目前阶段是已经拿到一面邀请。
```

Expected:

- Role preset: engineering.
- Gaps mention seniority/system design/Kubernetes or leadership.
- Plan is 5 days.

## Case 2: Product Manager

Candidate:

```text
我做过 3 年 B2B 产品经理，负责过客户后台、权限配置和数据看板。
熟悉用户访谈、PRD、需求优先级排序和跨部门推进。
上线过一个数据看板模块，使运营团队每周手动统计时间减少约 6 小时。
我做过基础 SQL 查询，但没有完整负责过增长实验和商业化定价。
```

JD:

```text
岗位：Product Manager - Growth
要求：负责增长漏斗分析、A/B 测试、用户分层、商业化转化策略。
需要能写清楚 PRD，与设计、研发、运营协作，并用数据评估上线效果。
加分项：SQL、定价策略、海外 SaaS 产品经验。
```

Constraints:

```text
目标投递日期是 9 天后，每天可以投入 60 分钟，目前阶段是准备定制简历和作品集。
```

Expected:

- Role preset: product.
- Plan is 7 days because date is more than 7 days away.
- Gaps mention growth/A-B testing/pricing or overseas SaaS.

## Case 3: Operations

Candidate:

```text
我有 2 年内容运营经验，负责公众号、社群和活动复盘。
曾策划 3 场线上活动，累计报名 1800 人，活动后社群留存约 42%。
熟悉内容排期、社群答疑、基础数据复盘。
我没有直接负责过投放预算，也没有使用过复杂 CRM 自动化。
```

JD:

```text
岗位：用户运营
要求：负责用户分层、社群活跃、活动策划、数据复盘和转化提升。
需要能独立设计运营节奏，和产品、销售协同推进转化。
加分项：CRM 自动化、付费投放、生命周期运营。
```

Constraints:

```text
面试日期是明天，每天可以投入 120 分钟，目前阶段是面试前最后准备。
```

Expected:

- Role preset: operations.
- Plan is 1 day.
- Gaps mention CRM/paid acquisition/lifecycle if evidence is missing.
