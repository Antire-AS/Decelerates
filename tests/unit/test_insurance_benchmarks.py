"""Unit tests for api/constants_insurance.py — premium benchmark data."""

from api.constants_insurance import (
    PREMIUM_BENCHMARKS,
    NACE_RISK_MULTIPLIERS,
    get_bracket_for_revenue,
    estimate_premiums_for_company,
)


class TestGetBracket:
    def test_xs(self):
        assert get_bracket_for_revenue(5_000_000) == "XS"

    def test_s(self):
        assert get_bracket_for_revenue(25_000_000) == "S"

    def test_m(self):
        assert get_bracket_for_revenue(100_000_000) == "M"

    def test_l(self):
        assert get_bracket_for_revenue(500_000_000) == "L"

    def test_xl(self):
        assert get_bracket_for_revenue(2_000_000_000) == "XL"

    def test_none_defaults_to_s(self):
        assert get_bracket_for_revenue(None) == "S"

    def test_zero_defaults_to_s(self):
        assert get_bracket_for_revenue(0) == "S"

    def test_negative_defaults_to_s(self):
        assert get_bracket_for_revenue(-100) == "S"


class TestEstimatePremiums:
    def test_returns_all_products(self):
        result = estimate_premiums_for_company(50_000_000)
        assert len(result) == len(PREMIUM_BENCHMARKS)
        for key in PREMIUM_BENCHMARKS:
            assert key in result

    def test_includes_required_fields(self):
        result = estimate_premiums_for_company(50_000_000)
        for key, est in result.items():
            assert "label" in est
            assert "low" in est
            assert "mid" in est
            assert "high" in est
            assert "bracket" in est
            assert est["low"] <= est["mid"] <= est["high"]

    def test_nace_adjustment_increases_premiums(self):
        base = estimate_premiums_for_company(50_000_000)
        adjusted = estimate_premiums_for_company(50_000_000, "F")  # Construction 1.30x
        for key in base:
            assert adjusted[key]["mid"] > base[key]["mid"]
            assert adjusted[key]["nace_adjustment"] == 1.30

    def test_nace_adjustment_default_is_1(self):
        result = estimate_premiums_for_company(50_000_000)
        for est in result.values():
            assert est["nace_adjustment"] == 1.0

    def test_unknown_nace_uses_default(self):
        result = estimate_premiums_for_company(50_000_000, "Z")
        for est in result.values():
            assert est["nace_adjustment"] == 1.0


class TestDataIntegrity:
    def test_all_brackets_have_low_mid_high(self):
        for product_key, product in PREMIUM_BENCHMARKS.items():
            for bracket_key, bracket in product["premiums"].items():
                assert "low" in bracket, f"{product_key}/{bracket_key} missing low"
                assert "mid" in bracket, f"{product_key}/{bracket_key} missing mid"
                assert "high" in bracket, f"{product_key}/{bracket_key} missing high"
                assert bracket["low"] <= bracket["mid"] <= bracket["high"], (
                    f"{product_key}/{bracket_key}: low <= mid <= high violated"
                )

    def test_premiums_increase_with_bracket(self):
        bracket_order = ["XS", "S", "M", "L", "XL"]
        for product_key, product in PREMIUM_BENCHMARKS.items():
            for i in range(1, len(bracket_order)):
                prev = product["premiums"][bracket_order[i - 1]]["mid"]
                curr = product["premiums"][bracket_order[i]]["mid"]
                assert curr >= prev, (
                    f"{product_key}: {bracket_order[i]} mid ({curr}) < {bracket_order[i - 1]} mid ({prev})"
                )

    def test_all_nace_sections_present(self):
        expected = set("ABCDEFGHIJKLMNOPQRS")
        actual = set(NACE_RISK_MULTIPLIERS.keys())
        assert expected == actual

    def test_all_multipliers_positive(self):
        for section, data in NACE_RISK_MULTIPLIERS.items():
            assert data["multiplier"] > 0, f"NACE {section} has non-positive multiplier"
