export interface Product {
  id: string;
  name: string;
  description: string;
  price: number;
  category: string;
  merchant: string;
  image_url?: string;
  in_stock: boolean;
}

export interface Mandate {
  id: string;
  name: string;
  max_budget: number;
  allowed_merchants: string[];
  allowed_categories: string[];
  restrictions: string[];
  is_active: boolean;
  created_at: string;
  current_spend?: number;
}

export type ProposalStatus = 'pending' | 'approved' | 'rejected' | 'captured';

export interface Proposal {
  id: string;
  mandate_id: string;
  product_id: string | number;
  product_name: string;
  merchant: string;
  category: string;
  price: number | string;
  quantity: number;
  total_amount: number | string;
  ai_reasoning: string;
  status: ProposalStatus;
  created_at: string;
  approval_token?: string;
  idempotency_key?: string;
  paypal_order_id?: string;
  paypal_capture_id?: string;
  paypal_approval_url?: string;
}

export interface AuditLogEntry {
  id: string;
  event_type: 'MANDATE_CREATED' | 'MANDATE_UPDATED' | 'PROPOSAL_GENERATED' | 'POLICY_EVALUATED' | 'APPROVAL_GRANTED' | 'APPROVAL_REJECTED' | 'PAYMENT_CAPTURED' | string;
  entity_type: 'mandate' | 'proposal' | 'transaction' | 'policy' | string;
  entity_id: string;
  details: Record<string, unknown> | string;
  timestamp: string;
}

export interface PolicyResult {
  passed: boolean;
  violations: string[];
}

export interface ShoppingMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  proposal?: Proposal;
  policyResult?: PolicyResult;
}

export interface DashboardStats {
  activeMandates: number;
  pendingApprovals: number;
  totalTransactions: number;
  budgetRemaining: number;
  totalBudget: number;
}
