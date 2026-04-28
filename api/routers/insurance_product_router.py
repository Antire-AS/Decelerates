"""Insurance product catalog endpoints — read-only for v1."""

from typing import List, Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from api.auth import get_current_user
from api.db import User
from api.dependencies import get_db
from api.limiter import limiter
from api.schemas import InsuranceProductOut, ProductCategoryOut
from api.services.insurance_product_service import InsuranceProductService

router = APIRouter(tags=["products"])


def _svc(db: Session = Depends(get_db)) -> InsuranceProductService:
    return InsuranceProductService(db)


@router.get("/products", response_model=List[InsuranceProductOut])
@limiter.limit("60/minute")
async def list_products(
    request: Request,
    category: Optional[str] = None,
    svc: InsuranceProductService = Depends(_svc),
    user: User = Depends(get_current_user),
):
    """List insurance products in the catalog, optionally filtered by category."""
    rows = svc.list_products(category=category)
    return [
        {
            "id": p.id,
            "category": p.category,
            "sub_category": p.sub_category,
            "name": p.name,
            "description": p.description,
            "typical_coverage_limits": p.typical_coverage_limits,
            "sort_order": int(p.sort_order or 0),
        }
        for p in rows
    ]


@router.get("/products/categories", response_model=List[ProductCategoryOut])
@limiter.limit("60/minute")
async def list_product_categories(
    request: Request,
    svc: InsuranceProductService = Depends(_svc),
    user: User = Depends(get_current_user),
):
    """List the catalog categories with product counts."""
    return svc.list_categories()
