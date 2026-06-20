// Shared types mirroring the SecureFlow FastAPI response models.

export type RiskTier = "LOW" | "MEDIUM" | "HIGH";
export type TxnStatus = "ALLOWED" | "STEP_UP" | "BLOCKED";
export type TxnType = "P2P" | "P2M" | "BILL_PAY";
export type Role = "ADMIN" | "ANALYST" | "VIEWER";

export interface AuthUser {
  id: string;
  email: string;
  vpa: string;
  role: Role;
  home_city: string;
  governance_access?: boolean;
}

export interface LoginResult {
  access_token: string | null;
  user: AuthUser;
  login_risk_score: number;
  login_risk_tier: RiskTier;
  step_up_required: boolean;
  challenge_id: string | null;
  demo_otp: string | null;
}

export interface RiskComponents {
  ml_fraud: number;
  anomaly: number;
  velocity: number;
  geo: number;
  new_device: number;
  amount: number;
  time: number;
}

export interface FeatureContribution {
  feature: string;
  value: number;
  importance: number;
}

export interface AnalyzeResult {
  id: string;
  from_vpa: string;
  to_vpa: string;
  amount_inr: number;
  txn_type: TxnType;
  risk_score: number;
  risk_tier: RiskTier;
  status: TxnStatus;
  ml_fraud_prob: number;
  anomaly_score: number;
  ml_confidence: number;
  components: RiskComponents;
  feature_contributions: FeatureContribution[];
  block_index: number | null;
  block_hash: string | null;
  recommended_action: string;
  created_at: string;
}

export interface TransactionSummary {
  id: string;
  from_vpa: string;
  to_vpa: string;
  amount_inr: number;
  txn_type: TxnType;
  risk_score: number;
  risk_tier: RiskTier;
  status: TxnStatus;
  block_hash: string | null;
  created_at: string;
}

export interface DashboardStats {
  total_transactions: number;
  fraud_detected: number;
  fraud_rate: number;
  average_risk_score: number;
  blocked_count: number;
  step_up_count: number;
  tier_distribution: Record<RiskTier, number>;
  daily_volume: { date: string; count: number; amount: number }[];
  risk_score_histogram: { range: string; count: number }[];
}

export interface Alert {
  transaction_id: string;
  from_vpa: string;
  to_vpa: string;
  amount_inr: number;
  risk_score: number;
  risk_tier: RiskTier;
  status: TxnStatus;
  created_at: string;
}

export interface Block {
  index: number;
  timestamp: number;
  transactions: Record<string, unknown>[];
  previous_hash: string;
  nonce: number;
  hash: string;
}

export interface ModelMetrics {
  accuracy: number;
  precision: number;
  recall: number;
  f1: number;
  auc_roc: number;
  cv_auc_mean: number;
  confusion_matrix: number[][];
  feature_importance: { feature: string; importance: number }[];
  n_train: number;
  n_test: number;
  trained_at: string;
  version: string;
}

// ── Multi-admin governance ────────────────────────────────────────────────────

export type ProposalStatus = "PENDING" | "APPLIED" | "REJECTED" | "DIVERGED";
export type VoteType = "APPROVE" | "REJECT";

export interface CouncilMember {
  id: string;
  name: string;
  email: string;
  vpa: string;
  role: Role;
}

export interface Council {
  members: CouncilMember[];
  size: number;
  threshold: string;
  demo_password: string;
}

export interface ProposalVoteItem {
  admin_id: string;
  vote: VoteType;
  diverged: boolean;
  attested_state_hash: string;
  created_at: string;
}

export interface ProposalTxn {
  from_vpa: string;
  to_vpa: string;
  amount_inr: number;
  risk_score: number;
  risk_tier: RiskTier;
  status: TxnStatus;
}

export interface Proposal {
  id: string;
  transaction_id: string;
  proposed_by: string;
  current_status: TxnStatus;
  proposed_status: TxnStatus;
  reason: string;
  status: ProposalStatus;
  required_approvals: number;
  approvals: number;
  rejects: number;
  diverged: boolean;
  block_index: number | null;
  block_hash: string | null;
  created_at: string;
  resolved_at: string | null;
  txn: ProposalTxn | null;
  votes?: ProposalVoteItem[];
}

export interface IntegrityState {
  status: string;
  risk_tier?: string;
  risk_score?: number;
}

export interface IntegrityResult {
  transaction_id: string;
  verified: boolean;
  tampered: boolean;
  current: IntegrityState;
  agreed: IntegrityState | null;
  reason?: string;
}

// ── UPI Simulation Lab ────────────────────────────────────────────────────────

export type UpiDecision = "APPROVED" | "STEP_UP" | "BLOCKED";

export interface UpiDemoUser {
  vpa: string;
  name: string;
  home_city: string;
  lat: number;
  lon: number;
  avg_transaction: number;
  risk_profile: string;
  known_device: string;
  seeded: boolean;
  last_risk_score: number | null;
}

export interface UpiScenario {
  id: string;
  name: string;
  emoji: string;
  description: string;
  expected_result: string;
  sender: string;
  receiver: string | null;
  amount: number | null;
  txn_type: string | null;
  city: string | null;
  rapid_fire: boolean;
}

export interface PipelineStage {
  status: string;
  timestamp: string;
  duration_ms: number;
  [k: string]: unknown;
}

export interface PipelineSnapshot {
  txn_id: string;
  stages: Record<string, PipelineStage>;
  stage_order: string[];
  total_duration_ms: number;
}

export interface UpiPayResult {
  txn_id: string;
  sender_vpa: string;
  receiver_vpa: string;
  amount_inr: number;
  txn_type: TxnType;
  note: string | null;
  decision: UpiDecision;
  decision_label: string;
  risk_score: number;
  risk_tier: RiskTier;
  ml_fraud_prob: number;
  anomaly_score: number;
  ml_confidence: number;
  components: RiskComponents;
  feature_contributions: FeatureContribution[];
  block_index: number | null;
  block_hash: string | null;
  recommended_action: string;
  total_duration_ms: number;
  pipeline: PipelineSnapshot;
  created_at: string;
  sequence?: number;
}

export interface UpiScenarioRun {
  scenario: UpiScenario;
  rapid_fire: boolean;
  result?: UpiPayResult;
  results?: UpiPayResult[];
  match?: boolean;
}

export interface UpiHistoryItem {
  id: string;
  from_vpa: string;
  to_vpa: string;
  amount_inr: number;
  txn_type: TxnType;
  risk_score: number;
  risk_tier: RiskTier;
  status: TxnStatus;
  block_index: number | null;
  block_hash: string | null;
  created_at: string;
}

export interface UpiHistory {
  vpa: string;
  transactions: UpiHistoryItem[];
}

export interface HealthStatus {
  status: string;
  version: string;
  redis: boolean;
  database: boolean;
  model_loaded: boolean;
  model_version: string | null;
  blockchain_blocks: number;
}
