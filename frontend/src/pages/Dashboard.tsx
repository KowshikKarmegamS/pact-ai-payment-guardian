import React from 'react';
import { Link } from 'react-router-dom';
import {
  ScrollText,
  Clock,
  CreditCard,
  DollarSign,
  ShieldCheck,
  ArrowRight,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  Sparkles,
} from 'lucide-react';
import { mockStats, mockProposals, mockMandates } from '../data/mockData';

export const Dashboard: React.FC = () => {
  const stats = mockStats;
  const recentProposals = mockProposals.slice(0, 3);
  const activeMandates = mockMandates.filter((m) => m.is_active);

  const budgetUsedPercentage = Math.round(
    ((stats.totalBudget - stats.budgetRemaining) / stats.totalBudget) * 100
  );

  return (
    <div className="space-y-8">
      {/* Welcome Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white p-6 md:p-8 shadow-lg shadow-indigo-950/20 border border-slate-800">
        <div className="relative z-10 max-w-3xl">
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-indigo-500/20 text-indigo-300 text-xs font-semibold mb-3 border border-indigo-500/30">
            <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
            <span>Autonomous Commerce Protection</span>
          </div>
          <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight">
            Welcome to PACT Payment Guardian
          </h1>
          <p className="mt-2 text-sm md:text-base text-slate-300 leading-relaxed">
            Give your AI agents the autonomy to source and propose purchases, while keeping your funds guarded by deterministic policy mandates and instant PayPal verification.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link
              to="/assistant"
              className="inline-flex items-center space-x-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs md:text-sm px-4 py-2.5 rounded-lg shadow-sm transition-all"
            >
              <Sparkles className="w-4 h-4" />
              <span>Launch Shopping Assistant</span>
            </Link>
            <Link
              to="/mandates"
              className="inline-flex items-center space-x-2 bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium text-xs md:text-sm px-4 py-2.5 rounded-lg border border-slate-700 transition-all"
            >
              <ScrollText className="w-4 h-4" />
              <span>Configure Mandates</span>
            </Link>
          </div>
        </div>

        {/* Decorative shield watermark */}
        <div className="absolute right-[-20px] bottom-[-30px] opacity-10 pointer-events-none">
          <ShieldCheck className="w-64 h-64 text-indigo-400" />
        </div>
      </div>

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* Active Mandates */}
        <div className="bg-white rounded-xl p-5 border border-slate-200/80 shadow-xs hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Active Mandates
            </span>
            <div className="p-2.5 rounded-lg bg-indigo-50 text-indigo-600">
              <ScrollText className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4 flex items-baseline justify-between">
            <span className="text-3xl font-extrabold text-slate-900">{stats.activeMandates}</span>
            <span className="text-xs font-medium text-emerald-600 flex items-center gap-1">
              <TrendingUp className="w-3.5 h-3.5" /> 100% active
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500">Deterministic spend limits enforced</p>
        </div>

        {/* Pending Approvals */}
        <div className="bg-white rounded-xl p-5 border border-slate-200/80 shadow-xs hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Pending Approvals
            </span>
            <div className="p-2.5 rounded-lg bg-amber-50 text-amber-600">
              <Clock className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4 flex items-baseline justify-between">
            <span className="text-3xl font-extrabold text-slate-900">{stats.pendingApprovals}</span>
            <span className="text-xs font-medium text-amber-600 flex items-center gap-1">
              <AlertTriangle className="w-3.5 h-3.5" /> Action needed
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500">AI proposals passing policy check</p>
        </div>

        {/* Total Transactions */}
        <div className="bg-white rounded-xl p-5 border border-slate-200/80 shadow-xs hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Total Transactions
            </span>
            <div className="p-2.5 rounded-lg bg-blue-50 text-blue-600">
              <CreditCard className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4 flex items-baseline justify-between">
            <span className="text-3xl font-extrabold text-slate-900">{stats.totalTransactions}</span>
            <span className="text-xs font-medium text-slate-500">All-time</span>
          </div>
          <p className="mt-1 text-xs text-slate-500">Via PayPal sandbox orders</p>
        </div>

        {/* Budget Remaining */}
        <div className="bg-white rounded-xl p-5 border border-slate-200/80 shadow-xs hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Budget Remaining
            </span>
            <div className="p-2.5 rounded-lg bg-emerald-50 text-emerald-600">
              <DollarSign className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4 flex items-baseline justify-between">
            <span className="text-2xl font-extrabold text-slate-900">
              ${stats.budgetRemaining.toLocaleString('en-US', { minimumFractionDigits: 2 })}
            </span>
            <span className="text-xs font-medium text-slate-500">
              of ${stats.totalBudget.toLocaleString('en-US', { minimumFractionDigits: 0 })}
            </span>
          </div>
          <div className="mt-2.5 w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
            <div
              className="bg-emerald-500 h-1.5 rounded-full transition-all"
              style={{ width: `${100 - budgetUsedPercentage}%` }}
            ></div>
          </div>
        </div>
      </div>

      {/* Two Column Layout: Recent Proposals & Active Mandates */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column (2 cols): Pending Proposals Requiring Attention */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200/80 shadow-xs p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-slate-900">Pending Agent Proposals</h2>
              <p className="text-xs text-slate-500">
                Awaiting human supervisor or automatic execution
              </p>
            </div>
            <Link
              to="/transactions"
              className="text-xs font-medium text-indigo-600 hover:text-indigo-800 flex items-center gap-1"
            >
              View all <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="divide-y divide-slate-100">
            {recentProposals.map((proposal) => (
              <div key={proposal.id} className="py-4 first:pt-2 last:pb-2 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center space-x-2">
                    <span className="font-semibold text-sm text-slate-900">{proposal.product_name}</span>
                    <span
                      className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full ${
                        proposal.status === 'pending'
                          ? 'bg-amber-100 text-amber-800 border border-amber-200'
                          : proposal.status === 'approved'
                          ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                          : proposal.status === 'captured'
                          ? 'bg-blue-100 text-blue-800 border border-blue-200'
                          : 'bg-rose-100 text-rose-800 border border-rose-200'
                      }`}
                    >
                      {proposal.status}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 line-clamp-1">
                    Merchant: <strong className="text-slate-700">{proposal.merchant}</strong> &bull; Category: <span className="text-slate-700">{proposal.category}</span>
                  </p>
                  <p className="text-xs text-slate-600 italic bg-slate-50 p-2 rounded-md border border-slate-100">
                    &ldquo;{proposal.ai_reasoning}&rdquo;
                  </p>
                </div>

                <div className="sm:text-right shrink-0">
                  <div className="text-base font-bold text-slate-900">
                    ${Number(proposal.total_amount).toFixed(2)}
                  </div>
                  <div className="text-[11px] text-slate-400">Qty: {proposal.quantity}</div>
                  <Link
                    to="/assistant"
                    className="mt-2 inline-block text-xs font-medium text-indigo-600 hover:text-indigo-800"
                  >
                    Inspect in Assistant &rarr;
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right Column (1 col): Active Mandates Snapshot */}
        <div className="bg-white rounded-xl border border-slate-200/80 shadow-xs p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-slate-900">Active Mandates</h2>
              <p className="text-xs text-slate-500">Autonomous spend policies</p>
            </div>
            <Link
              to="/mandates"
              className="text-xs font-medium text-indigo-600 hover:text-indigo-800 flex items-center gap-1"
            >
              Manage <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="space-y-3">
            {activeMandates.slice(0, 3).map((mandate) => {
              const spend = mandate.current_spend ?? 0;
              const percent = Math.min(100, Math.round((spend / mandate.max_budget) * 100));
              return (
                <div
                  key={mandate.id}
                  className="p-3.5 rounded-lg border border-slate-100 bg-slate-50/50 hover:bg-slate-50 transition-colors"
                >
                  <div className="flex items-center justify-between text-xs font-semibold text-slate-900">
                    <span className="truncate pr-2">{mandate.name}</span>
                    <span className="shrink-0 text-slate-600">${mandate.max_budget}</span>
                  </div>
                  <div className="mt-2 flex items-center justify-between text-[11px] text-slate-500">
                    <span>Spent: ${spend.toFixed(2)}</span>
                    <span>{percent}%</span>
                  </div>
                  <div className="mt-1 w-full bg-slate-200 rounded-full h-1 overflow-hidden">
                    <div
                      className={`h-1 rounded-full ${
                        percent > 80 ? 'bg-amber-500' : 'bg-indigo-600'
                      }`}
                      style={{ width: `${percent}%` }}
                    ></div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* System status checklist */}
          <div className="pt-2 border-t border-slate-100 space-y-2">
            <span className="text-xs font-bold text-slate-700 block">System Safeguards</span>
            <div className="flex items-center gap-2 text-xs text-slate-600">
              <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
              <span>Zero-knowledge merchant whitelisting</span>
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-600">
              <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
              <span>Real-time budget exhaustion limits</span>
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-600">
              <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
              <span>Cryptographic immutable audit trail</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
