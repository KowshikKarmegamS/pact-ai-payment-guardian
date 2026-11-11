"""PayPal checkout: order creation, buyer-approval verification and verified capture.

Invariants enforced here:
  * Only a human-approved proposal whose fingerprint and policy still hold can get
    a PayPal order or be captured.
  * The server asks PayPal for the order state; the browser returning from PayPal
    proves nothing and never triggers capture.
  * A proposal is marked CAPTURED only when PayPal returns a capture with a real ID,
    status COMPLETED, and the exact approved amount and currency.
  * Capture uses an atomic database lock plus PayPal-Request-Id idempotency, so
    repeated or concurrent requests cannot produce a second charge.
"""

import time
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Mandate, Product, Proposal, ProposalStatus, utc_now
from app.money import paypal_value, q
from app.paypal import (
    PayPalError,
    capture_order,
    create_order,
    extract_captures,
    get_order_details,
    verify_order_matches,
)
from app.schemas import ProposalOut
from app.services.audit import log_audit_event
from app.services.authorization import expire_approval, verify_authorization

router = APIRouter(prefix="/payments", tags=["Payments"])

CAPTURABLE_STATUSES = (
    ProposalStatus.AWAITING_PAYPAL_BUYER_APPROVAL,
    ProposalStatus.PAYPAL_BUYER_APPROVED,
    ProposalStatus.CAPTURE_PENDING,
)
ORDERABLE_STATUSES = (
    ProposalStatus.HUMAN_APPROVED,
    ProposalStatus.AWAITING_PAYPAL_BUYER_APPROVAL,
    ProposalStatus.PAYPAL_CANCELLED,
)
CAPTURE_LOCK_SECONDS = 60
AWAITING_BUYER_PAYPAL_STATES = {"CREATED", "SAVED", "PAYER_ACTION_REQUIRED"}


class CreateOrderResponse(BaseModel):
    order_id: str
    approve_url: str
    reused: bool = Field(default=False, description="True when an existing order was returned")
    proposal: ProposalOut


class PaymentStateResponse(BaseModel):
    """Result of a verify or capture call. Every PayPal field is PayPal's own value."""

    proposal: ProposalOut
    paypal_order_status: Optional[str] = None
    capture_id: Optional[str] = None
    capture_status: Optional[str] = None
    message: str


class VerifyRequest(BaseModel):
    order_token: Optional[str] = Field(default=None, max_length=64, description="`token` query param PayPal appended to the return URL")


