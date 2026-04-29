"""Tests for GET /dashboard/premium-trend."""


def test_schema_imports_from_api_schemas():
    """Schema must be re-exported from api.schemas top-level."""
    from api.schemas import PremiumTrendOut, PremiumTrendPoint  # noqa: F401
