import React, { useState } from 'react';
import { Check, CheckCircle2, Copy, Fingerprint, ShieldAlert, ShieldCheck, Sparkles, X } from 'lucide-react';
import type { AuthorizationReceipt as Receipt, PolicyCheck } from '../types';
import { aiLabel, isAIProvider, dateTime, eventMeta, money, shortHash } from '../lib/format';
import { Badge, Mono, StatusBadge } from './ui';

const Row: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <div className="flex items-baseline justify-between gap-4 py-1.5 text-sm">
    <dt className="shrink-0 text-slate-500">{label}</dt>
    <dd className="min-w-0 text-right font-medium text-slate-900">{children}</dd>
  </div>
);

const Section: React.FC<{ title: string; children: React.ReactNode; className?: string; aside?: React.ReactNode }> = ({
  title,
  children,
  className = '',
  aside,
}) => (
  <section className={`rounded-lg border border-slate-200 bg-white p-4 ${className}`}>
    <div className="mb-2 flex items-center justify-between gap-2">
      <h4 className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{title}</h4>
      {aside}
    </div>
    {children}
  </section>
);

export const CheckList: React.FC<{ checks: PolicyCheck[] }> = ({ checks }) => (
  <ul className="divide-y divide-slate-100">
    {checks.map((c) => (
      <li key={c.rule} className="flex gap-3 py-2">
        <span
          className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full ${
            c.passed ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'
          }`}
          aria-label={c.passed ? 'passed' : 'failed'}
        >
          {c.passed ? <Check className="h-3 w-3" strokeWidth={3} /> : <X className="h-3 w-3" strokeWidth={3} />}
        </span>
        <div className="min-w-0">
          <p className={`text-sm font-medium ${c.passed ? 'text-slate-900' : 'text-red-800'}`}>{c.label}</p>
          <p className="text-xs text-slate-500">{c.detail}</p>
        </div>
      </li>
    ))}
  </ul>
);

const CopyHash: React.FC<{ value: string | null | undefined }> = ({ value }) => {
  const [copied, setCopied] = useState(false);
  if (!value) return <span className="text-slate-400">—</span>;
  return (
    <button
      type="button"
      title={value}
      onClick={() => {
        void navigator.clipboard?.writeText(value).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 1200);
        });
      }}
      className="inline-flex items-center gap-1 font-mono text-[12px] text-slate-700 hover:text-slate-950"
    >
      {shortHash(value)}
      {copied ? <Check className="h-3 w-3 text-emerald-600" /> : <Copy className="h-3 w-3 text-slate-400" />}
    </button>
  );
};

export const AuthorizationReceipt: React.FC<{ receipt: Receipt }> = ({ receipt }) => {
  const { proposal: p, mandate: m, integrity } = receipt;
  const blocked = receipt.decision === 'BLOCKED';
  const failed = receipt.decision_checks.filter((c) => !c.passed);
  const r = m.restrictions;
  const captured = p.status === 'CAPTURED';

  return (
    <div className="space-y-3">
      {/* Decision banner */}
      <div
        className={`flex flex-col gap-2 rounded-lg border px-4 py-3 sm:flex-row sm:items-center sm:justify-between ${
          blocked ? 'border-red-200 bg-red-50' : 'border-emerald-200 bg-emerald-50'
        }`}
      >
        <div className="flex items-center gap-3">
          {blocked ? <ShieldAlert className="h-5 w-5 text-red-600" /> : <ShieldCheck className="h-5 w-5 text-emerald-600" />}
          <div>
            <p className={`text-sm font-semibold ${blocked ? 'text-red-900' : 'text-emerald-900'}`}>
              {blocked
                ? `Blocked by the policy engine: ${failed.length} of ${receipt.decision_checks.length} rules failed`
                : `Authorized by the policy engine: all ${receipt.decision_checks.length} rules passed`}
            </p>
            <p className={`text-xs ${blocked ? 'text-red-700' : 'text-emerald-700'}`}>
              Deterministic code decided this, not the AI.{' '}
              {blocked
                ? 'No approval or payment is possible.'
                : p.approved_at
                  ? `A human approved this exact proposal on ${dateTime(p.approved_at)}.`
                  : 'A human must still approve.'}
            </p>
          </div>
        </div>
        <StatusBadge status={p.status} />
      </div>

      {p.status_reason && !blocked && (
        <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">{p.status_reason}</p>
      )}

      <div className="grid gap-3 lg:grid-cols-2">
        <Section title="Purchase">
          <dl>
            <Row label="Product">{p.product_name}</Row>
            <Row label="Merchant">{p.merchant}</Row>
            <Row label="Category">{p.category}</Row>
            <Row label="Unit price">{money(p.price, p.currency)}</Row>
            <Row label="Quantity">{p.quantity}</Row>
            <Row label="Total">
              <span className="text-base">{money(p.total_amount, p.currency)}</span>{' '}
              <span className="text-xs font-normal text-slate-500">{p.currency}</span>
            </Row>
            <Row label="Proposal ID">
              <Mono>{p.id}</Mono>
            </Row>
          </dl>
        </Section>

        <Section title="Spending mandate" aside={<Badge tone={m.is_active ? 'green' : 'slate'}>{m.is_active ? 'Active' : 'Paused'}</Badge>}>
          <dl>
            <Row label="Mandate">{m.name}</Row>
            <Row label="Budget">{money(m.max_budget, m.currency)}</Row>
            <Row label="Remaining at decision">{p.remaining_budget_at_decision != null ? money(p.remaining_budget_at_decision, m.currency) : '—'}</Row>
            {r.max_price_per_item != null && <Row label="Max unit price">{money(r.max_price_per_item, m.currency)}</Row>}
            {r.max_quantity != null && <Row label="Max quantity">{r.max_quantity}</Row>}
          </dl>
          <div className="mt-2 space-y-1.5 text-xs">
            <p className="text-slate-500">
              Merchants: <span className="text-slate-800">{m.allowed_merchants.join(', ')}</span>
            </p>
            <p className="text-slate-500">
              Categories: <span className="text-slate-800">{m.allowed_categories.join(', ')}</span>
            </p>
            {!!r.prohibited_keywords?.length && (
              <p className="text-slate-500">
                Prohibited keywords: <span className="text-slate-800">{r.prohibited_keywords.join(', ')}</span>
              </p>
            )}
            {!!r.prohibited_merchants?.length && (
              <p className="text-slate-500">
                Blocked merchants: <span className="text-slate-800">{r.prohibited_merchants.join(', ')}</span>
              </p>
            )}
          </div>
        </Section>
      </div>

      <Section
        title="Policy rules evaluated"
        aside={
          <span className="text-xs text-slate-500">
            {receipt.decision_checks.length - failed.length}/{receipt.decision_checks.length} passed
          </span>
        }
      >
        <CheckList checks={receipt.decision_checks} />
        {receipt.revalidation_checks && receipt.revalidated_at && (
          <p className="mt-2 border-t border-slate-100 pt-2 text-xs text-slate-500">
            Last server revalidation {dateTime(receipt.revalidated_at)}:{' '}
            {receipt.revalidation_checks.every((c) => c.passed) ? (
              <span className="font-medium text-emerald-700">all rules still pass</span>
            ) : (
              <span className="font-medium text-red-700">
                {receipt.revalidation_checks.filter((c) => !c.passed).map((c) => c.label).join(', ')} failed
              </span>
            )}
          </p>
        )}
      </Section>

      <div className="grid gap-3 lg:grid-cols-2">
        <Section
          title="Approval integrity"
          aside={
            p.approval_fingerprint || !blocked ? (
              <Badge tone={integrity.intact ? 'green' : 'red'}>{integrity.intact ? 'Intact' : 'Changed'}</Badge>
            ) : null
          }
        >
          <dl>
            <Row label="Proposal fingerprint">
              <CopyHash value={integrity.proposal_fingerprint} />
            </Row>
            <Row label="Human approval">
              {p.approved_at ? (
                <span className="inline-flex items-center gap-1 text-emerald-700">
                  <CheckCircle2 className="h-3.5 w-3.5" /> {dateTime(p.approved_at)}
                </span>
              ) : (
                <span className="text-slate-400">{blocked ? 'Not possible (blocked)' : 'Not yet approved'}</span>
              )}
            </Row>
            <Row label="Approved fingerprint">
              <CopyHash value={integrity.approval_fingerprint} />
            </Row>
          </dl>
          {integrity.changes.length > 0 && (
            <ul className="mt-2 list-disc space-y-0.5 rounded-md bg-red-50 py-2 pl-7 pr-2 text-xs text-red-800">
              {integrity.changes.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          )}
          <p className="mt-2 flex items-start gap-1.5 text-[11px] text-slate-400">
            <Fingerprint className="mt-px h-3 w-3 shrink-0" />
            SHA-256 of the exact product, merchant, price, quantity, currency and mandate rules. Rechecked before order creation and capture.
          </p>
        </Section>

        <Section title="PayPal Sandbox">
          <dl>
            <Row label="Order ID">{p.paypal_order_id ? <Mono>{p.paypal_order_id}</Mono> : <span className="text-slate-400">Not created</span>}</Row>
            <Row label="PayPal order status">{p.paypal_order_status ?? <span className="text-slate-400">—</span>}</Row>
            <Row label="Capture ID">
              {p.paypal_capture_id ? <Mono>{p.paypal_capture_id}</Mono> : <span className="text-slate-400">None</span>}
            </Row>
            <Row label="Capture status">{p.paypal_capture_status ?? <span className="text-slate-400">—</span>}</Row>
            {captured && (
              <>
                <Row label="Captured amount">
                  {money(p.captured_amount, p.captured_currency ?? p.currency)} {p.captured_currency}
                </Row>
                <Row label="Captured at">{dateTime(p.captured_at)}</Row>
              </>
            )}
            {p.paypal_debug_id && (
              <Row label="PayPal debug ID">
                <Mono>{p.paypal_debug_id}</Mono>
              </Row>
            )}
          </dl>
        </Section>
      </div>

      <Section title="Recommendation source" aside={<Badge tone={isAIProvider(p.ai_provider) ? 'indigo' : 'slate'}>{aiLabel(p.ai_provider, p.ai_model)}</Badge>}>
        {p.user_prompt && (
          <p className="text-sm text-slate-700">
            <span className="text-slate-500">Request: </span>“{p.user_prompt}”
          </p>
        )}
        {p.ai_reasoning && (
          <p className="mt-1 flex gap-1.5 text-sm text-slate-700">
            <Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
            {p.ai_reasoning}
          </p>
        )}
        {p.ai_fallback_reason && <p className="mt-1 text-xs text-amber-700">Fallback reason: {p.ai_fallback_reason}</p>}
        <p className="mt-2 text-[11px] text-slate-400">
          Advisory only. Price, merchant and category come from the catalog; the decision comes from the policy engine.
        </p>
      </Section>

      <Section title="Lifecycle timeline">
        {receipt.timeline.length === 0 ? (
          <p className="text-xs text-slate-500">No events recorded.</p>
        ) : (
          <ol className="relative ml-1.5 border-l border-slate-200">
            {receipt.timeline.map((e) => {
              const meta = eventMeta(e.event_type);
              return (
                <li key={e.id} className="mb-2.5 ml-4 last:mb-0">
                  <span className="absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full border-2 border-white bg-slate-300" />
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                    <Badge tone={meta.tone}>{meta.label}</Badge>
                    <time className="text-xs text-slate-500">{dateTime(e.timestamp)}</time>
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </Section>
    </div>
  );
};

export default AuthorizationReceipt;
