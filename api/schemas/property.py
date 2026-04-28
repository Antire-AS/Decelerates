"""Property metadata schemas — building year, fire alarm, materials etc."""

from typing import Any, Dict, Optional

from pydantic import BaseModel


class PropertyMetadataOut(BaseModel):
    """Loose JSONB blob — frontend renders whatever keys are set."""

    orgnr: str
    metadata: Dict[str, Any]


class PropertyMetadataPatch(BaseModel):
    """Partial update — keys with `None` value are removed.

    Recognised fields (informational; the backend stores any keys):
    """

    building_year: Optional[int] = None
    ground_area_m2: Optional[float] = None
    fire_alarm: Optional[str] = None
    sprinkler: Optional[bool] = None
    flammable_materials: Optional[str] = None
    construction: Optional[str] = None
    roof_type: Optional[str] = None
    fire_resistance_rating: Optional[str] = None
    primary_use: Optional[str] = None
    address: Optional[str] = None
    gnr_bnr: Optional[str] = None
    notes: Optional[str] = None
