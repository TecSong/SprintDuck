import { LLMConfigResponse, SessionResponse, StreamEvent } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

export async function createSession(): Promise<SessionResponse> {
  const response = await fetch(`${API_BASE}/api/chat/sessions`, { method: "POST" });
  if (!response.ok) throw new Error("无法创建会话");
  return response.json();
}

export async function getLLMConfig(): Promise<LLMConfigResponse> {
  const response = await fetch(`${API_BASE}/api/llm/config`);
  if (!response.ok) throw new Error("无法读取模型配置");
  return response.json();
}

export async function sendMessage(
  sessionId: string,
  message: string,
  files: File[],
  onEvent: (event: StreamEvent) => void
): Promise<void> {
  const formData = new FormData();
  formData.set("message", message);
  files.forEach((file) => formData.append("files", file));

  const response = await fetch(`${API_BASE}/api/chat/sessions/${sessionId}/messages`, {
    method: "POST",
    body: formData
  });
  if (!response.ok || !response.body) {
    const detail = await response.text();
    throw new Error(detail || "消息发送失败");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      const parsed = parseSse(part);
      if (parsed) onEvent(parsed);
    }
  }

  const parsed = parseSse(buffer);
  if (parsed) onEvent(parsed);
}

function parseSse(raw: string): StreamEvent | null {
  const lines = raw.split("\n");
  const eventLine = lines.find((line) => line.startsWith("event:"));
  const dataLine = lines.find((line) => line.startsWith("data:"));
  if (!eventLine || !dataLine) return null;
  return {
    event: eventLine.replace("event:", "").trim() as StreamEvent["event"],
    data: JSON.parse(dataLine.replace("data:", "").trim())
  };
}
