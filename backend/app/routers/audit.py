"""Audit trail endpoints for transparency, security inspection, and compliance."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import AuditLog
from app.schemas import AuditLogOut

router = APIRouter(prefix="/audit", tags=["Audit Trail"])


@router.get("", response_model=List[AuditLogOut], summary="List chronological audit logs")
def list_audit_logs(
    entity_type: Optional[str] = Query(None, description="Filter by entity type (Mandate, Proposal)"),
    entity_id: Optional[str] = Query(None, description="Filter by entity ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
    db: Session = Depends(get_db),
):
    """Retrieve chronological audit trail entries (most recent first)."""
    query = db.query(AuditLog)

    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.filter(AuditLog.entity_id == entity_id)
    if event_type:
        query = query.filter(AuditLog.event_type == event_type)

    return query.order_by(AuditLog.timestamp.desc()).limit(limit).all()
