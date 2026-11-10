import React, { useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import { pactApi } from '../api/pact';
import type { Proposal } from '../types';
import { dateTime, money, shortId, statusMeta, type StatusMeta } from '../lib/format';
import { useAsync } from '../lib/useAsync';
import { ProposalCase } from '../components/ProposalCase';
import { Card, EmptyState, ErrorState, Modal, Mono, PageHeader, RefreshButton, Spinner, StatusBadge } from '../components/ui';

type Filter = 'all' | StatusMeta['group'];

const FILTERS: { key: Filter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'captured', label: 'Captured' },
  { key: 'in_progress', label: 'In progress' },
  { key: 'awaiting', label: 'Awaiting approval' },
  { key: 'blocked', label: 'Blocked' },
  { key: 'closed', label: 'Closed' },
];

export const Transactions: React.FC = () => {
  const state = useAsync(async () => {
    const [proposals, mandates] = await Promise.all([pactApi.getProposals(), pactApi.getMandates()]);
    return { proposals, mandateNames: Object.fromEntries(mandates.map((m) => [m.id, m.name])) as Record<string, string> };
  });
  const [filter, setFilter] = useState<Filter>('all');
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<string | null>(null);

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
      return [p.id, p.product_name, p.merchant, p.paypal_order_id, p.paypal_capture_id, state.data?.mandateNames[p.mandate_id]]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(q));
    });
  }, [state.data, filter, query]);

  const mandateName = (id: string) => state.data?.mandateNames[id] ?? shortId(id);

  return (
    <div>
      <PageHeader
        title="Transactions"
        description="Every proposal the assistant produced, with its policy outcome and real PayPal identifiers. IDs are shown only when PayPal returned them."
        actions={<RefreshButton onClick={() => void state.reload()} loading={state.loading} />}
      />

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-1.5" role="tablist">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              role="tab"
              aria-selected={filter === f.key}
              onClick={() => setFilter(f.key)}
              className={`rounded-full px-3 py-1 text-xs font-semibold ${
                filter === f.key ? 'bg-slate-900 text-white' : 'bg-white text-slate-600 ring-1 ring-inset ring-slate-200 hover:text-slate-900'
              }`}
            >
              {f.label} <span className="opacity-60">{counts[f.key] ?? 0}</span>
            </button>
          ))}
        </div>
        <div className="relative sm:w-72">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search product, merchant, PayPal ID…"
            aria-label="Search transactions"
            className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
          />
        </div>
      </div>

      {state.error && <ErrorState message={state.error} onRetry={() => void state.reload()} />}
      {!state.data && state.loading && <Spinner />}

      {state.data && (
        <Card className="overflow-hidden">
          {rows.length === 0 ? (
            <EmptyState title={state.data.proposals.length ? 'No transactions match' : 'No transactions yet'} />
          ) : (
            <>
              {/* Desktop table */}
              <div className="hidden overflow-x-auto md:block">
                <table className="min-w-full text-sm">
                  <thead className="bg-slate-50 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                    <tr>
                      <th className="px-4 py-2.5">Product</th>
                      <th className="px-4 py-2.5">Mandate</th>
                      <th className="px-4 py-2.5 text-right">Amount</th>
                      <th className="px-4 py-2.5">Status</th>
                      <th className="px-4 py-2.5">PayPal order / capture</th>
                      <th className="px-4 py-2.5">Created</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {rows.map((p) => (
                      <tr key={p.id} onClick={() => setSelected(p.id)} className="cursor-pointer hover:bg-slate-50" tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && setSelected(p.id)}>
                        <td className="max-w-xs px-4 py-3">
                          <p className="truncate font-medium text-slate-900">{p.product_name}</p>
                          <p className="text-xs text-slate-500">
                            {p.merchant} · qty {p.quantity} · <Mono className="text-[11px] text-slate-400">{shortId(p.id)}</Mono>
                          </p>
                        </td>
                        <td className="max-w-[12rem] truncate px-4 py-3 text-xs text-slate-600">{mandateName(p.mandate_id)}</td>
                        <td className="px-4 py-3 text-right font-semibold tabular-nums text-slate-900">{money(p.total_amount, p.currency)}</td>
                        <td className="px-4 py-3">
                          <StatusBadge status={p.status} />
                        </td>
                        <td className="px-4 py-3 text-xs">
                          {p.paypal_order_id ? <Mono>{p.paypal_order_id}</Mono> : <span className="text-slate-400">—</span>}
                          {p.paypal_capture_id && (
                            <p>
                              <Mono className="text-emerald-700">{p.paypal_capture_id}</Mono>
                            </p>
                          )}
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-500">{dateTime(p.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {/* Mobile list */}
              <ul className="divide-y divide-slate-100 md:hidden">
                {rows.map((p) => (
                  <li key={p.id}>
                    <button onClick={() => setSelected(p.id)} className="flex w-full items-start justify-between gap-3 px-4 py-3 text-left">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-slate-900">{p.product_name}</p>
                        <p className="text-xs text-slate-500">
                          {p.merchant} · {dateTime(p.created_at)}
                        </p>
                        {p.paypal_capture_id && <Mono className="text-[11px] text-emerald-700">{p.paypal_capture_id}</Mono>}
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-1">
                        <span className="text-sm font-semibold tabular-nums">{money(p.total_amount, p.currency)}</span>
                        <StatusBadge status={p.status} />
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </Card>
      )}

      <Modal
        open={selected !== null}
        onClose={() => {
          setSelected(null);
          void state.reload();
        }}
        title="Transaction detail"
        wide
      >
        {selected && <ProposalCase proposalId={selected} onNewProposal={(id) => setSelected(id)} />}
      </Modal>
    </div>
  );
};

export default Transactions;
