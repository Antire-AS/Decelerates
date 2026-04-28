"""Read-side service for the insurance product catalog."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from api.models.insurance_product import InsuranceProduct


class InsuranceProductService:
    """List + filter on the seeded product catalog. Read-only for now;
    admin write endpoints can be added when there's a UI for them."""

    def __init__(self, db: Session):
        self.db = db

    def list_products(
        self,
        category: Optional[str] = None,
        active_only: bool = True,
    ) -> list[InsuranceProduct]:
        q = self.db.query(InsuranceProduct)
        if active_only:
            q = q.filter(InsuranceProduct.active.is_(True))
        if category:
            q = q.filter(InsuranceProduct.category == category)
        return q.order_by(
            InsuranceProduct.category,
            InsuranceProduct.sort_order,
            InsuranceProduct.name,
        ).all()

    def list_categories(self) -> list[dict]:
        rows = (
            self.db.query(
                InsuranceProduct.category,
                func.count(InsuranceProduct.id).label("product_count"),
            )
            .filter(InsuranceProduct.active.is_(True))
            .group_by(InsuranceProduct.category)
            .order_by(InsuranceProduct.category)
            .all()
        )
        return [{"category": cat, "product_count": int(count)} for cat, count in rows]
