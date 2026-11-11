import React from 'react';
import type { Proposal } from '../types';
import { dayKey, parseDate } from '../lib/format';

/** Donut showing captured and committed spend against a mandate budget. */
export const BudgetRing: React.FC<{ max: number; spent: number; committed: number; size?: number; children?: React.ReactNode }> = ({
  max,
  spent,
  committed,
  size = 132,
  children,
}) => {
  const stroke = 10;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const frac = (v: number) => (max > 0 ? Math.max(0, Math.min(1, v / max)) : 0);
  const spentLen = frac(spent) * c;
  const committedLen = frac(committed) * c;
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90" role="img" aria-label="Budget used">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgb(255 255 255 / 0.06)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--color-warn)"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${spentLen + committedLen} ${c}`}
          className="transition-[stroke-dasharray] duration-700"
          opacity={committed > 0 ? 1 : 0}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--color-ok)"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${spentLen} ${c}`}
          className="transition-[stroke-dasharray] duration-700"
          opacity={spent > 0 ? 1 : 0}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">{children}</div>
    </div>
  );
};

interface DayBucket {
  key: string;
  label: string;
  captured: number;
  passed: number;
  blocked: number;
}

export function bucketDecisions(proposals: Proposal[], days = 14): DayBucket[] {
  const buckets: DayBucket[] = [];
  const index = new Map<string, DayBucket>();
  const today = new Date();
  for (let i = days - 1; i >= 0; i -= 1) {
    const d = new Date(today.getFullYear(), today.getMonth(), today.getDate() - i);
    const b: DayBucket = { key: dayKey(d), label: d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }), captured: 0, passed: 0, blocked: 0 };
    buckets.push(b);
    index.set(b.key, b);
  }
  proposals.forEach((p) => {
    const d = parseDate(p.created_at);
    const b = d ? index.get(dayKey(d)) : undefined;
    if (!b) return;
    if (p.status === 'POLICY_REJECTED') b.blocked += 1;
    else if (p.status === 'CAPTURED') b.captured += 1;
    else b.passed += 1;
  });
  return buckets;
}

/** Stacked bars: policy decisions per day (captured / passed policy / blocked). */
export const DecisionChart: React.FC<{ proposals: Proposal[]; days?: number }> = ({ proposals, days = 14 }) => {
  const data = bucketDecisions(proposals, days);
  const maxTotal = Math.max(1, ...data.map((d) => d.captured + d.passed + d.blocked));
  const H = 132;
  const unit = H / maxTotal;
  return (
    <div>
      <div className="flex items-end gap-1.5" style={{ height: H }} role="img" aria-label="Policy decisions per day">
        {data.map((d) => {
          const total = d.captured + d.passed + d.blocked;
          return (
            <div key={d.key} className="group relative flex h-full flex-1 flex-col justify-end" title={`${d.label}: ${d.captured} captured, ${d.passed} passed, ${d.blocked} blocked`}>
              {total === 0 ? (
                <div className="h-[3px] rounded-full bg-white/[0.06]" />
              ) : (
                <div className="flex flex-col gap-[2px] overflow-hidden rounded-[5px]">
                  {d.blocked > 0 && <div className="bg-bad/85" style={{ height: Math.max(4, d.blocked * unit - 2) }} />}
                  {d.passed > 0 && <div className="bg-accent/85" style={{ height: Math.max(4, d.passed * unit - 2) }} />}
                  {d.captured > 0 && <div className="bg-ok/90" style={{ height: Math.max(4, d.captured * unit - 2) }} />}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div className="mt-2 flex justify-between text-[10px] text-faint">
        <span>{data[0]?.label}</span>
        <span>{data[Math.floor(data.length / 2)]?.label}</span>
        <span>Today</span>
      </div>
    </div>
  );
};

export const Legend: React.FC<{ items: { label: string; className: string; value?: React.ReactNode }[] }> = ({ items }) => (
  <div className="flex flex-wrap gap-x-4 gap-y-1.5">
    {items.map((i) => (
      <span key={i.label} className="inline-flex items-center gap-1.5 text-xs text-muted">
        <span className={`h-2 w-2 rounded-sm ${i.className}`} />
        {i.label}
        {i.value !== undefined && <span className="text-fg tnum">{i.value}</span>}
      </span>
    ))}
  </div>
);
