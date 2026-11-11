import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Bot, Check, Copy, CreditCard, KeyRound, Plug, Plus, Scale, ShieldOff, UserCheck, X } from 'lucide-react';
import { pactApi } from '../api/pact';
import { errorMessage } from '../api/client';
import { useToast } from '../components/Toast';
import {
  Badge,
  Button,
  Card,
  CardHeader,
  ConfirmDialog,
  Dialog,
  EmptyState,
  ErrorState,
  Field,
  Mono,
  PageHeader,
  RefreshButton,
  SkeletonRows,
  StatusPill,
  cx,
  inputClass,
} from '../components/ui';
import { money, timeAgo } from '../lib/format';
import { useAsync } from '../lib/useAsync';
import type { ConnectedAgent, ConnectedAgentCreated, Mandate } from '../types';

const CAN = ['Check its spending authority', 'Search the merchant catalog', 'Dry-run a purchase', 'Request a purchase for your approval', 'Read the status of its own requests'];
const CANNOT = ['Approve a purchase', 'Create or capture a PayPal payment', 'Change a mandate or its budget', "See other agents' requests"];

const FLOW = [
  { icon: Bot, title: 'Any AI agent', text: 'Claude, ChatGPT, or your own' },
  { icon: Plug, title: 'PACT Agent Gateway', text: 'REST API or MCP server' },
  { icon: Scale, title: 'Policy engine', text: 'Your mandate, deterministic' },
  { icon: UserCheck, title: 'You approve', text: 'The exact purchase' },
  { icon: CreditCard, title: 'PayPal executes', text: 'Verified capture' },
];

const CopyButton: React.FC<{ text: string; label?: string }> = ({ text, label = 'Copy' }) => {
  const [done, setDone] = useState(false);
  return (
    <Button
      variant="secondary"
      size="sm"
      icon={done ? <Check className="h-3.5 w-3.5 text-ok" /> : <Copy className="h-3.5 w-3.5" />}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setDone(true);
          setTimeout(() => setDone(false), 1600);
        } catch {
          /* clipboard unavailable: the text is still selectable */
        }
      }}
    >
      {done ? 'Copied' : label}
    </Button>
  );
};

const Snippet: React.FC<{ title: string; code: string }> = ({ title, code }) => (
  <div>
    <div className="mb-1.5 flex items-center justify-between">
      <p className="text-xs font-medium text-fg/90">{title}</p>
      <CopyButton text={code} />
    </div>
    <pre className="max-h-56 overflow-auto rounded-lg border border-line bg-ink/70 p-3 font-mono text-[11.5px] leading-relaxed text-fg/85">{code}</pre>
  </div>
);

