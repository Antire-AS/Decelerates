"""Unit tests for property metadata service helpers."""

from unittest.mock import MagicMock

import pytest

from api.services.company import CompanyService


class TestGetPropertyMetadata:
    def test_unknown_orgnr_raises(self):
        db = MagicMock()
        q = MagicMock()
        q.filter.return_value.first.return_value = None
        db.query.return_value = q
        with pytest.raises(ValueError):
            CompanyService(db).get_property_metadata("999999999")

    def test_returns_empty_dict_when_unset(self):
        db = MagicMock()
        company = MagicMock()
        company.property_metadata = None
        q = MagicMock()
        q.filter.return_value.first.return_value = company
        db.query.return_value = q

        result = CompanyService(db).get_property_metadata("984851006")
        assert result == {}

    def test_returns_existing_blob(self):
        db = MagicMock()
        company = MagicMock()
        company.property_metadata = {"building_year": 1985, "fire_alarm": "yes"}
        q = MagicMock()
        q.filter.return_value.first.return_value = company
        db.query.return_value = q

        result = CompanyService(db).get_property_metadata("984851006")
        assert result == {"building_year": 1985, "fire_alarm": "yes"}


class TestUpdatePropertyMetadata:
    def test_unknown_orgnr_raises(self):
        db = MagicMock()
        q = MagicMock()
        q.filter.return_value.first.return_value = None
        db.query.return_value = q
        with pytest.raises(ValueError):
            CompanyService(db).update_property_metadata("999999999", {"x": 1})

    def test_merges_into_empty_metadata(self):
        db = MagicMock()
        company = MagicMock()
        company.property_metadata = None
        q = MagicMock()
        q.filter.return_value.first.return_value = company
        db.query.return_value = q

        result = CompanyService(db).update_property_metadata(
            "984851006", {"building_year": 1985}
        )

        assert result == {"building_year": 1985}
        assert company.property_metadata == {"building_year": 1985}
        db.commit.assert_called_once()

    def test_merges_into_existing_metadata(self):
        db = MagicMock()
        company = MagicMock()
        company.property_metadata = {"building_year": 1985, "fire_alarm": "old"}
        q = MagicMock()
        q.filter.return_value.first.return_value = company
        db.query.return_value = q

        result = CompanyService(db).update_property_metadata(
            "984851006", {"fire_alarm": "new", "sprinkler": True}
        )

        assert result == {
            "building_year": 1985,
            "fire_alarm": "new",
            "sprinkler": True,
        }

    def test_none_value_removes_key(self):
        db = MagicMock()
        company = MagicMock()
        company.property_metadata = {"building_year": 1985, "fire_alarm": "yes"}
        q = MagicMock()
        q.filter.return_value.first.return_value = company
        db.query.return_value = q

        result = CompanyService(db).update_property_metadata(
            "984851006", {"fire_alarm": None}
        )

        assert result == {"building_year": 1985}
        assert "fire_alarm" not in result
