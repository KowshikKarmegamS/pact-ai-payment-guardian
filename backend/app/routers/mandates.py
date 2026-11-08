"""Spending mandates management router."""

from decimal import Decimal
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Mandate
from app.schemas import MandateCreate, MandateOut, MandateUpdate
from app.services.audit import log_audit_event
from app.services.mandate_service import calculate_mandate_budget, build_mandate_out

router = APIRouter(prefix="/mandates", tags=["Mandates"])


@router.post("", response_model=MandateOut, status_code=status.HTTP_201_CREATED)
def create_mandate(
    payload: MandateCreate,
    db: Session = Depends(get_db),
) -> MandateOut:
    """Create a new spending mandate and initialize budget allocation."""
    mandate = Mandate(
        name=payload.name,
        max_budget=payload.max_budget,
        allowed_merchants=payload.allowed_merchants,
        allowed_categories=payload.allowed_categories,
        restrictions=payload.restrictions,
        is_active=True,
    )
    db.add(mandate)
    db.commit()
    db.refresh(mandate)

    # Initial spent budget is 0, remaining is max_budget
    spent_budget = Decimal("0.00")
    remaining_budget = Decimal(str(mandate.max_budget))

    log_audit_event(
        db=db,
        event_type="MANDATE_CREATED",
        entity_type="Mandate",
        entity_id=mandate.id,
        details={
            "name": mandate.name,
            "max_budget": str(mandate.max_budget),
            "allowed_merchants": mandate.allowed_merchants,
            "allowed_categories": mandate.allowed_categories,
            "restrictions": mandate.restrictions,
        },
    )

    return build_mandate_out(mandate, spent_budget, remaining_budget)


@router.get("", response_model=List[MandateOut])
def list_mandates(
    db: Session = Depends(get_db),
) -> List[MandateOut]:
    """Retrieve all spending mandates with computed spending and remaining budgets."""
    mandates = db.query(Mandate).order_by(Mandate.created_at.desc()).all()
    results: List[MandateOut] = []

    for m in mandates:
        spent_budget, remaining_budget = calculate_mandate_budget(db, m)
        results.append(build_mandate_out(m, spent_budget, remaining_budget))

    return results


@router.get("/{mandate_id}", response_model=MandateOut)
def get_mandate(
    mandate_id: str,
    db: Session = Depends(get_db),
) -> MandateOut:
    """Retrieve a single spending mandate with current remaining budget."""
    mandate = db.query(Mandate).filter(Mandate.id == mandate_id).first()
    if not mandate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mandate with ID '{mandate_id}' not found.",
        )

    spent_budget, remaining_budget = calculate_mandate_budget(db, mandate)
    return build_mandate_out(mandate, spent_budget, remaining_budget)


@router.put("/{mandate_id}", response_model=MandateOut)
def update_mandate(
    mandate_id: str,
    payload: MandateUpdate,
    db: Session = Depends(get_db),
) -> MandateOut:
    """Update fields of an existing spending mandate."""
    mandate = db.query(Mandate).filter(Mandate.id == mandate_id).first()
    if not mandate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mandate with ID '{mandate_id}' not found.",
        )

    update_data = payload.model_dump(exclude_unset=True)

    # Validate lists if updated
    if "allowed_merchants" in update_data and update_data["allowed_merchants"] is not None:
        cleaned = [m.strip() for m in update_data["allowed_merchants"] if m.strip()]
        if not cleaned:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="allowed_merchants cannot be empty.",
            )
        update_data["allowed_merchants"] = cleaned

    if "allowed_categories" in update_data and update_data["allowed_categories"] is not None:
        cleaned = [c.strip() for c in update_data["allowed_categories"] if c.strip()]
        if not cleaned:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="allowed_categories cannot be empty.",
            )
        update_data["allowed_categories"] = cleaned

    for field, val in update_data.items():
        setattr(mandate, field, val)

    db.commit()
    db.refresh(mandate)

    spent_budget, remaining_budget = calculate_mandate_budget(db, mandate)

    log_audit_event(
        db=db,
        event_type="MANDATE_UPDATED",
        entity_type="Mandate",
        entity_id=mandate.id,
        details={
            "updated_fields": list(update_data.keys()),
            "max_budget": str(mandate.max_budget),
            "is_active": mandate.is_active,
        },
    )

    return build_mandate_out(mandate, spent_budget, remaining_budget)
