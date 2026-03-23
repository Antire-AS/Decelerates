"""Unit tests for the analytics router _aggregate helper.

Pure static tests — no DB, no network, no API keys.
"""
from types import SimpleNamespace

from api.routers.analytics import _aggregate


def _policy(insurer: str, product: str, premium: float, status=None):
    p = SimpleNamespace(insurer=insurer, product_type=product, annual_premium_nok=premium)
    if status is not None:
        p.status = SimpleNamespace(value=status)
    return p


# ── _aggregate by insurer ─────────────────────────────────────────────────────


def test_aggregate_single():
    policies = [_policy("If", "Ting", 100_000)]
    result = _aggregate(policies, "insurer")
    assert len(result) == 1
    assert result[0]["insurer"] == "If"
    assert result[0]["count"] == 1
    assert result[0]["total_premium"] == 100_000
    assert result[0]["share_pct"] == 100.0


def test_aggregate_multiple_insurers():
    policies = [
        _policy("If", "Ting", 100_000),
        _policy("Gjensidige", "Ansvar", 200_000),
        _policy("If", "Cyber", 50_000),
    ]
    result = _aggregate(policies, "insurer")
    by_insurer = {r["insurer"]: r for r in result}
    assert by_insurer["If"]["count"] == 2
    assert by_insurer["If"]["total_premium"] == 150_000
    assert by_insurer["Gjensidige"]["total_premium"] == 200_000


def test_aggregate_sorted_by_premium_desc():
    policies = [
        _policy("Small", "X", 10_000),
        _policy("Large", "Y", 500_000),
        _policy("Medium", "Z", 100_000),
    ]
    result = _aggregate(policies, "insurer")
    assert result[0]["insurer"] == "Large"
    assert result[-1]["insurer"] == "Small"


def test_aggregate_share_pct_sums_100():
    policies = [
        _policy("A", "X", 300_000),
        _policy("B", "Y", 200_000),
        _policy("C", "Z", 500_000),
    ]
    result = _aggregate(policies, "insurer")
    total_share = sum(r["share_pct"] for r in result)
    assert abs(total_share - 100.0) < 0.1


def test_aggregate_none_premium_treated_as_zero():
    p = SimpleNamespace(insurer="NoFee", product_type="Ting", annual_premium_nok=None)
    result = _aggregate([p], "insurer")
    assert result[0]["total_premium"] == 0.0


def test_aggregate_empty_list():
    result = _aggregate([], "insurer")
    assert result == []


def test_aggregate_unknown_insurer_filled():
    p = SimpleNamespace(insurer=None, product_type="Ting", annual_premium_nok=50_000)
    result = _aggregate([p], "insurer")
    assert result[0]["insurer"] == "Ukjent"


def test_aggregate_by_product():
    policies = [
        _policy("If", "Cyber", 200_000),
        _policy("Gjensidige", "Cyber", 100_000),
        _policy("If", "Ting", 50_000),
    ]
    result = _aggregate(policies, "product_type")
    by_product = {r["product_type"]: r for r in result}
    assert by_product["Cyber"]["total_premium"] == 300_000
    assert by_product["Ting"]["total_premium"] == 50_000
