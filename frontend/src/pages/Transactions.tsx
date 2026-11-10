import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronRight, Search } from 'lucide-react';
import { pactApi } from '../api/pact';
import { ProductTile } from '../components/ProductTile';
import { Card, EmptyState, ErrorState, Mono, PageHeader, RefreshButton, Segmented, SkeletonRows, StatusPill, cx, inputClass } from '../components/ui';
import { dateTime, money, shortId, statusMeta, toNumber, type StatusGroup } from '../lib/format';
import { useAsync } from '../lib/useAsync';
import type { Proposal } from '../types';

type Filter = 'all' | StatusGroup;

const FILTERS: { value: Filter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'awaiting', label: 'Awaiting approval' },
  { value: 'paypal', label: 'In PayPal flow' },
  { value: 'captured', label: 'Captured' },
  { value: 'blocked', label: 'Blocked' },
  { value: 'closed', label: 'Failed · cancelled · expired' },
];

export const Transactions: React.FC = () => {
  const navigate = useNavigate();
  const state = useAsync(async () => {
    const [proposals, mandates] = await Promise.all([pactApi.getProposals(), pactApi.getMandates()]);
    return { proposals, names: Object.fromEntries(mandates.map((m) => [m.id, m.name])) as Record<string, string> };
  });
  const [filter, setFilter] = useState<Filter>('all');
  const [query, setQuery] = useState('');

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: 0 };
    state.data?.proposals.forEach((p) => {
      c.all += 1;
      const g = statusMeta(p.status).group;
      c[g] = (c[g] ?? 0) + 1;
    });
    return c;
  }, [state.data]);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (state.data?.proposals ?? []).filter((p: Proposal) => {
      if (filter !== 'all' && statusMeta(p.status).group !== filter) return false;
      if (!q) return true;
      return [p.id, p.product_name, p.merchant, p.paypal_order_id, p.paypal_capture_id, state.data?.names[p.mandate_id]].some((v) => v && String(v).toLowerCase().includes(q));
    });
  }, [state.data, filter, query]);

  const capturedTotal = useMemo(() => rows.filter((p) => p.status === 'CAPTURED').reduce((s, p) => s + toNumber(p.captured_amount ?? p.total_amount), 0), [rows]);
  const open = (id: string) => navigate(`/proposals/${id}`);

  return (
    <div>
      <PageHeader
        eyebrow="Ledger"
        title="Transactions"
        description="Every proposal with its policy outcome and PayPal references. Order and capture IDs appear only when PayPal returned them."
        actions={<RefreshButton onClick={() => void state.reload()} loading={state.loading} />}
      />

      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <Segmented label="Filter by status" value={filter} onChange={setFilter} options={FILTERS.map((f) => ({ ...f, count: counts[f.value] ?? 0 }))} />
        <div className="relative lg:w-80">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-faint" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search product, merchant, PayPal ID…" aria-label="Search transactions" className={cx(inputClass, 'pl-9')} />
        </div>
      </div>

      {state.error && <ErrorState message={state.error} onRetry={() => void state.reload()} />}

      <Card className="overflow-hidden">
        {!state.data ? (
          <SkeletonRows rows={6} />
        ) : rows.length === 0 ? (
          <EmptyState title={state.data.proposals.length ? 'No transactions match' : 'No transactions yet'} description={state.data.proposals.length ? 'Try a different filter or search.' : 'Proposals appear here as soon as the assistant makes one.'} />
        ) : (
          <>
            <div className="hidden overflow-x-auto md:block">
              <table className="min-w-full text-sm">
                <thead className="border-b border-line text-left text-[11px] font-medium uppercase tracking-wider text-faint">
                  <tr>
                    <th className="px-5 py-3 font-medium">Product</th>
                    <th className="px-4 py-3 font-medium">Transaction</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">PayPal reference</th>
                    <th className="px-4 py-3 font-medium">Date</th>
                    <th className="px-5 py-3 text-right font-medium">Amount</th>
                    <th className="w-8" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {rows.map((p) => (
                    <tr
                      key={p.id}
                      tabIndex={0}
                      onClick={() => open(p.id)}
                      onKeyDown={(e) => e.key === 'Enter' && open(p.id)}
                      className="group cursor-pointer transition-colors hover:bg-white/[0.03] focus-visible:bg-white/[0.04]"
                    >
                      <td className="max-w-xs px-5 py-3">
                        <div className="flex items-center gap-3">
                          <ProductTile name={p.product_name} category={p.category} size="sm" />
                          <div className="min-w-0">
                            <p className="truncate text-fg">{p.product_name}</p>
                            <p className="truncate text-[11px] text-faint">{p.merchant} · qty {p.quantity}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <Mono className="text-[11px] text-muted">{shortId(p.id)}</Mono>
                        <p className="max-w-[11rem] truncate text-[11px] text-faint">{state.data?.names[p.mandate_id] ?? shortId(p.mandate_id)}</p>
                      </td>
                      <td className="px-4 py-3"><StatusPill status={p.status} /></td>
                      <td className="px-4 py-3">
                        {p.paypal_order_id ? <Mono className="text-[11px] text-muted">{p.paypal_order_id}</Mono> : <span className="text-faint">—</span>}
                        {p.paypal_capture_id && <p><Mono className="text-[11px] text-ok">{p.paypal_capture_id}</Mono></p>}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-xs text-muted">{dateTime(p.created_at)}</td>
                      <td className="px-5 py-3 text-right font-medium text-fg tnum">{money(p.total_amount, p.currency)}</td>
                      <td className="pr-3 text-faint"><ChevronRight className="h-4 w-4 opacity-0 transition-opacity group-hover:opacity-100" /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <ul className="divide-y divide-line md:hidden">
              {rows.map((p) => (
                <li key={p.id}>
                  <button onClick={() => open(p.id)} className="flex w-full items-center gap-3 px-4 py-3 text-left">
                    <ProductTile name={p.product_name} category={p.category} size="sm" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm text-fg">{p.product_name}</p>
                      <p className="text-[11px] text-faint">{p.merchant} · {dateTime(p.created_at)}</p>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1">
                      <span className="text-sm font-medium text-fg tnum">{money(p.total_amount, p.currency)}</span>
                      <StatusPill status={p.status} />
                    </div>
                  </button>
                </li>
              ))}
            </ul>
            <div className="flex items-center justify-between border-t border-line px-5 py-3 text-xs text-faint">
              <span>{rows.length} transaction{rows.length === 1 ? '' : 's'}</span>
              <span>Captured in view: <span className="font-medium text-ok tnum">{money(capturedTotal, rows[0]?.currency)}</span></span>
            </div>
          </>
        )}
      </Card>
    </div>
  );
};

export default Transactions;
