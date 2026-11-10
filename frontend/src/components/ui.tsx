import React, { useEffect, useId, useRef } from 'react';
import { AlertTriangle, Inbox, Loader2, RefreshCw, X } from 'lucide-react';
import { statusMeta, type Tone } from '../lib/format';

/* ----------------------------------------------------------------------------
   Tone styles: one mapping used by badges, dots and panels.
---------------------------------------------------------------------------- */
export const TONE_TEXT: Record<Tone, string> = {
  ok: 'text-ok',
  bad: 'text-bad',
  warn: 'text-warn',
  info: 'text-info',
  accent: 'text-accent',
  caution: 'text-caution',
  neutral: 'text-muted',
};
const TONE_BADGE: Record<Tone, string> = {
  ok: 'bg-ok/10 text-ok ring-ok/25',
  bad: 'bg-bad/10 text-bad ring-bad/25',
  warn: 'bg-warn/10 text-warn ring-warn/25',
  info: 'bg-info/10 text-info ring-info/25',
  accent: 'bg-accent/10 text-accent ring-accent/25',
  caution: 'bg-caution/10 text-caution ring-caution/25',
  neutral: 'bg-white/5 text-muted ring-white/10',
};
export const TONE_DOT: Record<Tone, string> = {
  ok: 'bg-ok',
  bad: 'bg-bad',
  warn: 'bg-warn',
  info: 'bg-info',
  accent: 'bg-accent',
  caution: 'bg-caution',
  neutral: 'bg-faint',
};
export const TONE_PANEL: Record<Tone, string> = {
  ok: 'border-ok/25 bg-ok/[0.06]',
  bad: 'border-bad/25 bg-bad/[0.06]',
  warn: 'border-warn/25 bg-warn/[0.06]',
  info: 'border-info/25 bg-info/[0.06]',
  accent: 'border-accent/25 bg-accent/[0.06]',
  caution: 'border-caution/25 bg-caution/[0.06]',
  neutral: 'border-line bg-raised',
};

export const cx = (...parts: (string | false | null | undefined)[]) => parts.filter(Boolean).join(' ');

export const Badge: React.FC<{ tone?: Tone; children: React.ReactNode; dot?: boolean; className?: string; title?: string }> = ({
  tone = 'neutral',
  children,
  dot,
  className,
  title,
}) => (
  <span
    title={title}
    className={cx(
      'inline-flex max-w-full items-center gap-1.5 rounded-md px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset whitespace-nowrap',
      TONE_BADGE[tone],
      className,
    )}
  >
    {dot && <span className={cx('h-1.5 w-1.5 shrink-0 rounded-full', TONE_DOT[tone])} />}
    <span className="truncate">{children}</span>
  </span>
);

export const StatusPill: React.FC<{ status: string; className?: string }> = ({ status, className }) => {
  const meta = statusMeta(status);
  return (
    <Badge tone={meta.tone} dot title={meta.description} className={className}>
      {meta.label}
    </Badge>
  );
};

export const Card: React.FC<React.HTMLAttributes<HTMLDivElement> & { raised?: boolean }> = ({ className, raised, ...rest }) => (
  <div {...rest} className={cx('rounded-xl border border-line', raised ? 'bg-raised' : 'bg-surface', className)} />
);

export const CardHeader: React.FC<{ title: React.ReactNode; subtitle?: React.ReactNode; action?: React.ReactNode; icon?: React.ReactNode }> = ({
  title,
  subtitle,
  action,
  icon,
}) => (
  <div className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
    <div className="flex min-w-0 items-start gap-3">
      {icon && <div className="mt-0.5 text-faint">{icon}</div>}
      <div className="min-w-0">
        <h3 className="text-sm font-semibold text-fg">{title}</h3>
        {subtitle && <p className="mt-0.5 text-xs text-muted">{subtitle}</p>}
      </div>
    </div>
    {action}
  </div>
);

