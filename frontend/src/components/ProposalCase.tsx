import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Ban,
  BadgeCheck,
  CheckCircle2,
  ChevronDown,
  ExternalLink,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  Wallet,
  X,
} from 'lucide-react';
import { pactApi } from '../api/pact';
import { errorMessage } from '../api/client';
import type { AuthorizationReceipt as Receipt, Proposal } from '../types';
import { money, shortHash } from '../lib/format';
import { AuthorizationReceipt } from './AuthorizationReceipt';
import { Button, Card, ErrorState, Mono, Spinner, StatusBadge } from './ui';

export const CHECKOUT_WINDOW = 'pact-paypal-checkout';
const POLL_MS = 5000;
const POLL_LIMIT_MS = 10 * 60 * 1000;

type StepState = 'done' | 'current' | 'failed' | 'todo';

function steps(p: Proposal): { label: string; state: StepState }[] {
  const s = p.status;
  const approved = !!p.approved_at;
  const hasOrder = !!p.paypal_order_id;
  const buyerOk = ['PAYPAL_BUYER_APPROVED', 'CAPTURE_PENDING', 'CAPTURED'].includes(s);
  const expiredAt = s === 'APPROVAL_EXPIRED' ? (hasOrder ? 4 : approved ? 3 : 2) : -1;

  const st = (i: number, done: boolean, current: boolean, failed: boolean): StepState =>
    i === expiredAt ? 'failed' : failed ? 'failed' : done ? 'done' : current ? 'current' : 'todo';

  return [
    { label: 'Recommend', state: 'done' },
    { label: 'Policy', state: st(1, s !== 'POLICY_REJECTED', false, s === 'POLICY_REJECTED') },
    { label: 'You approve', state: st(2, approved, s === 'AWAITING_HUMAN_APPROVAL', s === 'HUMAN_REJECTED' && !approved) },
    { label: 'PayPal order', state: st(3, hasOrder, s === 'HUMAN_APPROVED', false) },
    { label: 'Buyer OK', state: st(4, buyerOk, s === 'AWAITING_PAYPAL_BUYER_APPROVAL', s === 'PAYPAL_CANCELLED') },
    { label: 'Captured', state: st(5, s === 'CAPTURED', s === 'PAYPAL_BUYER_APPROVED' || s === 'CAPTURE_PENDING', s === 'PAYMENT_FAILED') },
  ];
}

const Stepper: React.FC<{ proposal: Proposal }> = ({ proposal }) => (
  <ol className="grid grid-cols-3 gap-x-2 gap-y-3 sm:grid-cols-6">
    {steps(proposal).map((step, i) => (
      <li key={step.label} className="flex flex-col gap-1.5">
        <div
          className={`h-1 rounded-full ${
            step.state === 'done'
              ? 'bg-emerald-500'
              : step.state === 'current'
                ? 'bg-amber-400'
                : step.state === 'failed'
                  ? 'bg-red-500'
                  : 'bg-slate-200'
          }`}
        />
        <span
          className={`truncate text-[11px] font-medium ${
            step.state === 'todo' ? 'text-slate-400' : step.state === 'failed' ? 'text-red-700' : 'text-slate-700'
          }`}
        >
          {i + 1}. {step.label}
        </span>
      </li>
    ))}
  </ol>
);

interface Props {
  proposalId: string;
  refreshKey?: number;
  onChanged?: (p: Proposal) => void;
  onNewProposal?: (id: string) => void;
  initialReceiptOpen?: boolean;
  compactHeader?: boolean;
}

