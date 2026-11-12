import React, { useMemo, useState } from 'react';
import { AgStudio, AgStudioProvider } from 'ag-studio-react';
import { AgStudioAiModule, createAiHarness, studioTheme, type AgLlmAdapter, type AgLlmRequest, type AgLlmResponse, type AgAiEvent, type AgStudioApi, type AgFieldDefinition } from 'ag-studio';
import { Pencil, Eye } from 'lucide-react';
import { pactApi } from '../api/pact';
import { Button, EmptyState, ErrorState, PageHeader, RefreshButton, Skeleton } from '../components/ui';
import { useAsync } from '../lib/useAsync';

/** Studio's agents run in the browser; each model turn goes to PACT's server, which holds the Gemini key. */
const pactGeminiAdapter: AgLlmAdapter = {
  executeTurn(request: AgLlmRequest, options) {
    const complete: Promise<AgLlmResponse> = fetch('/api/analytics/agent-turn', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(request),
      signal: options?.signal,
    })
      .then(async (r) => {
        if (r.status === 401) window.dispatchEvent(new CustomEvent('pact:owner-auth', { detail: 'OWNER_AUTH_REQUIRED' }));
        if (!r.ok) throw new Error(`PACT returned HTTP ${r.status}`);
        return (await r.json()) as AgLlmResponse;
      })
      .catch((err: unknown) => ({
        id: `resp_error_${Date.now()}`,
        createdAt: Date.now(),
        output: [],
        status: 'failed' as const,
        error: { code: 'NETWORK', message: err instanceof Error ? err.message : 'Request failed' },
      }));

    async function* stream(): AsyncGenerator<AgAiEvent> {
      const res = await complete;
      for (const item of res.output) {
        if (item.type === 'message') {
          const text = item.content.map((c) => (c.type === 'text' ? c.text : c.refusal)).join('');
          yield { type: 'TEXT_MESSAGE_START', messageId: item.id, role: 'assistant' };
          if (text) yield { type: 'TEXT_MESSAGE_CONTENT', messageId: item.id, delta: text };
          yield { type: 'TEXT_MESSAGE_END', messageId: item.id };
        } else if (item.type === 'function_call') {
          yield { type: 'TOOL_CALL_START', toolCallId: item.callId, toolCallName: item.name };
          yield { type: 'TOOL_CALL_ARGS', toolCallId: item.callId, delta: item.arguments };
          yield { type: 'TOOL_CALL_END', toolCallId: item.callId };
        }
      }
    }
    return { stream: stream(), complete };
  },
};

const S = 'purchases';
const f = (field: string, aggregation?: 'sum' | 'count' | 'countd' | 'avg') => ({ id: `${S}.${field}`, ...(aggregation ? { aggregation } : {}) });
const title = (text: string) => ({ title: { text, enabled: true } });

/** The shipped report. Analysts can switch to Edit and change anything; nothing here is sample data. */
const INITIAL_STATE = {
  selectedPageId: 'spending',
  panels: { filters: { collapsed: true } },
  pages: [
    {
      id: 'spending',
      widgets: {
        kpiPaid: { type: 'value', format: title('Paid through PayPal'), dataMapping: { value: [f('paid_amount', 'sum')] } },
        kpiRequested: { type: 'value', format: title('Requested by agents'), dataMapping: { value: [f('requested_amount', 'sum')] } },
        kpiBlocked: { type: 'value', format: title('Stopped by the policy engine'), dataMapping: { value: [f('blocked_amount', 'sum')] } },
        kpiCount: { type: 'value', format: title('Purchase requests'), dataMapping: { value: [f('purchase_id', 'countd')] } },
        outcomes: { type: 'donut-chart', format: title('Outcome of every request'), dataMapping: { categoryKey: [f('outcome')], valueKey: [f('purchase_id', 'countd')] } },
        byAgent: { type: 'bar-chart-grouped', format: title('Requested amount by AI agent'), dataMapping: { categoryKey: [f('agent')], valueKey: [f('requested_amount', 'sum')] } },
        byMerchant: { type: 'bar-chart-grouped', format: title('Paid by merchant'), dataMapping: { categoryKey: [f('merchant')], valueKey: [f('paid_amount', 'sum')] } },
        trend: { type: 'line-chart', format: title('Requests per day'), dataMapping: { categoryKey: [f('day')], valueKey: [f('purchase_id', 'countd')] } },
        bySource: { type: 'column-chart-grouped', format: title('Requested amount by product source'), dataMapping: { categoryKey: [f('source')], valueKey: [f('requested_amount', 'sum')] } },
        mandateFilter: { type: 'list-filter', format: title('Mandate'), dataMapping: { value: [f('mandate')] } },
        policyFilter: { type: 'list-filter', format: title('Policy decision'), dataMapping: { value: [f('decided_by_policy')] } },
        table: {
          type: 'grid',
          format: { ...title('Every purchase request'), style: { columnAutoSize: true } },
          dataMapping: { cols: ['created_at', 'agent', 'product', 'merchant', 'source', 'outcome', 'requested_amount', 'paid_amount', 'mandate'].map((x) => f(x)) },
        },
      },
      widgetLayout: {
        kpiPaid: { xTrack: 0, yTrack: 0, xSpan: 6, ySpan: 4 },
        kpiRequested: { xTrack: 6, yTrack: 0, xSpan: 6, ySpan: 4 },
        kpiBlocked: { xTrack: 12, yTrack: 0, xSpan: 6, ySpan: 4 },
        kpiCount: { xTrack: 18, yTrack: 0, xSpan: 6, ySpan: 4 },
        outcomes: { xTrack: 0, yTrack: 4, xSpan: 8, ySpan: 9 },
        byAgent: { xTrack: 8, yTrack: 4, xSpan: 8, ySpan: 9 },
        byMerchant: { xTrack: 16, yTrack: 4, xSpan: 8, ySpan: 9 },
        trend: { xTrack: 0, yTrack: 13, xSpan: 12, ySpan: 8 },
        bySource: { xTrack: 12, yTrack: 13, xSpan: 12, ySpan: 8 },
        mandateFilter: { xTrack: 0, yTrack: 21, xSpan: 5, ySpan: 6 },
        policyFilter: { xTrack: 0, yTrack: 27, xSpan: 5, ySpan: 4 },
        table: { xTrack: 5, yTrack: 21, xSpan: 19, ySpan: 10 },
      },
    },
  ],
};

