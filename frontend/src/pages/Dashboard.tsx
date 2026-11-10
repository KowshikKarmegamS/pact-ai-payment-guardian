import React, { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Bot, CreditCard, Scale, ShieldCheck, UserCheck } from 'lucide-react';
import { pactApi } from '../api/pact';
import type { AuditLogEntry, Mandate, Proposal } from '../types';
import { dateTime, eventMeta, money, statusMeta, timeAgo, toNumber } from '../lib/format';
import { useAsync } from '../lib/useAsync';
import { Badge, BudgetBar, Button, Card, CardHeader, EmptyState, ErrorState, PageHeader, RefreshButton, Spinner, StatusBadge } from '../components/ui';

const SECURITY_EVENTS = new Set([
  'POLICY_CHECK_FAILED',
  'POLICY_CHECK_PASSED',
  'PROPOSAL_HUMAN_APPROVED',
  'PROPOSAL_HUMAN_REJECTED',
  'APPROVAL_INVALIDATED',
  'APPROVAL_FINGERPRINT_MISMATCH',
  'PAYPAL_PAYMENT_CAPTURED',
  'PAYPAL_CAPTURE_FAILED',
  'PAYPAL_CAPTURE_AMOUNT_MISMATCH',
  'PAYPAL_ORDER_MISMATCH',
  'PAYPAL_RETURN_TOKEN_MISMATCH',
  'DUPLICATE_CAPTURE_PREVENTED',
  'CAPTURE_BLOCKED_NOT_APPROVED',
  'MANDATE_UPDATED',
]);

const FLOW = [
  { icon: Bot, title: 'AI recommends', text: 'Picks one catalog item. Advisory only.' },
  { icon: Scale, title: 'Code authorizes', text: 'Deterministic policy engine checks the mandate.' },
  { icon: UserCheck, title: 'Human approves', text: 'Approval is bound to the exact proposal.' },
  { icon: CreditCard, title: 'PayPal executes', text: 'Sandbox order, buyer approval, verified capture.' },
];

