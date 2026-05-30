export type RolePreset = "engineering" | "product" | "operations" | "generic";
export type ReadinessBand = "high" | "medium" | "low";

export interface EvidenceItem {
  source: "resume" | "jd" | "inference";
  text: string;
}

export interface GapItem {
  title: string;
  severity: "high" | "medium" | "low";
  evidence: EvidenceItem[];
  gap_reason: string;
  suggested_action: string;
}

export interface SprintPlanDay {
  day: number;
  focus: string;
  minutes: number;
  tasks: string[];
  linked_gap: string;
  done_criteria: string;
}

export interface InterviewQuestion {
  question: string;
  why_it_matters: string;
  linked_gap: string;
}

export interface SprintReport {
  role: RolePreset;
  readiness_score: number;
  readiness_band: ReadinessBand;
  evidence_coverage: number;
  confidence: "high" | "medium" | "low";
  summary: string;
  top_gaps: GapItem[];
  sprint_plan: SprintPlanDay[];
  interview_questions: InterviewQuestion[];
  markdown: string;
}

export interface SessionResponse {
  session_id: string;
  status: string;
  message: string;
  missing: string[];
}

export interface LLMProviderConfig {
  id: string;
  name: string;
  api_key_env: string;
  model_env: string;
  base_url_env: string;
  configured: boolean;
  api_key_mask: string;
  model: string;
  base_url: string;
}

export interface LLMConfigResponse {
  active_provider: string;
  providers: LLMProviderConfig[];
}

export interface UpdateLLMConfigPayload {
  provider: string;
  api_key?: string;
  model?: string;
  base_url?: string;
}

export interface StreamEvent {
  event: "status" | "assistant_delta" | "state" | "report" | "error" | "done";
  data: Record<string, unknown>;
}

export interface ChatLine {
  id: string;
  role: "user" | "assistant" | "status";
  text: string;
}
