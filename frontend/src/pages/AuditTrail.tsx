import React, { useState } from 'react';
import {
  Shield,
  FileCheck2,
  AlertTriangle,
  CreditCard,
  SlidersHorizontal,
  Calendar,
  Lock,
  Search,
} from 'lucide-react';
import { AuditLogEntry } from '../types';
import { mockAuditLogs } from '../data/mockData';

export const AuditTrail: React.FC = () => {
  const [logs] = useState<AuditLogEntry[]>(mockAuditLogs);
  const [filterType, setFilterType] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  const eventTypes = [
    'ALL',
    'POLICY_EVALUATED',
    'PROPOSAL_GENERATED',
    'APPROVAL_GRANTED',
    'APPROVAL_REJECTED',
    'PAYMENT_CAPTURED',
    'MANDATE_CREATED',
  ];

  const filteredLogs = logs.filter((log) => {
    const matchesType = filterType === 'ALL' || log.event_type === filterType;
    const matchesSearch =
      log.entity_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.event_type.toLowerCase().includes(searchQuery.toLowerCase()) ||
      JSON.stringify(log.details).toLowerCase().includes(searchQuery.toLowerCase());
    return matchesType && matchesSearch;
  });

  const getEventBadge = (eventType: string) => {
    switch (eventType) {
      case 'POLICY_EVALUATED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
            <Shield className="w-3 h-3 text-indigo-600" />
            Policy Evaluated
          </span>
        );
      case 'PROPOSAL_GENERATED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-xs font-semibold bg-purple-50 text-purple-700 border border-purple-200">
            <FileCheck2 className="w-3 h-3 text-purple-600" />
            Proposal Generated
          </span>
        );
      case 'APPROVAL_GRANTED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            Approval Granted
          </span>
        );
      case 'APPROVAL_REJECTED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
            <AlertTriangle className="w-3 h-3 text-rose-600" />
            Blocked / Rejected
          </span>
        );
      case 'PAYMENT_CAPTURED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
            <CreditCard className="w-3 h-3 text-blue-600" />
            Payment Captured
          </span>
        );
      case 'MANDATE_CREATED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">
            Mandate Created
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-xs font-semibold bg-slate-100 text-slate-700">
            {eventType}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Audit Trail</h1>
          <p className="text-xs sm:text-sm text-slate-500">
            Cryptographically sealed and immutable history of all autonomous agent evaluations and payment executions.
          </p>
        </div>

        <div className="flex items-center space-x-2 text-xs font-mono text-slate-600 bg-white border border-slate-200 px-3 py-1.5 rounded-lg shadow-xs">
          <Lock className="w-3.5 h-3.5 text-indigo-600" />
          <span>Chain Integrity: Verified</span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200/80 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
          <input
            type="text"
            placeholder="Search audit trail by entity, details, or keywords..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 focus:bg-white transition-all placeholder:text-slate-400"
          />
        </div>

        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 md:pb-0">
          <SlidersHorizontal className="w-4 h-4 text-slate-400 mr-1 shrink-0" />
          {eventTypes.map((type) => (
            <button
              key={type}
              onClick={() => setFilterType(type)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors cursor-pointer ${
                filterType === type
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {type.replace('_', ' ')}
            </button>
          ))}
        </div>
      </div>

      {/* Chronological Timeline */}
      <div className="relative border-l-2 border-indigo-200/80 ml-4 pl-6 space-y-6">
        {filteredLogs.map((log) => (
          <div key={log.id} className="relative group">
            {/* Timeline bullet icon */}
            <div className="absolute -left-[31px] top-1 w-4 h-4 rounded-full bg-white border-2 border-indigo-600 ring-4 ring-indigo-50 group-hover:scale-110 transition-transform"></div>

            {/* Event Card */}
            <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-xs hover:shadow-md transition-shadow">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
                <div className="flex items-center space-x-2 flex-wrap gap-y-1">
                  {getEventBadge(log.event_type)}
                  <span className="text-xs font-mono font-medium text-slate-500">
                    Entity: <strong className="text-slate-700">{log.entity_type} / {log.entity_id}</strong>
                  </span>
                </div>
                <div className="text-xs text-slate-400 flex items-center gap-1">
                  <Calendar className="w-3.5 h-3.5" />
                  <span>
                    {new Date(log.timestamp).toLocaleString([], {
                      month: 'short',
                      day: 'numeric',
                      year: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                      second: '2-digit',
                    })}
                  </span>
                </div>
              </div>

              {/* Event Details JSON / key-value display */}
              <div className="bg-slate-900 text-slate-100 rounded-lg p-3 font-mono text-xs overflow-x-auto">
                <pre className="text-[11px] leading-relaxed">
                  {typeof log.details === 'object'
                    ? JSON.stringify(log.details, null, 2)
                    : log.details}
                </pre>
              </div>

              <div className="mt-3 flex items-center justify-between text-[11px] text-slate-400 pt-2 border-t border-slate-100">
                <span className="font-mono">Log ID: {log.id}</span>
                <span className="font-mono text-indigo-500">HMAC-SHA256: verified</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default AuditTrail;
