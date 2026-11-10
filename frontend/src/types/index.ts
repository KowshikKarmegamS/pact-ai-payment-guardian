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
}

export interface MandateRestrictions {
  max_price_per_item?: number;
  min_price_per_item?: number;
  max_quantity?: number;
  prohibited_keywords?: string[];
  prohibited_merchants?: string[];
}

export interface Mandate {
  id: string;
  name: string;
  max_budget: DecimalString;
  currency: string;
  allowed_merchants: string[];
  allowed_categories: string[];
  restrictions: MandateRestrictions;
  is_active: boolean;
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
}

export type ProposalStatus =
  | 'AWAITING_HUMAN_APPROVAL'
  | 'HUMAN_APPROVED'
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
}

export interface PolicyResult {
  passed: boolean;
  violations: string[];
  checks: PolicyCheck[];
  remaining_budget?: DecimalString | null;
  currency?: string | null;
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
  max_budget: DecimalString;
  currency: string;
  allowed_merchants: string[];
  allowed_categories: string[];
  restrictions: MandateRestrictions;
}

export interface AuthorizationReceipt {
  proposal: Proposal;
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

export interface SystemStatus {
  ai: {
    mode: 'openai' | 'heuristic';
    model: string | null;
    configured_model: string;
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
