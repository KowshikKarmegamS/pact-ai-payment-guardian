import React, { useState } from 'react';
import { Pause, Pencil, Play, Plus } from 'lucide-react';
import { pactApi } from '../api/pact';
import { errorMessage } from '../api/client';
import type { Mandate, MandateInput } from '../types';
import { dateTime, money, toNumber } from '../lib/format';
import { useAsync } from '../lib/useAsync';
import { Badge, BudgetBar, Button, Card, EmptyState, ErrorState, Modal, PageHeader, RefreshButton, Spinner } from '../components/ui';

interface FormState {
  name: string;
  max_budget: string;
  allowed_merchants: string;
  allowed_categories: string;
  max_price_per_item: string;
  max_quantity: string;
  prohibited_keywords: string;
  prohibited_merchants: string;
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
};

const split = (s: string) =>
  s
    .split(',')
    .map((x) => x.trim())
    .filter(Boolean);

function fromMandate(m: Mandate): FormState {
  const r = m.restrictions;
  return {
    name: m.name,
    max_budget: toNumber(m.max_budget).toFixed(2),
    allowed_merchants: m.allowed_merchants.join(', '),
    allowed_categories: m.allowed_categories.join(', '),
    max_price_per_item: r.max_price_per_item != null ? String(r.max_price_per_item) : '',
    max_quantity: r.max_quantity != null ? String(r.max_quantity) : '',
    prohibited_keywords: (r.prohibited_keywords ?? []).join(', '),
    prohibited_merchants: (r.prohibited_merchants ?? []).join(', '),
  };
}

function validate(f: FormState): string | null {
  if (!f.name.trim()) return 'Name is required.';
  const budget = Number(f.max_budget);
  if (!f.max_budget || !Number.isFinite(budget) || budget <= 0) return 'Budget must be a positive amount.';
  if (!/^\d+(\.\d{1,2})?$/.test(f.max_budget.trim())) return 'Budget can have at most two decimal places.';
  if (!split(f.allowed_merchants).length) return 'Add at least one allowed merchant.';
  if (!split(f.allowed_categories).length) return 'Add at least one allowed category.';
  if (f.max_price_per_item && !(Number(f.max_price_per_item) > 0)) return 'Max unit price must be positive.';
  if (f.max_quantity && !(Number.isInteger(Number(f.max_quantity)) && Number(f.max_quantity) >= 1 && Number(f.max_quantity) <= 20))
    return 'Max quantity must be a whole number from 1 to 20.';
  return null;
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
  };
}

const Field: React.FC<{
  label: string;
  hint?: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  inputMode?: 'decimal' | 'numeric' | 'text';
  id: string;
}> = ({ label, hint, value, onChange, placeholder, inputMode = 'text', id }) => (
  <div>
    <label htmlFor={id} className="mb-1 block text-xs font-semibold text-slate-700">
      {label}
    </label>
    <input
      id={id}
      value={value}
      inputMode={inputMode}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
    />
    {hint && <p className="mt-1 text-[11px] text-slate-500">{hint}</p>}
  </div>
);

