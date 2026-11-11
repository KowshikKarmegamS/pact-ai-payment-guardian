import React, { useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { Activity, CreditCard, LayoutDashboard, Menu, Plug, ScrollText, ShieldCheck, Sparkles, Store, X } from 'lucide-react';
import { pactApi } from '../api/pact';
import { aiLabel } from '../lib/format';
import { useAsync } from '../lib/useAsync';
import type { SystemStatus } from '../types';
import { cx } from './ui';
import { SignOutButton } from './OwnerGate';

const NAV = [
  { to: '/', label: 'Control Center', icon: LayoutDashboard },
  { to: '/mandates', label: 'Mandates', icon: ScrollText },
  { to: '/agents', label: 'Agents', icon: Plug },
  { to: '/assistant', label: 'Reference agent', icon: Sparkles },
  { to: '/transactions', label: 'Transactions', icon: CreditCard, match: '/proposals' },
  { to: '/audit', label: 'Audit Trail', icon: Activity },
  { to: '/catalog', label: 'Catalog', icon: Store },
];

export const Logo: React.FC<{ size?: number }> = ({ size = 32 }) => (
  <div
    className="flex items-center justify-center rounded-[10px] bg-gradient-to-br from-accent to-violet text-white shadow-[inset_0_1px_0_rgb(255_255_255/0.3)]"
    style={{ width: size, height: size }}
  >
    <ShieldCheck style={{ width: size * 0.56, height: size * 0.56 }} strokeWidth={2.2} />
  </div>
);

const Row: React.FC<{ label: string; ok: boolean | null; value: string }> = ({ label, ok, value }) => (
  <div className="flex items-center justify-between gap-3">
    <span className="text-faint">{label}</span>
    <span className="flex min-w-0 items-center gap-1.5 text-muted">
      <span className={cx('h-1.5 w-1.5 shrink-0 rounded-full', ok === null ? 'bg-faint' : ok ? 'bg-ok' : 'bg-warn')} />
      <span className="truncate">{value}</span>
    </span>
  </div>
);

const SystemPanel: React.FC<{ status: SystemStatus | null; error: string | null }> = ({ status, error }) => {
  if (error) {
    return <div className="rounded-lg border border-bad/30 bg-bad/[0.07] p-3 text-[11px] text-bad">API unreachable. Start the backend server.</div>;
  }
  const pp = status?.paypal;
  const oauthOk = pp?.oauth.checked ? !!pp.oauth.ok : null;
  return (
    <div className="space-y-2 rounded-lg border border-line bg-ink/40 p-3 text-[11px]">
      <Row
        label="PayPal"
        ok={pp ? (pp.environment === 'sandbox' ? oauthOk : false) : null}
        value={!pp ? '…' : pp.environment !== 'sandbox' ? 'Invalid config' : oauthOk === false ? 'Auth failed' : 'Sandbox connected'}
      />
      <Row
        label="Recommender"
        ok={status ? status.ai.mode !== 'heuristic' : null}
        value={!status ? '…' : status.ai.mode === 'heuristic' ? 'Keyword fallback' : aiLabel(status.ai.mode, status.ai.model).replace('Google ', '')}
      />
      <Row label="Policy engine" ok={status ? true : null} value="Deterministic" />
    </div>
  );
};

export const Layout: React.FC = () => {
  const [open, setOpen] = useState(false);
  const status = useAsync(() => pactApi.getStatus(true));
  const { pathname } = useLocation();

  return (
    <div className="min-h-screen lg:flex">
      {/* Mobile top bar */}
      <div className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-ink/90 px-4 py-3 backdrop-blur lg:hidden">
        <div className="flex items-center gap-2.5">
          <Logo size={28} />
          <span className="text-sm font-semibold tracking-wide">PACT</span>
        </div>
        <button onClick={() => setOpen((v) => !v)} className="rounded-md p-1.5 text-muted hover:bg-white/5" aria-label="Toggle navigation">
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      <aside
        className={cx(
          'fixed inset-y-0 left-0 z-40 flex w-60 flex-col border-r border-line bg-surface/95 backdrop-blur transition-transform lg:sticky lg:top-0 lg:h-screen lg:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex items-center gap-3 px-5 pb-5 pt-6">
          <Logo />
          <div>
            <p className="text-[15px] font-semibold leading-none tracking-wide text-fg">PACT</p>
            <p className="mt-1 text-[11px] text-faint">Authorization Gateway</p>
          </div>
        </div>
        <nav className="flex-1 space-y-0.5 px-3" aria-label="Main">
          {NAV.map((item) => {
            const extra = item.match ? pathname.startsWith(item.match) : false;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                onClick={() => setOpen(false)}
                className={({ isActive }) =>
                  cx(
                    'group flex items-center gap-3 rounded-lg px-3 py-2 text-[13px] font-medium transition-colors',
                    isActive || extra ? 'bg-white/[0.06] text-fg shadow-[inset_0_0_0_1px_var(--color-line)]' : 'text-muted hover:bg-white/[0.03] hover:text-fg',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <item.icon className={cx('h-4 w-4 shrink-0', isActive || extra ? 'text-accent' : 'text-faint group-hover:text-muted')} />
                    {item.label}
                  </>
                )}
              </NavLink>
            );
          })}
        </nav>
        <div className="space-y-3 p-4">
          <SystemPanel status={status.data} error={status.error} />
          <SignOutButton />
          <p className="px-1 text-[10px] leading-relaxed text-faint">PayPal Sandbox demo. Test accounts only; no real money moves.</p>
        </div>
      </aside>
      {open && <div className="fixed inset-0 z-30 bg-black/60 lg:hidden" onClick={() => setOpen(false)} />}

      <main className="min-w-0 flex-1">
        <div className="mx-auto w-full max-w-[1440px] px-4 py-6 sm:px-8 lg:px-10 lg:py-9">
          <Outlet />
        </div>
      </main>
    </div>
  );
};

export default Layout;
