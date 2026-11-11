import React, { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, ArrowUpRight, Ban, Bot, CreditCard, Plug, Scale, ShieldCheck, Sparkles, UserCheck, Wallet } from 'lucide-react';
import { pactApi } from '../api/pact';
import { BudgetRing, DecisionChart, Legend } from '../components/charts';
import { ProductTile } from '../components/ProductTile';
import { Badge, Button, Card, CardHeader, EmptyState, ErrorState, Eyebrow, Meter, RefreshButton, Skeleton, SkeletonRows, StatusPill, TONE_DOT, cx, inputClass } from '../components/ui';
import { MANDATE_STATUS, dateOnly, eventMeta, explainEvent, money, timeAgo, toNumber } from '../lib/format';
import { useAsync } from '../lib/useAsync';

const PIPELINE = [
  { icon: Bot, title: 'Any AI agent requests', text: 'Claude, ChatGPT or yours, via API or MCP.' },
  { icon: Scale, title: 'Policy engine authorizes', text: 'Deterministic rules from your mandate.' },
  { icon: UserCheck, title: 'Human approves', text: 'Bound to the exact purchase.' },
  { icon: CreditCard, title: 'PayPal executes', text: 'Verified capture, never assumed.' },
];

const Kpi: React.FC<{ label: string; value: React.ReactNode; hint: React.ReactNode; icon: React.ReactNode; tone?: string }> = ({ label, value, hint, icon, tone }) => (
  <Card className="p-4 animate-rise">
    <div className="flex items-center justify-between">
      <p className="text-xs text-muted">{label}</p>
      <span className={cx('text-faint', tone)}>{icon}</span>
    </div>
    <p className="mt-2 text-[26px] font-semibold leading-none tracking-tight text-fg tnum">{value}</p>
    <p className="mt-2 text-[11px] text-faint">{hint}</p>
  </Card>
);

