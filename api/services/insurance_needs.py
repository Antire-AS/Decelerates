"""Re-export from api.use_cases.insurance_needs — kept for backward compatibility."""
from api.use_cases.insurance_needs import (
    estimate_insurance_needs,
    build_insurance_narrative,
    _nace_section,
    _mnok,
    _estimate_premium,
)
import logging

logger = logging.getLogger(__name__)


__all__ = [
    "estimate_insurance_needs",
    "build_insurance_narrative",
    "_nace_section",
    "_mnok",
    "_estimate_premium",
]
