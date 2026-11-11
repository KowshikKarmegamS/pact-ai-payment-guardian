import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, ChevronDown, Search, ShieldCheck } from 'lucide-react';
import { pactApi } from '../api/pact';
import { Badge, Card, EmptyState, ErrorState, Mono, PageHeader, RefreshButton, Segmented, SkeletonRows, TONE_DOT, cx, inputClass } from '../components/ui';
import { eventMeta, explainEvent, parseDate, shortId, timeOnly, type EventCategory } from '../lib/format';
import { useAsync } from '../lib/useAsync';
import type { AuditLogEntry } from '../types';

type Filter = 'all' | 'alerts' | EventCategory;

const FILTERS: { value: Filter; label: string }[] = [
  { value: 'all', label: 'All events' },
  { value: 'alerts', label: 'Security alerts' },
  { value: 'policy', label: 'Policy' },
  { value: 'approval', label: 'Approvals' },
  { value: 'paypal', label: 'PayPal' },
  { value: 'mandate', label: 'Mandates' },
  { value: 'ai', label: 'AI' },
  { value: 'catalog', label: 'Catalog' },
  { value: 'agent', label: 'Agents' },
];

const SENSITIVE = /(secret|password|token|authorization|api_?key|card|cvv)/i;

/** Defence in depth: the server already redacts; never render anything that looks sensitive. */
function redact(value: unknown, key = ''): unknown {
  if (key && SENSITIVE.test(key)) return '***REDACTED***';
  if (Array.isArray(value)) return value.map((v) => redact(v));
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value as Record<string, unknown>).map(([k, v]) => [k, redact(v, k)]));
  return value;
}

const str = (v: unknown) => (typeof v === 'string' && v ? v : null);

function dayLabel(iso: string): string {
  const d = parseDate(iso);
  if (!d) return 'Unknown date';
  const today = new Date();
  const y = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 1);
  if (d.toDateString() === today.toDateString()) return 'Today';
  if (d.toDateString() === y.toDateString()) return 'Yesterday';
  return d.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' });
}

const EventRow: React.FC<{ e: AuditLogEntry; last: boolean }> = ({ e, last }) => {
  const [open, setOpen] = useState(false);
  const meta = eventMeta(e.event_type);
  const order = str(e.details.paypal_order_id);
  const capture = str(e.details.paypal_capture_id);
  return (
    <li className="relative flex gap-4 pb-5 last:pb-0">
      {!last && <span className="absolute left-[5px] top-5 h-full w-px bg-line" />}
      <span className={cx('relative z-10 mt-1.5 h-[11px] w-[11px] shrink-0 rounded-full ring-4 ring-surface', TONE_DOT[meta.tone])} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-medium text-fg">{meta.label}</p>
            {meta.alert && <Badge tone={meta.tone}>security</Badge>}
          </div>
          <time className="font-mono text-[11px] text-faint">{timeOnly(e.timestamp)}</time>
        </div>
        <p className="mt-0.5 text-[13px] leading-relaxed text-muted">{explainEvent(e)}</p>
        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-faint">
          {e.entity_type === 'Proposal' ? (
            <Link to={`/proposals/${e.entity_id}`} className="inline-flex items-center gap-1 text-accent hover:underline">
              Transaction <Mono className="text-[11px] text-accent">{shortId(e.entity_id)}</Mono> <ArrowUpRight className="h-3 w-3" />
            </Link>
          ) : (
            <span>{e.entity_type} <Mono className="text-[11px] text-faint">{shortId(e.entity_id)}</Mono></span>
          )}
          {order && <span>Order <Mono className="text-[11px] text-muted">{order}</Mono></span>}
          {capture && <span>Capture <Mono className="text-[11px] text-ok">{capture}</Mono></span>}
          <button onClick={() => setOpen((v) => !v)} aria-expanded={open} className="inline-flex items-center gap-0.5 hover:text-muted">
            Raw record <ChevronDown className={cx('h-3 w-3 transition-transform', open && 'rotate-180')} />
          </button>
        </div>
        {open && (
          <pre className="mt-2 max-h-72 overflow-auto rounded-lg border border-line bg-ink p-3 font-mono text-[11px] leading-relaxed text-muted animate-fade">
            {JSON.stringify({ event: e.event_type, entity: `${e.entity_type}:${e.entity_id}`, at: e.timestamp, details: redact(e.details) }, null, 2)}
          </pre>
        )}
      </div>
    </li>
  );
};

export const AuditTrail: React.FC = () => {
  const state = useAsync(() => pactApi.getAuditLogs(500));
  const [filter, setFilter] = useState<Filter>('all');
  const [query, setQuery] = useState('');

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (state.data ?? []).filter((e) => {
      const meta = eventMeta(e.event_type);
      if (filter === 'alerts' ? !meta.alert : filter !== 'all' && meta.category !== filter) return false;
      if (!q) return true;
      return meta.label.toLowerCase().includes(q) || e.entity_id.toLowerCase().includes(q) || explainEvent(e).toLowerCase().includes(q) || JSON.stringify(e.details).toLowerCase().includes(q);
    });
  }, [state.data, filter, query]);

  const groups = useMemo(() => {
    const out: { label: string; events: AuditLogEntry[] }[] = [];
    rows.forEach((e) => {
      const label = dayLabel(e.timestamp);
      const g = out[out.length - 1];
      if (g && g.label === label) g.events.push(e);
      else out.push({ label, events: [e] });
    });
    return out;
  }, [rows]);

  const alerts = useMemo(() => (state.data ?? []).filter((e) => eventMeta(e.event_type).alert).length, [state.data]);

  return (
    <div>
      <PageHeader
        eyebrow="Accountability"
        title="Security & audit trail"
        description="An append-only record of every mandate change, recommendation, policy decision, approval and PayPal call. Sensitive fields are redacted before they are stored."
        actions={<RefreshButton onClick={() => void state.reload()} loading={state.loading} />}
      />

      <div className="mb-4 flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <Segmented label="Filter events" value={filter} onChange={setFilter} options={FILTERS.map((f) => (f.value === 'alerts' ? { ...f, count: alerts } : f.value === 'all' ? { ...f, count: state.data?.length ?? 0 } : f))} />
        <div className="relative xl:w-80">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-faint" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search events, IDs, details…" aria-label="Search audit events" className={cx(inputClass, 'pl-9')} />
        </div>
      </div>

      {state.error && <ErrorState message={state.error} onRetry={() => void state.reload()} />}

      <Card>
        {!state.data ? (
          <SkeletonRows rows={6} />
        ) : rows.length === 0 ? (
          <EmptyState icon={<ShieldCheck className="h-8 w-8" />} title={state.data.length ? 'No events match' : 'No audit events yet'} />
        ) : (
          <div className="divide-y divide-line">
            {groups.map((g) => (
              <section key={g.label} className="px-5 py-5 sm:px-6">
                <h2 className="mb-4 flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.14em] text-faint">
                  {g.label}
                  <span className="h-px flex-1 bg-line" />
                  <span className="normal-case tracking-normal">{g.events.length} event{g.events.length === 1 ? '' : 's'}</span>
                </h2>
                <ol>
                  {g.events.map((e, i) => <EventRow key={e.id} e={e} last={i === g.events.length - 1} />)}
                </ol>
              </section>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
};

export default AuditTrail;