const Stat: React.FC<{ label: string; value: React.ReactNode; hint?: React.ReactNode }> = ({ label, value, hint }) => (
  <Card className="p-4">
    <p className="text-xs font-medium text-slate-500">{label}</p>
    <p className="mt-1 text-2xl font-semibold tracking-tight text-slate-900 tabular-nums">{value}</p>
    {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
  </Card>
);

export const Dashboard: React.FC = () => {
  const state = useAsync(async () => {
    const [mandates, proposals, audit] = await Promise.all([
      pactApi.getMandates(),
      pactApi.getProposals(),
      pactApi.getAuditLogs(100),
    ]);
    return { mandates, proposals, audit };
  });

  const metrics = useMemo(() => {
    if (!state.data) return null;
    const { mandates, proposals } = state.data;
    const active = mandates.filter((m: Mandate) => m.is_active);
    const currency = mandates[0]?.currency ?? proposals[0]?.currency ?? 'USD';
    const captured = proposals.filter((p: Proposal) => p.status === 'CAPTURED');
    return {
      currency,
      activeCount: active.length,
      totalMandates: mandates.length,
      remaining: active.reduce((s, m) => s + toNumber(m.remaining_budget), 0),
      allocated: active.reduce((s, m) => s + toNumber(m.max_budget), 0),
      pending: proposals.filter((p) => p.status === 'AWAITING_HUMAN_APPROVAL').length,
      inFlight: proposals.filter((p) => statusMeta(p.status).group === 'in_progress').length,
      capturedVolume: captured.reduce((s, p) => s + toNumber(p.captured_amount ?? p.total_amount), 0),
      capturedCount: captured.length,
      blocked: proposals.filter((p) => p.status === 'POLICY_REJECTED').length,
    };
  }, [state.data]);

  return (
    <div>
      <PageHeader
        title="Overview"
        description="Give AI the power to act, not unrestricted access to your money. Every number on this page comes from the PACT database."
        actions={<RefreshButton onClick={() => void state.reload()} loading={state.loading} />}
      />

      <Card className="mb-6 overflow-hidden">
        <div className="grid divide-y divide-slate-100 sm:grid-cols-4 sm:divide-x sm:divide-y-0">
          {FLOW.map((f, i) => (
            <div key={f.title} className="flex gap-3 p-4">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-900 text-white">
                <f.icon className="h-4 w-4" />
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-900">
                  <span className="mr-1 text-slate-400">{i + 1}.</span>
                  {f.title}
                </p>
                <p className="text-xs text-slate-500">{f.text}</p>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {state.error && <div className="mb-4"><ErrorState message={state.error} onRetry={() => void state.reload()} /></div>}
      {!state.data && state.loading && <Spinner />}

      {metrics && state.data && (
        <>
          <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-5">
            <Stat label="Active mandates" value={metrics.activeCount} hint={`${metrics.totalMandates} total`} />
            <Stat label="Remaining budget" value={money(metrics.remaining, metrics.currency)} hint={`of ${money(metrics.allocated, metrics.currency)} active`} />
            <Stat label="Awaiting your approval" value={metrics.pending} hint={`${metrics.inFlight} in PayPal flow`} />
            <Stat label="Captured volume" value={money(metrics.capturedVolume, metrics.currency)} hint={`${metrics.capturedCount} verified PayPal captures`} />
            <Stat label="Blocked by policy" value={metrics.blocked} hint="never reached approval" />
          </div>

          <div className="grid gap-5 lg:grid-cols-5">
            <div className="space-y-5 lg:col-span-3">
              <Card>
                <CardHeader
                  title="Recent proposals"
                  subtitle="Newest first"
                  action={
                    <Link to="/transactions" className="inline-flex items-center gap-1 text-xs font-semibold text-slate-600 hover:text-slate-900">
                      All transactions <ArrowRight className="h-3 w-3" />
                    </Link>
                  }
                />
                {state.data.proposals.length === 0 ? (
                  <EmptyState
                    title="No proposals yet"
                    description="Ask the Shopping Assistant for something to see the authorization pipeline in action."
                    action={
                      <Link to="/assistant">
                        <Button size="sm">Open assistant</Button>
                      </Link>
                    }
                  />
                ) : (
                  <ul className="divide-y divide-slate-100">
                    {state.data.proposals.slice(0, 6).map((p) => (
                      <li key={p.id} className="flex items-center justify-between gap-3 px-5 py-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-slate-900">{p.product_name}</p>
                          <p className="text-xs text-slate-500">
                            {p.merchant} · {timeAgo(p.created_at)}
                          </p>
                        </div>
                        <div className="flex shrink-0 items-center gap-3">
                          <span className="text-sm font-semibold tabular-nums text-slate-900">{money(p.total_amount, p.currency)}</span>
                          <StatusBadge status={p.status} />
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>

              <Card>
                <CardHeader title="Mandate budgets" subtitle="Green: captured · Amber: approved, not yet captured" />
                {state.data.mandates.length === 0 ? (
                  <EmptyState title="No mandates" />
                ) : (
                  <ul className="divide-y divide-slate-100">
                    {state.data.mandates.map((m) => (
                      <li key={m.id} className="space-y-2 px-5 py-3">
                        <div className="flex items-center justify-between gap-2">
                          <p className="truncate text-sm font-medium text-slate-900">{m.name}</p>
                          {m.is_active ? <Badge tone="green">Active</Badge> : <Badge tone="slate">Paused</Badge>}
                        </div>
                        <BudgetBar max={toNumber(m.max_budget)} spent={toNumber(m.spent_budget)} committed={toNumber(m.committed_budget)} />
                        <p className="text-xs text-slate-500 tabular-nums">
                          {money(m.remaining_budget, m.currency)} remaining of {money(m.max_budget, m.currency)}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </div>

            <Card className="lg:col-span-2">
              <CardHeader
                title="Security events"
                subtitle="Policy decisions, approvals, captures"
                action={
                  <Link to="/audit" className="inline-flex items-center gap-1 text-xs font-semibold text-slate-600 hover:text-slate-900">
                    Audit trail <ArrowRight className="h-3 w-3" />
                  </Link>
                }
              />
              {(() => {
                const events = state.data.audit.filter((a: AuditLogEntry) => SECURITY_EVENTS.has(a.event_type)).slice(0, 10);
                if (!events.length) return <EmptyState title="No events yet" />;
                return (
                  <ul className="divide-y divide-slate-100">
                    {events.map((e) => {
                      const meta = eventMeta(e.event_type);
                      return (
                        <li key={e.id} className="flex items-start justify-between gap-2 px-5 py-2.5">
                          <div className="min-w-0">
                            <Badge tone={meta.tone}>{meta.label}</Badge>
                            {typeof e.details.product_name === 'string' && (
                              <p className="mt-1 truncate text-xs text-slate-600">{e.details.product_name}</p>
                            )}
                          </div>
                          <time className="shrink-0 text-[11px] text-slate-400" title={dateTime(e.timestamp)}>
                            {timeAgo(e.timestamp)}
                          </time>
                        </li>
                      );
                    })}
                  </ul>
                );
              })()}
              <div className="flex items-center gap-2 border-t border-slate-100 px-5 py-3 text-xs text-slate-500">
                <ShieldCheck className="h-3.5 w-3.5" /> Captured volume counts only PayPal-verified captures.
              </div>
            </Card>
          </div>
        </>
      )}
    </div>
  );
};

export default Dashboard;
