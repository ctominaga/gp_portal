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

// Severity continua existindo para AIInsight.payload.severity (info/medium/high/critical).
// Para Risk usar RiskLevel (derivado de probability × impact) e enums dedicados.
export type Severity = "low" | "medium" | "high" | "critical";

// spec v3.1 §4.2.3 — eixos da matriz de risco
export type RiskProbability = "alta" | "media" | "baixa";
export type RiskImpact = "alto" | "medio" | "baixo";
export type RiskLevel = "low" | "medium" | "high" | "critical";
export type RiskStatus = "identified" | "monitoring" | "mitigated" | "materialized";

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
  // spec v3.1 §4.2.2 — confirmação do modal "Critério de aceite foi atingido?".
  // Obrigatório true quando status=done + percent_complete=100 (validado no backend).
  acceptance_confirmed?: boolean | null;
}

export interface Risk {
  id?: string;
  description: string;
  // spec v3.1 §4.2.3 — substitui `severity` único:
  probability: RiskProbability;
  impact: RiskImpact;
  // `level` é derivado no backend (Risk.level property). Frontend exibe read-only.
  level?: RiskLevel;
  mitigation_plan: string | null;
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

// ---- F4 ----

export type ApprovalStage = "pmo" | "client";
export type ApprovalDecisionValue =
  | "approved"
  | "approved_with_comment"
  | "requested_changes";

export interface ApprovalRecord {
  id: string;
  report_id: string;
  approver_id: string;
  stage: ApprovalStage;
  decision: ApprovalDecisionValue;
  comment: string | null;
  decided_at: string;
}

export interface AIInsight {
  id: string;
  scope: "project" | "portfolio";
  project_id: string | null;
  report_id: string | null;
  agent_run_id: string | null;
  payload: {
    kind?: string;
    severity?: string;
    headline?: string;
    detail?: string;
    evidence?: Record<string, unknown>;
    [k: string]: unknown;
  };
  created_at: string;
}

export type HealthBand = "green" | "amber" | "red";

export interface HealthScoreComponents {
  rag_avg: number;
  spi: number;
  risk_inverse: number;
  resolution_rate: number;
  stability: number;
}

export interface HealthScore {
  project_id: string;
  score: number;
  band: HealthBand;
  components: HealthScoreComponents;
  weights_applied?: Record<string, number> | null;
  last_report_id: string | null;
  last_report_period_end: string | null;
}

export interface PortfolioCard {
  project_id: string;
  project_name: string;
  client_name: string;
  gp_user_id: string;
  gp_name: string | null;
  health: HealthScore;
  last_report_rag: RAGStatus | null;
  open_risks_count: number;
  open_critical_alerts: number;
  pending_client_items: number;
}

export interface PortfolioOverview {
  projects: PortfolioCard[];
  total_projects: number;
  avg_health_score: number | null;
  counts_by_band: Record<HealthBand, number>;
}

export type HealthScoreWeightKey =
  | "rag_avg"
  | "spi"
  | "risk_inverse"
  | "resolution_rate"
  | "stability";

export type HealthScoreWeights = Record<HealthScoreWeightKey, number>;

export interface PortfolioConfig {
  health_score_weights: HealthScoreWeights;
  updated_at: string;
  updated_by_id: string | null;
}

export interface ClientReport {
  id: string;
  period_start: string;
  period_end: string;
  rag_status: RAGStatus | null;
  status: ReportStatus;
  highlights: string | null;
  next_steps: string | null;
  submitted_at: string | null;
  approved_at: string | null;
  pending_items: Array<{
    description: string;
    due_date: string | null;
    owner_party: string | null;
  }>;
}

export interface ClientProjectView {
  id: string;
  name: string;
  client_name: string;
  status: string;
  started_at: string | null;
  latest_rag: RAGStatus | null;
  health_score: number | null;
  open_pending_items: number;
  open_risks_count: number;
  reports: ClientReport[];
}

export interface BaselineDiffEntry {
  kind: "added" | "removed" | "changed";
  code: string | null;
  title_old: string | null;
  title_new: string | null;
  phase_old: string | null;
  phase_new: string | null;
  complexity_old: string | null;
  complexity_new: string | null;
}

export interface BaselineDiff {
  base_baseline_id: string;
  new_baseline_id: string;
  added: BaselineDiffEntry[];
  removed: BaselineDiffEntry[];
  changed: BaselineDiffEntry[];
  /** Apenas presente na resposta do worker (após criar ScopeChanges); GET é somente leitura. */
  scope_changes_created?: number;
}

export interface InAppNotification {
  id: string;
  kind: string;
  title: string;
  body: string | null;
  link: string | null;
  read_at: string | null;
  created_at: string;
}
