"""Proposal generation, policy evaluation, human approval and Authorization Receipts."""

from decimal import Decimal
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent import generate_shopping_recommendation, rank_alternatives
from app.config import get_settings
from app.database import get_db
from app.models import (
    COMMITTED_STATUSES,
    SPENT_STATUSES,
    AuditLog,
    Mandate,
    Product,
    Proposal,
    ProposalStatus,
    as_utc,
    utc_now,
)
from app.money import fmt, q
from app.policy import PolicyEngine, checks_to_json
from app.schemas import (
    AuditLogOut,
    AuthorizationReceipt,
    PolicyCheck,
    ProductOut,
    ReceiptBudget,
    PolicyResult,
    ProposalApproval,
    ProposalOut,
    ReceiptIntegrity,
    ReceiptMandate,
)
from app.connectors import ConnectorError
from app.services.audit import log_audit_event
from app.services.connector_sync import reverify_live_offer, search_and_import
from app.services.auto_authorization import AUTO_APPROVE, REQUIRES_APPROVAL, decide, lock_mandate_budget, reservation_ref
from app.services.authorization import (
    canonical_snapshot,
    describe_changes,
    catalog_drift,
    expire_approval,
    fingerprint_of,
    verify_authorization,
)
from app.services.mandate_service import budget_breakdown, mandate_status

router = APIRouter(prefix="/proposals", tags=["Proposals"])

REJECTABLE_STATUSES = (
    ProposalStatus.AWAITING_HUMAN_APPROVAL,
    ProposalStatus.HUMAN_APPROVED,
    ProposalStatus.AUTO_AUTHORIZED,
    ProposalStatus.AWAITING_PAYPAL_BUYER_APPROVAL,
    ProposalStatus.PAYPAL_BUYER_APPROVED,
    ProposalStatus.PAYPAL_CANCELLED,
    ProposalStatus.APPROVAL_EXPIRED,
)


def _fail(http_status: int, code: str, message: str, **extra) -> HTTPException:
    return HTTPException(status_code=http_status, detail={"code": code, "message": message, **extra})


class ShoppingPromptRequest(BaseModel):
    prompt: str = Field(..., min_length=2, max_length=1000, description="Natural-language shopping request")
    mandate_id: str = Field(..., description="Spending mandate that governs this purchase")
    source: Literal["demo-store", "channel3"] = Field(
        default="demo-store",
        description="'channel3' searches live retailers through Channel3 first; 'demo-store' uses the fixed-price "
                    "Demo Store connector. The AI then picks from those offers")


class ProposeRequest(BaseModel):
    """A user-selected catalog item, evaluated by exactly the same policy path as an AI pick."""

    mandate_id: str
    product_id: int
    quantity: int = Field(default=1, ge=1, le=20)
    source_proposal_id: Optional[str] = Field(default=None, description="The proposal whose alternative this was")


def _alternatives_preview(db: Session, mandate: Mandate, prompt: str, catalog: List[Product], chosen: Product,
                          remaining: Decimal) -> List[dict]:
    """Up to three other matches with a deterministic eligibility preview (quantity 1)."""
    settings = get_settings()
    out = []
    for alt in rank_alternatives(prompt, catalog, chosen.id):
        preview = PolicyEngine.evaluate(
            mandate=mandate,
            proposal={"merchant": alt.merchant, "category": alt.category, "product_name": alt.name,
                      "price": q(alt.price), "quantity": 1, "total_amount": q(alt.price),
                      "currency": settings.currency},
            product=alt, remaining_budget=remaining, expected_currency=settings.currency,
        )
        out.append({
            "product_id": alt.id, "name": alt.name, "merchant": alt.merchant, "category": alt.category,
            "price": f"{q(alt.price):.2f}", "in_stock": alt.in_stock, "eligible": preview.passed,
            "blocking": [c.label for c in preview.checks if not c.passed],
        })
    return out


