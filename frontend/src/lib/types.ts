// Tipos espelhados dos schemas Pydantic do backend.

export type Role = "GP" | "PMO" | "CLIENT" | "OPERATOR";

export interface User {
  id: string;
  name: string;
  email: string;
  role: Role;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in_s: number;
  user: User;
}

export type ProjectStatus = "active" | "paused" | "closed";

export interface Project {
  id: string;
  name: string;
  client_name: string;
  description: string | null;
  gp_user_id: string;
  client_user_id: string | null;
  status: ProjectStatus;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
}

export type ProposalStatus =
  | "pending_extraction"
  | "extracted"
  | "needs_ocr"
  | "superseded"
  | "extraction_failed";

export interface Proposal {
  id: string;
  project_id: string;
  version: number;
  file_url: string;
  original_filename: string;
  size_bytes: number;
  status: ProposalStatus;
  uploaded_by_id: string;
  uploaded_at: string;
}

export type DeliverableComplexity = "low" | "medium" | "high";

export interface Deliverable {
  id: string;
  code: string | null;
  title: string;
  description: string | null;
  phase: string | null;
  category: string | null;
  complexity: DeliverableComplexity | null;
  source_excerpt: string | null;
  due_date: string | null;
  order_index: number;
}

export type BaselineStatus = "draft" | "active" | "superseded";

export interface BaselineAudit {
  source_proposal_filename?: string;
  source_proposal_version?: number;
  extracted_at?: string;
  engine?: string;
  route?: string;
  confidence_score?: number;
}

export interface Baseline {
  id: string;
  project_id: string;
  proposal_id: string;
  status: BaselineStatus;
  activated_at: string | null;
  activated_by_id: string | null;
  payload: Record<string, unknown> & { audit?: BaselineAudit };
  created_at: string;
  deliverables: Deliverable[];
}

export type RAGStatus = "G" | "A" | "R";

export type ReportStatus =
  | "draft"
  | "submitted"
  | "pmo_approved"
  | "client_released"
  | "archived"
  | "needs_revision";

export type ProgressStatus = "planned" | "in_progress" | "done" | "blocked";
export type Severity = "low" | "medium" | "high" | "critical";
export type RiskStatus = "open" | "mitigated" | "closed";
export type ActionPlanStatus = "open" | "in_progress" | "done";
export type PendingItemStatus = "open" | "in_progress" | "resolved";

export interface DeliveryProgress {
  id?: string;
  deliverable_id: string;
  status: ProgressStatus;
  percent_complete: number;
  comment: string | null;
  revised_date?: string | null;
  deviation_flag?: boolean;
}

export interface Risk {
  id?: string;
  description: string;
  severity: Severity;
  owner_id: string | null;
  due_date: string | null;
  status: RiskStatus;
}

export interface ActionPlan {
  id?: string;
  description: string;
  owner_id: string | null;
  due_date: string | null;
  status: ActionPlanStatus;
}

export interface PendingItem {
  id?: string;
  description: string;
  owner_party: string | null;
  due_date: string | null;
  status: PendingItemStatus;
}

export interface Report {
  id: string;
  project_id: string;
  period_start: string;
  period_end: string;
  rag_status: RAGStatus | null;
  rag_prazo?: RAGStatus | null;
  rag_escopo?: RAGStatus | null;
  rag_qualidade?: RAGStatus | null;
  rag_prazo_justificativa?: string | null;
  rag_escopo_justificativa?: string | null;
  rag_qualidade_justificativa?: string | null;
  status: ReportStatus;
  highlights: string | null;
  next_steps: string | null;
  notes: string | null;
  health_score: number | null;
  created_by_id: string;
  created_at: string;
  submitted_at: string | null;
  approved_at: string | null;
  progresses: DeliveryProgress[];
  risks: Risk[];
  action_plans: ActionPlan[];
  pending_items: PendingItem[];
}

export interface ReportSummary {
  id: string;
  project_id: string;
  period_start: string;
  period_end: string;
  rag_status: RAGStatus | null;
  status: ReportStatus;
  created_at: string;
  submitted_at: string | null;
}
