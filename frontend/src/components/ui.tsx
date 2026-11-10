import React from 'react';
import { AlertTriangle, Inbox, Loader2, RefreshCw } from 'lucide-react';
import { statusMeta, type Tone } from '../lib/format';

const TONES: Record<Tone, string> = {
  red: 'bg-red-50 text-red-700 ring-red-600/20',
  amber: 'bg-amber-50 text-amber-800 ring-amber-600/25',
  blue: 'bg-sky-50 text-sky-700 ring-sky-600/20',
  indigo: 'bg-indigo-50 text-indigo-700 ring-indigo-600/20',
  teal: 'bg-teal-50 text-teal-700 ring-teal-600/20',
  green: 'bg-emerald-50 text-emerald-700 ring-emerald-600/25',
  slate: 'bg-slate-100 text-slate-700 ring-slate-500/20',
  orange: 'bg-orange-50 text-orange-700 ring-orange-600/20',
};

const DOTS: Record<Tone, string> = {
  red: 'bg-red-500',
  amber: 'bg-amber-500',
  blue: 'bg-sky-500',
  indigo: 'bg-indigo-500',
  teal: 'bg-teal-500',
  green: 'bg-emerald-500',
  slate: 'bg-slate-400',
  orange: 'bg-orange-500',
};

export const Badge: React.FC<{ tone: Tone; children: React.ReactNode; dot?: boolean; className?: string }> = ({
  tone,
  children,
  dot,
  className = '',
}) => (
  <span
    className={`inline-flex max-w-full items-center gap-1.5 rounded-md px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ring-1 ring-inset whitespace-nowrap ${TONES[tone]} ${className}`}
  >
    {dot && <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${DOTS[tone]}`} />}
    <span className="truncate">{children}</span>
  </span>
);

export const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const meta = statusMeta(status);
  return (
    <Badge tone={meta.tone} dot>
      <span title={meta.description}>{meta.label}</span>
    </Badge>
  );
};

export const Card: React.FC<{ children: React.ReactNode; className?: string; as?: 'div' | 'section' }> = ({
  children,
  className = '',
  as = 'div',
}) => {
  const Tag = as;
  return <Tag className={`rounded-xl border border-slate-200 bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04)] ${className}`}>{children}</Tag>;
};

export const CardHeader: React.FC<{ title: React.ReactNode; subtitle?: React.ReactNode; action?: React.ReactNode }> = ({
  title,
  subtitle,
  action,
}) => (
  <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-5 py-4">
    <div className="min-w-0">
      <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
      {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
    </div>
    {action}
  </div>
);

type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost' | 'success';
const BTN: Record<ButtonVariant, string> = {
  primary: 'bg-slate-900 text-white hover:bg-slate-800 focus-visible:outline-slate-900',
  success: 'bg-emerald-600 text-white hover:bg-emerald-700 focus-visible:outline-emerald-600',
  secondary: 'bg-white text-slate-700 ring-1 ring-inset ring-slate-300 hover:bg-slate-50 focus-visible:outline-slate-400',
  danger: 'bg-white text-red-700 ring-1 ring-inset ring-red-200 hover:bg-red-50 focus-visible:outline-red-500',
  ghost: 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-slate-400',
};

export const Button: React.FC<
  React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; loading?: boolean; icon?: React.ReactNode; size?: 'sm' | 'md' }
> = ({ variant = 'primary', loading, icon, children, className = '', disabled, size = 'md', ...rest }) => (
  <button
    {...rest}
    disabled={disabled || loading}
    className={`inline-flex items-center justify-center gap-2 rounded-lg font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-50 ${
      size === 'sm' ? 'px-2.5 py-1.5 text-xs' : 'px-3.5 py-2 text-sm'
    } ${BTN[variant]} ${className}`}
  >
    {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : icon}
    {children}
  </button>
);

export const Spinner: React.FC<{ label?: string }> = ({ label = 'Loading…' }) => (
  <div className="flex items-center justify-center gap-2 py-10 text-sm text-slate-500" role="status">
    <Loader2 className="h-4 w-4 animate-spin" />
    {label}
  </div>
);

export const ErrorState: React.FC<{ message: string; onRetry?: () => void; compact?: boolean }> = ({ message, onRetry, compact }) => (
  <div
    role="alert"
    className={`flex flex-col items-start gap-3 rounded-lg border border-red-200 bg-red-50 text-sm text-red-800 sm:flex-row sm:items-center ${
      compact ? 'px-3 py-2' : 'px-4 py-3'
    }`}
  >
    <AlertTriangle className="h-4 w-4 shrink-0" />
    <span className="flex-1 break-words">{message}</span>
    {onRetry && (
      <Button size="sm" variant="secondary" onClick={onRetry} icon={<RefreshCw className="h-3.5 w-3.5" />}>
        Retry
      </Button>
    )}
  </div>
);

export const EmptyState: React.FC<{ title: string; description?: string; action?: React.ReactNode }> = ({ title, description, action }) => (
  <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
    <Inbox className="h-8 w-8 text-slate-300" />
    <p className="text-sm font-semibold text-slate-700">{title}</p>
    {description && <p className="max-w-sm text-xs text-slate-500">{description}</p>}
    {action && <div className="mt-2">{action}</div>}
  </div>
);

export const PageHeader: React.FC<{ title: string; description?: React.ReactNode; actions?: React.ReactNode }> = ({
  title,
  description,
  actions,
}) => (
  <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
    <div>
      <h1 className="text-xl font-semibold tracking-tight text-slate-900">{title}</h1>
      {description && <p className="mt-1 max-w-2xl text-sm text-slate-500">{description}</p>}
    </div>
    {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
  </div>
);

export const RefreshButton: React.FC<{ onClick: () => void; loading?: boolean }> = ({ onClick, loading }) => (
  <Button variant="secondary" size="sm" onClick={onClick} loading={loading} icon={<RefreshCw className="h-3.5 w-3.5" />}>
    Refresh
  </Button>
);

export const Mono: React.FC<{ children: React.ReactNode; className?: string; title?: string }> = ({ children, className = '', title }) => (
  <span title={title} className={`font-mono text-[12px] text-slate-700 break-all ${className}`}>
    {children}
  </span>
);

export const BudgetBar: React.FC<{ max: number; spent: number; committed: number }> = ({ max, spent, committed }) => {
  const pct = (v: number) => (max > 0 ? Math.min(100, (v / max) * 100) : 0);
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100" aria-hidden>
      <div className="flex h-full">
        <div className="h-full bg-emerald-500" style={{ width: `${pct(spent)}%` }} />
        <div className="h-full bg-amber-400" style={{ width: `${pct(committed)}%` }} />
      </div>
    </div>
  );
};

export const Modal: React.FC<{ open: boolean; onClose: () => void; title: string; children: React.ReactNode; wide?: boolean }> = ({
  open,
  onClose,
  title,
  children,
  wide,
}) => {
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-950/50 p-3 sm:p-8" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`w-full ${wide ? 'max-w-4xl' : 'max-w-xl'} rounded-xl bg-white shadow-xl`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3.5">
          <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
          <button onClick={onClose} className="rounded-md px-2 py-1 text-sm text-slate-500 hover:bg-slate-100" aria-label="Close">
            ✕
          </button>
        </div>
        <div className="p-4 sm:p-5">{children}</div>
      </div>
    </div>
  );
};