export const Mandates: React.FC = () => {
  const list = useAsync(() => pactApi.getMandates());
  const [editing, setEditing] = useState<Mandate | 'new' | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY);
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [toggling, setToggling] = useState<string | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const open = (m: Mandate | 'new') => {
    setEditing(m);
    setForm(m === 'new' ? EMPTY : fromMandate(m));
    setFormError(null);
  };

  const save = async () => {
    const v = validate(form);
    if (v) {
      setFormError(v);
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      if (editing === 'new') {
        await pactApi.createMandate(toInput(form));
        setNotice('Mandate created.');
      } else if (editing) {
        await pactApi.updateMandate(editing.id, toInput(form));
        setNotice('Mandate updated. Any in-flight approval that no longer matches was invalidated automatically.');
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
    setToggling(m.id);
    setPageError(null);
    try {
      await pactApi.updateMandate(m.id, { is_active: !m.is_active });
      setNotice(m.is_active ? `“${m.name}” paused. Pending approvals under it were invalidated.` : `“${m.name}” resumed.`);
      await list.reload();
    } catch (err) {
      setPageError(errorMessage(err));
    } finally {
      setToggling(null);
    }
  };

  const set = (k: keyof FormState) => (v: string) => setForm((f) => ({ ...f, [k]: v }));

  return (
    <div>
      <PageHeader
        title="Spending mandates"
        description="A mandate is the user's standing instruction: how much an agent may spend, where, and on what. The policy engine enforces it on every proposal."
        actions={
          <>
            <RefreshButton onClick={() => void list.reload()} loading={list.loading} />
            <Button size="sm" onClick={() => open('new')} icon={<Plus className="h-3.5 w-3.5" />}>
              New mandate
            </Button>
          </>
        }
      />

      {notice && (
        <p className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-sm text-emerald-900" role="status">
          {notice}
        </p>
      )}
      {pageError && <div className="mb-4"><ErrorState message={pageError} /></div>}
      {list.error && <ErrorState message={list.error} onRetry={() => void list.reload()} />}
      {!list.data && list.loading && <Spinner />}

      {list.data && list.data.length === 0 && (
        <Card>
          <EmptyState title="No mandates yet" description="Create one to let the assistant propose purchases." action={<Button size="sm" onClick={() => open('new')}>New mandate</Button>} />
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        {list.data?.map((m) => {
          const r = m.restrictions;
          return (
            <Card key={m.id} className="flex flex-col">
              <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-5 py-4">
                <div className="min-w-0">
                  <h3 className="text-sm font-semibold text-slate-900">{m.name}</h3>
                  <p className="text-xs text-slate-500">Updated {dateTime(m.updated_at)}</p>
                </div>
                {m.is_active ? <Badge tone="green" dot>Active</Badge> : <Badge tone="slate" dot>Paused</Badge>}
              </div>
              <div className="flex-1 space-y-4 px-5 py-4">
                <div>
                  <div className="mb-2 grid grid-cols-4 gap-2 text-xs">
                    {[
                      ['Allocated', m.max_budget],
                      ['Spent', m.spent_budget],
                      ['Committed', m.committed_budget],
                      ['Remaining', m.remaining_budget],
                    ].map(([label, v]) => (
                      <div key={label}>
                        <p className="text-slate-500">{label}</p>
                        <p className="font-semibold tabular-nums text-slate-900">{money(v, m.currency)}</p>
                      </div>
                    ))}
                  </div>
                  <BudgetBar max={toNumber(m.max_budget)} spent={toNumber(m.spent_budget)} committed={toNumber(m.committed_budget)} />
                </div>
                <div className="space-y-2">
                  <div>
                    <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Allowed merchants</p>
                    <div className="flex flex-wrap gap-1">
                      {m.allowed_merchants.map((x) => <Badge key={x} tone="slate">{x}</Badge>)}
                    </div>
                  </div>
                  <div>
                    <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Allowed categories</p>
                    <div className="flex flex-wrap gap-1">
                      {m.allowed_categories.map((x) => <Badge key={x} tone="slate">{x}</Badge>)}
                    </div>
                  </div>
                  <dl className="grid grid-cols-2 gap-x-4 gap-y-1 pt-1 text-xs">
                    <dt className="text-slate-500">Max unit price</dt>
                    <dd className="text-slate-800">{r.max_price_per_item != null ? money(r.max_price_per_item, m.currency) : 'No limit'}</dd>
                    <dt className="text-slate-500">Max quantity</dt>
                    <dd className="text-slate-800">{r.max_quantity ?? '20 (system limit)'}</dd>
                    <dt className="text-slate-500">Prohibited keywords</dt>
                    <dd className="text-slate-800">{r.prohibited_keywords?.length ? r.prohibited_keywords.join(', ') : 'None'}</dd>
                    <dt className="text-slate-500">Blocked merchants</dt>
                    <dd className="text-slate-800">{r.prohibited_merchants?.length ? r.prohibited_merchants.join(', ') : 'None'}</dd>
                  </dl>
                </div>
              </div>
              <div className="flex gap-2 border-t border-slate-100 px-5 py-3">
                <Button size="sm" variant="secondary" onClick={() => open(m)} icon={<Pencil className="h-3.5 w-3.5" />}>
                  Edit
                </Button>
                <Button
                  size="sm"
                  variant={m.is_active ? 'danger' : 'secondary'}
                  onClick={() => void toggle(m)}
                  loading={toggling === m.id}
                  icon={m.is_active ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
                >
                  {m.is_active ? 'Pause' : 'Resume'}
                </Button>
              </div>
            </Card>
          );
        })}
      </div>

      <Modal open={editing !== null} onClose={() => setEditing(null)} title={editing === 'new' ? 'New spending mandate' : 'Edit mandate'}>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
          className="space-y-4"
        >
          <Field id="m-name" label="Name" value={form.name} onChange={set('name')} placeholder="Q1 developer peripherals" />
          <Field id="m-budget" label="Total budget" value={form.max_budget} onChange={set('max_budget')} inputMode="decimal" placeholder="750.00" />
          <Field id="m-merch" label="Allowed merchants" hint="Comma separated" value={form.allowed_merchants} onChange={set('allowed_merchants')} placeholder="TechHub, BookWorld" />
          <Field id="m-cat" label="Allowed categories" hint="Comma separated" value={form.allowed_categories} onChange={set('allowed_categories')} placeholder="Electronics, Books" />
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="m-maxp" label="Max unit price (optional)" value={form.max_price_per_item} onChange={set('max_price_per_item')} inputMode="decimal" />
            <Field id="m-maxq" label="Max quantity (optional)" value={form.max_quantity} onChange={set('max_quantity')} inputMode="numeric" />
          </div>
          <Field id="m-kw" label="Prohibited keywords" hint="Matched against product name and category" value={form.prohibited_keywords} onChange={set('prohibited_keywords')} placeholder="console, game" />
          <Field id="m-bm" label="Blocked merchants" value={form.prohibited_merchants} onChange={set('prohibited_merchants')} />
          {editing !== 'new' && (
            <p className="rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-900">
              Changing rules invalidates any approval made under the old rules. Those purchases must be re-evaluated and re-approved.
            </p>
          )}
          {formError && <ErrorState compact message={formError} />}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={() => setEditing(null)}>
              Cancel
            </Button>
            <Button type="submit" loading={saving}>
              {editing === 'new' ? 'Create mandate' : 'Save changes'}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

export default Mandates;
