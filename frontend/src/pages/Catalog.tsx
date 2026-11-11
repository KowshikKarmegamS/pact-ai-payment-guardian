import React, { useMemo, useState } from 'react';
import { Pencil, Search } from 'lucide-react';
import { pactApi } from '../api/pact';
import { errorMessage } from '../api/client';
import { ProductTile } from '../components/ProductTile';
import { useToast } from '../components/Toast';
import { Badge, Button, Card, Dialog, EmptyState, ErrorState, Field, PageHeader, RefreshButton, Skeleton, cx, inputClass } from '../components/ui';
import { money, toNumber } from '../lib/format';
import { useAsync } from '../lib/useAsync';
import type { Product } from '../types';

export const Catalog: React.FC = () => {
  const toast = useToast();
  const state = useAsync(() => pactApi.getProducts());
  const [query, setQuery] = useState('');
  const [editing, setEditing] = useState<Product | null>(null);
  const [price, setPrice] = useState('');
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (state.data ?? []).filter((p) => !q || `${p.name} ${p.merchant} ${p.category}`.toLowerCase().includes(q));
  }, [state.data, query]);

  const open = (p: Product) => {
    setEditing(p);
    setPrice(toNumber(p.price).toFixed(2));
    setFormError(null);
  };

  const valid = /^\d+(\.\d{1,2})?$/.test(price.trim()) && Number(price) > 0;
  const changed = editing ? Number(price).toFixed(2) !== toNumber(editing.price).toFixed(2) : false;

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editing || !valid || !changed || saving) return;
    setSaving(true);
    setFormError(null);
    try {
      const res = await pactApi.updateProduct(editing.id, { price: Number(price).toFixed(2) });
      const n = res.approvals_invalidated;
      toast.success(
        `Price changed to ${money(res.product.price)}`,
        n > 0 ? `${n} open approval${n === 1 ? ' was' : 's were'} invalidated. They cannot be paid at the new price without re-approval.` : 'No open approvals were affected.',
      );
      setEditing(null);
      await state.reload();
    } catch (err) {
      setFormError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <PageHeader
        eyebrow="Merchant feed"
        title="Catalog"
        description="Seeded demo catalog that stands in for a merchant feed. It is the only source of prices and merchants; the AI can only point at an item. Change a price here to see open approvals invalidate."
        actions={<RefreshButton onClick={() => void state.reload()} loading={state.loading} />}
      />

      <div className="relative mb-4 max-w-sm">
        <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-faint" />
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search products…" aria-label="Search catalog" className={cx(inputClass, 'pl-9')} />
      </div>

      {state.error && <ErrorState message={state.error} onRetry={() => void state.reload()} />}
      {!state.data ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-40" />)}</div>
      ) : rows.length === 0 ? (
        <Card><EmptyState title="No products match" /></Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {rows.map((p) => (
            <Card key={p.id} className="flex flex-col p-4">
              <div className="flex items-start gap-3">
                <ProductTile name={p.name} category={p.category} />
                <div className="min-w-0 flex-1">
                  <p className="line-clamp-2 text-sm font-medium leading-snug text-fg">{p.name}</p>
                  <p className="mt-0.5 truncate text-[11px] text-faint">{p.merchant} · {p.category}</p>
                </div>
              </div>
              <p className="mt-3 line-clamp-2 flex-1 text-xs leading-relaxed text-muted">{p.description}</p>
              <div className="mt-4 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-lg font-semibold text-fg tnum">{money(p.price)}</span>
                  {!p.in_stock && <Badge tone="warn">Out of stock</Badge>}
                </div>
                <Button size="sm" variant="ghost" onClick={() => open(p)} icon={<Pencil className="h-3.5 w-3.5" />} aria-label={`Change price of ${p.name}`}>
                  Price
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={editing !== null} onClose={() => setEditing(null)} title="Change catalog price" description={editing?.name}>
        <form onSubmit={save} className="space-y-4">
          <Field label="New price (USD)" error={price && !valid ? 'Enter a positive amount with at most two decimals.' : null} hint={editing ? `Current price ${money(editing.price)}` : undefined}>
            {(id) => <input id={id} className={inputClass} inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} />}
          </Field>
          <p className="rounded-lg border border-caution/25 bg-caution/[0.06] px-3 py-2.5 text-xs leading-relaxed text-fg/90">
            Approvals are bound to the exact price the user saw. Any open proposal for this product is re-verified now, and those that no longer match are invalidated.
          </p>
          {formError && <ErrorState compact message={formError} />}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setEditing(null)}>Cancel</Button>
            <Button type="submit" loading={saving} disabled={!valid || !changed}>Update price</Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
};

export default Catalog;
