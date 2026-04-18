"""Unit tests for api/services/screening_client.py — external API client.

All HTTP calls are mocked. Covers PEP screening, Finanstilsynet licences,
and Løsøreregisteret pledge lookups.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from api.services.screening_client import (
    pep_screen_name,
    fetch_finanstilsynet_licenses,
    fetch_losore,
)


def _mock_resp(status=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data or {}
    if status >= 400:
        err = requests.HTTPError(f"{status} error")
        resp.raise_for_status.side_effect = err
    else:
        resp.raise_for_status.return_value = None
    return resp


# ── pep_screen_name ───────────────────────────────────────────────────────────


def test_pep_screen_returns_none_for_empty_name():
    assert pep_screen_name("") is None
    assert pep_screen_name(None) is None


def test_pep_screen_returns_hits_from_results_field():
    fake = {
        "results": [
            {
                "id": "Q1",
                "name": "John Doe",
                "schema": "Person",
                "datasets": ["sanctions"],
                "topics": ["sanction"],
            },
            {
                "id": "Q2",
                "name": "John Doerson",
                "schema": "Person",
                "datasets": [],
                "topics": [],
            },
        ]
    }
    with patch(
        "api.services.screening_client.requests.get", return_value=_mock_resp(200, fake)
    ):
        result = pep_screen_name("John Doe")
    assert result["query"] == "John Doe"
    assert result["hit_count"] == 2
    assert result["hits"][0]["id"] == "Q1"
    assert result["hits"][0]["name"] == "John Doe"


def test_pep_screen_falls_back_to_entities_field():
    fake = {"entities": [{"id": "E1", "name": "Acme Corp", "schema": "Company"}]}
    with patch(
        "api.services.screening_client.requests.get", return_value=_mock_resp(200, fake)
    ):
        result = pep_screen_name("Acme")
    assert result["hit_count"] == 1
    assert result["hits"][0]["id"] == "E1"


def test_pep_screen_returns_zero_hits_when_no_results():
    with patch(
        "api.services.screening_client.requests.get", return_value=_mock_resp(200, {})
    ):
        result = pep_screen_name("Unknown")
    assert result["hit_count"] == 0
    assert result["hits"] == []


def test_pep_screen_returns_none_on_404():
    with patch(
        "api.services.screening_client.requests.get", return_value=_mock_resp(404)
    ):
        result = pep_screen_name("test")
    assert result is None


def test_pep_screen_raises_on_5xx():
    with patch(
        "api.services.screening_client.requests.get", return_value=_mock_resp(500)
    ):
        with pytest.raises(requests.HTTPError):
            pep_screen_name("test")


# ── fetch_finanstilsynet_licenses ─────────────────────────────────────────────


def test_finanstilsynet_returns_empty_on_404():
    with patch(
        "api.services.screening_client.requests.get", return_value=_mock_resp(404)
    ):
        result = fetch_finanstilsynet_licenses("123456789")
    assert result == []


def test_finanstilsynet_flattens_entity_licenses():
    fake = {
        "entities": [
            {
                "name": "DNB Bank ASA",
                "organizationNumber": "984851006",
                "country": "NO",
                "entityType": "Bank",
                "licenses": [
                    {
                        "id": "L1",
                        "type": "Banking",
                        "status": "Active",
                        "validFrom": "2020-01-01",
                        "validTo": None,
                        "description": "Bankvirksomhet",
                    },
                    {
                        "id": "L2",
                        "type": "Investment",
                        "status": "Active",
                        "validFrom": "2021-01-01",
                        "validTo": None,
                        "description": "Verdipapirhandel",
                    },
                ],
            }
        ]
    }
    with patch(
        "api.services.screening_client.requests.get", return_value=_mock_resp(200, fake)
    ):
        result = fetch_finanstilsynet_licenses("984851006")
    assert len(result) == 2
    assert result[0]["license_id"] == "L1"
    assert result[0]["name"] == "DNB Bank ASA"
    assert result[0]["country"] == "NO"
    assert result[1]["license_type"] == "Investment"


def test_finanstilsynet_falls_back_to_items_field():
    fake = {"items": [{"name": "X", "licenses": []}]}
    with patch(
        "api.services.screening_client.requests.get", return_value=_mock_resp(200, fake)
    ):
        result = fetch_finanstilsynet_licenses("123")
    assert result == []  # entity has no licenses → no rows produced


def test_finanstilsynet_uses_orgnr_when_missing_from_entity():
    fake = {"entities": [{"name": "X", "licenses": [{"id": "L1"}]}]}
    with patch(
        "api.services.screening_client.requests.get", return_value=_mock_resp(200, fake)
    ):
        result = fetch_finanstilsynet_licenses("999888777")
    assert result[0]["orgnr"] == "999888777"


# ── fetch_losore ──────────────────────────────────────────────────────────────


def test_fetch_losore_returns_auth_required_on_401():
    with patch(
        "api.services.screening_client.requests.get", return_value=_mock_resp(401)
    ):
        result = fetch_losore("123456789")
    assert result["auth_required"] is True
    assert result["pledges"] == []


def test_fetch_losore_returns_auth_required_on_403():
    with patch(
        "api.services.screening_client.requests.get", return_value=_mock_resp(403)
    ):
        result = fetch_losore("123456789")
    assert result["auth_required"] is True


def test_fetch_losore_returns_zero_count_on_404():
    with patch(
        "api.services.screening_client.requests.get", return_value=_mock_resp(404)
    ):
        result = fetch_losore("123456789")
    assert result["auth_required"] is False
    assert result["count"] == 0
    assert result["pledges"] == []


def test_fetch_losore_parses_pledge_list():
    fake = {
        "antallRettsstiftelser": 3,
        "rettsstiftelse": [
            {
                "dokumentnummer": "D1",
                "typeBeskrivelse": "Pant",
                "statusBeskrivelse": "Tinglyst",
                "innkomsttidspunkt": "2024-06-15T10:00:00",
            },
            {
                "dokumentnummer": "D2",
                "typeBeskrivelse": "Utlegg",
                "statusBeskrivelse": "Tinglyst",
                "innkomsttidspunkt": None,
            },
        ],
    }
    with patch(
        "api.services.screening_client.requests.get", return_value=_mock_resp(200, fake)
    ):
        result = fetch_losore("123")
    assert result["count"] == 3
    assert len(result["pledges"]) == 2
    assert result["pledges"][0]["dokumentnummer"] == "D1"
    assert result["pledges"][0]["dato"] == "2024-06-15"
    assert result["pledges"][1]["dato"] is None


def test_fetch_losore_returns_error_dict_on_exception():
    with patch(
        "api.services.screening_client.requests.get",
        side_effect=requests.ConnectionError("network down"),
    ):
        result = fetch_losore("123")
    assert "error" in result
    assert result["count"] is None
    assert result["pledges"] == []


def test_fetch_losore_caps_pledge_list_at_10():
    fake_pledges = [
        {"dokumentnummer": f"D{i}", "innkomsttidspunkt": "2024-01-01T00:00:00"}
        for i in range(20)
    ]
    fake = {"antallRettsstiftelser": 20, "rettsstiftelse": fake_pledges}
    with patch(
        "api.services.screening_client.requests.get", return_value=_mock_resp(200, fake)
    ):
        result = fetch_losore("123")
    assert result["count"] == 20
    assert len(result["pledges"]) == 10  # capped
