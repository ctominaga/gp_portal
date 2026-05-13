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

// spec v3.1 §4.2.2 + prompt v1 §3 — 5 níveis PT-BR (alinhado ao backend após F5.1)
export type DeliverableComplexity =
  | "baixa"
  | "baixa-media"
  | "media"
  | "media-alta"
  | "alta";

// spec v3.1 §4.2.2 + prompt v1 §3 — 9 tipos (alinhado ao schema ProposalExtraction)
export type DeliverableType =
  | "code_migration"
  | "documentation"
  | "knowledge_transfer"
  | "stabilization"
  | "deliverable_software"
  | "assessment"
  | "model"
  | "infrastructure"
  | "other";

// spec v3.1 + prompt v1 — 5 categorias PT-BR
export type DeliverableCategory =
  | "tecnico"
  | "tecnico-regulatorio"
  | "negocio"
  | "transversal"
  | "governanca";

// spec v3.1 §6.4.1 — ciclo de vida (auto-promovido para CONCLUDED via cross-model)
export type DeliverableStatus =
  | "not_started"
  | "in_progress"
  | "concluded"
  | "blocked";

export interface Deliverable {
  id: string;
  code: string | null;
  title: string;
  description: string | null;
  phase: string | null;
  category: DeliverableCategory | null;
  complexity: DeliverableComplexity | null;
  type: DeliverableType | null;
  source_excerpt: string | null;
  due_date: string | null;
  // spec v3.1 §4.2.2 + §6.4.1 — novos em F5.1
  acceptance_criteria: string | null;
  dependencies: string[];
  status: DeliverableStatus;
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
  /** F5.4 — true quando entregue como placeholder pelo prepopulate. */
  is_prepopulated?: boolean;
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
  /** F5.4 — true quando herdado do report anterior. Backend zera ao editar. */
  is_prepopulated?: boolean;
}

export interface ActionPlan {
  id?: string;
  description: string;
  // spec v3.1 §4.2.4 — "Objetivo: por que essa ação foi criada"
  objective: string;
  owner_id: string | null;
  due_date: string | null;
  status: ActionPlanStatus;
  // Vinculações opcionais e independentes (spec v3.1 §4.2.4).
  linked_risk_id?: string | null;
  linked_deliverable_id?: string | null;
  // Expansão preenchida pelo backend em GET /reports/{id} para exibir
  // descrição do vínculo na UI sem precisar de query adicional.
  linked_risk_description?: string | null;
  linked_deliverable_title?: string | null;
}

export interface PendingItem {
  id?: string;
  description: string;
  owner_party: string | null;
  due_date: string | null;
  status: PendingItemStatus;
  // spec v3.1 §4.2.5 — "se não resolvido, o que afeta"
  impact?: string | null;
  // spec v3.1 §4.2.5 — "Data de abertura: quando foi registrado".
  // Servido pelo backend como `created_at`; UI pode renderizar como "Aberto em".
  created_at?: string;
  /** F5.4 — true quando herdado do report anterior. Backend zera ao editar. */
  is_prepopulated?: boolean;
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
  /** F5.2 — total de ScopeChanges PROPOSED do projeto (badge no card). */
  pending_transitions_count: number;
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

export interface ChangedField {
  field: string;
  old: string | null;
  new: string | null;
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
  /** F5.2 commit 3 — presente em itens `changed`, lista campos divergentes. */
  changed_fields?: ChangedField[];
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

// F5.2 — versionamento de escopo (v3.1 §10.5)

export type ScopeChangeType = "added" | "removed" | "modified";
export type ScopeChangeStatus = "proposed" | "approved" | "rejected" | "implemented";

export interface ScopeChange {
  id: string;
  project_id: string;
  description: string;
  baseline_from_id: string | null;
  baseline_to_id: string | null;
  change_type: ScopeChangeType | null;
  deliverable_code: string | null;
  status: ScopeChangeStatus;
  requested_at: string;
  decided_at: string | null;
  approved_by_id: string | null;
}

export interface TransitionResult {
  baseline_id: string;
  baseline_status: string;
  decision: "approve" | "reject";
  scope_changes_count: number;
  decided_at: string;
  approved_by: string;
}

// F5.3 — Retrospectiva e encerramento de projeto (v3.1 §10.4)

export interface MaterializedRiskItem {
  risk_id: string;
  comment: string | null;
}

export interface ProjectRetrospective {
  id: string;
  project_id: string;
  delivered_vs_proposed: string;
  would_do_differently: string;
  client_feedback: string;
  materialized_risks: MaterializedRiskItem[];
  created_by_id: string;
  created_at: string;
}

export interface ProjectCloseResult {
  project_id: string;
  status: "closed";
  ended_at: string;
  retrospective: ProjectRetrospective;
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
