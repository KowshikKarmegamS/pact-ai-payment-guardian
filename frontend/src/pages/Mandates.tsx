import React, { useMemo, useState } from 'react';
import { Ban, CalendarClock, Check, Pause, Pencil, Play, Plus, ShieldOff, X } from 'lucide-react';
import { pactApi } from '../api/pact';
import { errorMessage } from '../api/client';
import { useToast } from '../components/Toast';
import { Badge, Button, Card, ConfirmDialog, Dialog, EmptyState, ErrorState, Eyebrow, Field, Meter, PageHeader, RefreshButton, Skeleton, cx, inputClass } from '../components/ui';
import { MANDATE_STATUS, dateOnly, dateTime, money, parseDate, toNumber } from '../lib/format';
import { useAsync } from '../lib/useAsync';
import type { Mandate, MandateInput } from '../types';

interface FormState {
  name: string;
  max_budget: string;
  allowed_merchants: string;
  allowed_categories: string;
  max_price_per_item: string;
  max_quantity: string;
  prohibited_keywords: string;
  prohibited_merchants: string;
  expires_on: string; // yyyy-mm-dd, local
  auto: boolean;
  max_auto_approve_amount: string;
}

const EMPTY: FormState = {
  name: '',
  max_budget: '',
  allowed_merchants: '',
  allowed_categories: '',
  max_price_per_item: '',
  max_quantity: '',
  prohibited_keywords: '',
  prohibited_merchants: '',
  expires_on: '',
  auto: false,
  max_auto_approve_amount: '',
};

const split = (s: string) => s.split(',').map((x) => x.trim()).filter(Boolean);
const pad = (n: number) => String(n).padStart(2, '0');

function fromMandate(m: Mandate): FormState {
  const r = m.restrictions;
  const exp = parseDate(m.expires_at);
  return {
    name: m.name,
    max_budget: toNumber(m.max_budget).toFixed(2),
    allowed_merchants: m.allowed_merchants.join(', '),
    allowed_categories: m.allowed_categories.join(', '),
    max_price_per_item: r.max_price_per_item != null ? String(r.max_price_per_item) : '',
    max_quantity: r.max_quantity != null ? String(r.max_quantity) : '',
    prohibited_keywords: (r.prohibited_keywords ?? []).join(', '),
    prohibited_merchants: (r.prohibited_merchants ?? []).join(', '),
    expires_on: exp ? `${exp.getFullYear()}-${pad(exp.getMonth() + 1)}-${pad(exp.getDate())}` : '',
    auto: m.authorization_mode === 'auto_approve_within_limits',
    max_auto_approve_amount: m.max_auto_approve_amount != null ? toNumber(m.max_auto_approve_amount).toFixed(2) : '',
  };
}

type TextKey = Exclude<keyof FormState, 'auto'>;
type Errors = Partial<Record<TextKey, string>>;

function validate(f: FormState): Errors {
  const e: Errors = {};
  if (!f.name.trim()) e.name = 'Give the mandate a name.';
  if (!/^\d+(\.\d{1,2})?$/.test(f.max_budget.trim()) || !(Number(f.max_budget) > 0)) e.max_budget = 'Enter a positive amount with at most two decimals.';
  if (!split(f.allowed_merchants).length) e.allowed_merchants = 'Add at least one merchant.';
  if (!split(f.allowed_categories).length) e.allowed_categories = 'Add at least one category.';
  if (f.max_price_per_item && !(Number(f.max_price_per_item) > 0)) e.max_price_per_item = 'Must be a positive amount.';
  if (f.max_quantity && !(Number.isInteger(Number(f.max_quantity)) && Number(f.max_quantity) >= 1 && Number(f.max_quantity) <= 20)) e.max_quantity = 'Whole number from 1 to 20.';
  if (f.auto) {
    const a = f.max_auto_approve_amount.trim();
    if (!/^\d+(\.\d{1,2})?$/.test(a) || !(Number(a) > 0)) e.max_auto_approve_amount = 'Enter the largest amount PACT may authorize on its own.';
    else if (Number(f.max_budget) > 0 && Number(a) > Number(f.max_budget)) e.max_auto_approve_amount = 'Cannot exceed the mandate budget.';
  }
  if (f.expires_on) {
    const end = new Date(`${f.expires_on}T23:59:59`);
    if (Number.isNaN(end.getTime()) || end.getTime() <= Date.now()) e.expires_on = 'Expiry must be in the future.';
  }
  return e;
}

