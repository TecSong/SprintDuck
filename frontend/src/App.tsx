import {
  Activity,
  ArrowRight,
  BriefcaseBusiness,
  Building2,
  ClipboardList,
  Download,
  FilePenLine,
  FileText,
  Gauge,
  MessageSquareText,
  Send,
  ShieldCheck,
  Upload,
  Workflow
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { createSession, getLLMConfig, sendMessage } from "./api";
import { ChatLine, LLMConfigResponse, LLMProviderConfig, SprintReport, StreamEvent } from "./types";

type PrivacyModeId = "local" | "redacted" | "full";
type DashboardMode = "collecting" | "processing" | "ready";

const DEMO_PROMPT = `简历：
姓名：王晓夏
手机：13812345678
邮箱：xiaoxia@example.com
微信：wx_xiaoxia_demo
目标：前端/全栈工程师，偏 AI 产品和增长工具。
工作经历：
- 在一家 B2B SaaS 公司负责 React + TypeScript 工作台，重构线索管理、报表和权限模块，把核心页面首屏加载从 4.2 秒优化到 1.6 秒。
- 主导 AI 助手原型，把用户上传的业务文档解析为结构化任务清单，接入 FastAPI 服务和 SSE 流式响应。
- 与产品和运营协作做 A/B 实验，优化新用户激活流程，7 日留存提升 12%。
项目经历：
- 求职 Agent Demo：使用 FastAPI、React、LLM provider abstraction 构建本地优先的求职诊断工作台。
- 数据看板：设计指标口径、权限模型和导出流程，支持销售团队日常复盘。
技能：React、TypeScript、Python、FastAPI、LLM 应用、SSE、数据可视化、性能优化。

JD：
岗位：AI 产品方向前端工程师
职责：
- 负责 AI Agent 产品的 Web 工作台，包括对话、报告、任务流和配置界面。
- 与后端协作接入大模型、工具调用和流式响应。
- 能独立把复杂业务流程抽象成清晰、稳定、可演示的产品体验。
要求：
- 熟练掌握 React、TypeScript、工程化和性能优化。
- 有 AI 应用、Agent、RAG 或工具调用相关经验。
- 能理解产品目标，快速完成高质量 Demo。
- 加分：有隐私、安全、企业级工作台或招聘/HR 产品经验。

约束：
面试日期：2026-06-03
每天可投入时间：90 分钟
当前求职阶段：准备投递并争取一面机会`;

const JOB_STAGES = ["岗位发现", "匹配诊断", "简历优化", "投递沟通", "面试冲刺", "Offer 谈判"];

export function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [lines, setLines] = useState<ChatLine[]>([]);
  const [draft, setDraft] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [pending, setPending] = useState(false);
  const [config, setConfig] = useState<LLMConfigResponse | null>(null);
  const [report, setReport] = useState<SprintReport | null>(null);
  const [missing, setMissing] = useState<string[]>([]);
  const [privacyMode] = useState<PrivacyModeId>("redacted");
  const fileRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    createSession()
      .then((session) => {
        setSessionId(session.session_id);
        setMissing(session.missing);
        setLines([{ id: crypto.randomUUID(), role: "assistant", text: session.message }]);
      })
      .catch((error: Error) => {
        setLines([{ id: crypto.randomUUID(), role: "status", text: error.message }]);
      });

    getLLMConfig().then(setConfig).catch(() => setConfig(null));
  }, []);

  const canSend = useMemo(() => Boolean(sessionId && !pending && (draft.trim() || files.length)), [draft, files, pending, sessionId]);
  const activeProvider = useMemo(() => {
    if (!config) return null;
    return config.providers.find((provider) => provider.id === config.active_provider) ?? null;
  }, [config]);
  const providerConfigured = Boolean(activeProvider?.configured);
  const egressSummary = privacyEgressSummary(privacyMode, activeProvider, providerConfigured);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!sessionId || !canSend) return;
    if (privacyMode === "local" && providerConfigured) {
      appendLine("status", "纯本地模式已阻止发送：当前模型服务商已配置。请切换到脱敏外发或完整外发。");
      return;
    }
    if (privacyMode === "redacted" && files.length) {
      appendLine("status", "脱敏外发模式暂不处理上传文件。请把文件内容粘贴到输入框，或切换到完整外发。");
      return;
    }

    const outgoing = [draft.trim(), files.map((file) => file.name).join("、")].filter(Boolean).join("\n");
    const outboundDraft = privacyMode === "redacted" ? redactSensitiveText(draft) : draft;
    setLines((prev) => [...prev, { id: crypto.randomUUID(), role: "user", text: outgoing }]);
    if (privacyMode === "redacted" && outboundDraft !== draft) {
      appendLine("status", "已按脱敏外发模式移除手机号、邮箱、微信等直接身份信息。");
    }
    setPending(true);
    setDraft("");
    const selected = files;
    setFiles([]);
    if (fileRef.current) fileRef.current.value = "";

    try {
      await sendMessage(sessionId, outboundDraft, selected, handleStreamEvent);
    } catch (error) {
      setLines((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: "status", text: error instanceof Error ? error.message : "消息发送失败" }
      ]);
    } finally {
      setPending(false);
    }
  };

  const handleStreamEvent = (event: StreamEvent) => {
    if (event.event === "status") {
      appendLine("status", String(event.data.message ?? ""));
    }
    if (event.event === "assistant_delta") {
      appendLine("assistant", String(event.data.text ?? ""));
    }
    if (event.event === "state") {
      const nextMissing = Array.isArray(event.data.missing) ? event.data.missing.map(String) : [];
      setMissing(nextMissing);
    }
    if (event.event === "report") {
      setReport(event.data as unknown as SprintReport);
      setMissing([]);
    }
    if (event.event === "error") {
      appendLine("status", String(event.data.message ?? "生成失败"));
    }
  };

  const appendLine = (role: ChatLine["role"], text: string) => {
    if (!text) return;
    setLines((prev) => [...prev, { id: crypto.randomUUID(), role, text }]);
  };

  const loadDemoPrompt = () => {
    setDraft(DEMO_PROMPT);
    setFiles([]);
    if (fileRef.current) fileRef.current.value = "";
    appendLine("status", "已加载黑客松演示材料：中文简历、目标 JD 和准备约束。");
  };

  const downloadMarkdown = () => {
    if (!report?.markdown) return;
    const blob = new Blob([report.markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "sprintduck-report.md";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <main className="shell">
      <header className="command-bar">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true">
            <Activity size={22} />
          </div>
          <div>
            <strong>SprintDuckAgent</strong>
            <span>Privacy-first job agent</span>
          </div>
        </div>

        <div className="command-status">
          <div className="status-chip">
            <ShieldCheck aria-hidden="true" size={16} />
            <span>{egressSummary.short}</span>
          </div>
        </div>
      </header>

      <section className="workspace">
        <section className="chat-panel" aria-label="实时对话">
          <div className="transcript">
            {lines.map((line) => (
              <article className={`bubble ${line.role}`} key={line.id}>
                <p>{line.text}</p>
              </article>
            ))}
            {pending ? (
              <article className="bubble status">
                <p>Agent 正在生成诊断、投递话术和面试冲刺计划...</p>
              </article>
            ) : null}
          </div>

          <form className="composer" onSubmit={handleSubmit}>
            <label className="composer-label sr-only" htmlFor="job-context">
              候选人资料 / 目标 JD / 约束
            </label>
            <textarea
              id="job-context"
              placeholder="粘贴简历、目标 JD、目标公司、面试日期、每天可投入时间、当前投递阶段。"
              rows={5}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
            />
            <div className="composer-actions">
              <div className="composer-tools">
                <button className="sample-button" type="button" onClick={loadDemoPrompt}>
                  <ClipboardList aria-hidden="true" size={16} />
                  <span>演示材料</span>
                </button>
                <label className="file-button">
                  <Upload aria-hidden="true" size={17} />
                  <span>{files.length ? `${files.length} 个文本文件` : "上传 .txt/.md"}</span>
                  <input
                    ref={fileRef}
                    accept=".txt,.md,.markdown,text/plain,text/markdown"
                    multiple
                    type="file"
                    onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
                  />
                </label>
              </div>
              <button className="send-button" disabled={!canSend} type="submit">
                <span>{pending ? "处理中" : "生成可信闭环"}</span>
                <Send aria-hidden="true" size={17} />
              </button>
            </div>
          </form>
        </section>

        <JobDashboard report={report} missing={missing} pending={pending} onDownload={downloadMarkdown} />
      </section>
    </main>
  );
}

function privacyEgressSummary(mode: PrivacyModeId, provider: LLMProviderConfig | null, providerConfigured: boolean) {
  if (mode === "local") {
    return {
      short: "纯本地模式 · 禁止外部模型"
    };
  }
  if (!providerConfigured) {
    return {
      short: "模型未连接 · 检查主 .env"
    };
  }
  if (mode === "redacted") {
    return {
      short: `脱敏外发 · ${provider?.name ?? "模型服务商"}`
    };
  }
  return {
    short: `完整外发 · ${provider?.name ?? "模型服务商"}`
  };
}

function redactSensitiveText(text: string) {
  return text
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, "[邮箱已脱敏]")
    .replace(/(?:\+?86[- ]?)?1[3-9]\d{9}/g, "[手机号已脱敏]")
    .replace(/(?:微信|wechat|weixin|wx)[:：\s_-]*[a-zA-Z0-9_-]{4,}/gi, "微信：[微信已脱敏]")
    .replace(/(?:身份证|证件号)[:：\s]*[0-9Xx]{8,}/g, "身份证：[证件号已脱敏]");
}

