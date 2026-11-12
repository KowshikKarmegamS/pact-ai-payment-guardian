import React from 'react';

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
