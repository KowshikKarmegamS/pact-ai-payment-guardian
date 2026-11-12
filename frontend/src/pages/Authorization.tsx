import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft,
  ArrowRight,
  BadgeCheck,
  Ban,
  Check,
  CheckCircle2,
  Clock,
  Copy,
  ExternalLink,
  Fingerprint,
  Loader2,
  Lock,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Store,
  X,
} from 'lucide-react';
import { pactApi } from '../api/pact';
import { errorMessage } from '../api/client';
import { ProductTile } from '../components/ProductTile';
import { useToast } from '../components/Toast';
import { Badge, Button, Card, CardHeader, ConfirmDialog, ErrorState, Eyebrow, Meter, Mono, Skeleton, StatusPill, TONE_DOT, TONE_PANEL, TONE_TEXT, cx } from '../components/ui';
import { aiLabel, dateTime, eventMeta, explainEvent, isAIProvider, money, shortHash, timeOnly, toNumber, type Tone } from '../lib/format';
import type { AuthorizationReceipt, PolicyCheck, Proposal } from '../types';

const RetailerPanel: React.FC<{ p: Proposal; onDone: () => void }> = ({ p, onDone }) => {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const captured = p.status === 'CAPTURED';
  const host = (() => {
    try {
      return new URL(p.purchase_url ?? '').host;
    } catch {
      return '';
    }
  })();
  const open = async () => {
    setBusy(true);
    try {
      const res = await pactApi.retailerHandoff(p.id);
      window.open(res.url, '_blank', 'noopener,noreferrer');
      toast.info(`Handed off to ${res.merchant}`, res.note);
      onDone();
    } catch (err) {
      toast.error('Handoff refused', errorMessage(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card>
      <CardHeader title="Retailer offer" subtitle={`Live listing via ${p.offer_source === 'channel3' ? 'Channel3' : p.offer_source}`} icon={<Store className="h-4 w-4" />} />
      <div className="space-y-3 p-5 text-xs leading-relaxed text-muted">
        <dl className="space-y-1.5">
          <div className="flex justify-between gap-3"><dt className="text-faint">Retailer</dt><dd className="font-medium text-fg">{p.merchant}</dd></div>
          <div className="flex justify-between gap-3"><dt className="text-faint">Offer</dt><dd><Mono className="text-[11px]">{p.offer_external_id}</Mono></dd></div>
          <div className="flex justify-between gap-3"><dt className="text-faint">Buy link</dt><dd><Mono className="text-[11px]">{host}</Mono></dd></div>
        </dl>
        <p>
          The retailer, price and buy link are part of the approval fingerprint. PACT re-reads this offer from Channel3 before
          approval, before the PayPal order and before capture; any change voids the approval.
        </p>
        {captured ? (
          <>
            <Button className="w-full" loading={busy} onClick={() => void open()} icon={<ExternalLink className="h-4 w-4" />}>
              {p.retailer_handoff_at ? `Open ${p.merchant} again` : `Continue to ${p.merchant}`}
            </Button>
            <p className="text-[11px] text-faint">
              {p.retailer_handoff_at ? `Handed off ${dateTime(p.retailer_handoff_at)}. ` : ''}
              The retailer's own checkout completes the order. PACT records the handoff, never a retailer payment.
            </p>
          </>
        ) : (
          <p className="rounded-lg border border-line bg-ink/40 px-3 py-2 text-[11px] text-faint">
            Retailer handoff opens only after the PayPal Sandbox payment is captured and verified.
          </p>
        )}
      </div>
    </Card>
  );
};

const POLL_MS = 5000;

/* ----------------------------- small pieces ----------------------------- */

const CopyValue: React.FC<{ value: string; display?: string }> = ({ value, display }) => {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      title={`Copy ${value}`}
      onClick={() => {
        void navigator.clipboard?.writeText(value).then(() => {
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1200);
        });
      }}
      className="inline-flex items-center gap-1.5 font-mono text-[12px] text-fg/85 hover:text-fg"
    >
      {display ?? value}
      {copied ? <Check className="h-3 w-3 text-ok" /> : <Copy className="h-3 w-3 text-faint" />}
    </button>
  );
};

const RuleRow: React.FC<{ check: PolicyCheck }> = ({ check }) => (
  <li className={cx('grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 px-5 py-3 sm:grid-cols-[auto_minmax(0,1.1fr)_minmax(0,1fr)_minmax(0,1.2fr)] sm:items-center', !check.passed && 'bg-bad/[0.05]')}>
    <span className={cx('flex h-5 w-5 items-center justify-center rounded-full', check.passed ? 'bg-ok/15 text-ok' : 'bg-bad/15 text-bad')} aria-label={check.passed ? 'passed' : 'violated'}>
      {check.passed ? <Check className="h-3 w-3" strokeWidth={3} /> : <X className="h-3 w-3" strokeWidth={3} />}
    </span>
    <span className={cx('text-[13px] font-medium', check.passed ? 'text-fg' : 'text-bad')}>{check.label}</span>
    {check.actual || check.limit ? (
      <>
        <span className="col-start-2 truncate text-xs sm:col-start-auto" title={check.actual ?? undefined}>
          <span className="text-faint">Attempted </span>
          <span className={cx('font-medium tnum', check.passed ? 'text-fg/90' : 'text-bad')}>{check.actual ?? '—'}</span>
        </span>
        <span className="col-start-2 truncate text-xs sm:col-start-auto" title={check.limit ?? undefined}>
          <span className="text-faint">Allowed </span>
          <span className="text-fg/90 tnum">{check.limit ?? '—'}</span>
        </span>
      </>
    ) : (
      <span className="col-start-2 text-xs text-muted sm:col-span-2 sm:col-start-auto">{check.detail}</span>
    )}
    {!check.passed && (check.actual || check.limit) && <span className="col-start-2 text-xs text-bad/90 sm:col-span-3">{check.detail}</span>}
  </li>
);

type StepState = 'done' | 'current' | 'todo' | 'failed';
const Step: React.FC<{ state: StepState; title: string; children?: React.ReactNode; last?: boolean }> = ({ state, title, children, last }) => (
  <li className="relative flex gap-3 pb-4 last:pb-0">
    {!last && <span className={cx('absolute left-[9px] top-5 h-full w-px', state === 'done' ? 'bg-ok/40' : 'bg-line')} />}
    <span
      className={cx(
        'relative z-10 mt-0.5 flex h-[19px] w-[19px] shrink-0 items-center justify-center rounded-full border',
        state === 'done' && 'border-ok bg-ok text-ink',
        state === 'current' && 'border-info bg-info/15 text-info',
        state === 'failed' && 'border-bad bg-bad/15 text-bad',
        state === 'todo' && 'border-line-strong bg-surface text-faint',
      )}
    >
      {state === 'done' ? <Check className="h-3 w-3" strokeWidth={3} /> : state === 'current' ? <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-info" /> : state === 'failed' ? <X className="h-3 w-3" strokeWidth={3} /> : null}
    </span>
    <div className="min-w-0 flex-1">
      <p className={cx('text-[13px] font-medium', state === 'todo' ? 'text-faint' : 'text-fg')}>{title}</p>
      {children && <div className="mt-0.5 text-xs text-muted">{children}</div>}
    </div>
  </li>
);

function verdict(p: Proposal, failedCount: number, total: number): { tone: Tone; icon: React.ReactNode; title: string; text: string } {
  switch (p.status) {
    case 'POLICY_REJECTED':
      return { tone: 'bad', icon: <ShieldAlert className="h-5 w-5" />, title: `Blocked by the policy engine: ${failedCount} of ${total} rules violated`, text: 'This transaction cannot proceed. It cannot be approved and no PayPal order can be created for it.' };
    case 'AWAITING_HUMAN_APPROVAL':
      return { tone: 'warn', icon: <Clock className="h-5 w-5" />, title: `Policy check passed (${total}/${total}). Your authorization is required.`, text: p.decision_reason ?? 'Passing policy does not authorize a payment. Nothing happens until you explicitly approve.' };
    case 'AUTO_AUTHORIZED':
      return { tone: 'accent', icon: <BadgeCheck className="h-5 w-5" />, title: 'Auto-authorized by your mandate. Payment not started.', text: `${p.decision_reason ?? ''} Nothing is paid until the buyer approves in PayPal Checkout; PACT then re-checks everything and captures.` };
    case 'HUMAN_APPROVED':
      return { tone: 'accent', icon: <BadgeCheck className="h-5 w-5" />, title: 'You authorized this purchase. Ready for PayPal Checkout.', text: 'The server re-checks your approval and every rule before it creates the PayPal order.' };
    case 'AWAITING_PAYPAL_BUYER_APPROVAL':
      return { tone: 'info', icon: <Clock className="h-5 w-5" />, title: 'Waiting for the buyer in PayPal Checkout', text: 'PACT confirms the approval with PayPal directly. Returning to this page alone proves nothing.' };
    case 'PAYPAL_BUYER_APPROVED':
      return { tone: 'info', icon: <ShieldCheck className="h-5 w-5" />, title: 'PayPal confirmed the buyer approved. Final capture is available.', text: 'Before capturing, the server re-verifies the order, the amount, your approval and every rule.' };
    case 'CAPTURE_PENDING':
      return { tone: 'warn', icon: <Clock className="h-5 w-5" />, title: 'Capture requested; PayPal has not confirmed completion', text: p.status_reason ?? 'Retrying is safe: the request is idempotent and cannot double-charge.' };
    case 'CAPTURED':
      return { tone: 'ok', icon: <CheckCircle2 className="h-5 w-5" />, title: 'Payment captured and verified with PayPal', text: p.purchase_url
        ? `PayPal Sandbox returned a completed capture for exactly the approved amount. No order has been placed at ${p.merchant}: the retailer handoff only opens its own checkout.`
        : 'PayPal Sandbox returned a completed capture for exactly the approved amount.' };
    case 'APPROVAL_EXPIRED':
      return { tone: 'caution', icon: <ShieldAlert className="h-5 w-5" />, title: 'Approval invalidated: something changed after it was evaluated', text: 'A change can never silently inherit an old approval. A fresh evaluation and a new approval are required.' };
    case 'PAYPAL_CANCELLED':
      return { tone: 'neutral', icon: <Ban className="h-5 w-5" />, title: 'PayPal Checkout was cancelled', text: 'Nothing was charged. You can reopen checkout or start over.' };
    case 'PAYMENT_FAILED':
      return { tone: 'bad', icon: <ShieldAlert className="h-5 w-5" />, title: 'PayPal did not complete the payment', text: p.status_reason ?? 'No funds were confirmed as captured.' };
    default:
      return { tone: 'neutral', icon: <Ban className="h-5 w-5" />, title: 'You rejected this purchase', text: 'No payment will be made.' };
  }
}

/* --------------------------------- page --------------------------------- */

export const Authorization: React.FC = () => {
  const { id = '' } = useParams();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const toast = useToast();
  const [receipt, setReceipt] = useState<AuthorizationReceipt | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [confirmReject, setConfirmReject] = useState(false);
  const [justCaptured, setJustCaptured] = useState(false);
  const handledReturn = useRef(false);

  const load = useCallback(async () => {
    try {
      setReceipt(await pactApi.getReceipt(id));
      setLoadError(null);
    } catch (err) {
      setLoadError(errorMessage(err));
    }
  }, [id]);

  useEffect(() => {
    setReceipt(null);
    handledReturn.current = false;
    void load();
  }, [load]);

  const run = useCallback(
    async (name: string, fn: () => Promise<void>) => {
      if (busy) return;
      setBusy(name);
      setActionError(null);
      try {
        await fn();
      } catch (err) {
        setActionError(errorMessage(err));
      } finally {
        await load();
        setBusy(null);
      }
    },
    [busy, load],
  );

  // Buyer returned from PayPal: the server asks PayPal whether the buyer approved (this call never captures).
  // Once PayPal confirms, the effect below records the payment automatically through the capture endpoint.
  useEffect(() => {
    const result = params.get('paypal');
    if ((result !== 'return' && result !== 'cancel') || handledReturn.current) return;
    handledReturn.current = true;
    const token = params.get('token') ?? undefined;
    setParams({}, { replace: true });
    void (async () => {
      setBusy('return');
      try {
        if (result === 'cancel') {
          await pactApi.cancelPayPalCheckout(id);
          toast.info('Checkout cancelled', 'Nothing was charged.');
        } else {
          const res = await pactApi.verifyPayPalOrder(id, token);
          if (res.proposal.status === 'PAYPAL_BUYER_APPROVED') toast.success('Buyer approval verified', 'PayPal confirmed it to the PACT server.');
          else toast.info('Back from PayPal', res.message);
        }
      } catch (err) {
        setActionError(errorMessage(err));
      } finally {
        await load();
        setBusy(null);
      }
    })();
  }, [params, setParams, id, load, toast]);

  const status = receipt?.proposal.status;

  // PayPal confirmed the buyer's approval: capture now instead of waiting for a click. The server re-checks the
  // order with PayPal, the approval fingerprint, the live offer and every policy rule before it captures, and the
  // request is idempotent, so a repeat cannot double-charge.
  const autoCaptured = useRef(false);
  useEffect(() => {
    if (status !== 'PAYPAL_BUYER_APPROVED' || autoCaptured.current || busy) return;
    autoCaptured.current = true;
    void (async () => {
      setBusy('capture');
      try {
        const res = await pactApi.capturePayPalPayment(id);
        if (res.capture_status === 'COMPLETED') {
          setJustCaptured(true);
          toast.success('Payment recorded automatically', `PayPal confirmed the buyer's approval; capture ${res.capture_id} completed.`);
        } else {
          toast.info('Capture not completed', res.message);
        }
      } catch (err) {
        setActionError(errorMessage(err));
      } finally {
        await load();
        setBusy(null);
      }
    })();
  }, [status, busy, id, load, toast]);

  // While checkout is open elsewhere, ask the server (which asks PayPal) whether the buyer approved.
  useEffect(() => {
    if (status !== 'AWAITING_PAYPAL_BUYER_APPROVAL') return;
    const t = window.setInterval(async () => {
      try {
        const res = await pactApi.verifyPayPalOrder(id);
        if (res.proposal.status !== 'AWAITING_PAYPAL_BUYER_APPROVAL') await load();
      } catch {
        /* the manual check button surfaces errors */
      }
    }, POLL_MS);
    return () => window.clearInterval(t);
  }, [status, id, load]);

  if (loadError && !receipt) {
    return (
      <div className="space-y-4">
        <Link to="/transactions" className="inline-flex items-center gap-1.5 text-xs text-muted hover:text-fg"><ArrowLeft className="h-3.5 w-3.5" /> Transactions</Link>
        <ErrorState message={loadError} onRetry={() => void load()} />
      </div>
    );
  }
  if (!receipt) {
    return (
      <div className="space-y-5">
        <Skeleton className="h-4 w-28" />
        <Skeleton className="h-36" />
        <div className="grid gap-6 xl:grid-cols-3"><Skeleton className="h-96 xl:col-span-2" /><Skeleton className="h-96" /></div>
      </div>
    );
  }

  const p = receipt.proposal;
  const m = receipt.mandate;
  const b = receipt.budget;
  const checks = receipt.decision_checks;
  const failed = checks.filter((c) => !c.passed);
  const blocked = p.status === 'POLICY_REJECTED';
  const v = verdict(p, failed.length, checks.length);
  const total = money(p.total_amount, p.currency);
  const after = b ? toNumber(b.remaining_after) : 0;
  const hasOrder = !!p.paypal_order_id;
  const buyerOk = ['PAYPAL_BUYER_APPROVED', 'CAPTURE_PENDING', 'CAPTURED'].includes(p.status);
  const showJourney = !!p.approved_at && !blocked;
  const approvalValid = receipt.integrity.intact && p.status !== 'APPROVAL_EXPIRED';
  const canReject = ['AWAITING_HUMAN_APPROVAL', 'HUMAN_APPROVED', 'AUTO_AUTHORIZED', 'AWAITING_PAYPAL_BUYER_APPROVAL', 'PAYPAL_BUYER_APPROVED', 'PAYPAL_CANCELLED'].includes(p.status);

  const approve = () =>
    run('approve', async () => {
      await pactApi.approveProposal(id, p.proposal_fingerprint ?? '');
      toast.success('Purchase authorized', 'Opening PayPal Checkout for exactly this amount…');
      // Straight on to PayPal: the order is created server-side only after the approval is re-verified.
      try {
        const res = await pactApi.createPayPalOrder(id);
        window.location.assign(res.approve_url);
        await new Promise(() => undefined);
      } catch (err) {
        toast.info('Approved; PayPal Checkout not opened yet', errorMessage(err));
      }
    });
  const reject = () =>
    run('reject', async () => {
      await pactApi.rejectProposal(id);
      setConfirmReject(false);
      toast.info('Purchase rejected', 'No payment will be made.');
    });
  const checkout = () =>
    run('checkout', async () => {
      const res = await pactApi.createPayPalOrder(id);
      window.location.assign(res.approve_url);
      await new Promise(() => undefined); // keep the button in its loading state while the browser navigates
    });
  const verify = () =>
    run('verify', async () => {
      const res = await pactApi.verifyPayPalOrder(id);
      toast.info('Checked with PayPal', res.message);
    });
  const capture = () =>
    run('capture', async () => {
      const res = await pactApi.capturePayPalPayment(id);
      if (res.capture_status === 'COMPLETED') {
        setJustCaptured(true);
        toast.success('Payment captured', `PayPal capture ${res.capture_id} completed.`);
      } else {
        toast.info('Capture not completed', res.message);
      }
    });
  const cancelCheckout = () =>
    run('cancel', async () => {
      await pactApi.cancelPayPalCheckout(id);
    });
  const reEvaluate = () =>
    run('reeval', async () => {
      const res = await pactApi.reEvaluateProposal(id);
      toast.info('Fresh proposal created', res.policy.passed ? 'It needs a new approval.' : 'The policy engine blocked it.');
      navigate(`/proposals/${res.proposal.id}`);
    });

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-4">
        <Link to="/transactions" className="inline-flex shrink-0 items-center gap-1.5 text-xs text-muted hover:text-fg">
          <ArrowLeft className="h-3.5 w-3.5" /> Transactions
        </Link>
        <span className="hidden items-center gap-2 text-[11px] text-faint sm:flex">
          Proposal <Mono className="text-[11px] text-muted">{p.id}</Mono>
        </span>
      </div>

      {/* Header */}
      <Card className="relative overflow-hidden animate-rise">
        <div className="flex flex-col gap-5 p-6 sm:flex-row sm:items-center">
          <ProductTile name={p.product_name} category={p.category} size="lg" />
          <div className="min-w-0 flex-1">
            <Eyebrow>Purchase authorization</Eyebrow>
            <h1 className="mt-1.5 text-xl font-semibold tracking-tight text-fg sm:text-2xl">{p.product_name}</h1>
            <p className="mt-1 text-sm text-muted">
              Sold by <span className="text-fg">{p.merchant}</span> · {p.category} · {p.quantity} × {money(p.price, p.currency)}
            </p>
            <p className="mt-1.5 text-xs text-faint">
              Requested by <span className="text-muted">{p.agent_name ?? 'PACT reference shopping agent'}</span>
              {p.agent_name ? ' · through the Agent Gateway' : ''}
            </p>
          </div>
          <div className="sm:text-right">
            <p className="text-[11px] uppercase tracking-wider text-faint">Proposed amount</p>
            <p className="text-3xl font-semibold tracking-tight text-fg tnum">{total}</p>
            <StatusPill status={p.status} className="mt-1.5" />
          </div>
        </div>
        <div className={cx('flex items-start gap-3 border-t px-6 py-4', TONE_PANEL[v.tone])}>
          <span className={cx('mt-0.5 shrink-0', TONE_TEXT[v.tone])}>{v.icon}</span>
          <div>
            <p className="text-sm font-medium text-fg">{v.title}</p>
            <p className="mt-0.5 text-xs leading-relaxed text-muted">{v.text}</p>
          </div>
        </div>
      </Card>

      <div className="grid gap-6 xl:grid-cols-3">
        {/* Left column */}
        <div className="space-y-6 xl:col-span-2">
          {p.status === 'APPROVAL_EXPIRED' && (
            <Card className={cx('p-5', TONE_PANEL.caution)}>
              <Eyebrow className="text-caution">What changed</Eyebrow>
              <p className="mt-2 text-sm leading-relaxed text-fg/90">{p.status_reason}</p>
              {receipt.integrity.changes.length > 0 && (
                <ul className="mt-3 space-y-1">
                  {receipt.integrity.changes.map((c) => (
                    <li key={c} className="flex gap-2 text-xs text-caution"><X className="mt-0.5 h-3.5 w-3.5 shrink-0" />{c}</li>
                  ))}
                </ul>
              )}
            </Card>
          )}

          <Card>
            <CardHeader
              title="Policy evaluation"
              subtitle={`Deterministic rules from “${m.name}”. The AI has no say here.`}
              action={<Badge tone={blocked ? 'bad' : 'ok'}>{checks.length - failed.length}/{checks.length} passed</Badge>}
            />
            <ul className="divide-y divide-line">
              {[...failed, ...checks.filter((c) => c.passed)].map((c) => <RuleRow key={c.rule} check={c} />)}
            </ul>
            {receipt.revalidated_at && receipt.revalidation_checks && (
              <p className="border-t border-line px-5 py-3 text-xs text-muted">
                Last server revalidation {dateTime(receipt.revalidated_at)}:{' '}
                {receipt.revalidation_checks.every((c) => c.passed) ? (
                  <span className="text-ok">all rules still pass</span>
                ) : (
                  <span className="text-bad">{receipt.revalidation_checks.filter((c) => !c.passed).map((c) => c.label).join(', ')} failed</span>
                )}
              </p>
            )}
          </Card>

          <Card>
            <CardHeader title="Purchase summary" subtitle="Advisory. Price, merchant and category come from the catalog." icon={<Sparkles className="h-4 w-4" />} action={<Badge tone={isAIProvider(p.ai_provider) ? 'accent' : 'neutral'}>{aiLabel(p.ai_provider, p.ai_model)}</Badge>} />
            <div className="space-y-3 p-5 text-sm">
              {p.user_prompt && <p className="text-muted"><span className="text-faint">Request: </span>“{p.user_prompt}”</p>}
              <p className="leading-relaxed text-fg/90">
                {p.agent_name && <span className="text-faint">{p.agent_name}’s reason: </span>}
                {p.ai_reasoning}
              </p>
              {receipt.product?.description && <p className="text-xs leading-relaxed text-faint">{receipt.product.description}</p>}
              {p.ai_fallback_reason && <p className="text-xs text-warn">Fallback used: {p.ai_fallback_reason}</p>}
            </div>
          </Card>

          <Card>
            <CardHeader title="Activity" subtitle="Every step recorded in the audit trail" />
            <ol className="p-5">
              {receipt.timeline.map((e, i) => {
                const meta = eventMeta(e.event_type);
                return (
                  <li key={e.id} className="relative flex gap-3 pb-4 last:pb-0">
                    {i < receipt.timeline.length - 1 && <span className="absolute left-[4px] top-4 h-full w-px bg-line" />}
                    <span className={cx('relative z-10 mt-1.5 h-[9px] w-[9px] shrink-0 rounded-full ring-4 ring-surface', TONE_DOT[meta.tone])} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline justify-between gap-3">
                        <p className="text-[13px] font-medium text-fg">{meta.label}</p>
                        <time className="shrink-0 font-mono text-[11px] text-faint">{timeOnly(e.timestamp)}</time>
                      </div>
                      <p className="mt-0.5 text-xs leading-relaxed text-muted">{explainEvent(e)}</p>
                    </div>
                  </li>
                );
              })}
            </ol>
          </Card>
        </div>

        {/* Right column: authorization panel */}
        <div className="space-y-6 xl:sticky xl:top-8 xl:self-start">
          {p.status === 'CAPTURED' && (
            <Card className={cx('p-6 text-center', TONE_PANEL.ok)}>
              <div className={cx('mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-ok text-ink', justCaptured ? 'animate-pop animate-ring' : '')}>
                <Check className="h-7 w-7" strokeWidth={3} />
              </div>
              <p className="mt-4 text-[11px] uppercase tracking-wider text-ok">Payment captured</p>
              <p className="mt-1 text-3xl font-semibold tracking-tight text-fg tnum">{money(p.captured_amount, p.captured_currency ?? p.currency)}</p>
              <p className="text-xs text-muted">{p.captured_currency} · {dateTime(p.captured_at)}</p>
              <dl className="mt-5 space-y-2 border-t border-ok/20 pt-4 text-left text-xs">
                <div className="flex items-center justify-between gap-3"><dt className="text-faint">PayPal capture ID</dt><dd><CopyValue value={p.paypal_capture_id ?? ''} /></dd></div>
                <div className="flex items-center justify-between gap-3"><dt className="text-faint">Capture status</dt><dd className="font-medium text-ok">{p.paypal_capture_status}</dd></div>
                <div className="flex items-center justify-between gap-3"><dt className="text-faint">PayPal order ID</dt><dd><CopyValue value={p.paypal_order_id ?? ''} /></dd></div>
              </dl>
            </Card>
          )}

          {p.purchase_url && <RetailerPanel p={p} onDone={() => void load()} />}

          <Card>
            <CardHeader title="Budget impact" subtitle={m.name} action={<Badge tone={m.status === 'active' ? 'ok' : 'warn'} dot>{m.status}</Badge>} />
            {b && (
              <div className="space-y-4 p-5">
                <Meter max={toNumber(b.max_budget)} spent={toNumber(b.spent)} committed={toNumber(b.committed_other)} preview={toNumber(b.this_purchase)} previewTone={after < 0 ? 'bad' : 'accent'} className="h-2.5" />
                <dl className="space-y-2 text-sm">
                  <div className="flex justify-between"><dt className="text-muted">Mandate budget</dt><dd className="text-fg tnum">{money(b.max_budget, m.currency)}</dd></div>
                  <div className="flex justify-between"><dt className="text-muted">Available before this purchase</dt><dd className="text-fg tnum">{money(b.available, m.currency)}</dd></div>
                  <div className="flex justify-between"><dt className="text-muted">This purchase</dt><dd className={cx('tnum', after < 0 ? 'text-bad' : 'text-accent')}>− {money(b.this_purchase, m.currency)}</dd></div>
                  <div className="flex justify-between border-t border-line pt-2">
                    <dt className="font-medium text-fg">{after < 0 ? 'Over budget by' : 'Remaining after'}</dt>
                    <dd className={cx('text-base font-semibold tnum', after < 0 ? 'text-bad' : 'text-fg')}>{money(Math.abs(after), m.currency)}</dd>
                  </div>
                </dl>
              </div>
            )}
          </Card>

          {!blocked && (
            <Card>
              <CardHeader title="Authorization" icon={<Lock className="h-4 w-4" />} />
              <div className="space-y-4 p-5">
                <div className="flex items-start gap-2.5 rounded-lg border border-line bg-ink/40 p-3">
                  <Fingerprint className="mt-0.5 h-4 w-4 shrink-0 text-faint" />
                  <div className="min-w-0 text-xs leading-relaxed text-muted">
                    <CopyValue value={p.approval_fingerprint ?? p.proposal_fingerprint ?? ''} display={shortHash(p.approval_fingerprint ?? p.proposal_fingerprint)} />
                    <p className="mt-0.5">
                      SHA-256 of the product, merchant, price, quantity, currency, mandate rules{p.purchase_url ? ', retailer offer and buy link' : ''}{p.agent_name ? ' and requesting agent' : ''}.{' '}
                      {p.approved_at ? (
                        <>{p.authorized_by === 'mandate' ? 'Auto-authorized by your mandate' : 'Approved'} {dateTime(p.approved_at)}. <span className={approvalValid ? 'text-ok' : 'text-caution'}>{approvalValid ? 'Still intact.' : 'Void: it no longer matches.'}</span></>
                      ) : (
                        'Your approval is bound to it; if anything changes, it is void.'
                      )}
                    </p>
                  </div>
                </div>

                {p.status === 'AWAITING_HUMAN_APPROVAL' && (
                  <>
                    <p className="text-sm leading-relaxed text-fg/90">
                      Authorize <span className="font-semibold">{total}</span> to <span className="font-semibold">{p.merchant}</span> for {p.quantity} × {p.product_name}?
                    </p>
                    <div className="grid gap-2">
                      <Button variant="success" size="lg" onClick={() => void approve()} loading={busy === 'approve'} disabled={!!busy} icon={<BadgeCheck className="h-4 w-4" />}>
                        Approve {total}
                      </Button>
                      <Button variant="secondary" onClick={() => setConfirmReject(true)} disabled={!!busy}>Reject</Button>
                    </div>
                  </>
                )}

                {showJourney && (
                  <ol>
                    <Step state="done" title={p.authorized_by === 'mandate' ? 'Auto-authorized by your mandate' : 'Approved by you'}>{dateTime(p.approved_at)}</Step>
                    <Step state={hasOrder ? 'done' : p.status === 'HUMAN_APPROVED' || p.status === 'AUTO_AUTHORIZED' ? 'current' : p.status === 'APPROVAL_EXPIRED' ? 'failed' : 'todo'} title="PayPal order created">
                      {hasOrder ? <Mono className="text-[11px] text-muted">{p.paypal_order_id}</Mono> : 'For exactly the approved amount'}
                    </Step>
                    <Step state={buyerOk ? 'done' : p.status === 'AWAITING_PAYPAL_BUYER_APPROVAL' ? 'current' : p.status === 'PAYPAL_CANCELLED' || (p.status === 'APPROVAL_EXPIRED' && hasOrder) ? 'failed' : 'todo'} title="Buyer approves in PayPal Checkout">
                      {buyerOk ? 'Verified by the PACT server with PayPal' : p.status === 'AWAITING_PAYPAL_BUYER_APPROVAL' ? 'Checking with PayPal every few seconds…' : 'Sandbox buyer account'}
                    </Step>
                    <Step last state={p.status === 'CAPTURED' ? 'done' : p.status === 'PAYPAL_BUYER_APPROVED' || p.status === 'CAPTURE_PENDING' ? 'current' : p.status === 'PAYMENT_FAILED' ? 'failed' : 'todo'} title="Payment captured">
                      {p.status === 'CAPTURED' ? <Mono className="text-[11px] text-muted">{p.paypal_capture_id}</Mono> : 'Only after every check passes again'}
                    </Step>
                  </ol>
                )}

                {(p.status === 'HUMAN_APPROVED' || p.status === 'AUTO_AUTHORIZED' || p.status === 'PAYPAL_CANCELLED') && (
                  <Button variant="paypal" size="lg" className="w-full" onClick={() => void checkout()} loading={busy === 'checkout'} disabled={!!busy} icon={<ExternalLink className="h-4 w-4" />}>
                    {p.status === 'PAYPAL_CANCELLED' ? 'Reopen PayPal Checkout' : 'Continue to PayPal Checkout'}
                  </Button>
                )}

                {p.status === 'AWAITING_PAYPAL_BUYER_APPROVAL' && (
                  <div className="grid gap-2">
                    <Button variant="paypal" size="lg" onClick={() => void checkout()} loading={busy === 'checkout'} disabled={!!busy} icon={<ExternalLink className="h-4 w-4" />}>
                      Open PayPal Checkout
                    </Button>
                    <div className="grid grid-cols-2 gap-2">
                      <Button variant="secondary" onClick={() => void verify()} loading={busy === 'verify'} disabled={!!busy} icon={<RefreshCw className="h-3.5 w-3.5" />}>Check with PayPal</Button>
                      <Button variant="ghost" onClick={() => void cancelCheckout()} loading={busy === 'cancel'} disabled={!!busy}>Cancel checkout</Button>
                    </div>
                  </div>
                )}

                {(p.status === 'PAYPAL_BUYER_APPROVED' || p.status === 'CAPTURE_PENDING') && (
                  <div className="grid gap-2">
                    <Button variant="success" size="lg" onClick={() => void capture()} loading={busy === 'capture'} disabled={!!busy} icon={<ShieldCheck className="h-4 w-4" />}>
                      {p.status === 'CAPTURE_PENDING' ? 'Retry capture (safe)' : `Capture ${total}`}
                    </Button>
                    <Button variant="secondary" onClick={() => void verify()} loading={busy === 'verify'} disabled={!!busy} icon={<RefreshCw className="h-3.5 w-3.5" />}>Verify with PayPal</Button>
                  </div>
                )}

                {(p.status === 'APPROVAL_EXPIRED' || p.status === 'PAYPAL_CANCELLED') && !p.status_reason?.includes('Superseded') && (
                  <Button variant="secondary" className="w-full" onClick={() => void reEvaluate()} loading={busy === 'reeval'} disabled={!!busy} icon={<RotateCcw className="h-4 w-4" />}>
                    Re-evaluate at current price and rules
                  </Button>
                )}

                {busy === 'return' && <p className="flex items-center gap-2 text-xs text-muted"><Loader2 className="h-3.5 w-3.5 animate-spin" /> Verifying with PayPal…</p>}
                {actionError && <ErrorState compact message={actionError} />}
                {canReject && p.status !== 'AWAITING_HUMAN_APPROVAL' && (
                  <button onClick={() => setConfirmReject(true)} disabled={!!busy} className="text-xs text-faint underline-offset-2 hover:text-bad hover:underline">
                    Reject this purchase
                  </button>
                )}
                <p className="text-[11px] leading-relaxed text-faint">PayPal Sandbox. PACT is not affiliated with PayPal; checkout happens on PayPal's own pages.</p>
              </div>
            </Card>
          )}

          {blocked && (
            <Card className={cx('p-5', TONE_PANEL.bad)}>
              <div className="flex items-center gap-2 text-sm font-medium text-bad"><Ban className="h-4 w-4" /> Approval and payment unavailable</div>
              <p className="mt-2 text-xs leading-relaxed text-muted">
                The policy engine decides before any human or PayPal step. To allow a purchase like this, the mandate itself has to change.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <Link to="/mandates"><Button size="sm" variant="secondary">View mandate</Button></Link>
                <Link to="/assistant"><Button size="sm" variant="ghost" icon={<ArrowRight className="h-3.5 w-3.5" />} className="flex-row-reverse">Ask for something else</Button></Link>
              </div>
            </Card>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={confirmReject}
        onClose={() => setConfirmReject(false)}
        onConfirm={() => void reject()}
        loading={busy === 'reject'}
        danger
        title="Reject this purchase?"
        confirmLabel="Reject purchase"
        body={<>No payment will be made for <span className="font-medium text-fg">{p.product_name}</span> ({total}). This cannot be undone; you can ask the assistant again later.</>}
      />
    </div>
  );
};

export default Authorization;
