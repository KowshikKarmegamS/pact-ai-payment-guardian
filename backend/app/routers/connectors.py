"""Control Center: merchant connectors that feed offers into PACT's catalog."""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.connectors import BUILTIN_SOURCE, ConnectorError, all_connectors, get_connector
from app.database import get_db
from app.models import AuditLog, Product
from app.services.connector_sync import sync_connector

router = APIRouter(prefix="/connectors", tags=["Merchant connectors"])


class ConnectorOut(BaseModel):
    id: str
    name: str
    platform: str
    description: str
    syncable: bool
    products: int
    in_stock: int
    last_synced_at: Optional[datetime] = None


class SyncOut(BaseModel):
    connector_id: str
    offers: int
    created: int
    updated: int
    unchanged: int
    delisted: int
    skipped: List[str]
    approvals_invalidated: int


def _counts(db: Session, source: str) -> tuple:
    total = db.query(func.count(Product.id)).filter(Product.source == source).scalar() or 0
    stocked = db.query(func.count(Product.id)).filter(Product.source == source, Product.in_stock.is_(True)).scalar() or 0
    return total, stocked


@router.get("", response_model=List[ConnectorOut])
def list_connectors(db: Session = Depends(get_db)) -> List[ConnectorOut]:
    total, stocked = _counts(db, BUILTIN_SOURCE)
    out = [ConnectorOut(
        id=BUILTIN_SOURCE, name="PACT demo catalog", platform="Built-in",
        description="The seeded TechHub and BookWorld catalog.", syncable=False, products=total, in_stock=stocked,
    )]
    for c in all_connectors():
        total, stocked = _counts(db, c.id)
        last = (
            db.query(func.max(AuditLog.timestamp))
            .filter(AuditLog.event_type == "CONNECTOR_SYNCED", AuditLog.entity_id == c.id)
            .scalar()
        )
        out.append(ConnectorOut(id=c.id, name=c.name, platform=c.platform, description=c.description,
                                syncable=True, products=total, in_stock=stocked, last_synced_at=last))
    return out


@router.post("/{connector_id}/sync", response_model=SyncOut)
def sync(connector_id: str, db: Session = Depends(get_db)) -> SyncOut:
    connector = get_connector(connector_id)
    if connector is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"Connector '{connector_id}' not found."})
    try:
        result = sync_connector(db, connector)
    except ConnectorError as exc:
        raise HTTPException(status_code=502, detail={"code": "CONNECTOR_UNAVAILABLE", "message": str(exc)}) from exc
    return SyncOut(**result.__dict__)
