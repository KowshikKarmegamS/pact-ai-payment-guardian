import React, { useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import {
  Shield,
  LayoutDashboard,
  ScrollText,
  Bot,
  CreditCard,
  History,
  Menu,
  X,
  CheckCircle2,
  Bell,
  ExternalLink,
} from 'lucide-react';

interface NavItem {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
}

const navItems: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/mandates', label: 'Mandates', icon: ScrollText },
  { to: '/assistant', label: 'Shopping Assistant', icon: Bot, badge: 'AI' },
  { to: '/transactions', label: 'Transactions', icon: CreditCard },
  { to: '/audit', label: 'Audit Trail', icon: History },
];

export const Layout: React.FC = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const location = useLocation();

  const getPageTitle = (path: string): string => {
    switch (path) {
      case '/':
        return 'Overview & Guardian Health';
      case '/mandates':
        return 'Spending Mandates';
      case '/assistant':
        return 'AI Autonomous Shopping Assistant';
      case '/transactions':
        return 'Transaction Ledger & Proposals';
      case '/audit':
        return 'Cryptographic Audit Trail';
      default:
        return 'Dashboard';
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col md:flex-row font-sans">
      {/* Mobile Top Bar */}
      <div className="md:hidden flex items-center justify-between bg-slate-950 px-4 py-3 text-white border-b border-slate-800">
        <div className="flex items-center space-x-2.5">
          <div className="p-1.5 bg-indigo-600 rounded-lg shadow-sm shadow-indigo-500/50">
            <Shield className="w-5 h-5 text-white" />
          </div>
          <div>
            <span className="font-extrabold tracking-wider text-base text-white">PACT</span>
            <span className="text-xs text-indigo-300 block -mt-1 font-medium">Payment Guardian</span>
          </div>
        </div>
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="p-2 rounded-lg bg-slate-900 text-slate-300 hover:text-white hover:bg-slate-800 focus:outline-none"
          aria-label="Toggle menu"
        >
          {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Sidebar for Desktop & Mobile Overlay */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-64 bg-slate-950 text-slate-200 flex flex-col justify-between border-r border-slate-800/80 transition-transform duration-200 ease-in-out md:translate-x-0 md:static ${
          mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex flex-col h-full">
          {/* Logo / Brand Header */}
          <div className="p-6 border-b border-slate-900">
            <div className="flex items-center space-x-3">
              <div className="p-2.5 bg-gradient-to-tr from-indigo-600 to-indigo-500 rounded-xl shadow-md shadow-indigo-600/30 flex items-center justify-center">
                <Shield className="w-6 h-6 text-white stroke-[2.5]" />
              </div>
              <div>
                <h1 className="text-xl font-black tracking-tight text-white flex items-center gap-1.5">
                  PACT
                  <span className="text-[10px] font-semibold uppercase tracking-widest px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                    AI Guardian
                  </span>
                </h1>
                <p className="text-xs text-slate-400 font-medium">Safe Agentic Commerce</p>
              </div>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="flex-1 px-3 py-6 space-y-1.5 overflow-y-auto">
            <div className="px-3 pb-2 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Navigation
            </div>
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  onClick={() => setMobileMenuOpen(false)}
                  end={item.to === '/'}
                  className={({ isActive }) =>
                    `flex items-center justify-between px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all ${
                      isActive
                        ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-600/30 font-semibold'
                        : 'text-slate-400 hover:text-slate-100 hover:bg-slate-900'
                    }`
                  }
                >
                  <div className="flex items-center space-x-3">
                    <Icon className="w-4 h-4 shrink-0" />
                    <span>{item.label}</span>
                  </div>
                  {item.badge && (
                    <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-indigo-400/20 text-indigo-300 border border-indigo-400/30">
                      {item.badge}
                    </span>
                  )}
                </NavLink>
              );
            })}
          </nav>

          {/* Sandbox & Guard Status Footer */}
          <div className="p-4 border-t border-slate-900 space-y-3 bg-slate-950/60">
            <div className="p-3 rounded-lg bg-slate-900/90 border border-slate-800">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-300">PayPal Sandbox</span>
                <span className="flex items-center gap-1.5 text-[11px] text-emerald-400 font-medium">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                  Active
                </span>
              </div>
              <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">
                Zero-trust policy enforcement before payment capture.
              </p>
            </div>

            <div className="flex items-center justify-between px-1 text-xs text-slate-400">
              <span className="font-mono text-[10px] text-slate-400">v0.1.0-alpha</span>
              <a
                href="https://github.com/KowshikKarmegamS/pact-ai-payment-guardian"
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1 hover:text-slate-300 transition-colors"
              >
                GitHub <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </div>
        </div>
      </aside>

      {/* Backdrop for mobile */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 z-30 bg-slate-950/60 backdrop-blur-xs md:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        {/* Top Header */}
        <header className="sticky top-0 z-20 bg-white/95 backdrop-blur-sm border-b border-slate-200 px-6 py-4 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-900 tracking-tight">
              {getPageTitle(location.pathname)}
            </h2>
            <p className="text-xs text-slate-500">
              PACT AI Payment Guardian &bull; PayPal Hackathon 2026
            </p>
          </div>

          <div className="flex items-center space-x-3">
            {/* Policy Guardian Status Pill */}
            <div className="hidden sm:flex items-center space-x-2 px-3 py-1.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-medium">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              <span>Policy Engine: Active</span>
            </div>

            {/* Notification Bell */}
            <button
              className="p-2 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors relative"
              aria-label="Notifications"
            >
              <Bell className="w-4 h-4" />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-indigo-600 ring-2 ring-white"></span>
            </button>

            {/* User Profile avatar */}
            <div className="flex items-center space-x-2.5 pl-2 border-l border-slate-200">
              <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-700 to-indigo-500 text-white flex items-center justify-center font-bold text-xs shadow-xs">
                EA
              </div>
              <div className="hidden lg:block text-left">
                <div className="text-xs font-semibold text-slate-800 leading-tight">Engineering Admin</div>
                <div className="text-[10px] text-slate-500 leading-tight">Admin Mandate Issuer</div>
              </div>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 p-6 lg:p-8 max-w-7xl w-full mx-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default Layout;
