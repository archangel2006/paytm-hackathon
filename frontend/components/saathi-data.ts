export type Merchant = {
  id: string;
  shop_name: string;
  owner_name: string;
  category: string;
  city: string;
  area: string;
  language: string;
  state: string;
  lead_score: number;
  fse_id: string | null;
  txn_count: number;
  successful_txn_count: number;
  docs_status: string;
  activation_eligible: boolean;
};

export type MerchantDetail = {
  id: string;
  shop_name: string;
  owner_name: string;
  category: string;
  city: string;
  area: string;
  language: string;
  state: string;
  lead_score: number;
  fse_id: string | null;
  pincode: string | null;
  phone_e164: string;
  preferred_channel: string;
  consent: boolean;
  footfall_score: number;
  score_explanation: string | null;
  state_updated_at: string | null;
  successful_txn_count: number;
  documents: Array<{
    id: string;
    doc_type: string;
    quality: string;
    precheck_passed: boolean;
    attempts: number;
    issues: string[];
    kyc_status: string;
    kyc_reference: string | null;
  }>;
  visits: Array<{
    id: string;
    slot_start: string;
    status: string;
    cluster_size: number;
  }>;
  device: { status: string; installed_at: string | null; first_txn_at: string | null } | null;
  settlement: { amount: number; expected_date: string; status: string; delay_reason: string | null } | null;
  tickets: Array<{ id: string; type: string; status: string; assigned_to: string; created_at: string }>;
};

export type Message = {
  id: string;
  direction: "in" | "out";
  channel: string;
  kind: string;
  text: string;
  intent: string | null;
  created_at: string;
};

export type AgentAction = {
  id: string;
  merchant_id: string;
  shop_name: string;
  action_type: string;
  autonomy_level: string;
  status: string;
  reasoning: string;
  confidence: number;
  source: string;
  guardrail_notes: string[];
  created_at: string;
  executed_at: string | null;
};

export type Handoff = {
  id: string;
  merchant_id: string;
  shop_name: string;
  target: string;
  reason: string;
  summary: Record<string, unknown> | string;
  status: string;
  resolution_note: string | null;
  created_at: string;
};

export type Scoreboard = {
  counters: {
    actions_executed: number;
    pending_approvals: number;
    blocked: number;
    handoffs_open: number;
  };
  funnel: Array<{ state: string; count: number }>;
  conversion_rate: number;
};

export type AutonomySettings = Record<
  string,
  { level: "L1" | "L2" | "L3"; updated_by: string; updated_at: string | null }
>;

export type Health = {
  status: string;
  database: string;
  llm_configured: boolean;
  whatsapp_configured: boolean;
};

export const stageLabels = [
  "NEW",
  "CONTACTED",
  "ENGAGED",
  "DOCS_PENDING",
  "DOCS_VERIFIED",
  "VISIT_SCHEDULED",
  "INSTALLED",
  "ACTIVATING",
  "ACTIVATED",
];

export const terminalMerchantStates = ["DORMANT", "LOST"];

export const label = (value: string) =>
  value.replace(/_/g, " ").toLowerCase().replace(/^./, (character) => character.toUpperCase());