const origin = () => (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8001');

const mcpConfig = (key: string) =>
  JSON.stringify(
    {
      mcpServers: {
        pact: {
          command: 'python',
          args: ['integrations/mcp/pact_mcp_server.py'],
          env: { PACT_URL: origin(), PACT_AGENT_KEY: key },
        },
      },
    },
    null,
    2,
  );

const curlExample = (key: string, mandateId: string) =>
  `curl -X POST ${origin()}/api/agent/v1/purchases \\
  -H "Authorization: Bearer ${key}" \\
  -H "Content-Type: application/json" \\
  -d '{"mandate_id": "${mandateId}", "product_id": 1, "quantity": 1,
       "reason": "The user asked for a USB-C hub"}'`;

const ConnectDialog: React.FC<{ open: boolean; onClose: () => void; mandates: Mandate[]; onCreated: (a: ConnectedAgentCreated) => void }> = ({
  open,
  onClose,
  mandates,
  onCreated,
}) => {
  const toast = useToast();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [chosen, setChosen] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [tried, setTried] = useState(false);
  const usable = mandates.filter((m) => m.status === 'active');
  const nameError = tried && name.trim().length < 2 ? 'Give the agent a name you will recognise.' : null;
  const mandateError = tried && chosen.length === 0 ? 'Grant at least one mandate.' : null;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setTried(true);
    if (name.trim().length < 2 || chosen.length === 0) return;
    setSaving(true);
    try {
      const created = await pactApi.createAgent({ name: name.trim(), description: description.trim() || undefined, mandate_ids: chosen });
      onCreated(created);
      setName('');
      setDescription('');
      setChosen([]);
      setTried(false);
    } catch (err) {
      toast.error('Could not connect the agent', errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} title="Connect an AI agent" description="The agent gets its own key and can only use the mandates you grant.">
      <form onSubmit={submit} className="space-y-4">
        <Field label="Agent name" error={nameError}>
          {(id) => <input id={id} className={inputClass} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Claude Desktop (MCP)" maxLength={100} />}
        </Field>
        <Field label="Description" hint="Optional. Shown in the Control Center only.">
          {(id) => <input id={id} className={inputClass} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Personal shopping agent" maxLength={300} />}
        </Field>
        <div>
          <p className="mb-1.5 text-xs font-medium text-fg/90">Mandates this agent may spend under</p>
          {usable.length === 0 ? (
            <p className="text-xs text-muted">
              No active mandates. <Link to="/mandates" className="text-accent hover:underline">Create one first.</Link>
            </p>
          ) : (
            <div className="space-y-1.5">
              {usable.map((m) => {
                const on = chosen.includes(m.id);
                return (
                  <label key={m.id} className={cx('flex cursor-pointer items-center justify-between gap-3 rounded-lg border px-3 py-2 text-sm', on ? 'border-accent/40 bg-accent/[0.06]' : 'border-line hover:bg-white/[0.02]')}>
                    <span className="flex items-center gap-2.5">
                      <input type="checkbox" className="accent-[var(--color-accent)]" checked={on} onChange={() => setChosen((c) => (on ? c.filter((x) => x !== m.id) : [...c, m.id]))} />
                      <span className="text-fg">{m.name}</span>
                    </span>
                    <span className="text-xs text-muted tnum">{money(m.remaining_budget, m.currency)} left</span>
                  </label>
                );
              })}
            </div>
          )}
          {mandateError && <p className="mt-1 text-[11px] text-bad">{mandateError}</p>}
        </div>
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={saving} icon={<KeyRound className="h-4 w-4" />}>Create agent key</Button>
        </div>
      </form>
    </Dialog>
  );
};

const KeyDialog: React.FC<{ agent: ConnectedAgentCreated | null; onClose: () => void }> = ({ agent, onClose }) => (
  <Dialog open={!!agent} onClose={onClose} wide title={agent ? `${agent.name} is connected` : ''} description="Copy the key now. PACT stores only its hash and cannot show it again.">
    {agent && (
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3 rounded-lg border border-warn/30 bg-warn/[0.06] px-3 py-2.5">
          <Mono className="text-fg">{agent.api_key}</Mono>
          <CopyButton text={agent.api_key} label="Copy key" />
        </div>
        <Snippet title="MCP server (Claude Desktop, Claude Code, any MCP client)" code={mcpConfig(agent.api_key)} />
        <Snippet title="Or call the REST API directly" code={curlExample(agent.api_key, agent.mandate_ids[0] ?? '<mandate id>')} />
        <div className="flex justify-end">
          <Button onClick={onClose}>Done</Button>
        </div>
      </div>
    )}
  </Dialog>
);

const AgentCard: React.FC<{ agent: ConnectedAgent; onRevoke: () => void }> = ({ agent, onRevoke }) => {
  const revoked = agent.status === 'revoked';
  return (
    <Card className={cx('p-5 animate-rise', revoked && 'opacity-60')}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-accent/25 to-violet/25 text-accent ring-1 ring-inset ring-accent/25">
            <Bot className="h-4.5 w-4.5" />
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-fg">{agent.name}</p>
            <p className="mt-0.5 truncate text-xs text-muted">{agent.description || 'External AI agent'}</p>
          </div>
        </div>
        <Badge tone={revoked ? 'bad' : 'ok'} dot>{revoked ? 'Revoked' : 'Active'}</Badge>
      </div>
      <dl className="mt-4 grid grid-cols-4 gap-2 text-center">
        {[
          ['Requests', agent.requests, 'text-fg'],
          ['Blocked', agent.blocked, agent.blocked ? 'text-bad' : 'text-fg'],
          ['Awaiting you', agent.awaiting_approval, agent.awaiting_approval ? 'text-accent' : 'text-fg'],
          ['Paid', agent.captured, agent.captured ? 'text-ok' : 'text-fg'],
        ].map(([label, value, tone]) => (
          <div key={label as string} className="rounded-lg border border-line bg-ink/40 px-2 py-2">
            <dd className={cx('text-lg font-semibold leading-none tnum', tone as string)}>{value}</dd>
            <dt className="mt-1 text-[10px] text-faint">{label}</dt>
          </div>
        ))}
      </dl>
      <div className="mt-4 space-y-1.5 text-xs">
        <div className="flex justify-between gap-3"><span className="text-faint">Key</span><Mono className="text-muted">{agent.key_prefix}</Mono></div>
        <div className="flex justify-between gap-3"><span className="text-faint">Mandates</span><span className="truncate text-right text-muted">{agent.mandate_names.join(', ') || '—'}</span></div>
        <div className="flex justify-between gap-3"><span className="text-faint">Last active</span><span className="text-muted">{agent.last_used_at ? timeAgo(agent.last_used_at) : 'Never'}</span></div>
      </div>
      {!revoked && (
        <div className="mt-4 flex justify-end">
          <Button variant="danger" size="sm" icon={<ShieldOff className="h-3.5 w-3.5" />} onClick={onRevoke}>Revoke access</Button>
        </div>
      )}
    </Card>
  );
};

export const Agents: React.FC = () => {
  const toast = useToast();
  const state = useAsync(async () => {
    const [agents, mandates, proposals] = await Promise.all([pactApi.getAgents(), pactApi.getMandates(), pactApi.getProposals()]);
    return { agents, mandates, proposals };
  });
  const [connecting, setConnecting] = useState(false);
  const [created, setCreated] = useState<ConnectedAgentCreated | null>(null);
  const [revoking, setRevoking] = useState<ConnectedAgent | null>(null);
  const [busy, setBusy] = useState(false);

  const requests = useMemo(() => (state.data?.proposals ?? []).filter((p) => p.agent_name).slice(0, 8), [state.data]);

  const revoke = async () => {
    if (!revoking) return;
    setBusy(true);
    try {
      await pactApi.revokeAgent(revoking.id);
      toast.success('Access revoked', `${revoking.name}'s key stopped working immediately.`);
      setRevoking(null);
      await state.reload();
    } catch (err) {
      toast.error('Could not revoke', errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader
        eyebrow="Agent Gateway"
        title="Connected agents"
        description="Any AI agent can ask PACT for spending authority through the REST API or the MCP server. Agents can ask. Only you approve, and only PACT moves money."
        actions={
          <>
            <RefreshButton onClick={() => void state.reload()} loading={state.loading && !!state.data} />
            <Button icon={<Plus className="h-4 w-4" />} onClick={() => setConnecting(true)}>Connect an agent</Button>
          </>
        }
      />

      <Card className="mb-6 overflow-hidden">
        <ol className="grid gap-px bg-line sm:grid-cols-5">
          {FLOW.map((s, i) => (
            <li key={s.title} className={cx('relative bg-surface p-4', i === 1 && 'bg-accent/[0.07]')}>
              <div className="flex items-center gap-2">
                <span className={cx('flex h-7 w-7 items-center justify-center rounded-md', i === 1 ? 'bg-accent/20 text-accent' : 'bg-white/[0.06] text-muted')}>
                  <s.icon className="h-4 w-4" />
                </span>
                {i < FLOW.length - 1 && <ArrowRight className="ml-auto hidden h-3.5 w-3.5 text-faint sm:block" />}
              </div>
              <p className="mt-2.5 text-[13px] font-medium text-fg">{s.title}</p>
              <p className="mt-0.5 text-[11px] text-faint">{s.text}</p>
            </li>
          ))}
        </ol>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[1fr_340px]">
        <div className="space-y-6">
          {state.error && !state.data ? (
            <ErrorState message={state.error} onRetry={() => void state.reload()} />
          ) : !state.data ? (
            <Card className="p-5"><SkeletonRows rows={3} /></Card>
          ) : state.data.agents.length === 0 ? (
            <Card>
              <EmptyState
                icon={<Bot className="h-8 w-8" />}
                title="No agents connected yet"
                description="Connect Claude, ChatGPT or your own agent. It gets a scoped key and can only request purchases under the mandates you grant."
                action={<Button icon={<Plus className="h-4 w-4" />} onClick={() => setConnecting(true)}>Connect an agent</Button>}
              />
            </Card>
          ) : (
            <div className="grid gap-4 lg:grid-cols-2">
              {state.data.agents.map((a) => (
                <AgentCard key={a.id} agent={a} onRevoke={() => setRevoking(a)} />
              ))}
            </div>
          )}

          <Card>
            <CardHeader title="Recent agent requests" subtitle="Every request went through the same policy engine as the built-in assistant." />
            {!state.data ? (
              <div className="p-5"><SkeletonRows rows={3} /></div>
            ) : requests.length === 0 ? (
              <p className="px-5 py-6 text-sm text-muted">No requests from external agents yet.</p>
            ) : (
              <ul className="divide-y divide-line">
                {requests.map((p) => (
                  <li key={p.id}>
                    <Link to={`/proposals/${p.id}`} className="flex items-center justify-between gap-4 px-5 py-3 transition-colors hover:bg-white/[0.02]">
                      <div className="min-w-0">
                        <p className="truncate text-sm text-fg">{p.product_name}</p>
                        <p className="mt-0.5 truncate text-xs text-muted">
                          <Bot className="mr-1 inline h-3 w-3 -translate-y-px" />
                          {p.agent_name} · {timeAgo(p.created_at)}
                        </p>
                      </div>
                      <div className="flex shrink-0 items-center gap-3">
                        <span className="text-sm font-medium text-fg tnum">{money(p.total_amount, p.currency)}</span>
                        <StatusPill status={p.status} />
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>

        <div className="space-y-6">
          <Card className="p-5">
            <p className="text-sm font-semibold text-fg">What a connected agent can do</p>
            <ul className="mt-3 space-y-2">
              {CAN.map((c) => (
                <li key={c} className="flex items-start gap-2 text-[13px] text-muted"><Check className="mt-0.5 h-4 w-4 shrink-0 text-ok" />{c}</li>
              ))}
            </ul>
            <p className="mt-5 text-sm font-semibold text-fg">What it can never do</p>
            <ul className="mt-3 space-y-2">
              {CANNOT.map((c) => (
                <li key={c} className="flex items-start gap-2 text-[13px] text-muted"><X className="mt-0.5 h-4 w-4 shrink-0 text-bad" />{c}</li>
              ))}
            </ul>
            <p className="mt-5 rounded-lg border border-line bg-ink/40 p-3 text-[11px] leading-relaxed text-faint">
              These limits are structural: the Agent Gateway has no approval or payment endpoint, and the MCP server has no pay tool. Prices always come from the catalog, never from the agent.
            </p>
          </Card>
          <Card className="p-5">
            <p className="text-sm font-semibold text-fg">MCP tools</p>
            <ul className="mt-3 space-y-1.5">
              {['check_spending_authority', 'search_catalog', 'evaluate_purchase', 'request_purchase', 'get_purchase_status'].map((t) => (
                <li key={t}><Mono className="text-muted">{t}</Mono></li>
              ))}
            </ul>
            <p className="mt-3 text-[11px] text-faint">
              Server: <Mono className="text-faint">integrations/mcp/pact_mcp_server.py</Mono>. REST reference at <a className="text-accent hover:underline" href="/docs#/Agent%20Gateway%20(for%20AI%20agents)" target="_blank" rel="noreferrer">/docs</a>.
            </p>
          </Card>
        </div>
      </div>

      <ConnectDialog
        open={connecting}
        onClose={() => setConnecting(false)}
        mandates={state.data?.mandates ?? []}
        onCreated={(a) => {
          setConnecting(false);
          setCreated(a);
          void state.reload();
        }}
      />
      <KeyDialog agent={created} onClose={() => setCreated(null)} />
      <ConfirmDialog
        open={!!revoking}
        onClose={() => setRevoking(null)}
        onConfirm={() => void revoke()}
        loading={busy}
        danger
        title={`Revoke ${revoking?.name ?? 'agent'}?`}
        body="Its key stops working immediately. Requests it already made stay in the history, and anything awaiting your approval stays there for you to decide."
        confirmLabel="Revoke access"
      />
    </div>
  );
};

export default Agents;
