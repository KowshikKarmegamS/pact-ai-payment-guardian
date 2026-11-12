// Types mirror backend/app/schemas.py. Decimal values arrive as JSON strings.

export type DecimalString = string;

export interface Product {
  id: number;
  name: string;
  description: string;
  price: DecimalString;
  category: string;
  merchant: string;
  image_url?: string | null;
  in_stock: boolean;
  source: string;
  external_id?: string | null;
  brand?: string | null;
  purchase_url?: string | null;
  offer_checked_at?: string | null;
}

export interface MerchantConnector {
  id: string;
  name: string;
  platform: string;
  description: string;
  syncable: boolean;
  configured: boolean;
  searchable: boolean;
  products: number;
  in_stock: number;
  last_synced_at: string | null;
}

export interface AnalyticsPurchaseRow {
  purchase_id: string;
  day: string;
  created_at: string;
  product: string;
  merchant: string;
  category: string;
  agent: string;
  source: string;
  mandate: string;
  outcome: string;
  status: string;
  decided_by_policy: string;
  authorization: string;
  requested_amount: number;
  paid_amount: number;
  authorized_amount: number;
  blocked_amount: number;
  quantity: number;
  currency: string;
  ai_engine: string;
}

export interface AnalyticsDataset {
  purchases: AnalyticsPurchaseRow[];
}

export interface Channel3SearchResult {
  result: ConnectorSyncResult;
  products: Product[];
}

export interface RetailerHandoff {
  url: string;
  merchant: string;
  handed_off_at: string;
  payment_status: string;
  note: string;
}

export interface ConnectorSyncResult {
  connector_id: string;
  offers: number;
  created: number;
  updated: number;
  unchanged: number;
  delisted: number;
  skipped: string[];
  approvals_invalidated: number;
}

export interface MandateRestrictions {
  max_price_per_item?: number;
  min_price_per_item?: number;
  max_quantity?: number;
  prohibited_keywords?: string[];
  prohibited_merchants?: string[];
}

export type MandateStatus = 'active' | 'paused' | 'expired' | 'revoked';

export interface Mandate {
  id: string;
  name: string;
  max_budget: DecimalString;
  currency: string;
  allowed_merchants: string[];
  allowed_categories: string[];
  restrictions: MandateRestrictions;
  is_active: boolean;
  expires_at: string | null;
  revoked_at: string | null;
  authorization_mode: AuthorizationMode;
  max_auto_approve_amount: DecimalString | null;
  status: MandateStatus;
  created_at: string;
  updated_at: string;
  spent_budget: DecimalString;
  committed_budget: DecimalString;
  remaining_budget: DecimalString;
}

export interface MandateInput {
  name?: string;
  max_budget?: string;
  allowed_merchants?: string[];
  allowed_categories?: string[];
  restrictions?: MandateRestrictions;
  is_active?: boolean;
  expires_at?: string | null;
  authorization_mode?: AuthorizationMode;
  max_auto_approve_amount?: string | null;
}

export type AuthorizationMode = 'approval_required' | 'auto_approve_within_limits';
export type AuthorizationDecision = 'AUTO_APPROVE' | 'REQUIRES_APPROVAL' | 'BLOCKED';

export type ProposalStatus =
  | 'AWAITING_HUMAN_APPROVAL'
  | 'HUMAN_APPROVED'
  | 'AUTO_AUTHORIZED'
  | 'AWAITING_PAYPAL_BUYER_APPROVAL'
  | 'PAYPAL_BUYER_APPROVED'
  | 'CAPTURE_PENDING'
  | 'CAPTURED'
  | 'POLICY_REJECTED'
  | 'HUMAN_REJECTED'
  | 'PAYPAL_CANCELLED'
  | 'PAYMENT_FAILED'
  | 'APPROVAL_EXPIRED';

export interface PolicyCheck {
  rule: string;
  label: string;
  passed: boolean;
  detail: string;
  actual?: string | null;
  limit?: string | null;
}

export interface PolicyResult {
  passed: boolean;
  violations: string[];
  checks: PolicyCheck[];
  remaining_budget?: DecimalString | null;
  currency?: string | null;
}

export interface Alternative {
  product_id: number;
  name: string;
  merchant: string;
  category: string;
  price: DecimalString;
  in_stock: boolean;
  eligible: boolean;
  blocking: string[];
}

