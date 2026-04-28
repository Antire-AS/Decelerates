"""Insurance product catalog schemas."""

from typing import Any, Dict, Optional

from pydantic import BaseModel


class InsuranceProductOut(BaseModel):
    id: int
    category: str
    sub_category: Optional[str] = None
    name: str
    description: Optional[str] = None
    typical_coverage_limits: Optional[Dict[str, Any]] = None
    sort_order: int = 0


class ProductCategoryOut(BaseModel):
    category: str
    product_count: int