function roleLabel(role: SprintReport["role"]) {
  return {
    engineering: "工程岗位",
    product: "产品岗位",
    operations: "运营岗位",
    generic: "目标岗位"
  }[role];
}

function applicationDrafts(report: SprintReport) {
  const firstGap = report.top_gaps[0]?.title ?? "岗位关键要求";
  const firstPlan = report.sprint_plan[0]?.focus ?? "近期准备重点";
  const role = roleLabel(report.role);
  return [
    {
      title: "招聘者开场白",
      text: `您好，我正在关注贵司${role}。我有相关项目和业务协作经验，已经根据 JD 梳理了匹配证据，也注意到需要重点补强「${firstGap}」。如果岗位仍在招聘，我希望进一步沟通岗位目标和团队要求。`
    },
    {
      title: "投递后跟进",
      text: `您好，我已投递该岗位，并补充整理了与 JD 相关的项目证据。接下来我会重点准备「${firstPlan}」。如果方便，也想了解这个岗位当前最看重的能力和面试安排。`
    }
  ];
}

function buildDashboardState(report: SprintReport | null, missing: string[], pending: boolean) {
  if (report) {
    const stageIndex = report.readiness_score >= 80 ? 3 : 2;
    return {
      mode: "ready" as DashboardMode,
      stageIndex,
      stage: JOB_STAGES[stageIndex],
      title: `匹配度 ${report.readiness_score}/100 · ${report.readiness_band}`,
      description: report.summary,
      signal: "Agent 输出已写入面板"
    };
  }

  if (pending) {
    return {
      mode: "processing" as DashboardMode,
      stageIndex: 1,
      stage: JOB_STAGES[1],
      title: "Agent 正在分析简历与 JD",
      description: "Dashboard 会在流式结果到达后切换为差距、行动、投递和面试模块。",
      signal: "实时生成中"
    };
  }

  return {
    mode: "collecting" as DashboardMode,
    stageIndex: 0,
    stage: JOB_STAGES[0],
    title: missing.length ? `还缺 ${missing.length} 类上下文` : "上下文已满足",
    description: missing.length ? "补齐材料后即可进入匹配诊断。" : "可以开始生成求职诊断。",
    signal: "等待输入"
  };
}