const money = { format: new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }) };
/** Field names and formats shown in Studio (and to its agents). Amounts are exact two-decimal USD values. */
const FIELDS: AgFieldDefinition[] = [
  { id: 'purchase_id', name: 'Purchase ID', format: 'textFormat' },
  { id: 'day', name: 'Day', format: 'textFormat' },
  { id: 'created_at', name: 'Requested at', format: 'textFormat' },
  { id: 'product', name: 'Product', format: 'textFormat' },
  { id: 'merchant', name: 'Merchant', format: 'textFormat' },
  { id: 'category', name: 'Category', format: 'textFormat' },
  { id: 'agent', name: 'Requesting agent', format: 'textFormat' },
  { id: 'source', name: 'Product source', format: 'textFormat' },
  { id: 'mandate', name: 'Mandate', format: 'textFormat' },
  { id: 'outcome', name: 'Outcome', format: 'textFormat' },
  { id: 'status', name: 'Status', format: 'textFormat' },
  { id: 'decided_by_policy', name: 'Policy decision', format: 'textFormat' },
  { id: 'requested_amount', name: 'Requested amount', format: 'currencyFormat', formatOptions: money },
  { id: 'paid_amount', name: 'Paid amount', format: 'currencyFormat', formatOptions: money },
  { id: 'blocked_amount', name: 'Blocked amount', format: 'currencyFormat', formatOptions: money },
  { id: 'quantity', name: 'Quantity', format: 'integerFormat' },
  { id: 'currency', name: 'Currency', format: 'textFormat' },
  { id: 'ai_engine', name: 'Recommended by', format: 'textFormat' },
];

const PROMPT_STARTERS = [
  { label: 'Where did the guardrail save money?', prompt: 'Which merchants and agents had the most blocked spending? Add a widget that shows it.' },
  { label: 'Agent leaderboard', prompt: 'Compare AI agents by number of requests, amount requested and amount actually paid.' },
  { label: 'Live retailer spend', prompt: 'How much was requested from live Channel3 retailers versus the PACT catalog, and what share was paid?' },
];

const theme = studioTheme.withParams(
  {
    backgroundColor: '#0f131b',
    foregroundColor: '#e7ebf3',
    accentColor: '#7c8cff',
    borderColor: '#1f2735',
    browserColorScheme: 'dark',
    fontFamily: 'Inter, ui-sans-serif, system-ui, sans-serif',
    studioCanvasBackgroundColor: '#090c12',
    studioPanelContainerBackgroundColor: '#0f131b',
    studioPopupBackgroundColor: '#151a24',
    chartBorderColor: '#1f2735',
  },
  'dark',
);

export const Analytics: React.FC = () => {
  const data = useAsync(() => pactApi.getAnalytics());
  const [mode, setMode] = useState<'view' | 'edit'>('view');
  const sources = useMemo(() => (data.data ? { sources: [{ id: S, name: 'Purchase requests', primaryKeyField: 'purchase_id', fields: FIELDS, data: data.data.purchases }] } : null), [data.data]);
  const licenseKey = (import.meta.env.VITE_AG_STUDIO_LICENSE_KEY as string | undefined) || undefined;

  return (
    <div className="flex h-[calc(100vh-4rem)] min-h-[720px] flex-col">
      <PageHeader
        eyebrow="Spending analytics · AG Studio"
        title="Where agents tried to spend, and what PACT allowed"
        description="Built from every persisted purchase request: amounts, outcomes, agents, merchants and sources. Click any chart to cross-filter the page. Edit lets you rearrange or add widgets; the AI panel's agents can query the data and build widgets, but have no way to approve or pay."
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" icon={mode === 'view' ? <Pencil className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />} onClick={() => setMode(mode === 'view' ? 'edit' : 'view')}>
              {mode === 'view' ? 'Edit dashboard' : 'Done editing'}
            </Button>
            <RefreshButton onClick={() => void data.reload()} loading={data.loading} />
          </div>
        }
      />
      {data.error && <ErrorState message={data.error} onRetry={() => void data.reload()} />}
      {!sources ? (
        !data.error && <Skeleton className="flex-1" />
      ) : data.data?.purchases.length === 0 ? (
        <EmptyState title="No purchase requests yet" description="Ask the reference agent or connect an external agent; every request, allowed or blocked, appears here." />
      ) : (
        <div className="ag-theme-mode min-h-0 flex-1 overflow-hidden rounded-xl border border-line" data-ag-theme-mode="dark">
          <AgStudioProvider modules={[AgStudioAiModule]} licenseKey={licenseKey}>
            <AgStudio
              data={sources}
              mode={mode}
              theme={theme}
              initialState={INITIAL_STATE as never}
              ai={({ api }) => createAiHarness(api as unknown as AgStudioApi, { adapter: pactGeminiAdapter, promptStarters: PROMPT_STARTERS })}
              style={{ height: '100%', width: '100%' }}
            />
          </AgStudioProvider>
        </div>
      )}
    </div>
  );
};

export default Analytics;
