"""Agent Gateway: the API any AI agent uses to ask PACT for spending authority.

    AI agent (Claude, ChatGPT, custom) --key--> /api/agent/v1 --> policy engine --> human approval --> PayPal

What an agent CAN do:  read its own authority, search the catalog, dry-run a purchase, request a
                       purchase (which then waits for a human), and read the status of its requests.
What an agent CANNOT do, by construction: approve a proposal, create or capture a PayPal payment,
                       change a mandate, or see another agent's requests. No such route exists here.

Prices, merchants and categories always come from the catalog, never from the agent.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import AgentClient, Mandate, Product, Proposal, ProposalStatus, as_utc
from app.money import q
from app.policy import PolicyEngine
from app.routers.proposals import _create_and_evaluate
from app.schemas import PolicyCheck
from app.services.agent_keys import current_agent
from app.services.audit import log_audit_event
from app.services.mandate_service import budget_breakdown, mandate_status
from app.connectors import ConnectorError, get_connector
from app.services.connector_sync import search_and_import

logger = logging.getLogger("pact.gateway")

router = APIRouter(prefix="/agent/v1", tags=["Agent Gateway (for AI agents)"])

NEXT_STEP = {
    ProposalStatus.AWAITING_HUMAN_APPROVAL: "Waiting for the human to approve this exact purchase in the PACT Control Center.",
    ProposalStatus.HUMAN_APPROVED: "Approved by the human. The human now completes payment with PayPal.",
    ProposalStatus.AUTO_AUTHORIZED: ("Authorized by PACT under the owner's auto-authorization limit. This is NOT payment: "
                                     "the owner completes PayPal Checkout, and PACT captures only after PayPal confirms."),
    ProposalStatus.AWAITING_PAYPAL_BUYER_APPROVAL: "The human is completing the PayPal checkout.",
    ProposalStatus.PAYPAL_BUYER_APPROVED: "PayPal buyer approved. PACT will re-verify and capture.",
    ProposalStatus.CAPTURE_PENDING: "PACT is confirming the capture with PayPal.",
    ProposalStatus.CAPTURED: "Paid. PayPal confirmed the capture.",
    ProposalStatus.POLICY_REJECTED: "Blocked by the mandate. Do not retry the same purchase; choose something within policy.",
    ProposalStatus.HUMAN_REJECTED: "The human declined this purchase.",
    ProposalStatus.PAYPAL_CANCELLED: "The PayPal checkout was cancelled.",
    ProposalStatus.PAYMENT_FAILED: "Payment failed; no money moved.",
    ProposalStatus.APPROVAL_EXPIRED: "The approval was voided because the price or the mandate changed. Request again.",
}


def _fail(code: int, err: str, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail={"code": err, "message": message})


def _mandate_for(db: Session, agent: AgentClient, mandate_id: str) -> Mandate:
    if mandate_id not in (agent.mandate_ids or []):
        log_audit_event(db, "AGENT_MANDATE_DENIED", "Agent", agent.id, {"agent_name": agent.name, "mandate_id": mandate_id})
        raise _fail(403, "MANDATE_NOT_GRANTED", "This agent has not been granted that mandate.")
    mandate = db.query(Mandate).filter(Mandate.id == mandate_id).first()
    if mandate is None:
        raise _fail(404, "NOT_FOUND", "Mandate not found.")
    return mandate


def _product(db: Session, product_id: int) -> Product:
    product = db.query(Product).filter(Product.id == product_id).first()
    if product is None:
        raise _fail(404, "NOT_FOUND", f"Product {product_id} is not in the catalog.")
    return product


# --------------------------------------------------------------------------- authority

class Authority(BaseModel):
    mandate_id: str
    name: str
    status: str
    currency: str
    max_budget: Decimal
    spent: Decimal
    committed: Decimal
    remaining: Decimal
    max_price_per_item: Optional[Decimal]
    max_quantity: Optional[int]
    allowed_categories: List[str]
    allowed_merchants: List[str]
    prohibited_keywords: List[str]
    expires_at: Optional[datetime]
    human_approval_required: bool = True


def _authority(db: Session, m: Mandate) -> Authority:
    spent, committed, remaining = budget_breakdown(db, m)
    r = m.restrictions or {}
    return Authority(
        mandate_id=m.id, name=m.name, status=mandate_status(m), currency=m.currency or "USD",
        max_budget=q(m.max_budget), spent=spent, committed=committed, remaining=remaining,
        max_price_per_item=q(r["max_price_per_item"]) if r.get("max_price_per_item") is not None else None,
        max_quantity=r.get("max_quantity"),
        allowed_categories=m.allowed_categories or [], allowed_merchants=m.allowed_merchants or [],
        prohibited_keywords=r.get("prohibited_keywords") or [], expires_at=as_utc(m.expires_at),
    )


class WhoAmI(BaseModel):
    agent_id: str
    agent_name: str
    mandates: List[Authority]
    can: List[str]
    cannot: List[str]


@router.get("/whoami", response_model=WhoAmI, summary="The calling agent and the authority it holds")
def whoami(agent: AgentClient = Depends(current_agent), db: Session = Depends(get_db)):
    mandates = db.query(Mandate).filter(Mandate.id.in_(agent.mandate_ids or [])).all()
    return WhoAmI(
        agent_id=agent.id, agent_name=agent.name, mandates=[_authority(db, m) for m in mandates],
        can=["search the catalog", "check spending authority", "dry-run a purchase",
             "request a purchase for human approval", "read the status of its own requests"],
        cannot=["approve a purchase", "create or capture a PayPal payment", "change a mandate",
                "see other agents' requests"],
    )


@router.get("/mandates/{mandate_id}/authority", response_model=Authority, summary="Remaining budget and limits")
def authority(mandate_id: str, agent: AgentClient = Depends(current_agent), db: Session = Depends(get_db)):
    return _authority(db, _mandate_for(db, agent, mandate_id))


# --------------------------------------------------------------------------- catalog

class CatalogItem(BaseModel):
    product_id: int
    name: str
    merchant: str
    category: str
    price: Decimal
    currency: str
    in_stock: bool
    description: str
    source: str = Field(description="'pact-catalog', 'channel3' (live retailer offer) or another connector")
    brand: Optional[str] = None


@router.get("/catalog", response_model=List[CatalogItem], summary="Search the merchant catalog")
def catalog(q_: Optional[str] = Query(default=None, alias="q", max_length=200),
            category: Optional[str] = Query(default=None, max_length=100),
            limit: int = Query(default=10, ge=1, le=50),
            live: bool = Query(default=True, description="Also search live retailers through Channel3 (when configured)"),
            response: Response = None,
            agent: AgentClient = Depends(current_agent), db: Session = Depends(get_db)):
    live_items: List[Product] = []
    c3 = get_connector("channel3")
    if q_ and live and c3 is not None and c3.configured:
        try:
            _, live_items = search_and_import(db, q_, limit=min(limit, 10))
            log_audit_event(db, "AGENT_CATALOG_SEARCHED", "Agent", agent.id,
                            {"agent_name": agent.name, "query": q_[:200], "live_results": len(live_items)})
        except ConnectorError as exc:
            logger.warning("Live retailer search unavailable for agent search: %s", exc)
            if response is not None:
                response.headers["X-PACT-Live-Search"] = "unavailable"
    if category:
        live_items = [p for p in live_items if p.category.lower() == category.strip().lower()]
    products = db.query(Product).filter(Product.source != "channel3").order_by(Product.id).all()
    if category:
        products = [p for p in products if p.category.lower() == category.strip().lower()]
    if q_:
        words = [w for w in q_.lower().split() if len(w) > 1]
        scored = []
        for p in products:
            text = f"{p.name} {p.description} {p.category} {p.merchant}".lower()
            score = sum(1 for w in words if w in text)
            if score:
                scored.append((score, p))
        products = [p for _, p in sorted(scored, key=lambda t: (-t[0], t[1].id))]
    return [_item(p) for p in (live_items + products)[:limit]]


# --------------------------------------------------------------------------- purchases

class PurchaseIntent(BaseModel):
    mandate_id: str
    product_id: int
    quantity: int = Field(default=1, ge=1, le=20)


class PurchaseRequest(PurchaseIntent):
    reason: str = Field(..., min_length=3, max_length=500, description="Why the agent wants this; shown to the human")
    request_id: Optional[str] = Field(default=None, max_length=100,
                                      description="Agent's idempotency key: retrying with the same id returns the same request")


class Decision(BaseModel):
    allowed: bool
    product: CatalogItem
    quantity: int
    total: Decimal
    currency: str
    remaining_budget: Decimal
    checks: List[PolicyCheck]
    violations: List[str]
    summary: str


@router.post("/purchases/evaluate", response_model=Decision,
             summary="Dry run: would this purchase be allowed? Nothing is created")
def evaluate(body: PurchaseIntent, agent: AgentClient = Depends(current_agent), db: Session = Depends(get_db)):
    mandate = _mandate_for(db, agent, body.mandate_id)
    product = _product(db, body.product_id)
    cur = get_settings().currency
    total = q(q(product.price) * body.quantity)
    _, _, remaining = budget_breakdown(db, mandate)
    result = PolicyEngine.evaluate(
        mandate=mandate,
        proposal={"merchant": product.merchant, "category": product.category, "product_name": product.name,
                  "price": q(product.price), "quantity": body.quantity, "total_amount": total, "currency": cur},
        product=product, remaining_budget=remaining, expected_currency=cur,
    )
    log_audit_event(db, "AGENT_AUTHORITY_CHECKED", "Agent", agent.id, {
        "agent_name": agent.name, "mandate_id": mandate.id, "product_id": product.id, "quantity": body.quantity,
        "total_amount": f"{total:.2f}", "allowed": result.passed, "violations": result.violations,
    })
    return Decision(
        allowed=result.passed, product=_item(product), quantity=body.quantity, total=total, currency=cur,
        remaining_budget=remaining, checks=result.checks, violations=result.violations,
        summary=("Within policy. A purchase request would still need explicit human approval."
                 if result.passed else "Not allowed: " + " ".join(result.violations)),
    )


def _item(p: Product) -> CatalogItem:
    # The retailer's buy link is deliberately not given to agents: purchases go through PACT only.
    return CatalogItem(product_id=p.id, name=p.name, merchant=p.merchant, category=p.category, price=q(p.price),
                       currency=get_settings().currency, in_stock=p.in_stock, description=p.description[:500],
                       source=p.source, brand=p.brand)


class PurchaseStatus(BaseModel):
    purchase_id: str
    status: ProposalStatus
    decision: str
    next_step: str
    product_name: str
    merchant: str
    quantity: int
    total: Decimal
    currency: str
    violations: List[str]
    approval_url: str
    paypal_capture_id: Optional[str]
    paypal_capture_status: Optional[str]
    authorization_decision: Optional[str] = Field(default=None, description="AUTO_APPROVE, REQUIRES_APPROVAL or BLOCKED")
    decision_reason: Optional[str] = None
    payment_status: str = Field(description="NOT_STARTED, IN_CHECKOUT, PENDING, COMPLETED, FAILED or CANCELLED")
    created_at: datetime
    updated_at: datetime


def _status(p: Proposal) -> PurchaseStatus:
    decision = {
        ProposalStatus.POLICY_REJECTED: "BLOCKED",
        ProposalStatus.CAPTURED: "PAID",
        ProposalStatus.HUMAN_REJECTED: "DECLINED",
        ProposalStatus.APPROVAL_EXPIRED: "VOIDED",
        ProposalStatus.PAYPAL_CANCELLED: "CANCELLED",
        ProposalStatus.PAYMENT_FAILED: "FAILED",
        ProposalStatus.AUTO_AUTHORIZED: "AUTHORIZED",
        ProposalStatus.HUMAN_APPROVED: "AUTHORIZED",
        ProposalStatus.AWAITING_PAYPAL_BUYER_APPROVAL: "AUTHORIZED",
        ProposalStatus.PAYPAL_BUYER_APPROVED: "AUTHORIZED",
        ProposalStatus.CAPTURE_PENDING: "AUTHORIZED",
    }.get(p.status, "PENDING_HUMAN")
    payment = {
        ProposalStatus.AWAITING_PAYPAL_BUYER_APPROVAL: "IN_CHECKOUT", ProposalStatus.PAYPAL_BUYER_APPROVED: "IN_CHECKOUT",
        ProposalStatus.CAPTURE_PENDING: "PENDING", ProposalStatus.CAPTURED: "COMPLETED",
        ProposalStatus.PAYMENT_FAILED: "FAILED", ProposalStatus.PAYPAL_CANCELLED: "CANCELLED",
    }.get(p.status, "NOT_STARTED")
    return PurchaseStatus(
        purchase_id=p.id, status=p.status, decision=decision, next_step=NEXT_STEP.get(p.status, ""),
        product_name=p.product_name, merchant=p.merchant, quantity=p.quantity, total=q(p.total_amount),
        currency=p.currency, violations=[c["detail"] for c in (p.policy_checks or []) if not c.get("passed")],
        approval_url=f"{get_settings().app_base_url.rstrip('/')}/proposals/{p.id}",
        paypal_capture_id=p.paypal_capture_id if p.status == ProposalStatus.CAPTURED else None,
        paypal_capture_status=p.paypal_capture_status if p.status == ProposalStatus.CAPTURED else None,
        authorization_decision=p.authorization_decision, decision_reason=p.decision_reason, payment_status=payment,
        created_at=as_utc(p.created_at), updated_at=as_utc(p.updated_at),
    )


@router.post("/purchases", response_model=PurchaseStatus, status_code=201,
             summary="Request a purchase. PACT decides (auto-authorize, ask the owner, or block); the agent never pays")
def request_purchase(body: PurchaseRequest, agent: AgentClient = Depends(current_agent), db: Session = Depends(get_db)):
    mandate = _mandate_for(db, agent, body.mandate_id)
    if body.request_id:
        prior = db.query(Proposal).filter(Proposal.agent_id == agent.id, Proposal.agent_request_id == body.request_id).first()
        if prior is not None:
            return _status(prior)
    product = _product(db, body.product_id)
    proposal, _ = _create_and_evaluate(
        db, mandate, product, body.quantity,
        prompt=None, reasoning=body.reason.strip(),
        provider="external-agent", model=None, fallback_reason=None,
        catalog=db.query(Product).order_by(Product.id).all(),
        origin_event="AGENT_PURCHASE_REQUESTED",
        ai_audit={"agent_id": agent.id, "agent_name": agent.name, "product_id": product.id,
                  "quantity": body.quantity, "reason": body.reason.strip()[:300], "request_id": body.request_id},
        agent_id=agent.id, agent_name=agent.name, agent_request_id=body.request_id,
    )
    return _status(proposal)


@router.get("/purchases", response_model=List[PurchaseStatus], summary="This agent's purchase requests")
def list_purchases(limit: int = Query(default=20, ge=1, le=100),
                   agent: AgentClient = Depends(current_agent), db: Session = Depends(get_db)):
    rows = (db.query(Proposal).filter(Proposal.agent_id == agent.id)
            .order_by(Proposal.created_at.desc()).limit(limit).all())
    return [_status(p) for p in rows]


@router.get("/purchases/{purchase_id}", response_model=PurchaseStatus, summary="Status of one of this agent's requests")
def get_purchase(purchase_id: str, agent: AgentClient = Depends(current_agent), db: Session = Depends(get_db)):
    p = db.query(Proposal).filter(Proposal.id == purchase_id, Proposal.agent_id == agent.id).first()
    if p is None:
        raise _fail(404, "NOT_FOUND", "No purchase request with that id for this agent.")
    return _status(p)
