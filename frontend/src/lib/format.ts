import type { AuditLogEntry, MandateStatus, ProposalStatus } from '../types';

export function toNumber(value: string | number | null | undefined): number {
  if (value === null || value === undefined || value === '') return 0;
  const n = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(n) ? n : 0;
}

const moneyFormatters = new Map<string, Intl.NumberFormat>();

export function money(value: string | number | null | undefined, currency = 'USD'): string {
  const key = (currency || 'USD').toUpperCase();
  let f = moneyFormatters.get(key);
  if (!f) {
    try {
      f = new Intl.NumberFormat('en-US', { style: 'currency', currency: key, minimumFractionDigits: 2 });
    } catch {
      f = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    moneyFormatters.set(key, f);
  }
  return f.format(toNumber(value));
}

/** Backend timestamps from SQLite are naive UTC; mark them as UTC before parsing. */
export function parseDate(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const hasZone = /([zZ]|[+-]\d\d:?\d\d)$/.test(iso);
  const d = new Date(hasZone ? iso : `${iso}Z`);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function dateTime(iso: string | null | undefined): string {
  const d = parseDate(iso);
  return d ? d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—';
}

export function timeOnly(iso: string | null | undefined): string {
  const d = parseDate(iso);
  return d ? d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—';
}

export function dateOnly(iso: string | null | undefined): string {
  const d = parseDate(iso);
  return d ? d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : '—';
}

export function dayKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function timeAgo(iso: string | null | undefined): string {
  const d = parseDate(iso);
  if (!d) return '—';
  const s = Math.round((Date.now() - d.getTime()) / 1000);
  if (s < 45) return 'just now';
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
}

export function shortId(id: string | null | undefined, n = 8): string {
  if (!id) return '—';
  return id.length > n ? id.slice(0, n) : id;
}

export function shortHash(hash: string | null | undefined): string {
  if (!hash) return '—';
  return `${hash.slice(0, 8)}…${hash.slice(-6)}`;
}

export type Tone = 'ok' | 'bad' | 'warn' | 'info' | 'accent' | 'caution' | 'neutral';
export type StatusGroup = 'awaiting' | 'paypal' | 'captured' | 'blocked' | 'closed';

export interface StatusMeta {
  label: string;
  tone: Tone;
  group: StatusGroup;
  description: string;
}

export const STATUS_META: Record<ProposalStatus, StatusMeta> = {
  POLICY_REJECTED: { label: 'Blocked', tone: 'bad', group: 'blocked', description: 'The policy engine blocked this purchase.' },
  AWAITING_HUMAN_APPROVAL: { label: 'Awaiting approval', tone: 'warn', group: 'awaiting', description: 'Policy passed. Waiting for your explicit approval.' },
  HUMAN_APPROVED: { label: 'Approved', tone: 'accent', group: 'paypal', description: 'You approved. Ready for PayPal checkout.' },
  AWAITING_PAYPAL_BUYER_APPROVAL: { label: 'Awaiting PayPal', tone: 'info', group: 'paypal', description: 'PayPal order created. Waiting for the buyer in PayPal Checkout.' },
  PAYPAL_BUYER_APPROVED: { label: 'Buyer approved', tone: 'info', group: 'paypal', description: 'PayPal confirms buyer approval. Capture is available.' },
  CAPTURE_PENDING: { label: 'Capture pending', tone: 'warn', group: 'paypal', description: 'Capture requested; PayPal has not confirmed completion.' },
  CAPTURED: { label: 'Captured', tone: 'ok', group: 'captured', description: 'PayPal confirmed the capture.' },
  PAYMENT_FAILED: { label: 'Failed', tone: 'bad', group: 'closed', description: 'PayPal did not complete the payment.' },
  PAYPAL_CANCELLED: { label: 'Cancelled', tone: 'neutral', group: 'closed', description: 'The buyer cancelled PayPal checkout.' },
  HUMAN_REJECTED: { label: 'Rejected', tone: 'neutral', group: 'closed', description: 'You rejected this proposal.' },
  APPROVAL_EXPIRED: { label: 'Expired', tone: 'caution', group: 'closed', description: 'Something changed after evaluation. The approval is void.' },
};

export function statusMeta(status: string): StatusMeta {
  return STATUS_META[status as ProposalStatus] ?? { label: status, tone: 'neutral', group: 'closed', description: status };
}

export const MANDATE_STATUS: Record<MandateStatus, { label: string; tone: Tone }> = {
  active: { label: 'Active', tone: 'ok' },
  paused: { label: 'Paused', tone: 'warn' },
  expired: { label: 'Expired', tone: 'caution' },
  revoked: { label: 'Revoked', tone: 'bad' },
};

export function isAIProvider(provider?: string | null): boolean {
  return provider === 'gemini' || provider === 'openai';
}

export function aiLabel(provider?: string | null, model?: string | null): string {
  if (provider === 'gemini') return `Google Gemini · ${model ?? 'model'}`;
  if (provider === 'openai') return `OpenAI · ${model ?? 'model'}`;
  if (provider === 'heuristic') return 'Keyword fallback (not AI)';
  if (provider === 're-evaluation') return 'Re-evaluation (no AI call)';
  if (provider === 'user-selected') return 'Selected by you';
  if (provider === 'external-agent') return model ? `External agent · ${model}` : 'External agent via Agent Gateway';
  return 'Unknown source';
}

// ---------------------------------------------------------------------------
// Audit events: label, tone, category and a plain-language explanation.
// ---------------------------------------------------------------------------

export type EventCategory = 'mandate' | 'ai' | 'policy' | 'approval' | 'paypal' | 'catalog' | 'agent';

interface EventDef {
  label: string;
  tone: Tone;
  category: EventCategory;
  alert?: boolean;
}

const EVENTS: Record<string, EventDef> = {
  MANDATE_CREATED: { label: 'Mandate created', tone: 'accent', category: 'mandate' },
  MANDATE_UPDATED: { label: 'Mandate updated', tone: 'accent', category: 'mandate' },
  MANDATE_REVOKED: { label: 'Mandate revoked', tone: 'bad', category: 'mandate', alert: true },
  AI_RECOMMENDATION_GENERATED: { label: 'Recommendation generated', tone: 'neutral', category: 'ai' },
  PROPOSAL_CREATED_BY_USER: { label: 'Alternative selected by user', tone: 'neutral', category: 'ai' },
  POLICY_CHECK_PASSED: { label: 'Policy evaluation passed', tone: 'ok', category: 'policy' },
  POLICY_CHECK_FAILED: { label: 'Policy violation detected', tone: 'bad', category: 'policy', alert: true },
  PROPOSAL_HUMAN_APPROVED: { label: 'User approved purchase', tone: 'accent', category: 'approval' },
  PROPOSAL_HUMAN_REJECTED: { label: 'User rejected purchase', tone: 'neutral', category: 'approval' },
  APPROVAL_FINGERPRINT_MISMATCH: { label: 'Approval fingerprint mismatch', tone: 'bad', category: 'approval', alert: true },
  APPROVAL_INVALIDATED: { label: 'Approval invalidated', tone: 'caution', category: 'approval', alert: true },
  PROPOSAL_RE_EVALUATED: { label: 'Re-evaluated', tone: 'neutral', category: 'approval' },
  PAYPAL_ORDER_CREATED: { label: 'PayPal order created', tone: 'info', category: 'paypal' },
  PAYPAL_ORDER_FAILED: { label: 'PayPal order failed', tone: 'bad', category: 'paypal', alert: true },
  PAYPAL_CHECKOUT_CANCELLED: { label: 'Checkout cancelled', tone: 'neutral', category: 'paypal' },
  PAYPAL_CHECKOUT_REOPENED: { label: 'Checkout reopened', tone: 'info', category: 'paypal' },
  PAYPAL_BUYER_APPROVED: { label: 'PayPal checkout approved', tone: 'info', category: 'paypal' },
  PAYPAL_RETURN_TOKEN_MISMATCH: { label: 'Return token mismatch', tone: 'bad', category: 'paypal', alert: true },
  PAYPAL_ORDER_MISMATCH: { label: 'PayPal order mismatch', tone: 'bad', category: 'paypal', alert: true },
  CAPTURE_BLOCKED_NOT_APPROVED: { label: 'Capture blocked: buyer not approved', tone: 'caution', category: 'paypal', alert: true },
  PAYPAL_CAPTURE_ATTEMPTED: { label: 'Capture attempted', tone: 'info', category: 'paypal' },
  PAYPAL_PAYMENT_CAPTURED: { label: 'Payment captured', tone: 'ok', category: 'paypal' },
  PAYPAL_CAPTURE_PENDING: { label: 'Capture pending', tone: 'warn', category: 'paypal' },
  PAYPAL_CAPTURE_FAILED: { label: 'Capture failed', tone: 'bad', category: 'paypal', alert: true },
  PAYPAL_CAPTURE_UNCERTAIN: { label: 'Capture outcome unknown', tone: 'warn', category: 'paypal', alert: true },
  PAYPAL_CAPTURE_UNVERIFIED: { label: 'Capture unverified', tone: 'warn', category: 'paypal', alert: true },
  PAYPAL_CAPTURE_AMOUNT_MISMATCH: { label: 'Captured amount mismatch', tone: 'bad', category: 'paypal', alert: true },
  DUPLICATE_CAPTURE_PREVENTED: { label: 'Duplicate capture prevented', tone: 'ok', category: 'paypal', alert: true },
  AGENT_REGISTERED: { label: 'Agent connected', tone: 'accent', category: 'agent' },
  AGENT_REVOKED: { label: 'Agent access revoked', tone: 'bad', category: 'agent', alert: true },
  AGENT_PURCHASE_REQUESTED: { label: 'Agent requested a purchase', tone: 'neutral', category: 'agent' },
  AGENT_AUTHORITY_CHECKED: { label: 'Agent checked its authority', tone: 'neutral', category: 'agent' },
  AGENT_MANDATE_DENIED: { label: 'Agent used an ungranted mandate', tone: 'bad', category: 'agent', alert: true },
  CATALOG_PRODUCT_CHANGED: { label: 'Catalog price changed', tone: 'caution', category: 'catalog' },
  CONNECTOR_SYNCED: { label: 'Merchant connector synced', tone: 'info', category: 'catalog' },
  APPROVAL_REVALIDATION_FAILED: { label: 'Approval revalidation failed', tone: 'bad', category: 'approval', alert: true },
};

export function eventMeta(type: string): EventDef {
  return (
    EVENTS[type] ?? {
      label: type.replace(/_/g, ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase()),
      tone: 'neutral',
      category: type.startsWith('PAYPAL') ? 'paypal' : 'policy',
    }
  );
}

const str = (v: unknown): string | null => (typeof v === 'string' && v ? v : typeof v === 'number' ? String(v) : null);
const arr = (v: unknown): string[] => (Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : []);

/** One plain-language sentence describing what happened, built only from the stored event details. */
export function explainEvent(e: AuditLogEntry): string {
  const d = e.details ?? {};
  const cur = str(d.currency) ?? 'USD';
  const amount = str(d.total_amount) ?? str(d.amount);
  const product = str(d.product_name);
  switch (e.event_type) {
    case 'MANDATE_CREATED':
      return `Mandate “${str(d.name) ?? ''}” created with a ${money(str(d.max_budget), cur)} budget.`;
    case 'MANDATE_UPDATED':
      return `Mandate rules changed (${arr(d.updated_fields).join(', ').replace(/_/g, ' ') || 'fields'}). Open approvals were re-verified.`;
    case 'MANDATE_REVOKED':
      return `Mandate “${str(d.name) ?? ''}” permanently revoked; ${str(d.approvals_invalidated) ?? '0'} open approval(s) invalidated.`;
    case 'AI_RECOMMENDATION_GENERATED': {
      const who = aiLabel(str(d.provider), str(d.model));
      const fb = str(d.fallback_reason);
      return `${who} recommended catalog item #${str(d.product_id) ?? '?'} × ${str(d.quantity) ?? '1'}.${fb ? ` ${fb}` : ''}`;
    }
    case 'AGENT_REGISTERED':
      return `Agent “${str(d.agent_name) ?? ''}” connected to the Agent Gateway (key ${str(d.key_prefix) ?? ''}).`;
    case 'AGENT_REVOKED':
      return `Agent “${str(d.agent_name) ?? ''}” lost access; its key no longer works.`;
    case 'AGENT_PURCHASE_REQUESTED':
      return `${str(d.agent_name) ?? 'An agent'} asked for catalog item #${str(d.product_id) ?? '?'} × ${str(d.quantity) ?? '1'}: “${str(d.reason) ?? ''}”`;
    case 'AGENT_AUTHORITY_CHECKED':
      return `${str(d.agent_name) ?? 'An agent'} dry-ran ${money(amount, cur)}: ${d.allowed ? 'within policy' : `not allowed (${arr(d.violations)[0] ?? 'policy'})`}.`;
    case 'AGENT_MANDATE_DENIED':
      return `${str(d.agent_name) ?? 'An agent'} tried a mandate it was never granted. Refused.`;
    case 'PROPOSAL_CREATED_BY_USER':
      return `User chose catalog item #${str(d.product_id) ?? '?'} from the listed alternatives.`;
    case 'POLICY_CHECK_PASSED':
      return `All ${str(d.rules_evaluated) ?? ''} rules passed for ${product ?? 'the item'} (${money(amount, cur)}).`;
    case 'POLICY_CHECK_FAILED': {
      const v = arr(d.violations);
      return `${product ?? 'Purchase'} blocked: ${v[0] ?? 'policy violation'}${v.length > 1 ? ` (+${v.length - 1} more)` : ''}`;
    }
    case 'PROPOSAL_HUMAN_APPROVED':
      return `User approved ${money(amount, cur)} to ${str(d.merchant) ?? 'merchant'}, bound to fingerprint ${shortHash(str(d.approval_fingerprint))}.`;
    case 'PROPOSAL_HUMAN_REJECTED':
      return 'User rejected the purchase. No payment will be made.';
    case 'APPROVAL_INVALIDATED': {
      const reasons = [...arr(d.changes), ...arr(d.violations)];
      return `Approval voided before ${str(d.stage) ?? 'the next step'}: ${reasons[0] ?? 'the proposal no longer matches.'}`;
    }
    case 'PROPOSAL_RE_EVALUATED':
      return `A fresh proposal ${shortId(str(d.new_proposal_id))} was created and needs new approval.`;
    case 'PAYPAL_ORDER_CREATED':
      return `PayPal order ${str(d.paypal_order_id) ?? ''} created for ${money(amount, cur)}.`;
    case 'PAYPAL_BUYER_APPROVED':
      return `PayPal confirmed to the server that the buyer approved order ${str(d.paypal_order_id) ?? ''}.`;
    case 'PAYPAL_CAPTURE_ATTEMPTED':
      return `Order, approval fingerprint and policy re-verified; capture of ${money(amount, cur)} requested.`;
    case 'PAYPAL_PAYMENT_CAPTURED':
      return `PayPal capture ${str(d.paypal_capture_id) ?? ''} ${str(d.capture_status) ?? 'COMPLETED'} for ${money(amount, cur)}.`;
    case 'DUPLICATE_CAPTURE_PREVENTED':
      return 'A repeat capture request was answered from the stored result. PayPal was not called again.';
    case 'CAPTURE_BLOCKED_NOT_APPROVED':
      return `Capture refused: PayPal reports the order as ${str(d.paypal_status) ?? 'not approved'}.`;
    case 'PAYPAL_CHECKOUT_CANCELLED':
      return 'The buyer cancelled PayPal Checkout. Nothing was charged.';
    case 'CATALOG_PRODUCT_CHANGED': {
      const b = (d.before ?? {}) as Record<string, unknown>;
      const a = (d.after ?? {}) as Record<string, unknown>;
      return `${product ?? 'Product'} changed from ${money(str(b.price), cur)} to ${money(str(a.price), cur)}; ${str(d.approvals_invalidated) ?? '0'} approval(s) invalidated.`;
    }
    case 'CONNECTOR_SYNCED':
      return `${str(d.connector) ?? 'Connector'} synced: ${str(d.created) ?? '0'} new, ${str(d.updated) ?? '0'} changed, ${str(d.delisted) ?? '0'} delisted; ${str(d.approvals_invalidated) ?? '0'} approval(s) invalidated.`;
    default:
      return str(d.message) ?? str(d.code) ?? eventMeta(e.event_type).label;
  }
}