function toInput(f: FormState): MandateInput {
  return {
    name: f.name.trim(),
    max_budget: Number(f.max_budget).toFixed(2),
    allowed_merchants: split(f.allowed_merchants),
    allowed_categories: split(f.allowed_categories),
    restrictions: {
      ...(f.max_price_per_item ? { max_price_per_item: Number(f.max_price_per_item) } : {}),
      ...(f.max_quantity ? { max_quantity: Number(f.max_quantity) } : {}),
      prohibited_keywords: split(f.prohibited_keywords),
      prohibited_merchants: split(f.prohibited_merchants),
    },
    expires_at: f.expires_on ? new Date(`${f.expires_on}T23:59:59`).toISOString() : null,
    authorization_mode: f.auto ? 'auto_approve_within_limits' : 'approval_required',
    ...(f.auto ? { max_auto_approve_amount: Number(f.max_auto_approve_amount).toFixed(2) } : {}),
  };
}

const Rule: React.FC<{ allow: boolean; children: React.ReactNode }> = ({ allow, children }) => (
  <li className="flex gap-2 text-xs leading-relaxed text-muted">
    <span className={cx('mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full', allow ? 'bg-ok/15 text-ok' : 'bg-bad/15 text-bad')}>
      {allow ? <Check className="h-2.5 w-2.5" strokeWidth={3} /> : <X className="h-2.5 w-2.5" strokeWidth={3} />}
    </span>
    <span>{children}</span>
  </li>
);

const Strong: React.FC<{ children: React.ReactNode }> = ({ children }) => <span className="font-medium text-fg">{children}</span>;

