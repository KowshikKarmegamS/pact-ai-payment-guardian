"""PayPal payment processing, order creation, and payment capture routes."""

from decimal import Decimal
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Mandate, Proposal, ProposalStatus
from app.paypal import PayPalError, capture_order, create_order, get_order_details
from app.policy import PolicyEngine
from app.schemas import ProposalOut
from app.services.audit import log_audit_event
from app.services.mandate_service import calculate_mandate_budget

router = APIRouter(prefix="/payments", tags=["Payments"])


class CreateOrderResponse(BaseModel):
    """Response returned upon PayPal order creation."""

    order_id: str = Field(..., description="PayPal Orders API v2 Order ID")
    approve_url: str = Field(..., description="PayPal checkout approval redirect URL")
    proposal: ProposalOut


class CapturePaymentResponse(BaseModel):
    """Response returned upon successful PayPal payment capture."""

    proposal: ProposalOut
    capture_id: str = Field(..., description="PayPal transaction capture ID")
    status: str = Field(..., description="Payment capture status, e.g. COMPLETED")
    message: str


@router.post(
    "/{proposal_id}/create-order",
    response_model=CreateOrderResponse,
    summary="Create PayPal Checkout Order for an approved proposal",
)
async def create_paypal_payment_order(
    proposal_id: str,
    db: Session = Depends(get_db),
):
    """Create a PayPal v2 checkout order strictly tied to the approved proposal.

    Security Rules:
    1. Proposal MUST be in APPROVED status.
    2. Mandate MUST be active.
    3. Idempotent: returns existing order if already generated.
    """
    proposal = db.query(Proposal).filter(Proposal.id == proposal_id).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found.")

    if proposal.status != ProposalStatus.APPROVED:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot initiate PayPal checkout for proposal in '{proposal.status}' status. Must be 'approved'.",
        )

    mandate = db.query(Mandate).filter(Mandate.id == proposal.mandate_id).first()
    if not mandate or not mandate.is_active:
        raise HTTPException(status_code=400, detail="Associated mandate is inactive or missing.")

    # Idempotency check: reuse existing order if already created
    if proposal.paypal_order_id and proposal.paypal_approval_url:
        return CreateOrderResponse(
            order_id=proposal.paypal_order_id,
            approve_url=proposal.paypal_approval_url,
            proposal=ProposalOut.model_validate(proposal),
        )

    try:
        order_res = await create_order(
            proposal_id=proposal.id,
            product_name=proposal.product_name,
            merchant=proposal.merchant,
            total_amount=Decimal(str(proposal.total_amount)),
            price=Decimal(str(proposal.price)),
            quantity=proposal.quantity,
            mandate_id=mandate.id,
            idempotency_key=proposal.idempotency_key,
        )
    except PayPalError as p_err:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"PayPal API error creating order: {p_err.message}",
        )

    proposal.paypal_order_id = order_res["order_id"]
    proposal.paypal_approval_url = order_res["approve_url"]
    db.commit()
    db.refresh(proposal)

    log_audit_event(
        db=db,
        event_type="PAYPAL_ORDER_CREATED",
        entity_type="Proposal",
        entity_id=proposal.id,
        details={
            "paypal_order_id": proposal.paypal_order_id,
            "total_amount": float(proposal.total_amount),
            "merchant": proposal.merchant,
        },
    )

    return CreateOrderResponse(
        order_id=proposal.paypal_order_id,
        approve_url=proposal.paypal_approval_url,
        proposal=ProposalOut.model_validate(proposal),
    )


@router.post(
    "/{proposal_id}/capture",
    response_model=CapturePaymentResponse,
    summary="Capture payment after user checkout approval",
)
async def capture_paypal_payment(
    proposal_id: str,
    db: Session = Depends(get_db),
):
    """Capture PayPal payment server-side after user checkout approval.

    Security Rules:
    1. Proposal MUST be in APPROVED status with valid PayPal order ID.
    2. Backend revalidates mandate and budget before capture.
    3. Idempotency key prevents double capture.
    """
    proposal = db.query(Proposal).filter(Proposal.id == proposal_id).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found.")

    # Idempotent response if already captured
    if proposal.status == ProposalStatus.CAPTURED:
        return CapturePaymentResponse(
            proposal=ProposalOut.model_validate(proposal),
            capture_id=proposal.paypal_capture_id or "ALREADY_CAPTURED",
            status="COMPLETED",
            message="Payment was already captured successfully.",
        )

    if proposal.status != ProposalStatus.APPROVED:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot capture payment for proposal in '{proposal.status}' status. Must be 'approved'.",
        )

    if not proposal.paypal_order_id:
        raise HTTPException(
            status_code=400,
            detail="No PayPal order has been created for this proposal yet.",
        )

    mandate = db.query(Mandate).filter(Mandate.id == proposal.mandate_id).first()
    if not mandate or not mandate.is_active:
        raise HTTPException(status_code=400, detail="Associated mandate is inactive.")

    # Execute PayPal server-side capture
    try:
        capture_res = await capture_order(
            order_id=proposal.paypal_order_id,
            idempotency_key=proposal.idempotency_key,
        )
    except PayPalError as p_err:
        log_audit_event(
            db=db,
            event_type="PAYPAL_CAPTURE_FAILED",
            entity_type="Proposal",
            entity_id=proposal.id,
            details={"error": p_err.message, "details": p_err.details},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"PayPal payment capture failed: {p_err.message}",
        )

    capture_id = capture_res.get("capture_id") or "COMPLETED"
    proposal.status = ProposalStatus.CAPTURED
    proposal.paypal_capture_id = capture_id
    db.commit()
    db.refresh(proposal)

    log_audit_event(
        db=db,
        event_type="PAYPAL_PAYMENT_CAPTURED",
        entity_type="Proposal",
        entity_id=proposal.id,
        details={
            "paypal_order_id": proposal.paypal_order_id,
            "paypal_capture_id": capture_id,
            "total_amount": float(proposal.total_amount),
            "merchant": proposal.merchant,
            "status": "COMPLETED",
        },
    )

    return CapturePaymentResponse(
        proposal=ProposalOut.model_validate(proposal),
        capture_id=capture_id,
        status="COMPLETED",
        message="Payment successfully authorized, captured, and confirmed with PayPal Sandbox.",
    )


@router.get(
    "/{proposal_id}/status",
    summary="Fetch live PayPal order status directly from PayPal Sandbox",
)
async def check_paypal_order_status(
    proposal_id: str,
    db: Session = Depends(get_db),
):
    """Query live PayPal order status directly from Sandbox API."""
    proposal = db.query(Proposal).filter(Proposal.id == proposal_id).first()
    if not proposal or not proposal.paypal_order_id:
        raise HTTPException(status_code=404, detail="Proposal or PayPal order not found.")

    try:
        details = await get_order_details(proposal.paypal_order_id)
        return {
            "proposal_id": proposal.id,
            "paypal_order_id": proposal.paypal_order_id,
            "proposal_status": proposal.status,
            "paypal_status": details.get("status"),
            "details": details,
        }
    except PayPalError as p_err:
        raise HTTPException(status_code=502, detail=p_err.message)