export interface Proposal {
  id: string;
  mandate_id: string;
  product_id: number;
  product_name: string;
  merchant: string;
  category: string;
  price: DecimalString;
  quantity: number;
  total_amount: DecimalString;
  currency: string;
  status: ProposalStatus;
  status_reason?: string | null;
  user_prompt?: string | null;
  ai_reasoning?: string | null;
  ai_provider?: string | null;
  ai_model?: string | null;
  ai_fallback_reason?: string | null;
  supersedes_id?: string | null;
  agent_id?: string | null;
  agent_name?: string | null;
  offer_source?: string | null;
  offer_external_id?: string | null;
  purchase_url?: string | null;
  retailer_handoff_at?: string | null;
  authorization_decision?: AuthorizationDecision | null;
  decision_reason?: string | null;
  authorized_by?: 'mandate' | 'owner' | null;
  budget_reserved_at?: string | null;
  alternatives?: Alternative[] | null;
  policy_checks?: PolicyCheck[] | null;
  remaining_budget_at_decision?: DecimalString | null;
  proposal_fingerprint?: string | null;
  approval_fingerprint?: string | null;
  approved_at?: string | null;
  idempotency_key: string;
  paypal_order_id?: string | null;
  paypal_order_status?: string | null;
  paypal_approval_url?: string | null;
  paypal_capture_id?: string | null;
  paypal_capture_status?: string | null;
  captured_amount?: DecimalString | null;
  captured_currency?: string | null;
  captured_at?: string | null;
  paypal_debug_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AuditLogEntry {
  id: number;
  event_type: string;
  entity_type: string;
  entity_id: string;
  details: Record<string, unknown>;
  timestamp: string;
}

export interface AIProvenance {
  provider: string;
  model: string | null;
  fallback_reason: string | null;
  ignored_fields?: string[] | null;
}

export interface ProposalGenerationResponse {
  proposal: Proposal;
  policy: PolicyResult;
  ai: AIProvenance;
  message: string;
}

export interface PayPalOrderResponse {
  order_id: string;
  approve_url: string;
  reused: boolean;
  proposal: Proposal;
}

export interface PaymentStateResponse {
  proposal: Proposal;
  paypal_order_status: string | null;
  capture_id: string | null;
  capture_status: string | null;
  message: string;
}

export interface ReceiptMandate {
  id: string;
  name: string;
  is_active: boolean;
  status: MandateStatus;
  expires_at: string | null;
  max_budget: DecimalString;
  currency: string;
  allowed_merchants: string[];
  allowed_categories: string[];
  restrictions: MandateRestrictions;
}

export interface ReceiptBudget {
  max_budget: DecimalString;
  spent: DecimalString;
  committed_other: DecimalString;
  available: DecimalString;
  this_purchase: DecimalString;
  remaining_after: DecimalString;
  counted: boolean;
}

export interface AuthorizationReceipt {
  proposal: Proposal;
  product: Product | null;
  budget: ReceiptBudget | null;
  mandate: ReceiptMandate;
  decision: 'BLOCKED' | 'AUTHORIZED';
  decision_checks: PolicyCheck[];
  revalidation_checks: PolicyCheck[] | null;
  revalidated_at: string | null;
  integrity: {
    proposal_fingerprint: string | null;
    approval_fingerprint: string | null;
    current_fingerprint: string;
    intact: boolean;
    changes: string[];
  };
  timeline: AuditLogEntry[];
}

export interface ProductUpdateResult {
  product: Product;
  approvals_invalidated: number;
}

export interface SystemStatus {
  ai: {
    mode: 'gemini' | 'openai' | 'heuristic';
    model: string | null;
    requested_provider: string;
    gemini_key_configured: boolean;
    openai_key_configured: boolean;
    api_key_configured: boolean;
    note: string | null;
  };
  paypal: {
    environment: string;
    api_host: string;
    sandbox_enforced: boolean;
    credentials_configured: boolean;
    currency: string;
    return_base_url: string;
    oauth: { checked: boolean; ok?: boolean; code?: string; message?: string };
  };
  currency: string;
}

export interface ConnectedAgent {
  id: string;
  name: string;
  description?: string | null;
  key_prefix: string;
  mandate_ids: string[];
  mandate_names: string[];
  status: 'active' | 'revoked';
  created_at: string;
  last_used_at?: string | null;
  revoked_at?: string | null;
  requests: number;
  blocked: number;
  awaiting_approval: number;
  captured: number;
}

export interface ConnectedAgentCreated extends ConnectedAgent {
  /** Shown once; PACT stores only its hash. */
  api_key: string;
}

export interface OwnerSession {
  auth_enabled: boolean;
  authenticated: boolean;
  misconfigured: boolean;
}