const MandateCard: React.FC<{ m: Mandate; onEdit: () => void; onToggle: () => void; onRevoke: () => void; busy: boolean }> = ({ m, onEdit, onToggle, onRevoke, busy }) => {
  const r = m.restrictions;
  const st = MANDATE_STATUS[m.status];
  const locked = m.status === 'revoked';
  return (
    <Card className={cx('flex flex-col animate-rise', locked && 'opacity-70')}>
      <div className="flex items-start justify-between gap-3 px-5 pt-5">
        <div className="min-w-0">
          <h3 className="truncate text-[15px] font-semibold text-fg">{m.name}</h3>
          <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[11px] text-faint">
            <span>Updated {dateTime(m.updated_at)}</span>
            {m.expires_at && (
              <span className="inline-flex items-center gap-1">
                <CalendarClock className="h-3 w-3" /> {m.status === 'expired' ? 'Expired' : 'Expires'} {dateOnly(m.expires_at)}
              </span>
            )}
            {!m.expires_at && !locked && <span>No expiry</span>}
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1.5">
          <Badge tone={st.tone} dot>{st.label}</Badge>
          {m.authorization_mode === 'auto_approve_within_limits' && m.max_auto_approve_amount != null ? (
            <Badge tone="accent" title="Purchases that pass every rule and cost at most this much are authorized without asking you. PayPal still asks the buyer.">
              Auto-authorizes up to {money(m.max_auto_approve_amount, m.currency)}
            </Badge>
          ) : (
            <Badge tone="neutral">You approve every purchase</Badge>
          )}
        </div>
      </div>

      <div className="px-5 pt-5">
        <div className="flex items-end justify-between">
          <div>
            <p className="text-[11px] uppercase tracking-wider text-faint">Remaining</p>
            <p className="text-2xl font-semibold tracking-tight text-fg tnum">{money(m.remaining_budget, m.currency)}</p>
          </div>
          <p className="text-xs text-muted tnum">of {money(m.max_budget, m.currency)} maximum</p>
        </div>
        <Meter className="mt-3" max={toNumber(m.max_budget)} spent={toNumber(m.spent_budget)} committed={toNumber(m.committed_budget)} />
        <div className="mt-2 flex gap-4 text-[11px] text-muted tnum">
          <span><span className="mr-1.5 inline-block h-1.5 w-1.5 rounded-sm bg-ok" />Spent {money(m.spent_budget, m.currency)}</span>
          <span><span className="mr-1.5 inline-block h-1.5 w-1.5 rounded-sm bg-warn" />Approved {money(m.committed_budget, m.currency)}</span>
        </div>
      </div>

      <div className="mt-5 grid flex-1 gap-5 border-t border-line px-5 py-4 sm:grid-cols-2">
        <div>
          <Eyebrow className="mb-2 text-ok/80">The AI may</Eyebrow>
          <ul className="space-y-1.5">
            <Rule allow>Propose purchases from <Strong>{m.allowed_merchants.join(', ')}</Strong></Rule>
            <Rule allow>In <Strong>{m.allowed_categories.join(', ')}</Strong></Rule>
            <Rule allow>Up to <Strong>{r.max_price_per_item != null ? money(r.max_price_per_item, m.currency) : 'the remaining budget'}</Strong> per item, <Strong>{r.max_quantity ?? 20}</Strong> max per order</Rule>
          </ul>
        </div>
        <div>
          <Eyebrow className="mb-2 text-bad/80">The AI may not</Eyebrow>
          <ul className="space-y-1.5">
            <Rule allow={false}>Spend beyond <Strong>{money(m.max_budget, m.currency)}</Strong> in total</Rule>
            <Rule allow={false}>
              {m.authorization_mode === 'auto_approve_within_limits' && m.max_auto_approve_amount != null
                ? <>Get anything over <Strong>{money(m.max_auto_approve_amount, m.currency)}</Strong> authorized without you</>
                : <>Get anything authorized without your explicit approval</>}
            </Rule>
            <Rule allow={false}>Pay: every payment needs the buyer's approval in PayPal</Rule>
            {!!r.prohibited_keywords?.length && <Rule allow={false}>Buy items matching <Strong>{r.prohibited_keywords.join(', ')}</Strong></Rule>}
            {!!r.prohibited_merchants?.length && <Rule allow={false}>Use <Strong>{r.prohibited_merchants.join(', ')}</Strong></Rule>}
          </ul>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 border-t border-line px-5 py-3">
        {locked ? (
          <p className="text-xs text-faint">Revoked {dateTime(m.revoked_at)}. This mandate can never authorize again.</p>
        ) : (
          <>
            <Button size="sm" variant="secondary" onClick={onEdit} icon={<Pencil className="h-3.5 w-3.5" />}>Edit</Button>
            <Button size="sm" variant="secondary" onClick={onToggle} loading={busy} icon={m.is_active ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}>
              {m.is_active ? 'Pause' : 'Resume'}
            </Button>
            <Button size="sm" variant="ghost" className="ml-auto text-bad hover:bg-bad/10 hover:text-bad" onClick={onRevoke} icon={<ShieldOff className="h-3.5 w-3.5" />}>
              Revoke
            </Button>
          </>
        )}
      </div>
    </Card>
  );
};