def _fail(http_status: int, code: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(status_code=http_status, detail={"code": code, "message": message, **extra})


def _paypal_fail(err: PayPalError) -> HTTPException:
    http_status = {
        "CONFIG_NOT_SANDBOX": 500,
        "MISSING_CREDENTIALS": 503,
        "OAUTH_FAILED": 502,
        "NETWORK_TIMEOUT": 504,
        "NETWORK_ERROR": 502,
        "CURRENCY_NOT_SUPPORTED": 422,
        "ORDER_NOT_APPROVED": 409,
        "INSTRUMENT_DECLINED": 402,
        "PAYER_ACTION_REQUIRED": 409,
    }.get(err.code, 502)
    return _fail(http_status, err.code, err.message, debug_id=err.debug_id, retryable=err.retryable)


def _load(db: Session, proposal_id: str) -> Tuple[Proposal, Mandate, Optional[Product]]:
    proposal = db.query(Proposal).filter(Proposal.id == proposal_id).first()
    if not proposal:
        raise _fail(404, "NOT_FOUND", "Proposal not found.")
    mandate = db.query(Mandate).filter(Mandate.id == proposal.mandate_id).first()
    if not mandate:
        raise _fail(409, "MANDATE_MISSING", "The mandate for this proposal no longer exists.")
    product = db.query(Product).filter(Product.id == proposal.product_id).first()
    return proposal, mandate, product


def _state(proposal: Proposal, message: str) -> PaymentStateResponse:
    return PaymentStateResponse(
        proposal=ProposalOut.model_validate(proposal),
        paypal_order_status=proposal.paypal_order_status,
        capture_id=proposal.paypal_capture_id,
        capture_status=proposal.paypal_capture_status,
        message=message,
    )


def _invalidated(message: str, proposal: Proposal) -> HTTPException:
    return _fail(409, "APPROVAL_INVALIDATED", message, proposal_status=proposal.status.value)


# ---------------------------------------------------------------------------
# Order creation
# ---------------------------------------------------------------------------

@router.post("/{proposal_id}/create-order", response_model=CreateOrderResponse,
             summary="Create (or reopen) the PayPal Sandbox order for a human-approved proposal")
async def create_paypal_payment_order(proposal_id: str, db: Session = Depends(get_db)):
    settings = get_settings()
    proposal, mandate, product = _load(db, proposal_id)

    if proposal.status not in ORDERABLE_STATUSES:
        raise _fail(
            409, "INVALID_STATE",
            f"PayPal checkout requires an explicitly approved proposal; current status is {proposal.status.value}.",
        )

    integrity = verify_authorization(db, proposal, mandate, product, require_approval=True)
    if not integrity.ok:
        raise _invalidated(expire_approval(db, proposal, "PayPal order creation", integrity), proposal)

    # Reuse an existing order: one proposal maps to exactly one PayPal order.
    if proposal.paypal_order_id and proposal.paypal_approval_url:
        reopened = proposal.status == ProposalStatus.PAYPAL_CANCELLED
        proposal.status = ProposalStatus.AWAITING_PAYPAL_BUYER_APPROVAL
        proposal.status_reason = None
        db.commit()
        if reopened:
            log_audit_event(db, "PAYPAL_CHECKOUT_REOPENED", "Proposal", proposal.id,
                            {"paypal_order_id": proposal.paypal_order_id})
        db.refresh(proposal)
        return CreateOrderResponse(order_id=proposal.paypal_order_id, approve_url=proposal.paypal_approval_url,
                                   reused=True, proposal=ProposalOut.model_validate(proposal))

    base = settings.app_base_url
    try:
        order = await create_order(
            proposal_id=proposal.id,
            product_name=proposal.product_name,
            merchant=proposal.merchant,
            total_amount=q(proposal.total_amount),
            price=q(proposal.price),
            quantity=proposal.quantity,
            mandate_id=mandate.id,
            idempotency_key=proposal.idempotency_key,
            currency=proposal.currency,
            return_url=f"{base}/proposals/{proposal.id}?paypal=return",
            cancel_url=f"{base}/proposals/{proposal.id}?paypal=cancel",
        )
    except PayPalError as err:
        log_audit_event(db, "PAYPAL_ORDER_FAILED", "Proposal", proposal.id, err.safe_details())
        raise _paypal_fail(err)

    if not order.get("order_id") or not order.get("approve_url"):
        log_audit_event(db, "PAYPAL_ORDER_FAILED", "Proposal", proposal.id,
                        {"code": "INCOMPLETE_RESPONSE", "paypal_status": order.get("status")})
        raise _fail(502, "INCOMPLETE_RESPONSE", "PayPal did not return an order ID and approval link.")

    proposal.paypal_order_id = order["order_id"]
    proposal.paypal_approval_url = order["approve_url"]
    proposal.paypal_order_status = order.get("status")
    proposal.status = ProposalStatus.AWAITING_PAYPAL_BUYER_APPROVAL
    proposal.status_reason = None
    db.commit()
    db.refresh(proposal)

    log_audit_event(db, "PAYPAL_ORDER_CREATED", "Proposal", proposal.id, {
        "paypal_order_id": proposal.paypal_order_id,
        "paypal_status": proposal.paypal_order_status,
        "amount": paypal_value(proposal.total_amount),
        "currency": proposal.currency,
        "merchant": proposal.merchant,
        "approval_fingerprint": proposal.approval_fingerprint,
    })
    return CreateOrderResponse(order_id=proposal.paypal_order_id, approve_url=proposal.paypal_approval_url,
                               proposal=ProposalOut.model_validate(proposal))


# ---------------------------------------------------------------------------
# Capture result interpretation
# ---------------------------------------------------------------------------

def _finalize_capture(db: Session, proposal: Proposal, paypal_response: Dict[str, Any], source: str) -> PaymentStateResponse:
    """Apply a PayPal capture/order response. Marks CAPTURED only on verified success."""
    order_status = paypal_response.get("status")
    proposal.paypal_order_status = order_status
    proposal.capture_lock_expires = None
    captures = extract_captures(paypal_response)
    cap = captures[0] if captures else None

    if not cap or not cap.get("id"):
        proposal.status = ProposalStatus.CAPTURE_PENDING
        proposal.status_reason = (
            "PayPal's response did not include a capture ID. The payment is NOT confirmed; "
            "use 'Verify with PayPal' to reconcile."
        )
        db.commit()
        log_audit_event(db, "PAYPAL_CAPTURE_UNVERIFIED", "Proposal", proposal.id,
                        {"paypal_order_id": proposal.paypal_order_id, "paypal_status": order_status, "source": source})
        raise _fail(502, "CAPTURE_UNVERIFIED", proposal.status_reason)

    cap_status = str(cap.get("status") or "")
    cap_amount = cap.get("amount") or {}
    proposal.paypal_capture_id = str(cap["id"])
    proposal.paypal_capture_status = cap_status
    proposal.captured_currency = cap_amount.get("currency_code")
    proposal.captured_amount = q(cap_amount.get("value")) if cap_amount.get("value") else None
    proposal.paypal_debug_id = None

    amount_ok = (
        cap_amount.get("value") == paypal_value(proposal.total_amount)
        and cap_amount.get("currency_code") == proposal.currency
    )
    if not amount_ok:
        proposal.status = ProposalStatus.PAYMENT_FAILED
        proposal.status_reason = (
            f"PayPal captured {cap_amount.get('value')} {cap_amount.get('currency_code')} but the approved amount was "
            f"{paypal_value(proposal.total_amount)} {proposal.currency}. Flagged for manual review."
        )
        db.commit()
        log_audit_event(db, "PAYPAL_CAPTURE_AMOUNT_MISMATCH", "Proposal", proposal.id, {
            "paypal_order_id": proposal.paypal_order_id, "paypal_capture_id": proposal.paypal_capture_id,
            "captured": cap_amount, "approved_amount": paypal_value(proposal.total_amount),
            "approved_currency": proposal.currency,
        })
        raise _fail(502, "CAPTURE_AMOUNT_MISMATCH", proposal.status_reason)

    if cap_status == "COMPLETED" and order_status == "COMPLETED":
        proposal.status = ProposalStatus.CAPTURED
        proposal.status_reason = None
        proposal.captured_at = utc_now()
        db.commit()
        db.refresh(proposal)
        log_audit_event(db, "PAYPAL_PAYMENT_CAPTURED", "Proposal", proposal.id, {
            "paypal_order_id": proposal.paypal_order_id,
            "paypal_capture_id": proposal.paypal_capture_id,
            "capture_status": cap_status,
            "amount": cap_amount.get("value"),
            "currency": cap_amount.get("currency_code"),
            "merchant": proposal.merchant,
            "source": source,
        })
        return _state(proposal, "PayPal confirmed the capture. Payment COMPLETED.")

    if cap_status == "PENDING":
        reason = ((cap.get("status_details") or {}).get("reason")) or "unspecified"
        proposal.status = ProposalStatus.CAPTURE_PENDING
        proposal.status_reason = f"PayPal capture is PENDING (reason: {reason}). Funds are not yet confirmed."
        db.commit()
        db.refresh(proposal)
        log_audit_event(db, "PAYPAL_CAPTURE_PENDING", "Proposal", proposal.id, {
            "paypal_order_id": proposal.paypal_order_id, "paypal_capture_id": proposal.paypal_capture_id,
            "pending_reason": reason,
        })
        return _state(proposal, proposal.status_reason)

    proposal.status = ProposalStatus.PAYMENT_FAILED
    proposal.status_reason = f"PayPal returned capture status {cap_status or 'UNKNOWN'} (order status {order_status})."
    db.commit()
    db.refresh(proposal)
    log_audit_event(db, "PAYPAL_CAPTURE_FAILED", "Proposal", proposal.id, {
        "paypal_order_id": proposal.paypal_order_id, "paypal_capture_id": proposal.paypal_capture_id,
        "capture_status": cap_status, "order_status": order_status,
    })
    raise _fail(402, "CAPTURE_NOT_COMPLETED", proposal.status_reason)


def _check_order(db: Session, proposal: Proposal, mandate: Mandate, order: Dict[str, Any]) -> None:
    problems = verify_order_matches(
        order, order_id=proposal.paypal_order_id, proposal_id=proposal.id,
        mandate_id=mandate.id, amount=q(proposal.total_amount), currency=proposal.currency,
    )
    if problems:
        proposal.capture_lock_expires = None
        db.commit()
        log_audit_event(db, "PAYPAL_ORDER_MISMATCH", "Proposal", proposal.id,
                        {"paypal_order_id": proposal.paypal_order_id, "problems": problems})
        raise _fail(409, "ORDER_MISMATCH", "The PayPal order does not match the approved proposal: " + " ".join(problems))


# ---------------------------------------------------------------------------
# Buyer-approval verification (never captures)
# ---------------------------------------------------------------------------

@router.post("/{proposal_id}/verify", response_model=PaymentStateResponse,
             summary="Ask PayPal for the real order state (does not capture)")
async def verify_paypal_order(proposal_id: str, body: Optional[VerifyRequest] = None, db: Session = Depends(get_db)):
    proposal, mandate, _ = _load(db, proposal_id)
    if not proposal.paypal_order_id:
        raise _fail(409, "NO_ORDER", "No PayPal order exists for this proposal yet.")
    if body and body.order_token and body.order_token != proposal.paypal_order_id:
        log_audit_event(db, "PAYPAL_RETURN_TOKEN_MISMATCH", "Proposal", proposal.id,
                        {"expected_order_id": proposal.paypal_order_id, "returned_order_id": body.order_token})
        raise _fail(400, "ORDER_TOKEN_MISMATCH", "The PayPal return token does not belong to this proposal.")
    if proposal.status == ProposalStatus.CAPTURED:
        return _state(proposal, "Payment already captured and verified.")

    try:
        order = await get_order_details(proposal.paypal_order_id)
    except PayPalError as err:
        raise _paypal_fail(err)
    _check_order(db, proposal, mandate, order)

    paypal_status = order.get("status")
    proposal.paypal_order_status = paypal_status

    if paypal_status == "COMPLETED" and proposal.status in CAPTURABLE_STATUSES:
        return _finalize_capture(db, proposal, order, source="verify")

    if paypal_status == "APPROVED":
        if proposal.status == ProposalStatus.AWAITING_PAYPAL_BUYER_APPROVAL:
            proposal.status = ProposalStatus.PAYPAL_BUYER_APPROVED
            proposal.status_reason = None
            db.commit()
            log_audit_event(db, "PAYPAL_BUYER_APPROVED", "Proposal", proposal.id,
                            {"paypal_order_id": proposal.paypal_order_id, "paypal_status": paypal_status})
            message = "PayPal confirms the buyer approved checkout. Final capture is now available."
        elif proposal.status == ProposalStatus.PAYPAL_CANCELLED:
            message = "PayPal shows the order approved, but checkout was cancelled in PACT. Reopen checkout to continue."
        else:
            message = f"PayPal order is APPROVED; proposal status is {proposal.status.value}."
    elif paypal_status in AWAITING_BUYER_PAYPAL_STATES:
        message = f"PayPal reports {paypal_status}: the buyer has not approved checkout yet."
    elif paypal_status == "VOIDED":
        if proposal.status in CAPTURABLE_STATUSES:
            proposal.status = ProposalStatus.PAYPAL_CANCELLED
            proposal.status_reason = "PayPal voided this order."
        message = "PayPal voided this order."
    else:
        message = f"PayPal reports order status {paypal_status}."

    db.commit()
    db.refresh(proposal)
    return _state(proposal, message)


@router.post("/{proposal_id}/cancel", response_model=PaymentStateResponse,
             summary="Record that the buyer cancelled PayPal checkout")
def cancel_paypal_checkout(proposal_id: str, db: Session = Depends(get_db)):
    proposal, _, _ = _load(db, proposal_id)
    if proposal.status in (ProposalStatus.AWAITING_PAYPAL_BUYER_APPROVAL, ProposalStatus.PAYPAL_BUYER_APPROVED):
        proposal.status = ProposalStatus.PAYPAL_CANCELLED
        proposal.status_reason = "The buyer cancelled PayPal checkout. No payment was taken."
        db.commit()
        db.refresh(proposal)
        log_audit_event(db, "PAYPAL_CHECKOUT_CANCELLED", "Proposal", proposal.id,
                        {"paypal_order_id": proposal.paypal_order_id})
        return _state(proposal, proposal.status_reason)
    return _state(proposal, f"No change: proposal status is {proposal.status.value}.")


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------

def _acquire_capture_lock(db: Session, proposal_id: str) -> bool:
    now = time.time()
    rows = (
        db.query(Proposal)
        .filter(
            Proposal.id == proposal_id,
            Proposal.status.in_(CAPTURABLE_STATUSES),
            or_(Proposal.capture_lock_expires.is_(None), Proposal.capture_lock_expires < now),
        )
        .update({Proposal.capture_lock_expires: now + CAPTURE_LOCK_SECONDS}, synchronize_session=False)
    )
    db.commit()
    return rows == 1


@router.post("/{proposal_id}/capture", response_model=PaymentStateResponse,
             summary="Explicit final capture, after PayPal confirms buyer approval")
async def capture_paypal_payment(proposal_id: str, db: Session = Depends(get_db)):
    proposal, mandate, product = _load(db, proposal_id)

    if proposal.status == ProposalStatus.CAPTURED:
        log_audit_event(db, "DUPLICATE_CAPTURE_PREVENTED", "Proposal", proposal.id,
                        {"paypal_order_id": proposal.paypal_order_id, "paypal_capture_id": proposal.paypal_capture_id})
        return _state(proposal, "Already captured. PayPal was not called again; no duplicate charge was made.")

    if proposal.status not in CAPTURABLE_STATUSES or not proposal.paypal_order_id:
        hints = {
            ProposalStatus.AWAITING_HUMAN_APPROVAL: "The proposal has not been approved by a human.",
            ProposalStatus.HUMAN_APPROVED: "No PayPal order exists yet. Start PayPal checkout first.",
            ProposalStatus.PAYPAL_CANCELLED: "PayPal checkout was cancelled. Reopen checkout first.",
            ProposalStatus.POLICY_REJECTED: "The policy engine blocked this proposal.",
        }
        raise _fail(409, "INVALID_STATE",
                    hints.get(proposal.status, f"Capture is not allowed in status {proposal.status.value}."))

    if not _acquire_capture_lock(db, proposal.id):
        db.refresh(proposal)
        if proposal.status == ProposalStatus.CAPTURED:
            return _state(proposal, "Already captured. No duplicate charge was made.")
        log_audit_event(db, "DUPLICATE_CAPTURE_PREVENTED", "Proposal", proposal.id, {"reason": "capture already in progress"})
        raise _fail(409, "CAPTURE_IN_PROGRESS", "A capture for this proposal is already in progress.")
    db.refresh(proposal)

    try:
        # 1. Ask PayPal for the real order state.
        try:
            order = await get_order_details(proposal.paypal_order_id)
        except PayPalError as err:
            raise _paypal_fail(err)
        _check_order(db, proposal, mandate, order)
        paypal_status = order.get("status")

        # A previous attempt may already have captured (e.g. after a timeout): reconcile, never re-capture.
        if paypal_status == "COMPLETED":
            return _finalize_capture(db, proposal, order, source="reconcile")

        if paypal_status != "APPROVED":
            proposal.paypal_order_status = paypal_status
            if proposal.status == ProposalStatus.PAYPAL_BUYER_APPROVED:
                proposal.status = ProposalStatus.AWAITING_PAYPAL_BUYER_APPROVAL
            db.commit()
            log_audit_event(db, "CAPTURE_BLOCKED_NOT_APPROVED", "Proposal", proposal.id,
                            {"paypal_order_id": proposal.paypal_order_id, "paypal_status": paypal_status})
            raise _fail(409, "ORDER_NOT_APPROVED",
                        f"PayPal reports the order as {paypal_status}. The buyer must approve checkout before capture.")

        if proposal.status == ProposalStatus.AWAITING_PAYPAL_BUYER_APPROVAL:
            proposal.status = ProposalStatus.PAYPAL_BUYER_APPROVED
            db.commit()
            log_audit_event(db, "PAYPAL_BUYER_APPROVED", "Proposal", proposal.id,
                            {"paypal_order_id": proposal.paypal_order_id, "paypal_status": paypal_status})

        # 2. Revalidate the human approval and policy right before money moves.
        integrity = verify_authorization(db, proposal, mandate, product, require_approval=True)
        if not integrity.ok:
            raise _invalidated(expire_approval(db, proposal, "capture", integrity), proposal)

        # 3. Capture.
        proposal.status = ProposalStatus.CAPTURE_PENDING
        proposal.paypal_order_status = paypal_status
        proposal.status_reason = "Capture request sent to PayPal."
        db.commit()
        log_audit_event(db, "PAYPAL_CAPTURE_ATTEMPTED", "Proposal", proposal.id, {
            "paypal_order_id": proposal.paypal_order_id,
            "amount": paypal_value(proposal.total_amount),
            "currency": proposal.currency,
            "fingerprint": integrity.current_fingerprint,
        })

        try:
            result = await capture_order(proposal.paypal_order_id, proposal.idempotency_key)
        except PayPalError as err:
            proposal.paypal_debug_id = err.debug_id
            if err.code == "ORDER_ALREADY_CAPTURED":
                order = await get_order_details(proposal.paypal_order_id)
                return _finalize_capture(db, proposal, order, source="already-captured")
            if err.retryable:
                proposal.status_reason = (
                    f"{err.message} Status remains CAPTURE_PENDING; retrying is safe and cannot double-charge."
                )
                db.commit()
                log_audit_event(db, "PAYPAL_CAPTURE_UNCERTAIN", "Proposal", proposal.id, err.safe_details())
                raise _paypal_fail(err)
            if err.code in ("INSTRUMENT_DECLINED", "PAYER_ACTION_REQUIRED"):
                proposal.status = ProposalStatus.AWAITING_PAYPAL_BUYER_APPROVAL
            else:
                proposal.status = ProposalStatus.PAYMENT_FAILED
            proposal.status_reason = err.message
            db.commit()
            log_audit_event(db, "PAYPAL_CAPTURE_FAILED", "Proposal", proposal.id, err.safe_details())
            raise _paypal_fail(err)

        return _finalize_capture(db, proposal, result, source="capture")
    finally:
        # Always release the lock; terminal states make it irrelevant anyway.
        db.refresh(proposal)
        if proposal.capture_lock_expires is not None:
            proposal.capture_lock_expires = None
            db.commit()


@router.get("/{proposal_id}/status", summary="Read-only PayPal order status (sanitized)")
async def check_paypal_order_status(proposal_id: str, db: Session = Depends(get_db)):
    proposal, _, _ = _load(db, proposal_id)
    if not proposal.paypal_order_id:
        raise _fail(404, "NO_ORDER", "No PayPal order exists for this proposal.")
    try:
        order = await get_order_details(proposal.paypal_order_id)
    except PayPalError as err:
        raise _paypal_fail(err)
    captures = extract_captures(order)
    return {
        "proposal_id": proposal.id,
        "proposal_status": proposal.status.value,
        "paypal_order_id": proposal.paypal_order_id,
        "paypal_status": order.get("status"),
        "captures": [{"id": c.get("id"), "status": c.get("status"), "amount": c.get("amount")} for c in captures],
    }
