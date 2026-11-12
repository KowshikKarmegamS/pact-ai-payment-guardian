"""Control Center: merchant connectors that feed offers into PACT's catalog."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.connectors import BUILTIN_SOURCE, ConnectorError, all_connectors, get_connector
from app.database import get_db
from app.models import AuditLog, Product
from app.schemas import ProductOut
from app.services.connector_sync import search_and_import, sync_connector

router = APIRouter(prefix="/connectors", tags=["Merchant connectors"])


class ConnectorOut(BaseModel):
    id: str
    name: str
    platform: str
    description: str
    syncable: bool
    configured: bool = True
    searchable: bool = False
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
                                syncable=True, configured=c.configured, searchable=c.id == "channel3",
                                products=total, in_stock=stocked, last_synced_at=last))
    return out


@router.post("/{connector_id}/sync", response_model=SyncOut)
def sync(connector_id: str, db: Session = Depends(get_db)) -> SyncOut:
    connector = get_connector(connector_id)
    if connector is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"Connector '{connector_id}' not found."})
    if not connector.configured:
        raise HTTPException(status_code=503, detail={"code": "CONNECTOR_NOT_CONFIGURED",
                                                     "message": f"{connector.name} is not configured on this server."})
    try:
        result = sync_connector(db, connector)
    except ConnectorError as exc:
        raise HTTPException(status_code=getattr(exc, "status", None) or 502,
                            detail={"code": "CONNECTOR_UNAVAILABLE", "message": str(exc)}) from exc
    return SyncOut(**result.__dict__)


class SearchIn(BaseModel):
    query: str = Field(..., min_length=2, max_length=300)
    limit: int = Field(default=10, ge=1, le=30)
    max_price: Optional[Decimal] = Field(default=None, gt=0, le=Decimal("100000"))


class SearchOut(BaseModel):
    result: SyncOut
    products: List[ProductOut]


@router.post("/channel3/search", response_model=SearchOut,
             summary="Natural-language search across live retailers (Channel3); offers enter the catalog with PACT IDs")
def channel3_search(body: SearchIn, db: Session = Depends(get_db)) -> SearchOut:
    c3 = get_connector("channel3")
    if c3 is None or not c3.configured:
        raise HTTPException(status_code=503, detail={
            "code": "CONNECTOR_NOT_CONFIGURED",
            "message": "Channel3 is not configured: set CHANNEL3_API_KEY on the server."})
    try:
        result, products = search_and_import(db, body.query, limit=body.limit, max_price=body.max_price)
    except ConnectorError as exc:
        raise HTTPException(status_code=getattr(exc, "status", None) or 502,
                            detail={"code": "CHANNEL3_UNAVAILABLE", "message": str(exc)}) from exc
    return SearchOut(result=SyncOut(**result.__dict__), products=[ProductOut.model_validate(p) for p in products])