function JobDashboard({
  report,
  missing,
  pending,
  onDownload
}: {
  report: SprintReport | null;
  missing: string[];
  pending: boolean;
  onDownload: () => void;
}) {
  const dashboard = buildDashboardState(report, missing, pending);
  const drafts = report ? applicationDrafts(report) : [];
  const requiredContext = missing.length
    ? missing
    : ["简历材料", "目标岗位 JD", "关键日期", "每天可投入时间", "当前求职阶段"];

  return (
    <section className={`dashboard-panel ${dashboard.mode}`} aria-label="求职 Dashboard">
      <header className="dashboard-head">
        <div>
          <p className="eyebrow">JOB DASHBOARD / {dashboard.stage}</p>
          <h2>{dashboard.title}</h2>
          <p>{dashboard.description}</p>
        </div>
        {report ? (
          <button className="download-button" type="button" onClick={onDownload}>
            <Download aria-hidden="true" size={17} />
            <span>导出 Markdown</span>
          </button>
        ) : (
          <div className="dashboard-state-chip">
            <Workflow aria-hidden="true" size={17} />
            <span>{dashboard.signal}</span>
          </div>
        )}
      </header>

      <ol className="stage-rail" aria-label="求职环节">
        {JOB_STAGES.map((stage, index) => (
          <li className={index === dashboard.stageIndex ? "active" : index < dashboard.stageIndex ? "done" : ""} key={stage}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <strong>{stage}</strong>
          </li>
        ))}
      </ol>

      <section className="dashboard-hero" aria-live="polite">
        {report ? (
          <div className="score-block">
            <span>Job Fit Readiness</span>
            <strong>{report.readiness_score}</strong>
            <small>/100</small>
          </div>
        ) : (
          <div className="dashboard-counter">
            <FileText aria-hidden="true" size={28} />
            <strong>{pending ? "..." : requiredContext.length}</strong>
            <span>{pending ? "生成中" : "待补上下文"}</span>
          </div>
        )}
        <div className="dashboard-hero-copy">
          <p className="eyebrow">{report ? `DIAGNOSIS / ${roleLabel(report.role)}` : "LIVE STATE"}</p>
          <h3>{dashboard.signal}</h3>
          {report ? (
            <div className="metric-row">
              <span>{report.readiness_band}</span>
              <span>证据覆盖率 {(report.evidence_coverage * 100).toFixed(0)}%</span>
              <span>信心 {report.confidence}</span>
            </div>
          ) : (
            <p>{dashboard.description}</p>
          )}
        </div>
      </section>

      <div className="dynamic-stack">
        {!report ? (
          <>
            <section className="dashboard-section">
              <div className="section-kicker">
                <FileText aria-hidden="true" size={17} />
                <span>当前需要的上下文</span>
              </div>
              <div className="context-grid">
                {requiredContext.map((item) => (
                  <span className={missing.length ? "needed" : "ready"} key={item}>
                    {item}
                  </span>
                ))}
              </div>
            </section>
            <section className="dashboard-section">
              <div className="section-kicker">
                <Gauge aria-hidden="true" size={17} />
                <span>待生成模块</span>
              </div>
              <div className="signal-list">
                <span>JD 匹配差距</span>
                <span>简历证据补强</span>
                <span>投递话术</span>
                <span>面试冲刺计划</span>
              </div>
            </section>
          </>
        ) : (
          <>
            <section className="dashboard-section">
              <div className="section-kicker">
                <Gauge aria-hidden="true" size={17} />
                <span>简历与 JD 差距</span>
              </div>
              <div className="gap-list">
                {report.top_gaps.map((gap) => (
                  <article className="gap-card" key={gap.title}>
                    <header>
                      <strong>{gap.title}</strong>
                      <span className={`severity ${gap.severity}`}>{gap.severity}</span>
                    </header>
                    <p>{gap.gap_reason}</p>
                    <small>证据：{gap.evidence.map((item) => item.text).join("；")}</small>
                    <small>行动：{gap.suggested_action}</small>
                  </article>
                ))}
              </div>
            </section>

            <section className="dashboard-section">
              <div className="section-kicker">
                <FilePenLine aria-hidden="true" size={17} />
                <span>简历优化优先级</span>
              </div>
              <div className="action-list">
                {report.top_gaps.slice(0, 3).map((gap, index) => (
                  <article className="action-row" key={gap.title}>
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <div>
                      <strong>{gap.title}</strong>
                      <p>{gap.suggested_action}</p>
                    </div>
                  </article>
                ))}
              </div>
            </section>

            <section className="dashboard-section scenario-apply">
              <div className="section-kicker">
                <MessageSquareText aria-hidden="true" size={17} />
                <span>投递话术草稿</span>
              </div>
              <div className="draft-list">
                {drafts.map((draft) => (
                  <article className="draft-card" key={draft.title}>
                    <strong>{draft.title}</strong>
                    <p>{draft.text}</p>
                  </article>
                ))}
              </div>
            </section>

            <section className="dashboard-section">
              <div className="section-kicker">
                <BriefcaseBusiness aria-hidden="true" size={17} />
                <span>Pipeline 下一步</span>
              </div>
              <div className="pipeline-row">
                <Building2 aria-hidden="true" size={18} />
                <div>
                  <strong>目标岗位 · 准备投递</strong>
                  <p>发送开场白，确认岗位仍在招聘，并用冲刺计划准备一面。</p>
                </div>
                <span>Today</span>
              </div>
            </section>

            <section className="dashboard-section scenario-interview">
              <div className="section-kicker">
                <ClipboardList aria-hidden="true" size={17} />
                <span>面试冲刺计划</span>
              </div>
              <div className="plan-list">
                {report.sprint_plan.map((day) => (
                  <article className="plan-row" key={day.day}>
                    <span>Day {day.day}</span>
                    <div>
                      <strong>{day.focus}</strong>
                      <p>{day.tasks[0]}</p>
                      <small>
                        {day.minutes} 分钟 · {day.done_criteria}
                      </small>
                    </div>
                  </article>
                ))}
              </div>
            </section>

            <section className="dashboard-section">
              <div className="section-kicker">
                <ArrowRight aria-hidden="true" size={17} />
                <span>高频追问</span>
              </div>
              <ol className="question-list">
                {report.interview_questions.map((item) => (
                  <li key={item.question}>
                    <strong>{item.question}</strong>
                    <span>{item.why_it_matters}</span>
                  </li>
                ))}
              </ol>
            </section>
          </>
        )}
      </div>
    </section>
  );
}
