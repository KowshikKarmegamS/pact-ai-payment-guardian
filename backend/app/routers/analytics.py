"""Control Center analytics: real PACT purchase data for the AG Studio dashboard.

Every row is a persisted proposal. Nothing is sampled, estimated or generated. Amounts are exact
two-decimal values rendered as JSON numbers for charting; payment logic never reads this endpoint.
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import COMMITTED_STATUSES, Mandate, Proposal, ProposalStatus, as_utc
from app.money import q
from app.services.studio_llm import run_turn

router = APIRouter(prefix="/analytics", tags=["Analytics (Control Center)"])

OUTCOME = {
    ProposalStatus.POLICY_REJECTED: "Blocked by policy",
    ProposalStatus.HUMAN_REJECTED: "Rejected by owner",
    ProposalStatus.APPROVAL_EXPIRED: "Approval voided",
    ProposalStatus.AWAITING_HUMAN_APPROVAL: "Awaiting approval",
    ProposalStatus.HUMAN_APPROVED: "Approved, in checkout",
    ProposalStatus.AUTO_AUTHORIZED: "Approved, in checkout",
    ProposalStatus.AWAITING_PAYPAL_BUYER_APPROVAL: "Approved, in checkout",
    ProposalStatus.PAYPAL_BUYER_APPROVED: "Approved, in checkout",
    ProposalStatus.CAPTURE_PENDING: "Approved, in checkout",
    ProposalStatus.CAPTURED: "Paid",
    ProposalStatus.PAYPAL_CANCELLED: "Checkout cancelled",
    ProposalStatus.PAYMENT_FAILED: "Payment failed",
}

SOURCE = {None: "PACT catalog", "pact-catalog": "PACT catalog", "channel3": "Channel3 (live retailers)",
          "northwind-supply": "Northwind Supply"}


class PurchaseRow(BaseModel):
    purchase_id: str
    day: str
    created_at: str
    product: str
    merchant: str
    category: str
    agent: str
    source: str
    mandate: str
    outcome: str
    status: str
    decided_by_policy: str
    authorization: str
    requested_amount: float
    paid_amount: float
    authorized_amount: float
    blocked_amount: float
    quantity: int
    currency: str
    ai_engine: str


class AnalyticsDataset(BaseModel):
    purchases: List[PurchaseRow]


def _engine(p: Proposal) -> str:
    if p.agent_id:
        return "External agent"
    return {"gemini": "Gemini", "openai": "OpenAI", "heuristic": "Keyword fallback (not AI)",
            "user-selected": "Chosen by owner"}.get(p.ai_provider or "", p.ai_provider or "Unknown")


def purchase_rows(db: Session) -> List[PurchaseRow]:
    mandates: Dict[str, str] = {m.id: m.name for m in db.query(Mandate).all()}
    rows: List[PurchaseRow] = []
    for p in db.query(Proposal).order_by(Proposal.created_at.asc()).all():
        created = as_utc(p.created_at)
        total = float(q(p.total_amount))
        paid = float(q(p.captured_amount)) if p.status == ProposalStatus.CAPTURED and p.captured_amount is not None else 0.0
        blocked = p.status == ProposalStatus.POLICY_REJECTED
        rows.append(PurchaseRow(
            purchase_id=p.id,
            day=created.date().isoformat() if created else "",
            created_at=created.strftime("%Y-%m-%d %H:%M UTC") if created else "",
            product=p.product_name,
            merchant=p.merchant,
            category=p.category,
            agent=p.agent_name or "PACT reference agent",
            source=SOURCE.get(p.offer_source, p.offer_source or "PACT catalog"),
            mandate=mandates.get(p.mandate_id, "Deleted mandate"),
            outcome=OUTCOME.get(p.status, p.status.value),
            status=p.status.value,
            decided_by_policy="Blocked" if blocked else "Passed",
            authorization={"AUTO_APPROVE": "Auto-authorized", "REQUIRES_APPROVAL": "Needed owner approval",
                           "BLOCKED": "Blocked"}.get(p.authorization_decision or "",
                                                     "Blocked" if blocked else "Needed owner approval"),
            requested_amount=total,
            paid_amount=paid,
            authorized_amount=total if p.status in COMMITTED_STATUSES or p.status == ProposalStatus.CAPTURED else 0.0,
            blocked_amount=total if blocked else 0.0,
            quantity=int(p.quantity),
            currency=(p.currency or "USD").upper(),
            ai_engine=_engine(p),
        ))
    return rows


@router.get("/dataset", response_model=AnalyticsDataset,
            summary="Every purchase request with its outcome, for the spending analytics dashboard")
def dataset(db: Session = Depends(get_db)) -> AnalyticsDataset:
    return AnalyticsDataset(purchases=purchase_rows(db))


@router.post("/agent-turn", summary="One LLM turn for AG Studio's Agent Framework (Gemini, server-side key)")
async def agent_turn(request: Dict[str, Any]) -> Dict[str, Any]:
    return await run_turn(request)
