import { Activity, Download, FileText, Send, ShieldCheck, Upload } from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { createSession, sendMessage } from "./api";
import { ChatLine, SprintReport, StreamEvent } from "./types";

export function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [lines, setLines] = useState<ChatLine[]>([]);
  const [draft, setDraft] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [pending, setPending] = useState(false);
  const [report, setReport] = useState<SprintReport | null>(null);
  const [missing, setMissing] = useState<string[]>([]);
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
  }, []);

  const canSend = useMemo(() => Boolean(sessionId && !pending && (draft.trim() || files.length)), [draft, files, pending, sessionId]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!sessionId || !canSend) return;

    const outgoing = [draft.trim(), files.map((file) => file.name).join("、")].filter(Boolean).join("\n");
    setLines((prev) => [...prev, { id: crypto.randomUUID(), role: "user", text: outgoing }]);
    setPending(true);
    setDraft("");
    const selected = files;
    setFiles([]);
    if (fileRef.current) fileRef.current.value = "";

    try {
      await sendMessage(sessionId, draft, selected, handleStreamEvent);
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
      <header className="topbar">
        <div className="brand">
          <Activity aria-hidden="true" size={22} />
          <div>
            <strong>SprintDuckAgent</strong>
            <span>开源求职冲刺教练</span>
          </div>
        </div>
        <div className="privacy-note">
          <ShieldCheck aria-hidden="true" size={18} />
          <span>本地会话 · 默认不持久化</span>
        </div>
      </header>

      <section className="workspace">
        <section className="chat-panel" aria-label="Agent chat">
          <header className="panel-head">
            <div>
              <p>Agent Intake</p>
              <h1>用对话生成证据化冲刺报告</h1>
            </div>
          </header>

          <div className="missing-strip" aria-label="missing context">
            {missing.length ? missing.map((item) => <span key={item}>{item}</span>) : <span>上下文已满足报告生成要求</span>}
          </div>

          <div className="transcript">
            {lines.map((line) => (
              <article className={`bubble ${line.role}`} key={line.id}>
                <p>{line.text}</p>
              </article>
            ))}
            {pending ? (
              <article className="bubble status">
                <p>Agent 正在处理...</p>
              </article>
            ) : null}
          </div>

          <form className="composer" onSubmit={handleSubmit}>
            <textarea
              placeholder="粘贴简历、JD、面试日期、每天可投入时间或当前阶段。"
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
                <Send aria-hidden="true" size={17} />
                <span>{pending ? "发送中" : "发送"}</span>
              </button>
            </div>
          </form>
        </section>

        <section className="report-panel" aria-label="Sprint report">
          {!report ? (
            <div className="empty-report">
              <FileText aria-hidden="true" size={34} />
              <h2>等待报告生成</h2>
              <p>报告会展示准备度、证据覆盖率、Top Gaps、1-7 天冲刺计划和高频追问。</p>
            </div>
          ) : (
            <ReportView report={report} onDownload={downloadMarkdown} />
          )}
        </section>
      </section>
    </main>
  );
}

function ReportView({ report, onDownload }: { report: SprintReport; onDownload: () => void }) {
  return (
    <div className="report">
      <header className="report-head">
        <div>
          <p>Readiness</p>
          <h2>{report.readiness_score}/100</h2>
          <span>{report.readiness_band} · 证据覆盖率 {(report.evidence_coverage * 100).toFixed(0)}%</span>
        </div>
        <button className="download-button" type="button" onClick={onDownload}>
          <Download aria-hidden="true" size={17} />
          <span>Markdown</span>
        </button>
      </header>

      <section className="summary-block">
        <h3>总结</h3>
        <p>{report.summary}</p>
      </section>

      <section className="section-block">
        <h3>Top Gaps</h3>
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

      <section className="section-block">
        <h3>冲刺计划</h3>
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

      <section className="section-block">
        <h3>高频追问</h3>
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