class AIProvenance(BaseModel):
    provider: str
    model: Optional[str]
    fallback_reason: Optional[str]
    ignored_fields: Optional[List[str]] = None


class ProposalGenerationResponse(BaseModel):
    proposal: ProposalOut
    policy: PolicyResult
    ai: AIProvenance
    message: str


def _create_and_evaluate(
    db: Session,
    mandate: Mandate,
    product: Product,
    quantity: int,
    *,
    prompt: Optional[str],
    reasoning: Optional[str],
    provider: str,
    model: Optional[str],
    fallback_reason: Optional[str],
    supersedes_id: Optional[str] = None,
    ai_audit: Optional[dict] = None,
    catalog: Optional[List[Product]] = None,
    origin_event: str = "AI_RECOMMENDATION_GENERATED",
    agent_id: Optional[str] = None,
    agent_name: Optional[str] = None,
    agent_request_id: Optional[str] = None,
) -> tuple:
    """Price the item from the catalog, run the policy engine, decide, and reserve budget atomically."""
    settings = get_settings()
    lock_mandate_budget(db, mandate)
    unit_price = q(product.price)
    total = q(unit_price * Decimal(quantity))

    proposal = Proposal(
        mandate_id=mandate.id,
        product_id=product.id,
        product_name=product.name,
        merchant=product.merchant,
        category=product.category,
        price=unit_price,
        quantity=quantity,
        total_amount=total,
        currency=settings.currency,
        user_prompt=prompt,
        ai_reasoning=reasoning,
        ai_provider=provider,
        ai_model=model,
        ai_fallback_reason=fallback_reason,
        supersedes_id=supersedes_id,
        agent_id=agent_id,
        agent_name=agent_name,
        agent_request_id=agent_request_id,
    )
    if product.purchase_url:
        proposal.offer_source = product.source
        proposal.offer_external_id = product.external_id
        proposal.purchase_url = product.purchase_url
    db.add(proposal)
    db.flush()  # assigns id, idempotency key

    _, _, remaining = budget_breakdown(db, mandate, exclude_proposal_id=proposal.id)
    policy = PolicyEngine.evaluate(
        mandate=mandate, proposal=proposal, product=product,
        remaining_budget=remaining, expected_currency=settings.currency,
    )
    decision, reason = decide(mandate, policy, total, settings.currency)
    proposal.authorization_decision = decision
    proposal.decision_reason = reason
    if decision == AUTO_APPROVE:
        proposal.authorized_by = "mandate"
    snapshot = canonical_snapshot(proposal, mandate)
    proposal.policy_checks = checks_to_json(policy)
    if catalog is not None:
        proposal.alternatives = _alternatives_preview(db, mandate, prompt or product.name, catalog, product, remaining)
    proposal.remaining_budget_at_decision = remaining
    proposal.approval_snapshot = snapshot
    proposal.proposal_fingerprint = fingerprint_of(snapshot)
    if decision == AUTO_APPROVE:
        now = utc_now()
        proposal.status = ProposalStatus.AUTO_AUTHORIZED
        proposal.approval_fingerprint = proposal.proposal_fingerprint
        proposal.approved_at = now
        proposal.budget_reserved_at = now
        proposal.status_reason = None
    elif decision == REQUIRES_APPROVAL:
        proposal.status = ProposalStatus.AWAITING_HUMAN_APPROVAL
        proposal.status_reason = None
    else:
        proposal.status = ProposalStatus.POLICY_REJECTED
        proposal.status_reason = reason
    db.commit()  # releases the mandate budget lock
    db.refresh(proposal)

    if ai_audit is not None:
        log_audit_event(db, origin_event, "Proposal", proposal.id, ai_audit)
    log_audit_event(db, "POLICY_CHECK_PASSED" if policy.passed else "POLICY_CHECK_FAILED", "Proposal", proposal.id, {
        "mandate_id": mandate.id,
        "requested_by": proposal.agent_name or "PACT reference shopping agent",
        "product_name": proposal.product_name,
        "merchant": proposal.merchant,
        "category": proposal.category,
        "unit_price": f"{proposal.price:.2f}",
        "quantity": proposal.quantity,
        "total_amount": f"{proposal.total_amount:.2f}",
        "currency": proposal.currency,
        "remaining_budget": f"{remaining:.2f}",
        "passed": policy.passed,
        "rules_evaluated": len(policy.checks),
        "violations": policy.violations,
        "proposal_fingerprint": proposal.proposal_fingerprint,
    })
    log_audit_event(db, "AUTHORIZATION_DECIDED", "Proposal", proposal.id, {
        "decision": decision, "reason": reason, "mandate_id": mandate.id, "agent_id": proposal.agent_id,
        "requested_by": proposal.agent_name or "PACT reference shopping agent",
        "total_amount": f"{proposal.total_amount:.2f}", "currency": proposal.currency,
        "authorization_mode": mandate.authorization_mode,
        "max_auto_approve_amount": f"{q(mandate.max_auto_approve_amount):.2f}" if mandate.max_auto_approve_amount is not None else None,
        "fingerprint": proposal.proposal_fingerprint,
        "budget_reservation": reservation_ref(proposal.id) if decision == AUTO_APPROVE else None,
        "remaining_budget_before": f"{remaining:.2f}",
        "payment_status": "NOT_STARTED",
    })
    return proposal, policy