export const Mandates: React.FC = () => {
  const toast = useToast();
  const list = useAsync(() => pactApi.getMandates());
  const [editing, setEditing] = useState<Mandate | 'new' | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY);
  const [touched, setTouched] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [revoking, setRevoking] = useState<Mandate | null>(null);

  const errors = useMemo(() => validate(form), [form]);
  const show = (k: TextKey) => (touched ? errors[k] : undefined);
  const set = (k: TextKey) => (e: React.ChangeEvent<HTMLInputElement>) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const open = (m: Mandate | 'new') => {
    setEditing(m);
    setForm(m === 'new' ? EMPTY : fromMandate(m));
    setTouched(false);
    setFormError(null);
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (Object.keys(errors).length || saving) return;
    setSaving(true);
    setFormError(null);
    try {
      if (editing === 'new') {
        await pactApi.createMandate(toInput(form));
        toast.success('Mandate created', 'The assistant can now propose purchases under it.');
      } else if (editing) {
        await pactApi.updateMandate(editing.id, toInput(form));
        toast.success('Mandate updated', 'Approvals made under the old rules were re-verified.');
      }
      setEditing(null);
      await list.reload();
    } catch (err) {
      setFormError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const toggle = async (m: Mandate) => {
    setBusyId(m.id);
    try {
      await pactApi.updateMandate(m.id, { is_active: !m.is_active });
      toast.success(m.is_active ? 'Mandate paused' : 'Mandate resumed', m.is_active ? 'Every purchase under it is now blocked.' : undefined);
      await list.reload();
    } catch (err) {
      toast.error('Could not update mandate', errorMessage(err));
    } finally {
      setBusyId(null);
    }
  };

  const revoke = async () => {
    if (!revoking) return;
    setBusyId(revoking.id);
    try {
      await pactApi.revokeMandate(revoking.id);
      toast.success('Mandate revoked', 'Open approvals under it were invalidated.');
      setRevoking(null);
      await list.reload();
    } catch (err) {
      toast.error('Could not revoke mandate', errorMessage(err));
    } finally {
      setBusyId(null);
    }
  };

  const summary = useMemo(() => {
    const merchants = split(form.allowed_merchants);
    const cats = split(form.allowed_categories);
    if (!(Number(form.max_budget) > 0) || !merchants.length || !cats.length) return null;
    return `The AI may propose ${cats.join(', ')} purchases from ${merchants.join(', ')}, up to ${money(form.max_budget)} in total${
      form.max_price_per_item ? ` and ${money(form.max_price_per_item)} per item` : ''
    }${form.expires_on ? `, until ${new Date(`${form.expires_on}T23:59:59`).toLocaleDateString()}` : ''}. ${
      form.auto && Number(form.max_auto_approve_amount) > 0
        ? `Purchases that pass every rule and cost at most ${money(form.max_auto_approve_amount)} are authorized automatically; larger ones wait for you. Rule violations are always blocked.`
        : 'Every purchase waits for your approval.'
    } PayPal always asks the buyer before money moves.`;
  }, [form]);

  return (
    <div>
      <PageHeader
        eyebrow="Authorization control"
        title="Spending mandates"
        description="A mandate is your standing instruction to the agent: how much it may spend, where, on what, and until when. The policy engine enforces it on every proposal."
        actions={
          <>
            <RefreshButton onClick={() => void list.reload()} loading={list.loading} />
            <Button size="sm" onClick={() => open('new')} icon={<Plus className="h-3.5 w-3.5" />}>New mandate</Button>
          </>
        }
      />

      {list.error && <ErrorState message={list.error} onRetry={() => void list.reload()} />}
      {!list.data && list.loading && (
        <div className="grid gap-5 xl:grid-cols-2">
          <Skeleton className="h-80" />
          <Skeleton className="h-80" />
        </div>
      )}
      {list.data?.length === 0 && (
        <Card>
          <EmptyState icon={<Ban className="h-8 w-8" />} title="No mandates yet" description="Without a mandate the assistant cannot propose anything." action={<Button size="sm" onClick={() => open('new')}>Create your first mandate</Button>} />
        </Card>
      )}
      <div className="grid gap-5 xl:grid-cols-2">
        {list.data?.map((m) => (
          <MandateCard key={m.id} m={m} busy={busyId === m.id} onEdit={() => open(m)} onToggle={() => void toggle(m)} onRevoke={() => setRevoking(m)} />
        ))}
      </div>

      <Dialog
        open={editing !== null}
        onClose={() => setEditing(null)}
        wide
        title={editing === 'new' ? 'New spending mandate' : 'Edit mandate'}
        description="These limits are enforced by deterministic code, not by the AI."
      >
        <form onSubmit={save} className="space-y-4" noValidate>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Name" error={show('name')}>{(id) => <input id={id} className={inputClass} value={form.name} onChange={set('name')} placeholder="Home office essentials" />}</Field>
            <Field label="Maximum budget (USD)" error={show('max_budget')}>{(id) => <input id={id} className={inputClass} inputMode="decimal" value={form.max_budget} onChange={set('max_budget')} placeholder="100.00" />}</Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Permitted merchants" hint="Comma separated" error={show('allowed_merchants')}>{(id) => <input id={id} className={inputClass} value={form.allowed_merchants} onChange={set('allowed_merchants')} placeholder="TechHub, BookWorld" />}</Field>
            <Field label="Permitted categories" hint="Comma separated" error={show('allowed_categories')}>{(id) => <input id={id} className={inputClass} value={form.allowed_categories} onChange={set('allowed_categories')} placeholder="Electronics, Books" />}</Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Max price per item" hint="Optional" error={show('max_price_per_item')}>{(id) => <input id={id} className={inputClass} inputMode="decimal" value={form.max_price_per_item} onChange={set('max_price_per_item')} />}</Field>
            <Field label="Max quantity" hint="Optional, 1 to 20" error={show('max_quantity')}>{(id) => <input id={id} className={inputClass} inputMode="numeric" value={form.max_quantity} onChange={set('max_quantity')} />}</Field>
            <Field label="Expires on" hint="Optional" error={show('expires_on')}>{(id) => <input id={id} type="date" className={inputClass} value={form.expires_on} onChange={set('expires_on')} />}</Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Prohibited keywords" hint="Matched against product name and category">{(id) => <input id={id} className={inputClass} value={form.prohibited_keywords} onChange={set('prohibited_keywords')} placeholder="console, game" />}</Field>
            <Field label="Blocked merchants" hint="Never allowed, even if listed above">{(id) => <input id={id} className={inputClass} value={form.prohibited_merchants} onChange={set('prohibited_merchants')} />}</Field>
          </div>

          <div className="rounded-lg border border-line bg-ink/40 p-3">
            <label className="flex cursor-pointer items-start gap-2.5 text-sm text-fg">
              <input type="checkbox" className="mt-0.5 accent-[var(--color-accent)]" checked={form.auto} onChange={(e) => setForm((f) => ({ ...f, auto: e.target.checked }))} />
              <span>
                <span className="font-medium">Auto-authorize purchases within limits</span>
                <span className="block text-xs text-muted">PACT authorizes purchases that pass every rule and cost at most the amount below, without asking you. Larger purchases wait for your approval; rule violations are always blocked. PayPal still asks the buyer before any payment.</span>
              </span>
            </label>
            {form.auto && (
              <div className="mt-3 max-w-xs">
                <Field label="Auto-authorize up to (USD)" error={show('max_auto_approve_amount')}>{(id) => <input id={id} className={inputClass} inputMode="decimal" value={form.max_auto_approve_amount} onChange={set('max_auto_approve_amount')} placeholder="100.00" />}</Field>
              </div>
            )}
          </div>

          {summary && <p className="rounded-lg border border-accent/20 bg-accent/[0.06] px-3 py-2.5 text-xs leading-relaxed text-fg/90">{summary}</p>}
          {editing !== 'new' && <p className="text-[11px] text-faint">Changing rules voids approvals made under the old rules; those purchases must be re-evaluated and re-approved.</p>}
          {formError && <ErrorState compact message={formError} />}
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="secondary" onClick={() => setEditing(null)}>Cancel</Button>
            <Button type="submit" loading={saving}>{editing === 'new' ? 'Create mandate' : 'Save changes'}</Button>
          </div>
        </form>
      </Dialog>

      <ConfirmDialog
        open={revoking !== null}
        onClose={() => setRevoking(null)}
        onConfirm={() => void revoke()}
        loading={busyId === revoking?.id}
        danger
        title="Revoke this mandate?"
        confirmLabel="Revoke permanently"
        body={
          <>
            <span className="font-medium text-fg">{revoking?.name}</span> will never authorize another purchase, and every open approval under it is invalidated.
            This cannot be undone. To stop spending temporarily, pause it instead.
          </>
        }
      />
    </div>
  );
};

export default Mandates;