export const ProposalCase: React.FC<Props> = ({
  proposalId,
  refreshKey = 0,
  onChanged,
  onNewProposal,
  initialReceiptOpen = true,
  compactHeader,
}) => {
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [receiptOpen, setReceiptOpen] = useState(initialReceiptOpen);
  const [popupBlockedUrl, setPopupBlockedUrl] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);
  const pollStarted = useRef(0);
  const onChangedRef = useRef(onChanged);
  onChangedRef.current = onChanged;

  const load = useCallback(async () => {
    try {
      const r = await pactApi.getReceipt(proposalId);
      setReceipt(r);
      setLoadError(null);
      onChangedRef.current?.(r.proposal);
      return r;
    } catch (err) {
      setLoadError(errorMessage(err));
      return null;
    }
  }, [proposalId]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  const p = receipt?.proposal;

  // While checkout is open in another window, ask the server (which asks PayPal) for approval state.
  useEffect(() => {
    if (!polling || p?.status !== 'AWAITING_PAYPAL_BUYER_APPROVAL') {
      if (polling && p && p.status !== 'AWAITING_PAYPAL_BUYER_APPROVAL') setPolling(false);
      return;
    }
    const t = setInterval(async () => {
      if (Date.now() - pollStarted.current > POLL_LIMIT_MS) {
        setPolling(false);
        return;
      }
      try {
        const res = await pactApi.verifyPayPalOrder(proposalId);
        if (res.proposal.status !== 'AWAITING_PAYPAL_BUYER_APPROVAL') {
          setNotice(res.message);
          await load();
        }
      } catch {
        /* transient; the manual button surfaces errors */
      }
    }, POLL_MS);
    return () => clearInterval(t);
  }, [polling, p?.status, proposalId, load, p]);

  const run = async (name: string, fn: () => Promise<string | void>) => {
    setBusy(name);
    setActionError(null);
    setNotice(null);
    try {
      const msg = await fn();
      if (msg) setNotice(msg);
    } catch (err) {
      setActionError(errorMessage(err));
    } finally {
      setBusy(null);
      await load();
    }
  };

  const approve = () =>
    run('approve', async () => {
      await pactApi.approveProposal(proposalId, p!.proposal_fingerprint!);
      return 'Approval recorded and bound to this exact proposal.';
    });

  const reject = () =>
    run('reject', async () => {
      await pactApi.rejectProposal(proposalId);
      return 'Proposal rejected. No payment will be made.';
    });

  const openCheckout = async () => {
    // Open the window synchronously inside the click so popup blockers allow it.
    const win = window.open('', CHECKOUT_WINDOW, 'popup,width=520,height=760');
    if (win) {
      try {
        win.document.title = 'Connecting to PayPal…';
        win.document.body.innerHTML =
          '<p style="font:14px system-ui;padding:24px;color:#334155">Creating your PayPal Sandbox order…</p>';
      } catch {
        /* cross-origin if reused; ignore */
      }
    }
    setPopupBlockedUrl(null);
    await run('checkout', async () => {
      try {
        const res = await pactApi.createPayPalOrder(proposalId);
        if (win && !win.closed) {
          win.location.href = res.approve_url;
          win.focus();
          pollStarted.current = Date.now();
          setPolling(true);
          return `PayPal Sandbox checkout opened for order ${res.order_id}. Log in with the Sandbox buyer account and approve.`;
        }
        setPopupBlockedUrl(res.approve_url);
        return 'Your browser blocked the checkout window. Use the link below.';
      } catch (err) {
        if (win && !win.closed) win.close();
        throw err;
      }
    });
  };

  const verify = () =>
    run('verify', async () => {
      const res = await pactApi.verifyPayPalOrder(proposalId);
      return res.message;
    });

  const capture = () =>
    run('capture', async () => {
      const res = await pactApi.capturePayPalPayment(proposalId);
      return res.capture_status === 'COMPLETED'
        ? `PayPal capture ${res.capture_id} COMPLETED.`
        : res.message;
    });

  const cancelCheckout = () =>
    run('cancel', async () => {
      const res = await pactApi.cancelPayPalCheckout(proposalId);
      return res.message;
    });

  const reEvaluate = () =>
    run('reeval', async () => {
      const res = await pactApi.reEvaluateProposal(proposalId);
      onNewProposal?.(res.proposal.id);
      return `New proposal ${res.proposal.id.slice(0, 8)} created: ${res.policy.passed ? 'policy passed' : 'blocked'}.`;
    });

  if (!receipt) {
    return (
      <Card className="p-4">
        {loadError ? <ErrorState message={loadError} onRetry={() => void load()} /> : <Spinner label="Loading proposal…" />}
      </Card>
    );
  }

  const proposal = receipt.proposal;
  const s = proposal.status;
  const total = money(proposal.total_amount, proposal.currency);
  const canReject = ['AWAITING_HUMAN_APPROVAL', 'HUMAN_APPROVED', 'AWAITING_PAYPAL_BUYER_APPROVAL', 'PAYPAL_BUYER_APPROVED', 'PAYPAL_CANCELLED'].includes(s);

  return (
    <Card className="overflow-hidden">
      {/* Header */}
      <div className="flex flex-col gap-3 border-b border-slate-100 px-4 py-4 sm:px-5">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            {!compactHeader && proposal.user_prompt && (
              <p className="mb-1 truncate text-xs text-slate-500" title={proposal.user_prompt}>
                “{proposal.user_prompt}”
              </p>
            )}
            <h3 className="text-base font-semibold text-slate-900">{proposal.product_name}</h3>
            <p className="text-sm text-slate-500">
              {proposal.merchant} · {proposal.quantity} × {money(proposal.price, proposal.currency)} ={' '}
              <span className="font-semibold text-slate-900">{total}</span>
            </p>
          </div>
          <StatusBadge status={s} />
        </div>
        <Stepper proposal={proposal} />
      </div>

      {/* Action panel */}
      <div className="space-y-3 bg-slate-50/70 px-4 py-4 sm:px-5">
        {s === 'POLICY_REJECTED' && (
          <div className="flex items-start gap-2 text-sm text-red-800">
            <Ban className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p className="font-semibold">Purchase blocked. Approval and PayPal checkout are unavailable.</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs">
                {receipt.decision_checks.filter((c) => !c.passed).map((c) => (
                  <li key={c.rule}>{c.detail}</li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {s === 'AWAITING_HUMAN_APPROVAL' && (
          <div className="space-y-3">
            <p className="text-sm text-slate-700">
              You are authorizing a payment of <strong>{total}</strong> to <strong>{proposal.merchant}</strong> for{' '}
              <strong>
                {proposal.quantity} × {proposal.product_name}
              </strong>
              . Your approval is bound to fingerprint <Mono>{shortHash(proposal.proposal_fingerprint)}</Mono>; if anything changes, it is void.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button variant="success" onClick={approve} loading={busy === 'approve'} disabled={!!busy} icon={<BadgeCheck className="h-4 w-4" />}>
                Approve {total} to {proposal.merchant}
              </Button>
              <Button variant="danger" onClick={reject} loading={busy === 'reject'} disabled={!!busy} icon={<X className="h-4 w-4" />}>
                Reject
              </Button>
            </div>
          </div>
        )}

        {(s === 'HUMAN_APPROVED' || s === 'PAYPAL_CANCELLED') && (
          <div className="space-y-3">
            <p className="text-sm text-slate-700">
              {s === 'PAYPAL_CANCELLED'
                ? 'PayPal checkout was cancelled; nothing was charged. You can reopen the same order (the server revalidates first) or reject.'
                : 'Approved. The server will re-check the fingerprint and policy, then create a PayPal Sandbox order for exactly this amount.'}
            </p>
            <div className="flex flex-wrap gap-2">
              <Button onClick={openCheckout} loading={busy === 'checkout'} disabled={!!busy} icon={<Wallet className="h-4 w-4" />}>
                {s === 'PAYPAL_CANCELLED' ? 'Reopen PayPal checkout' : 'Pay with PayPal (Sandbox)'}
              </Button>
              {s === 'PAYPAL_CANCELLED' && (
                <Button variant="secondary" onClick={reEvaluate} loading={busy === 'reeval'} disabled={!!busy} icon={<RotateCcw className="h-4 w-4" />}>
                  Start over with fresh evaluation
                </Button>
              )}
            </div>
          </div>
        )}

        {s === 'AWAITING_PAYPAL_BUYER_APPROVAL' && (
          <div className="space-y-3">
            <p className="text-sm text-slate-700">
              PayPal order <Mono>{proposal.paypal_order_id}</Mono> is waiting for the buyer. Log in with the <strong>Sandbox personal (buyer)</strong>{' '}
              account and approve. PACT then confirms the approval with PayPal; returning to this page alone proves nothing.
              {polling && <span className="ml-1 text-xs text-slate-500">(checking with PayPal every few seconds…)</span>}
            </p>
            <div className="flex flex-wrap gap-2">
              {proposal.paypal_approval_url && (
                <Button onClick={openCheckout} loading={busy === 'checkout'} disabled={!!busy} icon={<ExternalLink className="h-4 w-4" />}>
                  Open PayPal checkout
                </Button>
              )}
              <Button variant="secondary" onClick={verify} loading={busy === 'verify'} disabled={!!busy} icon={<RefreshCw className="h-4 w-4" />}>
                Check approval with PayPal
              </Button>
              <Button variant="ghost" onClick={cancelCheckout} loading={busy === 'cancel'} disabled={!!busy}>
                Cancel checkout
              </Button>
            </div>
          </div>
        )}

        {(s === 'PAYPAL_BUYER_APPROVED' || s === 'CAPTURE_PENDING') && (
          <div className="space-y-3">
            <p className="text-sm text-slate-700">
              {s === 'PAYPAL_BUYER_APPROVED' ? (
                <>
                  PayPal confirms the buyer approved order <Mono>{proposal.paypal_order_id}</Mono>. Final step: capture. The server re-verifies the
                  order, the amount, your approval fingerprint and every policy rule first.
                </>
              ) : (
                <>{proposal.status_reason ?? 'Capture requested; PayPal has not confirmed completion yet.'}</>
              )}
            </p>
            <div className="flex flex-wrap gap-2">
              <Button variant="success" onClick={capture} loading={busy === 'capture'} disabled={!!busy} icon={<ShieldCheck className="h-4 w-4" />}>
                {s === 'CAPTURE_PENDING' ? 'Retry capture (idempotent)' : `Capture ${total}`}
              </Button>
              <Button variant="secondary" onClick={verify} loading={busy === 'verify'} disabled={!!busy} icon={<RefreshCw className="h-4 w-4" />}>
                Verify with PayPal
              </Button>
            </div>
          </div>
        )}

        {s === 'CAPTURED' && (
          <div className="flex items-start gap-2 text-sm text-emerald-900">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
            <p>
              PayPal capture <Mono className="text-emerald-900">{proposal.paypal_capture_id}</Mono> is{' '}
              <strong>{proposal.paypal_capture_status}</strong> for {money(proposal.captured_amount, proposal.captured_currency ?? proposal.currency)}{' '}
              {proposal.captured_currency}. Verified against the approved amount.
            </p>
          </div>
        )}

        {s === 'APPROVAL_EXPIRED' && (
          <div className="space-y-3">
            <p className="text-sm text-orange-900">{proposal.status_reason ?? 'The approval no longer matches the proposal or mandate.'}</p>
            {!proposal.status_reason?.includes('Superseded') && (
              <Button variant="secondary" onClick={reEvaluate} loading={busy === 'reeval'} disabled={!!busy} icon={<RotateCcw className="h-4 w-4" />}>
                Re-evaluate against current mandate
              </Button>
            )}
          </div>
        )}

        {(s === 'PAYMENT_FAILED' || s === 'HUMAN_REJECTED') && proposal.status_reason && (
          <p className="text-sm text-slate-700">{proposal.status_reason}</p>
        )}

        {canReject && s !== 'AWAITING_HUMAN_APPROVAL' && (
          <button onClick={reject} disabled={!!busy} className="text-xs font-medium text-slate-500 underline-offset-2 hover:text-red-700 hover:underline">
            Reject this purchase
          </button>
        )}

        {popupBlockedUrl && (
          <p className="text-sm">
            <a href={popupBlockedUrl} target={CHECKOUT_WINDOW} className="font-semibold text-sky-700 underline" onClick={() => { pollStarted.current = Date.now(); setPolling(true); }}>
              Open PayPal Sandbox checkout
            </a>{' '}
            <span className="text-slate-500">or</span>{' '}
            <a href={popupBlockedUrl} className="font-semibold text-sky-700 underline">
              continue in this tab
            </a>
          </p>
        )}
        {notice && <p className="rounded-md bg-white px-3 py-2 text-sm text-slate-700 ring-1 ring-slate-200">{notice}</p>}
        {actionError && <ErrorState compact message={actionError} />}
      </div>

      {/* Receipt */}
      <div className="border-t border-slate-100">
        <button
          onClick={() => setReceiptOpen((v) => !v)}
          className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-semibold text-slate-800 hover:bg-slate-50 sm:px-5"
          aria-expanded={receiptOpen}
        >
          Authorization Receipt
          <ChevronDown className={`h-4 w-4 text-slate-400 transition-transform ${receiptOpen ? 'rotate-180' : ''}`} />
        </button>
        {receiptOpen && (
          <div className="px-3 pb-4 sm:px-5">
            <AuthorizationReceipt receipt={receipt} />
          </div>
        )}
      </div>
    </Card>
  );
};

export default ProposalCase;