@router.post("/generate", response_model=ProposalGenerationResponse, status_code=status.HTTP_201_CREATED,
             summary="AI recommends a product; the deterministic policy engine decides")
async def generate_proposal(request: ShoppingPromptRequest, db: Session = Depends(get_db)):
    mandate = db.query(Mandate).filter(Mandate.id == request.mandate_id).first()
    if not mandate:
        raise _fail(404, "NOT_FOUND", f"Mandate '{request.mandate_id}' was not found.")

    if request.source == "channel3":
        try:
            _, found = await run_in_threadpool(search_and_import, db, request.prompt, 10)
        except ConnectorError as exc:
            raise _fail(getattr(exc, "status", None) or 502, "CHANNEL3_UNAVAILABLE", f"Live retailer search failed: {exc}")
        products = ([p for p in found if p.in_stock] or found)[:15]
        if not products:
            raise _fail(404, "NO_RESULTS", "Channel3 found no retailer offers in USD for that request.")
    else:
        products = db.query(Product).filter(Product.source == "demo-store").order_by(Product.id).all()
    if not products:
        raise _fail(400, "EMPTY_CATALOG", "Catalog has no products available.")

    rec = await generate_shopping_recommendation(request.prompt, mandate, products)

    proposal, policy = _create_and_evaluate(
        db, mandate, rec.product, rec.quantity,
        prompt=request.prompt.strip(),
        reasoning=rec.ai_reasoning,
        provider=rec.provider,
        model=rec.model,
        fallback_reason=rec.fallback_reason,
        catalog=products,
        ai_audit={
            "provider": rec.provider,
            "model": rec.model,
            "fallback_reason": rec.fallback_reason,
            "product_id": rec.product.id,
            "quantity": rec.quantity,
            "ignored_ai_fields": rec.ignored_fields,
            "prompt": request.prompt.strip()[:300],
        },
    )

    engine = {"gemini": f"Google Gemini {rec.model}"}.get(
        rec.provider, "heuristic fallback (not AI)"
    )
    message = (
        f"Recommended by {engine}. Policy engine PASSED all {len(policy.checks)} rules — awaiting your explicit approval."
        if policy.passed
        else f"Recommended by {engine}. Policy engine BLOCKED this purchase: {' '.join(policy.violations)}"
    )
    return ProposalGenerationResponse(
        proposal=ProposalOut.model_validate(proposal),
        policy=policy,
        ai=AIProvenance(provider=rec.provider, model=rec.model, fallback_reason=rec.fallback_reason,
                        ignored_fields=rec.ignored_fields),
        message=message,
    )


