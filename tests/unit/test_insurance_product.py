"""Unit tests for insurance product catalog (seed + service)."""

from unittest.mock import MagicMock

import pytest

from api.services.insurance_product_seed import _CATALOG, catalog_size
from api.services.insurance_product_service import InsuranceProductService


def test_catalog_includes_15_personell_products():
    """User explicitly asked for 15 produkter på personalforsikring."""
    personell = [p for p in _CATALOG if p["category"] == "personell"]
    assert len(personell) == 15, (
        f"Expected exactly 15 personell products, got {len(personell)}: "
        f"{[p['name'] for p in personell]}"
    )


def test_catalog_covers_required_categories():
    cats = {p["category"] for p in _CATALOG}
    expected = {
        "personell",
        "bygning",
        "ansvar",
        "drift",
        "transport",
        "marine",
        "annet",
    }
    assert expected <= cats, f"Missing categories: {expected - cats}"


def test_each_entry_has_required_fields():
    for entry in _CATALOG:
        assert "category" in entry, entry
        assert "name" in entry, entry
        # description is recommended but not strictly required
        # sort_order has a default in the schema, so optional


def test_no_duplicate_natural_keys():
    """The unique constraint is (category, sub_category, name)."""
    seen: set[tuple] = set()
    for p in _CATALOG:
        key = (p["category"], p.get("sub_category"), p["name"])
        assert key not in seen, f"Duplicate natural key: {key}"
        seen.add(key)


def test_catalog_size_helper():
    assert catalog_size() == len(_CATALOG)
    assert catalog_size() >= 40  # 15 personell + 6 bygning + 8 ansvar + …


class TestServiceListProducts:
    def test_filters_by_category_when_given(self):
        db = MagicMock()
        q = MagicMock()
        db.query.return_value = q
        q.filter.return_value = q
        q.order_by.return_value = q
        q.all.return_value = []

        InsuranceProductService(db).list_products(category="personell")
        # active filter + category filter = 2 filter calls
        assert q.filter.call_count == 2

    def test_no_category_filter_when_none(self):
        db = MagicMock()
        q = MagicMock()
        db.query.return_value = q
        q.filter.return_value = q
        q.order_by.return_value = q
        q.all.return_value = []

        InsuranceProductService(db).list_products()
        # only the active filter
        assert q.filter.call_count == 1


class TestServiceListCategories:
    def test_groups_by_category(self):
        db = MagicMock()
        q = MagicMock()
        db.query.return_value = q
        q.filter.return_value = q
        q.group_by.return_value = q
        q.order_by.return_value = q
        q.all.return_value = [("personell", 15), ("bygning", 6)]

        result = InsuranceProductService(db).list_categories()
        assert result == [
            {"category": "personell", "product_count": 15},
            {"category": "bygning", "product_count": 6},
        ]


@pytest.mark.parametrize(
    "category",
    ["personell", "bygning", "ansvar", "drift", "transport", "marine", "annet"],
)
def test_each_canonical_category_has_at_least_one_entry(category):
    matches = [p for p in _CATALOG if p["category"] == category]
    assert len(matches) >= 1, f"Empty category: {category}"
