import React, { useMemo, useState } from 'react';
import { ChevronRight, Search } from 'lucide-react';
import { pactApi } from '../api/pact';
import type { AuditLogEntry } from '../types';
import { dateTime, eventMeta, shortId } from '../lib/format';
import { useAsync } from '../lib/useAsync';
import { ProposalCase } from '../components/ProposalCase';
import { Badge, Card, EmptyState, ErrorState, Modal, Mono, PageHeader, RefreshButton, Spinner } from '../components/ui';

type Category = 'all' | 'mandate' | 'ai' | 'policy' | 'approval' | 'paypal' | 'security';

const CATEGORIES: { key: Category; label: string; match: (t: string) => boolean }[] = [
  { key: 'all', label: 'All', match: () => true },
  { key: 'mandate', label: 'Mandates', match: (t) => t.startsWith('MANDATE_') },
  { key: 'ai', label: 'AI', match: (t) => t.startsWith('AI_') },
  { key: 'policy', label: 'Policy', match: (t) => t.startsWith('POLICY_') },
  { key: 'approval', label: 'Approval', match: (t) => t.includes('APPROV') || t.includes('REJECTED') || t.includes('RE_EVALUATED') },
  { key: 'paypal', label: 'PayPal', match: (t) => t.startsWith('PAYPAL_') || t.includes('CAPTURE') },
  {
    key: 'security',
    label: 'Security alerts',
    match: (t) => /MISMATCH|INVALIDATED|FAILED|DUPLICATE|BLOCKED|UNVERIFIED|UNCERTAIN/.test(t),
  },
];

const SENSITIVE = /(secret|password|token|authorization|api_?key|access_token|card|cvv)/i;

/** Defence in depth: the server already redacts; never render anything that looks sensitive. */
function redact(value: unknown, key = ''): unknown {
  if (key && SENSITIVE.test(key) && !/fingerprint/i.test(key)) return '***REDACTED***';
  if (Array.isArray(value)) return value.map((v) => redact(v));
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value as Record<string, unknown>).map(([k, v]) => [k, redact(v, k)]));
  }
  return value;
}

function summary(e: AuditLogEntry): string {
  const d = e.details;
  const parts: string[] = [];
  if (typeof d.product_name === 'string') parts.push(d.product_name);
  if (typeof d.name === 'string') parts.push(d.name);
  if (typeof d.provider === 'string') parts.push(d.provider === 'openai' ? `OpenAI ${d.model ?? ''}`.trim() : `${d.provider} (not AI)`);
  if (typeof d.paypal_order_id === 'string') parts.push(`order ${d.paypal_order_id}`);
  if (typeof d.paypal_capture_id === 'string') parts.push(`capture ${d.paypal_capture_id}`);
  if (Array.isArray(d.violations) && d.violations.length) parts.push(`${d.violations.length} violation(s)`);
  if (Array.isArray(d.changes) && d.changes.length) parts.push(String(d.changes[0]));
  if (typeof d.code === 'string') parts.push(d.code);
  return parts.join(' · ');
}

export const AuditTrail: React.FC = () => {
  const state = useAsync(() => pactApi.getAuditLogs(500));
  const [category, setCategory] = useState<Category>('all');
  const [query, setQuery] = useState('');
  const [expanded, setExpanded] = useState<number | null>(null);
  const [proposalId, setProposalId] = useState<string | null>(null);

  const rows = useMemo(() => {
    const cat = CATEGORIES.find((c) => c.key === category)!;
    const q = query.trim().toLowerCase();
    return (state.data ?? []).filter(
      (e) =>
        cat.match(e.event_type) &&
        (!q || e.event_type.toLowerCase().includes(q) || e.entity_id.toLowerCase().includes(q) || JSON.stringify(e.details).toLowerCase().includes(q)),
    );
  }, [state.data, category, query]);

  return (
    <div>
      <PageHeader
        title="Audit trail"
        description="Append-only record of every mandate change, recommendation, policy decision, approval and PayPal call. Sensitive fields are redacted before storage."
        actions={<RefreshButton onClick={() => void state.reload()} loading={state.loading} />}
      />

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-1.5">
          {CATEGORIES.map((c) => (
            <button
              key={c.key}
              onClick={() => setCategory(c.key)}
              aria-pressed={category === c.key}
              className={`rounded-full px-3 py-1 text-xs font-semibold ${
                category === c.key ? 'bg-slate-900 text-white' : 'bg-white text-slate-600 ring-1 ring-inset ring-slate-200 hover:text-slate-900'
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>
        <div className="relative sm:w-72">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search events, IDs, details…"
            aria-label="Search audit events"
            className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
          />
        </div>
      </div>

      {state.error && <ErrorState message={state.error} onRetry={() => void state.reload()} />}
      {!state.data && state.loading && <Spinner />}

      {state.data && (
        <Card className="overflow-hidden">
          {rows.length === 0 ? (
            <EmptyState title={state.data.length ? 'No events match' : 'No audit events yet'} />
          ) : (
            <ul className="divide-y divide-slate-100">
              {rows.map((e) => {
                const meta = eventMeta(e.event_type);
                const open = expanded === e.id;
                return (
                  <li key={e.id}>
                    <button
                      onClick={() => setExpanded(open ? null : e.id)}
                      aria-expanded={open}
                      className="flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-slate-50 sm:items-center"
                    >
                      <ChevronRight className={`mt-0.5 h-4 w-4 shrink-0 text-slate-400 transition-transform sm:mt-0 ${open ? 'rotate-90' : ''}`} />
                      <div className="flex min-w-0 flex-1 flex-col gap-1 sm:flex-row sm:items-center sm:gap-3">
                        <Badge tone={meta.tone} className="self-start sm:self-auto">
                          {meta.label}
                        </Badge>
                        <span className="min-w-0 flex-1 truncate text-sm text-slate-700">{summary(e)}</span>
                      </div>
                      <div className="hidden shrink-0 text-right sm:block">
                        <p className="text-xs text-slate-500">{dateTime(e.timestamp)}</p>
                        <p className="text-[11px] text-slate-400">
                          {e.entity_type} <Mono className="text-[11px] text-slate-400">{shortId(e.entity_id)}</Mono>
                        </p>
                      </div>
                    </button>
                    {open && (
                      <div className="space-y-2 bg-slate-50 px-4 pb-4 pl-11">
                        <p className="text-xs text-slate-500 sm:hidden">{dateTime(e.timestamp)}</p>
                        <p className="text-xs text-slate-500">
                          <span className="font-semibold">{e.event_type}</span> · {e.entity_type} <Mono className="text-[11px]">{e.entity_id}</Mono>
                        </p>
                        <pre className="max-h-80 overflow-auto rounded-lg bg-slate-900 p-3 text-[11px] leading-relaxed text-slate-100">
                          {JSON.stringify(redact(e.details), null, 2)}
                        </pre>
                        {e.entity_type === 'Proposal' && (
                          <button onClick={() => setProposalId(e.entity_id)} className="text-xs font-semibold text-slate-700 underline underline-offset-2">
                            Open authorization receipt
                          </button>
                        )}
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
      )}

      <Modal open={proposalId !== null} onClose={() => setProposalId(null)} title="Authorization receipt" wide>
        {proposalId && <ProposalCase proposalId={proposalId} onNewProposal={setProposalId} />}
      </Modal>
    </div>
  );
};

export default AuditTrail;