@router.post("/propose", response_model=ProposalGenerationResponse, status_code=201,
             summary="Evaluate a user-selected catalog item (no AI); same policy path")
def propose_product(request: ProposeRequest, db: Session = Depends(get_db)):
    mandate = db.query(Mandate).filter(Mandate.id == request.mandate_id).first()
    if not mandate:
        raise _fail(404, "NOT_FOUND", f"Mandate '{request.mandate_id}' was not found.")
    product = db.query(Product).filter(Product.id == request.product_id).first()
    if not product:
        raise _fail(404, "NOT_FOUND", f"Product {request.product_id} is not in the catalog.")
    source = None
    if request.source_proposal_id:
        source = db.query(Proposal).filter(Proposal.id == request.source_proposal_id).first()

    proposal, policy = _create_and_evaluate(
        db, mandate, product, request.quantity,
        prompt=source.user_prompt if source else None,
        reasoning="Selected by the user from the alternatives PACT listed.",
        provider="user-selected", model=None, fallback_reason=None,
        catalog=db.query(Product).order_by(Product.id).all(),
        origin_event="PROPOSAL_CREATED_BY_USER",
        ai_audit={"product_id": product.id, "quantity": request.quantity,
                  "source_proposal_id": request.source_proposal_id},
    )
    return ProposalGenerationResponse(
        proposal=ProposalOut.model_validate(proposal),
        policy=policy,
        ai=AIProvenance(provider="user-selected", model=None, fallback_reason=None),
        message=("Policy engine PASSED. Awaiting your explicit approval." if policy.passed
                 else "Policy engine BLOCKED this purchase: " + " ".join(policy.violations)),
    )


