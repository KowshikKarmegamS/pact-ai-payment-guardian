"""Catalog products router."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Product
from app.schemas import ProductOut

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=List[ProductOut])
def list_products(
    category: Optional[str] = Query(None, description="Filter products by category name"),
    merchant: Optional[str] = Query(None, description="Filter products by merchant name"),
    in_stock: Optional[bool] = Query(None, description="Filter products by stock status"),
    db: Session = Depends(get_db),
) -> List[ProductOut]:
    """Retrieve catalog products with optional category, merchant, and stock filters."""
    query = db.query(Product)

    if category:
        query = query.filter(Product.category.ilike(category.strip()))
    if merchant:
        query = query.filter(Product.merchant.ilike(merchant.strip()))
    if in_stock is not None:
        query = query.filter(Product.in_stock == in_stock)

    products = query.order_by(Product.id.asc()).all()
    return products


@router.get("/{product_id}", response_model=ProductOut)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
) -> ProductOut:
    """Retrieve details for a single catalog product by its ID."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found.",
        )
    return product
