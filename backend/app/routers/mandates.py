"""Spending mandates management router."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Mandate, Proposal, as_utc, utc_now
from app.schemas import MandateCreate, MandateOut, MandateUpdate
from app.services.audit import log_audit_event
from app.services.authorization import OPEN_STATUSES, recheck_open_proposals
from app.services.mandate_service import build_mandate_out

router = APIRouter(prefix="/mandates", tags=["Mandates"])


def _fail(http_status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=http_status, detail={"code": code, "message": message})


def _get(db: Session, mandate_id: str) -> Mandate:
    mandate = db.query(Mandate).filter(Mandate.id == mandate_id).first()
    if not mandate:
        raise _fail(404, "NOT_FOUND", f"Mandate '{mandate_id}' not found.")
    return mandate


def _check_expiry(expires_at) -> None:
    if expires_at is not None and as_utc(expires_at) <= utc_now():
        raise _fail(422, "VALIDATION_ERROR", "expires_at must be in the future.")


def _open_proposals(db: Session, mandate: Mandate) -> List[Proposal]:
    return (
        db.query(Proposal)
        .filter(Proposal.mandate_id == mandate.id, Proposal.status.in_(OPEN_STATUSES))
        .all()
    )


def _jsonable(v):
    if hasattr(v, "quantize"):
        return f"{v:.2f}"
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


@router.post("", response_model=MandateOut, status_code=status.HTTP_201_CREATED)
def create_mandate(payload: MandateCreate, db: Session = Depends(get_db)) -> MandateOut:
    _check_expiry(payload.expires_at)
    mandate = Mandate(
        name=payload.name.strip(),
        max_budget=payload.max_budget,
        currency=get_settings().currency,
        allowed_merchants=payload.allowed_merchants,
        allowed_categories=payload.allowed_categories,
        restrictions=payload.restrictions,
        expires_at=as_utc(payload.expires_at),
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
        "expires_at": _jsonable(as_utc(mandate.expires_at)),
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
    if mandate.revoked_at is not None:
        raise _fail(409, "MANDATE_REVOKED", "This mandate was revoked and can no longer be changed.")

    raw = payload.model_dump(exclude_unset=True)
    # expires_at may be explicitly null (remove the expiry); every other null means "not provided".
    update_data = {k: v for k, v in raw.items() if v is not None or k == "expires_at"}
    if not update_data:
        return build_mandate_out(db, mandate)
    if "expires_at" in update_data:
        _check_expiry(update_data["expires_at"])
        update_data["expires_at"] = as_utc(update_data["expires_at"])

    before = {k: getattr(mandate, k) for k in update_data}
    for field, val in update_data.items():
        setattr(mandate, field, val.strip() if isinstance(val, str) else val)
    db.commit()
    db.refresh(mandate)

    log_audit_event(db, "MANDATE_UPDATED", "Mandate", mandate.id, {
        "name": mandate.name,
        "updated_fields": sorted(update_data.keys()),
        "before": {k: _jsonable(v) for k, v in before.items()},
        "after": {k: _jsonable(getattr(mandate, k)) for k in update_data},
    })

    recheck_open_proposals(db, _open_proposals(db, mandate), "mandate change")
    db.refresh(mandate)
    return build_mandate_out(db, mandate)


@router.post("/{mandate_id}/revoke", response_model=MandateOut, summary="Permanently revoke a mandate")
def revoke_mandate(mandate_id: str, db: Session = Depends(get_db)) -> MandateOut:
    """Revocation is permanent: the mandate can never authorize again and open approvals are invalidated."""
    mandate = _get(db, mandate_id)
    if mandate.revoked_at is None:
        mandate.revoked_at = utc_now()
        mandate.is_active = False
        db.commit()
        db.refresh(mandate)
        invalidated = recheck_open_proposals(db, _open_proposals(db, mandate), "mandate revocation")
        log_audit_event(db, "MANDATE_REVOKED", "Mandate", mandate.id,
                        {"name": mandate.name, "approvals_invalidated": invalidated})
        db.refresh(mandate)
    return build_mandate_out(db, mandate)