@router.get("", response_model=List[ProposalOut], summary="List proposals (most recent first)")
def list_proposals(
    mandate_id: Optional[str] = Query(None),
    status_filter: Optional[ProposalStatus] = Query(None, alias="status"),
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(Proposal)
    if mandate_id:
        query = query.filter(Proposal.mandate_id == mandate_id)
    if status_filter:
        query = query.filter(Proposal.status == status_filter)
    return query.order_by(Proposal.created_at.desc()).limit(limit).all()


@router.get("/{proposal_id}", response_model=ProposalOut)
def get_proposal(proposal_id: str, db: Session = Depends(get_db)):
    proposal = db.query(Proposal).filter(Proposal.id == proposal_id).first()
    if not proposal:
        raise _fail(404, "NOT_FOUND", "Proposal not found.")
    return proposal


def _load(db: Session, proposal_id: str):
    proposal = db.query(Proposal).filter(Proposal.id == proposal_id).first()
    if not proposal:
        raise _fail(404, "NOT_FOUND", "Proposal not found.")
    mandate = db.query(Mandate).filter(Mandate.id == proposal.mandate_id).first()
    if not mandate:
        raise _fail(409, "MANDATE_MISSING", "The mandate for this proposal no longer exists.")
    product = db.query(Product).filter(Product.id == proposal.product_id).first()
    return proposal, mandate, product


@router.post("/{proposal_id}/approve", response_model=ProposalOut,
             summary="Explicit human approval, bound to the exact fingerprint the user reviewed")
def approve_proposal(proposal_id: str, body: ProposalApproval, db: Session = Depends(get_db)):
    proposal, mandate, product = _load(db, proposal_id)

    if proposal.status != ProposalStatus.AWAITING_HUMAN_APPROVAL:
        raise _fail(409, "INVALID_STATE",
                    f"Only proposals awaiting approval can be approved; status is {proposal.status.value}.")

    if body.expected_fingerprint != proposal.proposal_fingerprint:
        log_audit_event(db, "APPROVAL_FINGERPRINT_MISMATCH", "Proposal", proposal.id, {
            "submitted_fingerprint": body.expected_fingerprint,
            "proposal_fingerprint": proposal.proposal_fingerprint,
        })
        raise _fail(409, "FINGERPRINT_MISMATCH",
                    "The approval does not match the proposal you are approving. Reload and review it again.")

    try:
        reverify_live_offer(db, proposal, product, "human approval")
    except ConnectorError as exc:
        raise _fail(503, "OFFER_UNVERIFIED", f"PACT could not re-check this retailer offer before approval: {exc} "
                    "Nothing was approved. Try again in a moment.")

    # Reserve budget atomically: concurrent approvals and auto-authorizations on this mandate wait here.
    lock_mandate_budget(db, mandate)
    db.refresh(proposal)
    if proposal.status != ProposalStatus.AWAITING_HUMAN_APPROVAL:
        raise _fail(409, "INVALID_STATE", f"Only proposals awaiting approval can be approved; status is {proposal.status.value}.")

    integrity = verify_authorization(db, proposal, mandate, product, require_approval=False)
    if not integrity.ok:
        raise _fail(409, "APPROVAL_INVALIDATED", expire_approval(db, proposal, "human approval", integrity),
                    proposal_status=ProposalStatus.APPROVAL_EXPIRED.value)

    proposal.status = ProposalStatus.HUMAN_APPROVED
    proposal.authorized_by = "owner"
    proposal.budget_reserved_at = utc_now()
    proposal.status_reason = None
    proposal.approval_fingerprint = integrity.current_fingerprint
    proposal.approval_snapshot = canonical_snapshot(proposal, mandate)
    proposal.approved_at = utc_now()
    db.commit()
    db.refresh(proposal)

    log_audit_event(db, "PROPOSAL_HUMAN_APPROVED", "Proposal", proposal.id, {
        "product_name": proposal.product_name,
        "merchant": proposal.merchant,
        "quantity": proposal.quantity,
        "total_amount": f"{proposal.total_amount:.2f}",
        "currency": proposal.currency,
        "approval_fingerprint": proposal.approval_fingerprint,
        "rules_revalidated": len(integrity.policy.checks),
        "budget_reservation": reservation_ref(proposal.id),
    })
    return proposal


@router.post("/{proposal_id}/reject", response_model=ProposalOut, summary="Explicit human rejection")
def reject_proposal(proposal_id: str, db: Session = Depends(get_db)):
    proposal, _, _ = _load(db, proposal_id)
    if proposal.status not in REJECTABLE_STATUSES:
        raise _fail(409, "INVALID_STATE", f"Cannot reject a proposal in status {proposal.status.value}.")
    previous = proposal.status.value
    proposal.status = ProposalStatus.HUMAN_REJECTED
    proposal.status_reason = "Rejected by the user."
    db.commit()
    db.refresh(proposal)
    log_audit_event(db, "PROPOSAL_HUMAN_REJECTED", "Proposal", proposal.id,
                    {"previous_status": previous, "total_amount": f"{proposal.total_amount:.2f}"})
    return proposal


@router.post("/{proposal_id}/re-evaluate", response_model=ProposalGenerationResponse, status_code=201,
             summary="Create a fresh proposal from current catalog + mandate after an approval was invalidated")
def re_evaluate_proposal(proposal_id: str, db: Session = Depends(get_db)):
    old, mandate, product = _load(db, proposal_id)
    if old.status not in (ProposalStatus.APPROVAL_EXPIRED, ProposalStatus.PAYPAL_CANCELLED):
        raise _fail(409, "INVALID_STATE", f"Re-evaluation is only for expired or cancelled proposals; status is {old.status.value}.")
    if product is None:
        raise _fail(409, "PRODUCT_MISSING", "The product no longer exists in the catalog.")

    proposal, policy = _create_and_evaluate(
        db, mandate, product, old.quantity,
        prompt=old.user_prompt, reasoning=old.ai_reasoning,
        provider="re-evaluation", model=None,
        fallback_reason=None, supersedes_id=old.id,
        agent_id=old.agent_id, agent_name=old.agent_name,
    )
    if old.status == ProposalStatus.PAYPAL_CANCELLED:
        old.status = ProposalStatus.APPROVAL_EXPIRED
    old.status_reason = (old.status_reason or "") + f" Superseded by proposal {proposal.id}."
    db.commit()
    log_audit_event(db, "PROPOSAL_RE_EVALUATED", "Proposal", old.id, {"new_proposal_id": proposal.id, "passed": policy.passed})

    return ProposalGenerationResponse(
        proposal=ProposalOut.model_validate(proposal),
        policy=policy,
        ai=AIProvenance(provider="re-evaluation", model=None, fallback_reason=None),
        message=("Re-evaluated against the current mandate and catalog: PASSED. Awaiting your explicit approval."
                 if policy.passed else "Re-evaluated: BLOCKED. " + " ".join(policy.violations)),
    )


@router.get("/{proposal_id}/receipt", response_model=AuthorizationReceipt,
            summary="Authorization Receipt: why this purchase was permitted or blocked")
def get_receipt(proposal_id: str, db: Session = Depends(get_db)):
    proposal, mandate, product = _load(db, proposal_id)

    snapshot = canonical_snapshot(proposal, mandate)
    current = fingerprint_of(snapshot)
    bound = proposal.approval_fingerprint or proposal.proposal_fingerprint
    changes: List[str] = []
    terminal = proposal.status in (ProposalStatus.CAPTURED, ProposalStatus.POLICY_REJECTED,
                                   ProposalStatus.HUMAN_REJECTED, ProposalStatus.APPROVAL_EXPIRED,
                                   ProposalStatus.PAYMENT_FAILED)
    if bound and current != bound:
        changes = describe_changes(proposal.approval_snapshot, snapshot)
    if not terminal:
        changes += catalog_drift(proposal, product)

    timeline = (
        db.query(AuditLog)
        .filter(AuditLog.entity_type == "Proposal", AuditLog.entity_id == proposal.id)
        .order_by(AuditLog.timestamp.asc(), AuditLog.id.asc())
        .all()
    )
    decision_checks = [PolicyCheck(**c) for c in (proposal.policy_checks or [])]
    reval = [PolicyCheck(**c) for c in proposal.revalidation_checks] if proposal.revalidation_checks else None

    spent, committed_other, available = budget_breakdown(db, mandate, exclude_proposal_id=proposal.id)
    counted = proposal.status in COMMITTED_STATUSES or proposal.status in SPENT_STATUSES
    this_amount = q(proposal.total_amount)
    budget = ReceiptBudget(
        max_budget=q(mandate.max_budget), spent=spent, committed_other=committed_other,
        available=available, this_purchase=this_amount,
        remaining_after=available - this_amount, counted=counted,
    )

    return AuthorizationReceipt(
        proposal=ProposalOut.model_validate(proposal),
        product=ProductOut.model_validate(product) if product else None,
        budget=budget,
        mandate=ReceiptMandate(
            id=mandate.id, name=mandate.name, is_active=mandate.is_active,
            status=mandate_status(mandate), expires_at=as_utc(mandate.expires_at),
            max_budget=q(mandate.max_budget), currency=mandate.currency or "USD",
            allowed_merchants=mandate.allowed_merchants or [],
            allowed_categories=mandate.allowed_categories or [],
            restrictions=mandate.restrictions or {},
        ),
        decision="BLOCKED" if proposal.status == ProposalStatus.POLICY_REJECTED else "AUTHORIZED",
        decision_checks=decision_checks,
        revalidation_checks=reval,
        revalidated_at=proposal.revalidated_at,
        integrity=ReceiptIntegrity(
            proposal_fingerprint=proposal.proposal_fingerprint,
            approval_fingerprint=proposal.approval_fingerprint,
            current_fingerprint=current,
            intact=not changes,
            changes=changes,
        ),
        timeline=[AuditLogOut.model_validate(t) for t in timeline],
    )


__all__ = ["router", "fmt"]
