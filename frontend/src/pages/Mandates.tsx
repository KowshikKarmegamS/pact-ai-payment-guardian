import React, { useState } from 'react';
import {
  ScrollText,
  Plus,
  CheckCircle,
  XCircle,
  Tag,
  Store,
  AlertCircle,
  DollarSign,
  X,
  Search,
} from 'lucide-react';
import { Mandate } from '../types';
import { mockMandates } from '../data/mockData';

export const Mandates: React.FC = () => {
  const [mandates, setMandates] = useState<Mandate[]>(mockMandates);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

  // Form state
  const [name, setName] = useState('');
  const [maxBudget, setMaxBudget] = useState('');
  const [merchantsInput, setMerchantsInput] = useState('');
  const [categoriesInput, setCategoriesInput] = useState('');
  const [restrictionsInput, setRestrictionsInput] = useState('');

  const filteredMandates = mandates.filter((m) =>
    m.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    m.allowed_merchants.some((merch) => merch.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  const handleCreateMandate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !maxBudget) return;

    const newMandate: Mandate = {
      id: `man-${Math.floor(1000 + Math.random() * 9000)}`,
      name,
      max_budget: parseFloat(maxBudget),
      current_spend: 0,
      allowed_merchants: merchantsInput
        .split(',')
        .map((m) => m.trim())
        .filter(Boolean),
      allowed_categories: categoriesInput
        .split(',')
        .map((c) => c.trim())
        .filter(Boolean),
      restrictions: restrictionsInput
        .split(',')
        .map((r) => r.trim())
        .filter(Boolean),
      is_active: true,
      created_at: new Date().toISOString(),
    };

    setMandates([newMandate, ...mandates]);
    setIsModalOpen(false);

    // Reset form
    setName('');
    setMaxBudget('');
    setMerchantsInput('');
    setCategoriesInput('');
    setRestrictionsInput('');
  };

  const toggleMandateStatus = (id: string) => {
    setMandates((prev) =>
      prev.map((m) => (m.id === id ? { ...m, is_active: !m.is_active } : m))
    );
  };

  return (
    <div className="space-y-6">
      {/* Header and Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Spending Mandates</h1>
          <p className="text-xs sm:text-sm text-slate-500">
            Define boundaries, permitted merchants, and caps for autonomous AI purchases.
          </p>
        </div>

        <button
          onClick={() => setIsModalOpen(true)}
          className="inline-flex items-center space-x-2 bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-xs sm:text-sm px-4 py-2.5 rounded-lg shadow-xs transition-colors self-start sm:self-auto"
        >
          <Plus className="w-4 h-4" />
          <span>New Spend Mandate</span>
        </button>
      </div>

      {/* Filter / Search Bar */}
      <div className="relative max-w-md">
        <Search className="w-4 h-4 absolute left-3 top-3 text-slate-400" />
        <input
          type="text"
          placeholder="Filter mandates by name or merchant..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full pl-9 pr-4 py-2 bg-white border border-slate-200 rounded-lg text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition-all placeholder:text-slate-400 shadow-xs"
        />
      </div>

      {/* Mandates Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {filteredMandates.map((mandate) => {
          const spend = mandate.current_spend ?? 0;
          const percent = Math.min(100, Math.round((spend / mandate.max_budget) * 100));

          return (
            <div
              key={mandate.id}
              className={`bg-white rounded-xl border transition-all shadow-xs hover:shadow-md flex flex-col justify-between p-6 ${
                mandate.is_active ? 'border-slate-200/80' : 'border-slate-200 opacity-75'
              }`}
            >
              <div className="space-y-4">
                {/* Title & Status Badge */}
                <div className="flex items-start justify-between gap-2">
                  <div className="space-y-1">
                    <span className="text-[11px] font-mono font-medium text-slate-400">
                      {mandate.id}
                    </span>
                    <h2 className="text-base font-bold text-slate-900">{mandate.name}</h2>
                  </div>
                  <button
                    onClick={() => toggleMandateStatus(mandate.id)}
                    className={`inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-semibold cursor-pointer transition-colors ${
                      mandate.is_active
                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100'
                        : 'bg-slate-100 text-slate-600 border border-slate-200 hover:bg-slate-200'
                    }`}
                    title="Click to toggle status"
                  >
                    {mandate.is_active ? (
                      <>
                        <CheckCircle className="w-3.5 h-3.5 text-emerald-600" />
                        <span>Active</span>
                      </>
                    ) : (
                      <>
                        <XCircle className="w-3.5 h-3.5 text-slate-500" />
                        <span>Paused</span>
                      </>
                    )}
                  </button>
                </div>

                {/* Budget Progress Bar */}
                <div className="bg-slate-50 p-3.5 rounded-lg border border-slate-100">
                  <div className="flex items-center justify-between text-xs font-semibold text-slate-700 mb-1.5">
                    <span>Spend Utilization</span>
                    <span>
                      ${spend.toFixed(2)} / ${mandate.max_budget.toFixed(2)}
                    </span>
                  </div>
                  <div className="w-full bg-slate-200 rounded-full h-2 overflow-hidden">
                    <div
                      className={`h-2 rounded-full transition-all ${
                        percent > 85 ? 'bg-amber-500' : 'bg-indigo-600'
                      }`}
                      style={{ width: `${percent}%` }}
                    ></div>
                  </div>
                  <div className="mt-1 text-[11px] text-slate-500 flex justify-between">
                    <span>{percent}% utilized</span>
                    <span>${(mandate.max_budget - spend).toFixed(2)} remaining</span>
                  </div>
                </div>

                {/* Whitelisted Merchants */}
                <div>
                  <div className="flex items-center gap-1.5 text-xs font-bold text-slate-700 mb-2">
                    <Store className="w-3.5 h-3.5 text-slate-400" />
                    <span>Allowed Merchants</span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {mandate.allowed_merchants.length > 0 ? (
                      mandate.allowed_merchants.map((merchant) => (
                        <span
                          key={merchant}
                          className="px-2 py-0.5 rounded-md text-xs bg-slate-100 text-slate-700 font-medium border border-slate-200"
                        >
                          {merchant}
                        </span>
                      ))
                    ) : (
                      <span className="text-xs text-slate-400 italic">Any merchant</span>
                    )}
                  </div>
                </div>

                {/* Whitelisted Categories */}
                <div>
                  <div className="flex items-center gap-1.5 text-xs font-bold text-slate-700 mb-2">
                    <Tag className="w-3.5 h-3.5 text-slate-400" />
                    <span>Allowed Categories</span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {mandate.allowed_categories.map((cat) => (
                      <span
                        key={cat}
                        className="px-2 py-0.5 rounded-md text-xs bg-indigo-50 text-indigo-700 font-medium border border-indigo-100"
                      >
                        {cat}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Specific Restrictions */}
                {mandate.restrictions && mandate.restrictions.length > 0 && (
                  <div>
                    <div className="flex items-center gap-1.5 text-xs font-bold text-slate-700 mb-1.5">
                      <AlertCircle className="w-3.5 h-3.5 text-amber-500" />
                      <span>Policy Constraints</span>
                    </div>
                    <ul className="list-disc list-inside text-xs text-slate-600 space-y-0.5">
                      {mandate.restrictions.map((res, i) => (
                        <li key={i} className="leading-relaxed">
                          {res}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              {/* Card Footer */}
              <div className="mt-5 pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
                <span>Created {new Date(mandate.created_at).toLocaleDateString()}</span>
                <span className="font-mono">Guardian Hash: 0x{mandate.id.replace('man-', '')}af</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Create Mandate Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-xs">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 relative animate-in fade-in zoom-in-95 duration-150">
            <button
              onClick={() => setIsModalOpen(false)}
              className="absolute top-4 right-4 text-slate-400 hover:text-slate-600 p-1 rounded-lg"
              aria-label="Close modal"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center space-x-2.5 mb-5">
              <div className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
                <ScrollText className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-slate-900">Create Spending Mandate</h3>
                <p className="text-xs text-slate-500">Autonomous authorization rules for AI agents</p>
              </div>
            </div>

            <form onSubmit={handleCreateMandate} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                  Mandate Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Q1 Developer Software & Tools"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full px-3.5 py-2 border border-slate-300 rounded-lg text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                  Max Budget (USD) *
                </label>
                <div className="relative">
                  <DollarSign className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                  <input
                    type="number"
                    step="0.01"
                    min="1"
                    required
                    placeholder="1500.00"
                    value={maxBudget}
                    onChange={(e) => setMaxBudget(e.target.value)}
                    className="w-full pl-9 pr-3.5 py-2 border border-slate-300 rounded-lg text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                  Allowed Merchants (comma-separated)
                </label>
                <input
                  type="text"
                  placeholder="AWS, GitHub, Keychron, Best Buy"
                  value={merchantsInput}
                  onChange={(e) => setMerchantsInput(e.target.value)}
                  className="w-full px-3.5 py-2 border border-slate-300 rounded-lg text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                  Allowed Categories (comma-separated)
                </label>
                <input
                  type="text"
                  placeholder="Electronics, Peripherals, Cloud Services"
                  value={categoriesInput}
                  onChange={(e) => setCategoriesInput(e.target.value)}
                  className="w-full px-3.5 py-2 border border-slate-300 rounded-lg text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                  Restrictions / Constraints (comma-separated)
                </label>
                <input
                  type="text"
                  placeholder="No gaming consoles, Max $300 single item, Digital only"
                  value={restrictionsInput}
                  onChange={(e) => setRestrictionsInput(e.target.value)}
                  className="w-full px-3.5 py-2 border border-slate-300 rounded-lg text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600"
                />
              </div>

              <div className="pt-3 flex items-center justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-semibold shadow-xs transition-colors"
                >
                  Save Mandate
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Mandates;