export const Eyebrow: React.FC<{ children: React.ReactNode; className?: string }> = ({ children, className }) => (
  <p className={cx('text-[11px] font-medium uppercase tracking-[0.14em] text-faint', className)}>{children}</p>
);

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'success' | 'danger' | 'paypal';
const BTN: Record<ButtonVariant, string> = {
  primary: 'bg-accent-strong text-white hover:bg-accent shadow-[inset_0_1px_0_rgb(255_255_255/0.18)]',
  success: 'bg-ok text-ink hover:bg-ok/90 shadow-[inset_0_1px_0_rgb(255_255_255/0.35)]',
  paypal: 'bg-paypal text-white hover:bg-paypal/90 shadow-[inset_0_1px_0_rgb(255_255_255/0.2)]',
  secondary: 'bg-raised text-fg ring-1 ring-inset ring-line-strong hover:bg-hover',
  danger: 'bg-bad/10 text-bad ring-1 ring-inset ring-bad/30 hover:bg-bad/15',
  ghost: 'text-muted hover:bg-white/5 hover:text-fg',
};

export const Button: React.FC<
  React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; loading?: boolean; icon?: React.ReactNode; size?: 'sm' | 'md' | 'lg' }
> = ({ variant = 'primary', loading, icon, children, className, disabled, size = 'md', type = 'button', ...rest }) => (
  <button
    {...rest}
    type={type}
    disabled={disabled || loading}
    className={cx(
      'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-45',
      size === 'sm' ? 'h-8 px-2.5 text-xs' : size === 'lg' ? 'h-11 px-5 text-sm' : 'h-9 px-3.5 text-sm',
      BTN[variant],
      className,
    )}
  >
    {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : icon}
    {children}
  </button>
);

export const Spinner: React.FC<{ label?: string }> = ({ label = 'Loading…' }) => (
  <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted" role="status">
    <Loader2 className="h-4 w-4 animate-spin" />
    {label}
  </div>
);

export const Skeleton: React.FC<{ className?: string }> = ({ className }) => <div className={cx('skeleton', className)} aria-hidden />;

export const SkeletonRows: React.FC<{ rows?: number }> = ({ rows = 4 }) => (
  <div className="space-y-3 p-5" role="status" aria-label="Loading">
    {Array.from({ length: rows }).map((_, i) => (
      <div key={i} className="flex items-center gap-3">
        <Skeleton className="h-9 w-9 shrink-0" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-3 w-2/5" />
          <Skeleton className="h-2.5 w-1/4" />
        </div>
        <Skeleton className="h-5 w-20" />
      </div>
    ))}
  </div>
);

export const ErrorState: React.FC<{ message: string; onRetry?: () => void; compact?: boolean }> = ({ message, onRetry, compact }) => (
  <div
    role="alert"
    className={cx(
      'flex flex-col items-start gap-3 rounded-lg border border-bad/30 bg-bad/[0.07] text-sm text-bad sm:flex-row sm:items-center',
      compact ? 'px-3 py-2' : 'px-4 py-3',
    )}
  >
    <AlertTriangle className="h-4 w-4 shrink-0" />
    <span className="flex-1 break-words text-fg/90">{message}</span>
    {onRetry && (
      <Button size="sm" variant="secondary" onClick={onRetry} icon={<RefreshCw className="h-3.5 w-3.5" />}>
        Retry
      </Button>
    )}
  </div>
);

export const EmptyState: React.FC<{ title: string; description?: string; action?: React.ReactNode; icon?: React.ReactNode }> = ({
  title,
  description,
  action,
  icon,
}) => (
  <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
    <div className="text-line-strong">{icon ?? <Inbox className="h-8 w-8" />}</div>
    <p className="text-sm font-medium text-fg">{title}</p>
    {description && <p className="max-w-sm text-xs text-muted">{description}</p>}
    {action && <div className="mt-2">{action}</div>}
  </div>
);