export const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const [ask, setAsk] = useState('');
  const state = useAsync(async () => {
    const [mandates, proposals, audit] = await Promise.all([pactApi.getMandates(), pactApi.getProposals(), pactApi.getAuditLogs(120)]);
    return { mandates, proposals, audit };
  });

  const m = useMemo(() => {
    if (!state.data) return null;
    const { mandates, proposals } = state.data;
    const active = mandates.filter((x) => x.status === 'active');
    const captured = proposals.filter((p) => p.status === 'CAPTURED');
    const blocked = proposals.filter((p) => p.status === 'POLICY_REJECTED').length;
    return {
      currency: mandates[0]?.currency ?? proposals[0]?.currency ?? 'USD',
      activeCount: active.length,
      remaining: active.reduce((s, x) => s + toNumber(x.remaining_budget), 0),
      allocated: active.reduce((s, x) => s + toNumber(x.max_budget), 0),
      capturedVolume: captured.reduce((s, p) => s + toNumber(p.captured_amount ?? p.total_amount), 0),
      capturedCount: captured.length,
      evaluated: proposals.length,
      blocked,
      passed: proposals.length - blocked,
      awaiting: proposals.filter((p) => p.status === 'AWAITING_HUMAN_APPROVAL'),
    };
  }, [state.data]);

  const submitAsk = (e: React.FormEvent) => {
    e.preventDefault();
    navigate(ask.trim() ? `/assistant?q=${encodeURIComponent(ask.trim())}` : '/assistant');
  };

  return (
    <div className="space-y-6">
      {/* Hero */}
      <Card className="relative overflow-hidden">
        <div className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-accent/10 blur-3xl" />
        <div className="grid gap-8 p-6 lg:grid-cols-[1.25fr_1fr] lg:p-8">
          <div>
            <Eyebrow>PACT Control Center</Eyebrow>
            <h1 className="mt-3 max-w-xl text-[30px] font-semibold leading-[1.15] tracking-tight text-fg sm:text-[34px]">
              The authorization gateway{' '}
              <span className="bg-gradient-to-r from-accent to-violet bg-clip-text text-transparent">for AI-powered commerce.</span>
            </h1>
            <p className="mt-3 max-w-lg text-sm leading-relaxed text-muted">
              Let any AI agent shop for you, only within the limits you set. Agents ask PACT for authority; your mandate, enforced by deterministic
              code, decides; you approve the exact purchase; PayPal executes. No agent ever holds the power to pay.
            </p>
            <ol className="mt-6 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
              {PIPELINE.map((s, i) => (
                <li key={s.title} className="rounded-lg border border-line bg-ink/40 p-3">
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 items-center justify-center rounded-md bg-white/[0.06] text-accent">
                      <s.icon className="h-3.5 w-3.5" />
                    </span>
                    <span className="text-[10px] font-medium text-faint tnum">0{i + 1}</span>
                  </div>
                  <p className="mt-2 text-[13px] font-medium text-fg">{s.title}</p>
                  <p className="mt-0.5 text-[11px] leading-snug text-faint">{s.text}</p>
                </li>
              ))}
            </ol>
          </div>

          <form onSubmit={submitAsk} className="flex flex-col justify-between rounded-xl border border-line-strong bg-raised/80 p-5">
            <div>
              <div className="flex items-center gap-2 text-sm font-medium text-fg">
                <Sparkles className="h-4 w-4 text-accent" /> Try the reference agent
              </div>
              <p className="mt-1 text-xs text-muted">
                Describe what you need. The built-in Gemini agent recommends, PACT checks your mandate, then waits for you. Or{' '}
                <Link to="/agents" className="inline-flex items-center gap-1 text-accent hover:underline">
                  <Plug className="h-3 w-3" />
                  connect your own agent
                </Link>
                .
              </p>
              <label htmlFor="ask" className="sr-only">
                Shopping request
              </label>
              <textarea
                id="ask"
                value={ask}
                onChange={(e) => setAsk(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) submitAsk(e);
                }}
                rows={3}
                maxLength={1000}
                placeholder="e.g. A wireless mechanical keyboard for coding, under $100"
                className={cx(inputClass, 'mt-4 resize-none')}
              />
            </div>
            <div className="mt-4 flex items-center justify-between gap-3">
              <span className="text-[11px] text-faint">{m ? `${m.activeCount} active mandate${m.activeCount === 1 ? '' : 's'} guarding ${money(m.remaining, m.currency)}` : ' '}</span>
              <Button type="submit" icon={<ArrowRight className="h-4 w-4" />}>
                Get a recommendation
              </Button>
            </div>
          </form>
        </div>
      </Card>

      {state.error && <ErrorState message={state.error} onRetry={() => void state.reload()} />}

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        {!m ? (
          Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-[104px]" />)
        ) : (
          <>
            <Kpi label="Authorized spending" value={money(m.capturedVolume, m.currency)} hint="captured and verified by PayPal" icon={<ShieldCheck className="h-4 w-4" />} tone="text-ok" />
            <Kpi label="Remaining budget" value={money(m.remaining, m.currency)} hint={`of ${money(m.allocated, m.currency)} across active mandates`} icon={<Wallet className="h-4 w-4" />} />
            <Kpi label="Purchases evaluated" value={m.evaluated} hint={`${m.passed} passed policy`} icon={<Scale className="h-4 w-4" />} />
            <Kpi label="Blocked by policy" value={m.blocked} hint="never reached approval or PayPal" icon={<Ban className="h-4 w-4" />} tone="text-bad" />
            <Kpi label="PayPal transactions" value={m.capturedCount} hint="successful Sandbox captures" icon={<CreditCard className="h-4 w-4" />} tone="text-info" />
          </>
        )}
      </div>

      {m && m.awaiting.length > 0 && (
        <Link
          to={`/proposals/${m.awaiting[0].id}`}
          className="flex items-center justify-between gap-3 rounded-xl border border-warn/25 bg-warn/[0.06] px-5 py-3.5 transition-colors hover:bg-warn/10"
        >
          <span className="flex items-center gap-3 text-sm text-fg">
            <span className="h-2 w-2 rounded-full bg-warn" />
            {m.awaiting.length} purchase{m.awaiting.length === 1 ? '' : 's'} passed policy and {m.awaiting.length === 1 ? 'is' : 'are'} waiting for your approval
            <span className="hidden text-muted sm:inline">· {m.awaiting[0].product_name}, {money(m.awaiting[0].total_amount, m.awaiting[0].currency)}</span>
          </span>
          <span className="flex shrink-0 items-center gap-1 text-xs font-medium text-warn">
            Review <ArrowRight className="h-3.5 w-3.5" />
          </span>
        </Link>
      )}

      <div className="grid gap-6 xl:grid-cols-5">
        {/* Spending overview */}
        <Card className="xl:col-span-3">
          <CardHeader
            title="Spending overview"
            subtitle="Each mandate's budget: captured, approved and still available"
            action={
              <Link to="/mandates" className="inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-fg">
                Manage <ArrowUpRight className="h-3 w-3" />
              </Link>
            }
          />
          {!state.data ? (
            <SkeletonRows rows={2} />
          ) : state.data.mandates.length === 0 ? (
            <EmptyState title="No mandates yet" description="Create a spending mandate to let the assistant propose purchases." action={<Link to="/mandates"><Button size="sm">Create mandate</Button></Link>} />
          ) : (
            <ul className="divide-y divide-line">
              {state.data.mandates.slice(0, 3).map((x) => {
                const st = MANDATE_STATUS[x.status];
                return (
                  <li key={x.id} className="flex flex-col gap-5 p-5 sm:flex-row sm:items-center">
                    <BudgetRing max={toNumber(x.max_budget)} spent={toNumber(x.spent_budget)} committed={toNumber(x.committed_budget)} size={112}>
                      <span className="text-[10px] uppercase tracking-wider text-faint">Left</span>
                      <span className="text-base font-semibold text-fg tnum">{money(x.remaining_budget, x.currency)}</span>
                    </BudgetRing>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate text-sm font-medium text-fg">{x.name}</p>
                        <Badge tone={st.tone} dot>{st.label}</Badge>
                        {x.expires_at && x.status === 'active' && <span className="text-[11px] text-faint">until {dateOnly(x.expires_at)}</span>}
                      </div>
                      <Meter className="mt-3" max={toNumber(x.max_budget)} spent={toNumber(x.spent_budget)} committed={toNumber(x.committed_budget)} />
                      <div className="mt-3">
                        <Legend
                          items={[
                            { label: 'Captured', className: 'bg-ok', value: money(x.spent_budget, x.currency) },
                            { label: 'Approved', className: 'bg-warn', value: money(x.committed_budget, x.currency) },
                            { label: 'Limit', className: 'bg-white/20', value: money(x.max_budget, x.currency) },
                          ]}
                        />
                      </div>
                      <p className="mt-2 truncate text-[11px] text-faint">
                        {x.allowed_merchants.join(', ')} · {x.allowed_categories.join(', ')}
                      </p>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        {/* Decisions */}
        <Card className="xl:col-span-2">
          <CardHeader title="Policy decisions" subtitle="Last 14 days, by outcome" action={<RefreshButton onClick={() => void state.reload()} loading={state.loading} />} />
          <div className="p-5">
            {!state.data ? (
              <Skeleton className="h-40" />
            ) : (
              <>
                <DecisionChart proposals={state.data.proposals} />
                <div className="mt-4">
                  <Legend
                    items={[
                      { label: 'Captured', className: 'bg-ok', value: m?.capturedCount },
                      { label: 'Passed policy', className: 'bg-accent', value: (m?.passed ?? 0) - (m?.capturedCount ?? 0) },
                      { label: 'Blocked', className: 'bg-bad', value: m?.blocked },
                    ]}
                  />
                </div>
              </>
            )}
          </div>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-5">
        <Card className="xl:col-span-3">
          <CardHeader
            title="Recent purchase activity"
            action={
              <Link to="/transactions" className="inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-fg">
                All transactions <ArrowUpRight className="h-3 w-3" />
              </Link>
            }
          />
          {!state.data ? (
            <SkeletonRows />
          ) : state.data.proposals.length === 0 ? (
            <EmptyState title="No purchases yet" description="Ask PACT for something to see the pipeline in action." />
          ) : (
            <ul className="divide-y divide-line">
              {state.data.proposals.slice(0, 6).map((p) => (
                <li key={p.id}>
                  <Link to={`/proposals/${p.id}`} className="flex items-center gap-3 px-5 py-3 transition-colors hover:bg-white/[0.03]">
                    <ProductTile name={p.product_name} category={p.category} size="sm" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm text-fg">{p.product_name}</p>
                      <p className="text-[11px] text-faint">
                        {p.merchant} · {timeAgo(p.created_at)}
                      </p>
                    </div>
                    <span className="text-sm font-medium text-fg tnum">{money(p.total_amount, p.currency)}</span>
                    <StatusPill status={p.status} className="hidden w-[132px] justify-start sm:inline-flex" />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="xl:col-span-2">
          <CardHeader
            title="Security events"
            subtitle="Blocks, approvals, invalidations, captures"
            action={
              <Link to="/audit" className="inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-fg">
                Audit trail <ArrowUpRight className="h-3 w-3" />
              </Link>
            }
          />
          {!state.data ? (
            <SkeletonRows />
          ) : (
            (() => {
              const events = state.data.audit
                .filter((e) => ['POLICY_CHECK_FAILED', 'PROPOSAL_HUMAN_APPROVED', 'APPROVAL_INVALIDATED', 'PAYPAL_PAYMENT_CAPTURED', 'DUPLICATE_CAPTURE_PREVENTED', 'MANDATE_UPDATED', 'MANDATE_REVOKED', 'CATALOG_PRODUCT_CHANGED', 'CAPTURE_BLOCKED_NOT_APPROVED'].includes(e.event_type))
                .slice(0, 6);
              if (!events.length) return <EmptyState title="No security events yet" />;
              return (
                <ul className="divide-y divide-line">
                  {events.map((e) => {
                    const meta = eventMeta(e.event_type);
                    return (
                      <li key={e.id} className="flex gap-3 px-5 py-3">
                        <span className={cx('mt-1.5 h-2 w-2 shrink-0 rounded-full', TONE_DOT[meta.tone])} />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-baseline justify-between gap-2">
                            <p className="truncate text-[13px] font-medium text-fg">{meta.label}</p>
                            <time className="shrink-0 text-[11px] text-faint">{timeAgo(e.timestamp)}</time>
                          </div>
                          <p className="mt-0.5 line-clamp-2 text-xs text-muted">{explainEvent(e)}</p>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              );
            })()
          )}
        </Card>
      </div>
    </div>
  );
};

export default Dashboard;
