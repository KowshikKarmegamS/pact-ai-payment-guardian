import React, { useState } from 'react';
import {
  CreditCard,
  Search,
  CheckCircle,
  Clock,
  XCircle,
  Filter,
} from 'lucide-react';
import { Proposal, ProposalStatus } from '../types';
import { mockProposals } from '../data/mockData';

export const Transactions: React.FC = () => {
  const [proposals] = useState<Proposal[]>(mockProposals);
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedProposal, setSelectedProposal] = useState<Proposal | null>(null);

  const filteredProposals = proposals.filter((p) => {
    const matchesStatus = filterStatus === 'all' || p.status === filterStatus;
    const matchesSearch =
      p.product_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.merchant.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.id.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesStatus && matchesSearch;
  });

  const getStatusBadge = (status: ProposalStatus) => {
    switch (status) {
      case 'pending':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            <Clock className="w-3 h-3 text-amber-500" />
            Pending
          </span>
        );
      case 'approved':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle className="w-3 h-3 text-emerald-500" />
            Approved
          </span>
        );
      case 'captured':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
            <CreditCard className="w-3 h-3 text-blue-500" />
            Captured
          </span>
        );
      case 'rejected':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
            <XCircle className="w-3 h-3 text-rose-500" />
            Rejected
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">
            Transaction & Proposal Ledger
          </h1>
          <p className="text-xs sm:text-sm text-slate-500">
            Immutable log of all AI purchase proposals, policy verdicts, and PayPal payment captures.
          </p>
        </div>

        {/* Quick summary counters */}
        <div className="flex items-center gap-2">
          <span className="px-3 py-1.5 rounded-lg bg-white border border-slate-200 text-xs font-semibold text-slate-700 shadow-xs">
            Total: {proposals.length}
          </span>
          <span className="px-3 py-1.5 rounded-lg bg-emerald-50 border border-emerald-200 text-xs font-semibold text-emerald-700">
            Captured: {proposals.filter((p) => p.status === 'captured').length}
          </span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200/80 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
          <input
            type="text"
            placeholder="Search proposals by product, merchant, or ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 focus:bg-white transition-all placeholder:text-slate-400"
          />
        </div>

        {/* Status Filter Buttons */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 md:pb-0">
          <Filter className="w-4 h-4 text-slate-400 mr-1 shrink-0" />
          {['all', 'pending', 'approved', 'captured', 'rejected'].map((status) => (
            <button
              key={status}
              onClick={() => setFilterStatus(status)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold capitalize whitespace-nowrap transition-colors cursor-pointer ${
                filterStatus === status
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {status}
            </button>
          ))}
        </div>
      </div>

      {/* Transactions Table */}
      <div className="bg-white rounded-xl border border-slate-200/80 shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50/80 border-b border-slate-200 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                <th className="py-3.5 px-4">Proposal / ID</th>
                <th className="py-3.5 px-4">Merchant & Category</th>
                <th className="py-3.5 px-4">Amount</th>
                <th className="py-3.5 px-4">Status</th>
                <th className="py-3.5 px-4">Timestamp</th>
                <th className="py-3.5 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-sm">
              {filteredProposals.length > 0 ? (
                filteredProposals.map((proposal) => (
                  <tr key={proposal.id} className="hover:bg-slate-50/60 transition-colors">
                    {/* ID & Title */}
                    <td className="py-4 px-4">
                      <div className="font-semibold text-slate-900">{proposal.product_name}</div>
                      <div className="text-xs font-mono text-slate-400 mt-0.5">
                        {proposal.id} &bull; Mandate: {proposal.mandate_id}
                      </div>
                    </td>

                    {/* Merchant & Category */}
                    <td className="py-4 px-4">
                      <div className="font-medium text-slate-800">{proposal.merchant}</div>
                      <div className="text-xs text-slate-500">{proposal.category}</div>
                    </td>

                    {/* Amount */}
                    <td className="py-4 px-4">
                      <div className="font-extrabold text-slate-900">
                        ${Number(proposal.total_amount).toFixed(2)}
                      </div>
                      <div className="text-xs text-slate-400">Qty: {proposal.quantity}</div>
                    </td>

                    {/* Status */}
                    <td className="py-4 px-4">{getStatusBadge(proposal.status)}</td>

                    {/* Timestamp */}
                    <td className="py-4 px-4 text-xs text-slate-500 whitespace-nowrap">
                      {new Date(proposal.created_at).toLocaleDateString([], {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </td>

                    {/* Actions */}
                    <td className="py-4 px-4 text-right">
                      <button
                        onClick={() => setSelectedProposal(proposal)}
                        className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 bg-indigo-50 hover:bg-indigo-100 px-3 py-1.5 rounded-lg transition-colors cursor-pointer"
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-sm text-slate-500">
                    No transactions matching your criteria.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Proposal Details Modal */}
      {selectedProposal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-xs">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 relative animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-xs font-mono text-slate-400 font-semibold">
                  {selectedProposal.id}
                </span>
                <h3 className="text-lg font-bold text-slate-900 mt-1">
                  {selectedProposal.product_name}
                </h3>
              </div>
              <div>{getStatusBadge(selectedProposal.status)}</div>
            </div>

            <div className="mt-5 space-y-4 text-xs">
              <div className="bg-slate-50 p-3 rounded-lg border border-slate-100 space-y-1.5">
                <div className="flex justify-between">
                  <span className="text-slate-500 font-medium">Merchant:</span>
                  <span className="font-semibold text-slate-800">{selectedProposal.merchant}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500 font-medium">Category:</span>
                  <span className="font-semibold text-slate-800">{selectedProposal.category}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500 font-medium">Price per unit:</span>
                  <span className="font-semibold text-slate-800">${Number(selectedProposal.price).toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500 font-medium">Quantity:</span>
                  <span className="font-semibold text-slate-800">{selectedProposal.quantity}</span>
                </div>
                <div className="flex justify-between border-t border-slate-200 pt-1.5 font-bold text-sm">
                  <span className="text-slate-700">Total Authorized Amount:</span>
                  <span className="text-slate-900">${Number(selectedProposal.total_amount).toFixed(2)}</span>
                </div>
              </div>

              <div>
                <span className="font-bold text-slate-700 block mb-1">AI Guardian Reasoning</span>
                <p className="text-slate-600 bg-slate-50 p-3 rounded-lg border border-slate-100 italic leading-relaxed">
                  &ldquo;{selectedProposal.ai_reasoning}&rdquo;
                </p>
              </div>

              {selectedProposal.paypal_order_id && (
                <div className="p-3 bg-blue-50/70 rounded-lg border border-blue-200">
                  <span className="font-bold text-blue-900 block mb-1">PayPal Order Reference</span>
                  <p className="font-mono text-[11px] text-blue-700">
                    {selectedProposal.paypal_order_id}
                  </p>
                </div>
              )}
            </div>

            <div className="mt-6 flex justify-end">
              <button
                onClick={() => setSelectedProposal(null)}
                className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-xs font-semibold transition-colors cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Transactions;
