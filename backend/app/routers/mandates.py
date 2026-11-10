"""Spending mandates management router."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import APPROVED_STATUSES, Mandate, Product, Proposal, ProposalStatus
from app.schemas import MandateCreate, MandateOut, MandateUpdate
from app.services.audit import log_audit_event
from app.services.authorization import expire_approval, verify_authorization
from app.services.mandate_service import build_mandate_out

router = APIRouter(prefix="/mandates", tags=["Mandates"])


def _get(db: Session, mandate_id: str) -> Mandate:
    mandate = db.query(Mandate).filter(Mandate.id == mandate_id).first()
    if not mandate:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"Mandate '{mandate_id}' not found."})
    return mandate


@router.post("", response_model=MandateOut, status_code=status.HTTP_201_CREATED)
def create_mandate(payload: MandateCreate, db: Session = Depends(get_db)) -> MandateOut:
    mandate = Mandate(
        name=payload.name.strip(),
        max_budget=payload.max_budget,
        currency=get_settings().currency,
        allowed_merchants=payload.allowed_merchants,
        allowed_categories=payload.allowed_categories,
        restrictions=payload.restrictions,
        is_active=True,
    )
    db.add(mandate)
    db.commit()
    db.refresh(mandate)
    log_audit_event(db, "MANDATE_CREATED", "Mandate", mandate.id, {
        "name": mandate.name,
        "max_budget": f"{mandate.max_budget:.2f}",
        "currency": mandate.currency,
        "allowed_merchants": mandate.allowed_merchants,
        "allowed_categories": mandate.allowed_categories,
        "restrictions": mandate.restrictions,
    })
    return build_mandate_out(db, mandate)


@router.get("", response_model=List[MandateOut])
def list_mandates(db: Session = Depends(get_db)) -> List[MandateOut]:
    mandates = db.query(Mandate).order_by(Mandate.created_at.desc()).all()
    return [build_mandate_out(db, m) for m in mandates]


@router.get("/{mandate_id}", response_model=MandateOut)
def get_mandate(mandate_id: str, db: Session = Depends(get_db)) -> MandateOut:
    return build_mandate_out(db, _get(db, mandate_id))


@router.put("/{mandate_id}", response_model=MandateOut)
def update_mandate(mandate_id: str, payload: MandateUpdate, db: Session = Depends(get_db)) -> MandateOut:
    """Update a mandate. Any in-flight approval that no longer matches is invalidated immediately."""
    mandate = _get(db, mandate_id)
    update_data = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if not update_data:
        return build_mandate_out(db, mandate)

    before = {k: getattr(mandate, k) for k in update_data}
    for field, val in update_data.items():
        setattr(mandate, field, val.strip() if isinstance(val, str) else val)
    db.commit()
    db.refresh(mandate)

    def _jsonable(v):
        return f"{v:.2f}" if hasattr(v, "quantize") else v

    log_audit_event(db, "MANDATE_UPDATED", "Mandate", mandate.id, {
        "updated_fields": sorted(update_data.keys()),
        "before": {k: _jsonable(v) for k, v in before.items()},
        "after": {k: _jsonable(getattr(mandate, k)) for k in update_data},
    })

    # Re-check every approval that is still in force under this mandate.
    in_flight = (
        db.query(Proposal)
        .filter(Proposal.mandate_id == mandate.id, Proposal.status.in_(APPROVED_STATUSES))
        .all()
    )
    for proposal in in_flight:
        product = db.query(Product).filter(Product.id == proposal.product_id).first()
        result = verify_authorization(db, proposal, mandate, product, require_approval=True)
        if not result.ok:
            expire_approval(db, proposal, "mandate change", result)
        else:
            db.commit()

    # Proposals awaiting approval were evaluated under the old mandate: require re-evaluation.
    pending = (
        db.query(Proposal)
        .filter(Proposal.mandate_id == mandate.id, Proposal.status == ProposalStatus.AWAITING_HUMAN_APPROVAL)
        .all()
    )
    for proposal in pending:
        product = db.query(Product).filter(Product.id == proposal.product_id).first()
        result = verify_authorization(db, proposal, mandate, product, require_approval=False)
        if not result.ok:
            expire_approval(db, proposal, "human approval (mandate changed)", result)
        else:
            db.commit()

    db.refresh(mandate)
    return build_mandate_out(db, mandate)
