import React, { useMemo, useState } from 'react';
import { ExternalLink, Pencil, PlugZap, RefreshCw, Search } from 'lucide-react';
import { pactApi } from '../api/pact';
import { errorMessage } from '../api/client';
import { ProductTile } from '../components/ProductTile';
import { useToast } from '../components/Toast';
import { Badge, Button, Card, Dialog, EmptyState, ErrorState, Field, PageHeader, RefreshButton, Skeleton, cx, inputClass } from '../components/ui';
import { money, timeAgo, toNumber } from '../lib/format';
import { useAsync } from '../lib/useAsync';
import type { MerchantConnector, Product } from '../types';


const LiveSearch: React.FC<{ onImported: () => Promise<void> }> = ({ onImported }) => {
  const toast = useToast();
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const run = async (e: React.FormEvent) => {
    e.preventDefault();
    if (q.trim().length < 2 || busy) return;
    setBusy(true);
    try {
      const res = await pactApi.searchChannel3(q.trim());
      toast.success(
        `Channel3: ${res.result.offers} retailer offers for “${q.trim()}”`,
        `${res.result.created} new, ${res.result.updated} changed. Each offer now has a PACT product ID and faces your mandate like any other item.`,
      );
      await onImported();
    } catch (err) {
      toast.error('Live search failed', errorMessage(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={run} className="mt-3 flex gap-2">
      <div className="relative flex-1">
        <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-faint" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search live retailers, e.g. “logitech mx master 3s”" aria-label="Search live retailers with Channel3" className={cx(inputClass, 'pl-9')} maxLength={300} />
      </div>
      <Button type="submit" loading={busy} disabled={q.trim().length < 2}>Search</Button>
    </form>
  );
};

export const Catalog: React.FC = () => {
  const toast = useToast();
  const state = useAsync(() => pactApi.getProducts());
  const connectors = useAsync(() => pactApi.getConnectors());
  const [query, setQuery] = useState('');
  const [source, setSource] = useState<string | null>(null);
  const [syncing, setSyncing] = useState<string | null>(null);
  const sourceName = useMemo(() => new Map((connectors.data ?? []).map((c) => [c.id, c.name])), [connectors.data]);

  const sync = async (c: MerchantConnector) => {
    setSyncing(c.id);
    try {
      const r = await pactApi.syncConnector(c.id);
      const n = r.approvals_invalidated;
      toast.success(
        `${c.name} synced: ${r.created} new, ${r.updated} changed, ${r.delisted} delisted`,
        n > 0 ? `${n} open approval${n === 1 ? ' was' : 's were'} invalidated by the new offer data.` : 'Every offer now goes through the same policy engine, fingerprint and PayPal flow.',
      );
      setSource(c.id);
      await Promise.all([state.reload(), connectors.reload()]);
    } catch (err) {
      toast.error(`${c.name} sync failed`, errorMessage(err));
    } finally {
      setSyncing(null);
    }
  };
  const [editing, setEditing] = useState<Product | null>(null);
  const [price, setPrice] = useState('');
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (state.data ?? []).filter(
      (p) => (!source || p.source === source) && (!q || `${p.name} ${p.merchant} ${p.category}`.toLowerCase().includes(q)),
    );
  }, [state.data, query, source]);

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
        eyebrow="Merchant connectors"
        title="Catalog"
        description="Every offer comes from a merchant connector: live retailers through Channel3, or the fixed-price Demo Store. Prices and merchants come only from the connector; agents can only point at an item. When a retailer's offer changes, a store syncs, or you change a Demo Store price, open approvals are re-verified."
        actions={<RefreshButton onClick={() => void Promise.all([state.reload(), connectors.reload()])} loading={state.loading} />}
      />

      <div className="mb-6 grid gap-3">
        {(connectors.data ?? []).map((c) => (
          <Card key={c.id} className={cx('flex flex-wrap items-start gap-3 p-4', source === c.id && 'ring-1 ring-accent/50')}>
            <div className="mt-0.5 rounded-lg bg-accent/10 p-2 text-accent"><PlugZap className="h-4 w-4" /></div>
            <button type="button" className="min-w-0 flex-1 text-left" onClick={() => setSource(source === c.id ? null : c.id)} aria-pressed={source === c.id}>
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-semibold text-fg">{c.name}</p>
                <Badge tone={c.syncable ? 'info' : 'neutral'}>{c.platform}</Badge>
              </div>
              <p className="mt-1 text-xs text-muted">{c.description}</p>
              <p className="mt-1.5 text-[11px] text-faint tnum">
                {c.products} offers · {c.in_stock} in stock{c.syncable ? ` · ${c.last_synced_at ? `synced ${timeAgo(c.last_synced_at)}` : 'never synced'}` : ''}
              </p>
            </button>
            {c.syncable && (
              <Button size="sm" variant="secondary" loading={syncing === c.id} disabled={!c.configured} onClick={() => void sync(c)} icon={<RefreshCw className="h-3.5 w-3.5" />} aria-label={`Sync ${c.name}`}>
                Sync
              </Button>
            )}
            {c.searchable && (
              <div className="basis-full">
                {c.configured ? (
                  <LiveSearch onImported={async () => { setSource(c.id); await Promise.all([state.reload(), connectors.reload()]); }} />
                ) : (
                  <p className="mt-2 text-[11px] text-warn">Not configured: set CHANNEL3_API_KEY on the server.</p>
                )}
              </div>
            )}
          </Card>
        ))}
      </div>

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
                  <Badge tone={p.source === 'channel3' ? 'info' : 'neutral'} className="mt-1.5">via {sourceName.get(p.source) ?? p.source}</Badge>
                  {p.purchase_url && (
                    <a href={p.purchase_url} target="_blank" rel="noopener noreferrer" className="ml-1.5 inline-flex items-center gap-1 text-[11px] text-accent hover:underline">
                      View at retailer <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                </div>
              </div>
              <p className="mt-3 line-clamp-2 flex-1 text-xs leading-relaxed text-muted">{p.description}</p>
              <div className="mt-4 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-lg font-semibold text-fg tnum">{money(p.price)}</span>
                  {!p.in_stock && <Badge tone="warn">Out of stock</Badge>}
                </div>
                {p.source === 'demo-store' && (
                  <Button size="sm" variant="ghost" onClick={() => open(p)} icon={<Pencil className="h-3.5 w-3.5" />} aria-label={`Change price of ${p.name}`}>
                    Price
                  </Button>
                )}
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
