"""Catalog products router (demo merchant feed)."""

from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Product, Proposal
from app.money import q
from app.schemas import ProductOut
from app.services.audit import log_audit_event
from app.services.authorization import OPEN_STATUSES, recheck_open_proposals

router = APIRouter(prefix="/products", tags=["Products"])


class ProductUpdate(BaseModel):
    """A merchant-side change to a catalog item."""

    price: Optional[Decimal] = Field(default=None, gt=0, le=Decimal("100000"), decimal_places=2)
    in_stock: Optional[bool] = None


class ProductUpdateResult(BaseModel):
    product: ProductOut
    approvals_invalidated: int = Field(description="Open proposals whose approval no longer matches the catalog")


@router.get("", response_model=List[ProductOut])
def list_products(
    category: Optional[str] = Query(None),
    merchant: Optional[str] = Query(None),
    in_stock: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
) -> List[ProductOut]:
    query = db.query(Product)
    if category:
        query = query.filter(Product.category.ilike(category.strip()))
    if merchant:
        query = query.filter(Product.merchant.ilike(merchant.strip()))
    if in_stock is not None:
        query = query.filter(Product.in_stock == in_stock)
    return query.order_by(Product.id.asc()).all()


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)) -> ProductOut:
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"Product {product_id} not found."})
    return product


@router.put("/{product_id}", response_model=ProductUpdateResult,
            summary="Change a catalog price or stock flag (simulates a merchant feed update)")
def update_product(product_id: int, payload: ProductUpdate, db: Session = Depends(get_db)) -> ProductUpdateResult:
    """Catalog changes never silently flow into approved purchases.

    Every open proposal for this product is re-verified; any whose approved price or
    policy result no longer holds becomes APPROVAL_EXPIRED.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"Product {product_id} not found."})

    if product.source != "demo-store":
        raise HTTPException(status_code=409, detail={
            "code": "LIVE_OFFER", "message": "This price comes from a live retailer and is re-checked with Channel3 before "
                                             "approval, order and capture. Only Demo Store prices can be changed here."})

    before = {"price": f"{q(product.price):.2f}", "in_stock": product.in_stock}
    if payload.price is not None:
        product.price = q(payload.price)
    if payload.in_stock is not None:
        product.in_stock = payload.in_stock
    db.commit()
    db.refresh(product)
    after = {"price": f"{q(product.price):.2f}", "in_stock": product.in_stock}

    invalidated = 0
    if after != before:
        open_proposals = (
            db.query(Proposal)
            .filter(Proposal.product_id == product.id, Proposal.status.in_(OPEN_STATUSES))
            .all()
        )
        invalidated = recheck_open_proposals(db, open_proposals, "catalog change")
        log_audit_event(db, "CATALOG_PRODUCT_CHANGED", "Product", str(product.id), {
            "product_name": product.name, "merchant": product.merchant,
            "before": before, "after": after, "approvals_invalidated": invalidated,
        })
    return ProductUpdateResult(product=ProductOut.model_validate(product), approvals_invalidated=invalidated)