export const PageHeader: React.FC<{ eyebrow?: string; title: string; description?: React.ReactNode; actions?: React.ReactNode }> = ({
  eyebrow,
  title,
  description,
  actions,
}) => (
  <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
    <div>
      {eyebrow && <Eyebrow className="mb-1.5">{eyebrow}</Eyebrow>}
      <h1 className="text-2xl font-semibold tracking-tight text-fg">{title}</h1>
      {description && <p className="mt-1.5 max-w-2xl text-sm text-muted">{description}</p>}
    </div>
    {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
  </div>
);

export const RefreshButton: React.FC<{ onClick: () => void; loading?: boolean }> = ({ onClick, loading }) => (
  <Button variant="secondary" size="sm" onClick={onClick} loading={loading} icon={<RefreshCw className="h-3.5 w-3.5" />}>
    Refresh
  </Button>
);

export const Mono: React.FC<{ children: React.ReactNode; className?: string; title?: string }> = ({ children, className, title }) => (
  <span title={title} className={cx('font-mono text-[12px] break-all', className ?? 'text-fg/85')}>
    {children}
  </span>
);

/** Budget meter: captured (emerald) + committed (amber) + optional highlighted slice for "this purchase". */
export const Meter: React.FC<{ max: number; spent: number; committed: number; preview?: number; previewTone?: 'accent' | 'bad'; className?: string }> = ({
  max,
  spent,
  committed,
  preview = 0,
  previewTone = 'accent',
  className,
}) => {
  const pct = (v: number) => (max > 0 ? Math.max(0, Math.min(100, (v / max) * 100)) : 0);
  return (
    <div className={cx('h-2 w-full overflow-hidden rounded-full bg-white/[0.06]', className)} aria-hidden>
      <div className="flex h-full">
        <div className="h-full bg-ok transition-[width] duration-500" style={{ width: `${pct(spent)}%` }} />
        <div className="h-full bg-warn transition-[width] duration-500" style={{ width: `${pct(committed)}%` }} />
        <div
          className={cx('h-full transition-[width] duration-500', previewTone === 'bad' ? 'bg-bad' : 'bg-accent')}
          style={{ width: `${pct(Math.min(preview, Math.max(0, max - spent - committed)))}%` }}
        />
      </div>
    </div>
  );
};

export const Segmented = <T extends string>({
  value,
  onChange,
  options,
  label,
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string; count?: number }[];
  label: string;
}) => (
  <div role="tablist" aria-label={label} className="inline-flex max-w-full flex-wrap gap-1 rounded-lg border border-line bg-surface p-1">
    {options.map((o) => (
      <button
        key={o.value}
        role="tab"
        type="button"
        aria-selected={value === o.value}
        onClick={() => onChange(o.value)}
        className={cx(
          'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
          value === o.value ? 'bg-hover text-fg shadow-[inset_0_0_0_1px_var(--color-line-strong)]' : 'text-muted hover:text-fg',
        )}
      >
        {o.label}
        {o.count !== undefined && <span className="ml-1.5 text-faint tnum">{o.count}</span>}
      </button>
    ))}
  </div>
);

export const inputClass =
  'w-full rounded-lg border border-line-strong bg-ink/60 px-3 py-2 text-sm text-fg placeholder:text-faint transition-colors focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/25';

export const Field: React.FC<{ label: string; hint?: string; error?: string | null; children: (id: string) => React.ReactNode }> = ({
  label,
  hint,
  error,
  children,
}) => {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-xs font-medium text-fg/90">
        {label}
      </label>
      {children(id)}
      {error ? <p className="mt-1 text-[11px] text-bad">{error}</p> : hint ? <p className="mt-1 text-[11px] text-faint">{hint}</p> : null}
    </div>
  );
};

export const Dialog: React.FC<{ open: boolean; onClose: () => void; title: string; description?: string; children: React.ReactNode; wide?: boolean }> = ({
  open,
  onClose,
  title,
  description,
  children,
  wide,
}) => {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const prev = document.activeElement as HTMLElement | null;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    ref.current?.querySelector<HTMLElement>('input, textarea, select, button:not([aria-label="Close"])')?.focus();
    return () => {
      window.removeEventListener('keydown', onKey);
      prev?.focus?.();
    };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/60 p-3 backdrop-blur-[2px] animate-fade sm:p-10" onMouseDown={onClose}>
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={cx('w-full rounded-xl border border-line-strong bg-surface shadow-2xl shadow-black/50 animate-rise', wide ? 'max-w-2xl' : 'max-w-md')}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
          <div>
            <h2 className="text-sm font-semibold text-fg">{title}</h2>
            {description && <p className="mt-1 text-xs text-muted">{description}</p>}
          </div>
          <button onClick={onClose} className="rounded-md p-1 text-faint hover:bg-white/5 hover:text-fg" aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
};

export const ConfirmDialog: React.FC<{
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  body: React.ReactNode;
  confirmLabel: string;
  danger?: boolean;
  loading?: boolean;
}> = ({ open, onClose, onConfirm, title, body, confirmLabel, danger, loading }) => (
  <Dialog open={open} onClose={onClose} title={title}>
    <div className="space-y-5">
      <div className="text-sm leading-relaxed text-muted">{body}</div>
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>
          Cancel
        </Button>
        <Button variant={danger ? 'danger' : 'primary'} onClick={onConfirm} loading={loading}>
          {confirmLabel}
        </Button>
      </div>
    </div>
  </Dialog>
);
