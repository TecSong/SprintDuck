import {
  Activity,
  ArrowRight,
  BriefcaseBusiness,
  Building2,
  CheckCircle2,
  ClipboardList,
  Download,
  FilePenLine,
  FileText,
  Gauge,
  KeyRound,
  LockKeyhole,
  MessageSquareText,
  Network,
  Save,
  Send,
  Settings,
  ShieldCheck,
  Upload,
  Workflow,
  X
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { createSession, getLLMConfig, sendMessage, updateLLMConfig } from "./api";
import { ChatLine, LLMConfigResponse, LLMProviderConfig, SprintReport, StreamEvent } from "./types";

type PrivacyModeId = "local" | "redacted" | "full";

const PRIVACY_MODES: Array<{
  id: PrivacyModeId;
  label: string;
  description: string;
}> = [
  {
    id: "redacted",
    label: "脱敏外发",
    description: "默认推荐。发送前脱敏手机号、邮箱、微信等直接身份信息。"
  },
  {
    id: "local",
    label: "纯本地",
    description: "不允许调用已配置的外部模型，适合隐私敏感材料。"
  },
  {
    id: "full",
    label: "完整外发",
    description: "发送完整上下文给当前模型服务商，换取更完整的表达优化。"
  }
];

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

const WORKFLOW_STAGES = ["发现岗位", "匹配诊断", "简历优化", "投递沟通", "面试冲刺", "Offer 谈判"];

const SKILL_SURFACE = [
  { name: "resume_optimizer", target: "简历证据与岗位改写" },
  { name: "company_researcher", target: "公司背调与风险信号" },
  { name: "interview_sprint", target: "1-7 天面试冲刺" },
  { name: "platform_connector", target: "Boss / 脉脉 · 授权后执行" }
];

export function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [lines, setLines] = useState<ChatLine[]>([]);
  const [draft, setDraft] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [pending, setPending] = useState(false);
  const [config, setConfig] = useState<LLMConfigResponse | null>(null);
  const [selectedProviderId, setSelectedProviderId] = useState("wanjie_ark");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [savingConfig, setSavingConfig] = useState(false);
  const [configMessage, setConfigMessage] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [report, setReport] = useState<SprintReport | null>(null);
  const [missing, setMissing] = useState<string[]>([]);
  const [privacyMode, setPrivacyMode] = useState<PrivacyModeId>("redacted");
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

    getLLMConfig()
      .then((nextConfig) => syncConfigForm(nextConfig, nextConfig.active_provider))
      .catch((error: Error) => setConfigMessage(error.message));
  }, []);

  const canSend = useMemo(() => Boolean(sessionId && !pending && (draft.trim() || files.length)), [draft, files, pending, sessionId]);
  const selectedProvider = useMemo(
    () => config?.providers.find((provider) => provider.id === selectedProviderId) ?? null,
    [config, selectedProviderId]
  );
  const providerConfigured = Boolean(selectedProvider?.configured);
  const selectedPrivacyMode = PRIVACY_MODES.find((mode) => mode.id === privacyMode) ?? PRIVACY_MODES[0];
  const egressSummary = privacyEgressSummary(privacyMode, selectedProvider, providerConfigured);

  const syncConfigForm = (nextConfig: LLMConfigResponse, providerId: string) => {
    const provider = nextConfig.providers.find((item) => item.id === providerId) ?? nextConfig.providers[0];
    setConfig(nextConfig);
    setSelectedProviderId(provider?.id ?? "wanjie_ark");
    setModel(provider?.model ?? "");
    setBaseUrl(provider?.base_url ?? "");
    setApiKey("");
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!sessionId || !canSend) return;
    if (privacyMode === "local" && providerConfigured) {
      appendLine("status", "纯本地模式已阻止发送：当前模型服务商已配置。请清空模型配置，或切换到脱敏外发/完整外发。");
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

  const handleProviderChange = (providerId: string) => {
    if (!config) return;
    syncConfigForm(config, providerId);
    setConfigMessage("");
  };

  const handleSaveConfig = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSavingConfig(true);
    setConfigMessage("");
    try {
      const nextConfig = await updateLLMConfig({
        provider: selectedProviderId,
        api_key: apiKey,
        model,
        base_url: baseUrl
      });
      syncConfigForm(nextConfig, selectedProviderId);
      setConfigMessage("已保存到本地 .env");
    } catch (error) {
      setConfigMessage(error instanceof Error ? error.message : "模型配置保存失败");
    } finally {
      setSavingConfig(false);
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
          <div className="settings-menu">
            <button
              aria-expanded={settingsOpen}
              aria-label="模型配置"
              className={`settings-trigger ${providerConfigured ? "ready" : "needs-config"}`}
              title="模型配置"
              type="button"
              onClick={() => setSettingsOpen((open) => !open)}
            >
              <Settings aria-hidden="true" size={19} />
            </button>
            {settingsOpen ? (
              <section className="settings-popover" aria-label="Model configuration">
                <header className="settings-title">
                  <div>
                    <strong>模型配置</strong>
                    <span>{selectedProvider ? providerStatusText(selectedProvider) : "读取中"}</span>
                  </div>
                  <button
                    aria-label="关闭模型配置"
                    className="close-settings-button"
                    title="关闭"
                    type="button"
                    onClick={() => setSettingsOpen(false)}
                  >
                    <X aria-hidden="true" size={17} />
                  </button>
                </header>
                <form className="settings-form" onSubmit={handleSaveConfig}>
                  <label>
                    <span>服务商</span>
                    <select value={selectedProviderId} onChange={(event) => handleProviderChange(event.target.value)}>
                      {config?.providers.map((provider) => (
                        <option key={provider.id} value={provider.id}>
                          {provider.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    <span>API Key</span>
                    <div className="key-input">
                      <KeyRound aria-hidden="true" size={16} />
                      <input
                        autoComplete="off"
                        placeholder={providerConfigured ? "保持当前 API key" : "输入 API key"}
                        type="password"
                        value={apiKey}
                        onChange={(event) => setApiKey(event.target.value)}
                      />
                    </div>
                  </label>
                  <label>
                    <span>模型</span>
                    <input value={model} onChange={(event) => setModel(event.target.value)} />
                  </label>
                  <label>
                    <span>Base URL</span>
                    <input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} />
                  </label>
                  <button className="save-config-button" disabled={!config || savingConfig} type="submit">
                    <Save aria-hidden="true" size={16} />
                    <span>{savingConfig ? "保存中" : "保存"}</span>
                  </button>
                </form>
                <div className={`config-state ${providerConfigured ? "ready" : "empty"}`}>
                  <CheckCircle2 aria-hidden="true" size={16} />
                  <span>{configMessage || (selectedProvider?.api_key_env ?? "未读取配置")}</span>
                </div>
              </section>
            ) : null}
          </div>
        </div>
      </header>

      <section className="workspace">
        <aside className="left-rail" aria-label="Job command center">
          <section className="mission-panel">
            <p className="eyebrow">JOB SEARCH WORKBENCH / CHINA MARKET</p>
            <h1>从岗位发现到 Offer 的行动工作台</h1>
            <p>
              本地组织简历、JD、公司资料和投递上下文；外部模型和平台连接只在用户看清数据边界后执行。
            </p>
          </section>

          <section className="privacy-panel" aria-label="privacy mode">
            <div className="section-title">
              <LockKeyhole aria-hidden="true" size={18} />
              <div>
                <strong>外发控制台</strong>
                <span>{egressSummary.detail}</span>
              </div>
            </div>
            <div className="privacy-options">
              {PRIVACY_MODES.map((mode) => (
                <button
                  className={`privacy-option ${privacyMode === mode.id ? "active" : ""}`}
                  key={mode.id}
                  title={mode.description}
                  type="button"
                  onClick={() => setPrivacyMode(mode.id)}
                >
                  <span>{mode.label}</span>
                </button>
              ))}
            </div>
            <p>{selectedPrivacyMode.description}</p>
          </section>

          <section className="chain-panel" aria-label="job chain">
            <div className="section-title">
              <Workflow aria-hidden="true" size={18} />
              <div>
                <strong>求职链路</strong>
                <span>Agent 负责判断与草稿，高影响动作由用户确认。</span>
              </div>
            </div>
            <ol className="chain-list">
              {WORKFLOW_STAGES.map((stage, index) => (
                <li className={index === 2 ? "active" : ""} key={stage}>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <strong>{stage}</strong>
                </li>
              ))}
            </ol>
          </section>

          <section className="surface-panel" aria-label="skills and mcps">
            <div className="section-title">
              <Network aria-hidden="true" size={18} />
              <div>
                <strong>Skills / MCP 边界</strong>
                <span>本地优先，连接器授权后再行动。</span>
              </div>
            </div>
            <div className="skill-grid">
              {SKILL_SURFACE.map((skill) => (
                <article key={skill.name}>
                  <span>{skill.name}</span>
                  <p>{skill.target}</p>
                </article>
              ))}
            </div>
          </section>
        </aside>

        <section className="workbench-panel" aria-label="Agent workspace">
          <header className="panel-head">
            <div>
              <p className="eyebrow">CURRENT LOOP / RESUME + JD</p>
              <h2>先跑通可信诊断，再进入投递与面试行动。</h2>
            </div>
            <button className="sample-button" type="button" onClick={loadDemoPrompt}>
              <ClipboardList aria-hidden="true" size={16} />
              <span>加载演示材料</span>
            </button>
          </header>

          <div className="context-strip" aria-label="missing context">
            <span className="context-label">缺失上下文</span>
            <div>
              {missing.length ? missing.map((item) => <span key={item}>{item}</span>) : <span>上下文已满足报告生成要求</span>}
            </div>
          </div>

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
            <label className="composer-label" htmlFor="job-context">
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
              <button className="send-button" disabled={!canSend} type="submit">
                <span>{pending ? "处理中" : "生成可信闭环"}</span>
                <Send aria-hidden="true" size={17} />
              </button>
            </div>
          </form>
        </section>

        <section className="report-panel" aria-label="Sprint report">
          {!report ? <EmptyReport /> : <ReportView report={report} onDownload={downloadMarkdown} />}
        </section>
      </section>
    </main>
  );
}

function providerStatusText(provider: LLMProviderConfig) {
  return provider.configured ? `${provider.name} 已配置 · ${provider.api_key_mask}` : `${provider.name} 未配置`;
}

function privacyEgressSummary(mode: PrivacyModeId, provider: LLMProviderConfig | null, providerConfigured: boolean) {
  if (mode === "local") {
    return {
      short: "纯本地模式 · 禁止外部模型",
      detail: providerConfigured ? "当前已配置模型，发送会被阻止。" : "当前未配置模型，报告仅使用本地确定性逻辑。"
    };
  }
  if (!providerConfigured) {
    return {
      short: "本地会话 · 模型未配置",
      detail: "当前不会调用外部模型；配置 API Key 后才会启用模型增强。"
    };
  }
  if (mode === "redacted") {
    return {
      short: `脱敏外发 · ${provider?.name ?? "模型服务商"}`,
      detail: `点击发送后，会把脱敏后的文本上下文发送给 ${provider?.name ?? "当前模型服务商"}。`
    };
  }
  return {
    short: `完整外发 · ${provider?.name ?? "模型服务商"}`,
    detail: `点击发送后，会把完整文本上下文发送给 ${provider?.name ?? "当前模型服务商"}。`
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

function EmptyReport() {
  return (
    <div className="empty-report">
      <div className="empty-mark" aria-hidden="true">
        <FileText size={30} />
      </div>
      <p className="eyebrow">WAITING FOR TRUSTED LOOP</p>
      <h2>等待首个求职诊断</h2>
      <p>
        发送简历和目标 JD 后，这里会生成一份可行动报告：匹配差距、简历改写、投递话术、面试冲刺和下一步 Pipeline。
      </p>
      <div className="empty-grid">
        <span>JD 匹配</span>
        <span>简历证据</span>
        <span>投递草稿</span>
        <span>面试冲刺</span>
      </div>
    </div>
  );
}

function ReportView({ report, onDownload }: { report: SprintReport; onDownload: () => void }) {
  const drafts = applicationDrafts(report);
  return (
    <div className="report">
      <header className="report-head">
        <div className="score-block">
          <span>Job Fit Readiness</span>
          <strong>{report.readiness_score}</strong>
          <small>/100</small>
        </div>
        <div className="report-head-copy">
          <p className="eyebrow">DIAGNOSIS / {roleLabel(report.role)}</p>
          <h2>{report.summary}</h2>
          <div className="metric-row">
            <span>{report.readiness_band}</span>
            <span>证据覆盖率 {(report.evidence_coverage * 100).toFixed(0)}%</span>
            <span>信心 {report.confidence}</span>
          </div>
        </div>
        <button className="download-button" type="button" onClick={onDownload}>
          <Download aria-hidden="true" size={17} />
          <span>导出 Markdown</span>
        </button>
      </header>

      <section className="report-section">
        <div className="section-kicker">
          <Gauge aria-hidden="true" size={17} />
          <span>JD 匹配差距</span>
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

      <section className="report-section">
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

      <section className="report-section">
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

      <section className="report-section">
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

      <section className="report-section">
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
                <small>{day.minutes} 分钟 · {day.done_criteria}</small>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="report-section">
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
    </div>
  );
}
