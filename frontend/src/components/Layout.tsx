import React, { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { Bot, CreditCard, ExternalLink, History, LayoutDashboard, Menu, ScrollText, Shield, X } from 'lucide-react';
import { pactApi } from '../api/pact';
import { useAsync } from '../lib/useAsync';
import type { SystemStatus } from '../types';
import { aiLabel } from '../lib/format';

const NAV = [
  { to: '/', label: 'Overview', icon: LayoutDashboard },
  { to: '/assistant', label: 'Shopping Assistant', icon: Bot },
  { to: '/mandates', label: 'Mandates', icon: ScrollText },
  { to: '/transactions', label: 'Transactions', icon: CreditCard },
  { to: '/audit', label: 'Audit Trail', icon: History },
];

const Dot: React.FC<{ ok: boolean | null }> = ({ ok }) => (
  <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${ok === null ? 'bg-slate-500' : ok ? 'bg-emerald-400' : 'bg-amber-400'}`} />
);

const SystemPanel: React.FC<{ status: SystemStatus | null; error: string | null }> = ({ status, error }) => {
  if (error) {
    return (
      <div className="rounded-lg border border-red-900/60 bg-red-950/40 p-3 text-[11px] text-red-200">
        Backend unreachable. Start the API server.
      </div>
    );
  }
  const pp = status?.paypal;
  const oauthOk = pp?.oauth.checked ? !!pp.oauth.ok : null;
  return (
    <div className="space-y-2 rounded-lg border border-slate-800 bg-slate-900/80 p-3 text-[11px]">
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold text-slate-300">PayPal</span>
        <span className="flex items-center gap-1.5 text-slate-400">
          <Dot ok={oauthOk} />
          {!pp ? '…' : pp.environment !== 'sandbox' ? 'Invalid config' : oauthOk === null ? 'Sandbox' : oauthOk ? 'Sandbox connected' : 'Sandbox auth failed'}
        </span>
      </div>
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold text-slate-300">Recommender</span>
        <span className="flex items-center gap-1.5 text-slate-400">
          <Dot ok={status ? status.ai.mode !== 'heuristic' : null} />
          {!status ? '…' : status.ai.mode === 'heuristic' ? 'Heuristic (no AI key)' : aiLabel(status.ai.mode, status.ai.model)}
        </span>
      </div>
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold text-slate-300">Policy engine</span>
        <span className="flex items-center gap-1.5 text-slate-400">
          <Dot ok={status ? true : null} />
          Deterministic
        </span>
      </div>
      {pp && <p className="text-slate-500">Currency {pp.currency}</p>}
    </div>
  );
};

export const Layout: React.FC = () => {
  const [open, setOpen] = useState(false);
  const status = useAsync(() => pactApi.getStatus(true));

  const sidebar = (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 px-5 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white text-slate-950">
          <Shield className="h-5 w-5" strokeWidth={2.5} />
        </div>
        <div>
          <p className="text-base font-bold tracking-tight text-white">PACT</p>
          <p className="text-[11px] text-slate-400">AI Payment Guardian</p>
        </div>
      </div>
      <nav className="flex-1 space-y-0.5 px-3 py-2" aria-label="Main">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            onClick={() => setOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                isActive ? 'bg-white/10 text-white' : 'text-slate-400 hover:bg-white/5 hover:text-slate-100'
              }`
            }
          >
            <item.icon className="h-4 w-4 shrink-0" />
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="space-y-3 p-4">
        <SystemPanel status={status.data} error={status.error} />
        <a
          href="https://github.com/KowshikKarmegamS/pact-ai-payment-guardian"
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-1 px-1 text-[11px] text-slate-500 hover:text-slate-300"
        >
          Source on GitHub <ExternalLink className="h-3 w-3" />
        </a>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-50 md:flex">
      {/* Mobile top bar */}
      <div className="sticky top-0 z-30 flex items-center justify-between bg-slate-950 px-4 py-3 md:hidden">
        <div className="flex items-center gap-2 text-white">
          <Shield className="h-5 w-5" />
          <span className="font-bold">PACT</span>
        </div>
        <button onClick={() => setOpen((v) => !v)} className="rounded-md p-1.5 text-slate-300 hover:bg-white/10" aria-label="Toggle navigation">
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-64 bg-slate-950 transition-transform md:sticky md:top-0 md:h-screen md:translate-x-0 ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {sidebar}
      </aside>
      {open && <div className="fixed inset-0 z-30 bg-slate-950/50 md:hidden" onClick={() => setOpen(false)} />}

      <div className="min-w-0 flex-1">
        <div className="border-b border-amber-200 bg-amber-50 px-4 py-1.5 text-center text-[11px] font-medium text-amber-900">
          PayPal Sandbox demo — no real money moves. Test accounts only.
        </div>
        <main className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default Layout;
