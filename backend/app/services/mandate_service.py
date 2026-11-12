"""Service layer for mandate budget accounting and serialization."""

from decimal import Decimal
from typing import Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import COMMITTED_STATUSES, SPENT_STATUSES, Mandate, Proposal, as_utc, utc_now
from app.money import q
from app.schemas import MandateOut


def _sum(db: Session, mandate_id: str, statuses, exclude_proposal_id: Optional[str]) -> Decimal:
    query = db.query(func.coalesce(func.sum(Proposal.total_amount), 0)).filter(
        Proposal.mandate_id == mandate_id,
        Proposal.status.in_(statuses),
    )
    if exclude_proposal_id:
        query = query.filter(Proposal.id != exclude_proposal_id)
    return q(query.scalar() or 0)


def budget_breakdown(
    db: Session, mandate: Mandate, exclude_proposal_id: Optional[str] = None
) -> Tuple[Decimal, Decimal, Decimal]:
    """Return (spent, committed, remaining).

    spent:     verified CAPTURED payments only.
    committed: human-approved proposals that are not yet captured.
    remaining: max_budget - spent - committed (never negative).

    exclude_proposal_id removes one proposal's own claim, so revalidating an
    already-approved proposal does not count its amount twice.
    """
    spent = _sum(db, mandate.id, SPENT_STATUSES, exclude_proposal_id)
    committed = _sum(db, mandate.id, COMMITTED_STATUSES, exclude_proposal_id)
    remaining = max(Decimal("0.00"), q(mandate.max_budget) - spent - committed)
    return spent, committed, remaining


def mandate_status(mandate: Mandate) -> str:
    if mandate.revoked_at is not None:
        return "revoked"
    if mandate.expires_at is not None and as_utc(mandate.expires_at) <= utc_now():
        return "expired"
    return "active" if mandate.is_active else "paused"


def build_mandate_out(db: Session, mandate: Mandate) -> MandateOut:
    spent, committed, remaining = budget_breakdown(db, mandate)
    return MandateOut(
        id=mandate.id,
        name=mandate.name,
        max_budget=q(mandate.max_budget),
        currency=mandate.currency or "USD",
        allowed_merchants=mandate.allowed_merchants or [],
        allowed_categories=mandate.allowed_categories or [],
        restrictions=mandate.restrictions or {},
        authorization_mode=mandate.authorization_mode or "approval_required",
        max_auto_approve_amount=q(mandate.max_auto_approve_amount) if mandate.max_auto_approve_amount is not None else None,
        is_active=mandate.is_active,
        expires_at=as_utc(mandate.expires_at),
        revoked_at=as_utc(mandate.revoked_at),
        status=mandate_status(mandate),
        created_at=mandate.created_at,
        updated_at=mandate.updated_at,
        spent_budget=spent,
        committed_budget=committed,
        remaining_budget=remaining,
    )
