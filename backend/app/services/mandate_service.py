"""Service layer for mandate calculations, budget tracking, and serialization."""

from decimal import Decimal
from typing import Tuple
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models import Mandate, Proposal, ProposalStatus
from app.schemas import MandateOut


def calculate_mandate_budget(db: Session, mandate: Mandate) -> Tuple[Decimal, Decimal]:
    """Calculate the spent and remaining budget for a mandate.

    Approved and captured proposals count towards committed spending.

    Args:
        db: Active database session.
        mandate: Target Mandate instance.

    Returns:
        Tuple of (spent_budget, remaining_budget).
    """
    committed_statuses = [ProposalStatus.APPROVED, ProposalStatus.CAPTURED]

    spent = (
        db.query(func.coalesce(func.sum(Proposal.total_amount), Decimal("0.00")))
        .filter(
            Proposal.mandate_id == mandate.id,
            Proposal.status.in_(committed_statuses),
        )
        .scalar()
    )

    spent_budget = Decimal(str(spent or "0.00"))
    max_budget = Decimal(str(mandate.max_budget))
    remaining_budget = max(Decimal("0.00"), max_budget - spent_budget)

    return spent_budget, remaining_budget


def build_mandate_out(
    mandate: Mandate,
    spent_budget: Decimal,
    remaining_budget: Decimal,
) -> MandateOut:
    """Construct a full MandateOut schema with calculated budget values."""
    return MandateOut(
        id=mandate.id,
        name=mandate.name,
        max_budget=mandate.max_budget,
        allowed_merchants=mandate.allowed_merchants,
        allowed_categories=mandate.allowed_categories,
        restrictions=mandate.restrictions,
        is_active=mandate.is_active,
        created_at=mandate.created_at,
        updated_at=mandate.updated_at,
        spent_budget=spent_budget,
        remaining_budget=remaining_budget,
    )
