"""Unit tests for Altman Z''-Score computation in api/risk.py.

Uses synthetic financials sized to land in each of the three Altman 2000
zones (safe / grey / distress) so the test names describe the intended
economic meaning, not the specific arithmetic.
"""

from api.risk import (
    Z_DISTRESS_TOP,
    Z_GREY_TOP,
    _map_z_to_risk_score,
    _z_zone,
    compute_altman_z_score,
    derive_simple_risk,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _regn(
    total_assets: float,
    total_liab: float,
    equity: float,
    ebit: float,
    retained: float,
    current_assets: float,
    short_term_debt: float,
) -> dict:
    """Build a synthetic regn dict with the exact fields the extraction emits.
    Keeping the helper explicit means each test names its inputs instead of
    hiding them in a fixture."""
    return {
        "sum_eiendeler": total_assets,
        "sum_gjeld": total_liab,
        "sum_egenkapital": equity,
        "driftsresultat": ebit,
        "sum_opptjent_egenkapital": retained,
        "sum_omloepsmidler": current_assets,
        "short_term_debt": short_term_debt,
    }


# ── Happy path: three zones ──────────────────────────────────────────────────


def test_healthy_company_lands_in_safe_zone():
    """Equity-funded, profitable, plenty of current assets → Z'' > 2.60."""
    regn = _regn(
        total_assets=1000,
        total_liab=200,
        equity=800,
        ebit=150,
        retained=600,
        current_assets=500,
        short_term_debt=150,
    )
    result = compute_altman_z_score(regn)
    assert result is not None
    assert result["z_score"] > Z_GREY_TOP
    assert result["zone"] == "safe"
    assert result["score_20"] <= 5  # Lav risk band


def test_borderline_company_lands_in_grey_zone():
    """Modest profit + moderate leverage → 1.10 ≤ Z'' ≤ 2.60."""
    regn = _regn(
        total_assets=1000,
        total_liab=600,
        equity=400,
        ebit=50,
        retained=150,
        current_assets=400,
        short_term_debt=350,
    )
    result = compute_altman_z_score(regn)
    assert result is not None
    assert Z_DISTRESS_TOP <= result["z_score"] <= Z_GREY_TOP
    assert result["zone"] == "grey"
    assert 5 < result["score_20"] < 15


def test_distressed_company_lands_in_distress_zone():
    """Negative EBIT + high leverage + thin working capital → Z'' < 1.10."""
    regn = _regn(
        total_assets=1000,
        total_liab=900,
        equity=100,
        ebit=-200,
        retained=-400,
        current_assets=200,
        short_term_debt=700,
    )
    result = compute_altman_z_score(regn)
    assert result is not None
    assert result["z_score"] < Z_DISTRESS_TOP
    assert result["zone"] == "distress"
    assert result["score_20"] >= 15  # Høy or Svært høy band


# ── Missing-input fallback ───────────────────────────────────────────────────


def test_returns_none_when_total_assets_missing():
    """Required-input guard. Banks often omit sum_eiendeler via the extractor
    when the asset breakdown isn't cleanly parseable."""
    regn = _regn(1000, 200, 800, 150, 600, 500, 150)
    regn.pop("sum_eiendeler")
    assert compute_altman_z_score(regn) is None


def test_returns_none_when_current_assets_missing_banks_insurers():
    """Banks + insurers don't report current/non-current split — Altman's
    working-capital term is undefined, so we bail and the caller falls back
    to rule-based scoring."""
    regn = _regn(1000, 200, 800, 150, 600, 500, 150)
    regn["sum_omloepsmidler"] = None
    assert compute_altman_z_score(regn) is None


def test_returns_none_when_total_liabilities_zero():
    """Guards the BE/TL ratio from divide-by-zero. Companies with zero debt
    are real (young startups funded only by equity) but Altman's Z'' isn't
    defined for them and zero-debt ≠ zero-risk anyway."""
    regn = _regn(1000, 0, 1000, 100, 500, 400, 0)
    assert compute_altman_z_score(regn) is None


# ── Score mapping edge cases ─────────────────────────────────────────────────


def test_score_clamps_to_zero_above_safe_threshold():
    """Z'' ≥ 3.50 all maps to 0 regardless of how much higher."""
    assert _map_z_to_risk_score(3.50) == 0
    assert _map_z_to_risk_score(10.0) == 0


def test_score_clamps_to_twenty_below_critical_threshold():
    """Negative Z'' all maps to 20."""
    assert _map_z_to_risk_score(0.0) == 20
    assert _map_z_to_risk_score(-5.0) == 20


def test_score_mapping_is_monotonically_decreasing():
    """Lower Z'' should always produce a higher or equal risk score."""
    scores = [_map_z_to_risk_score(z / 10) for z in range(-10, 40)]
    for earlier, later in zip(scores, scores[1:]):
        # iterating low→high Z''; risk score should go high→low
        assert earlier >= later, f"non-monotonic at {earlier} → {later}"


# ── Zone classification ──────────────────────────────────────────────────────


def test_zone_safe_above_grey_top():
    assert _z_zone(3.0) == "safe"
    assert _z_zone(Z_GREY_TOP + 0.01) == "safe"


def test_zone_grey_between_thresholds():
    assert _z_zone(Z_GREY_TOP) == "grey"
    assert _z_zone(1.85) == "grey"
    assert _z_zone(Z_DISTRESS_TOP) == "grey"


def test_zone_distress_below_distress_top():
    assert _z_zone(Z_DISTRESS_TOP - 0.01) == "distress"
    assert _z_zone(-1.0) == "distress"


# ── Integration with derive_simple_risk ──────────────────────────────────────


def test_derive_simple_risk_exposes_altman_z_alongside_rule_score():
    """End-to-end: derive_simple_risk returns the Z'' result as a sibling
    of the rule-based score, so the UI can show both transparently."""
    regn = _regn(
        total_assets=1000,
        total_liab=200,
        equity=800,
        ebit=150,
        retained=600,
        current_assets=500,
        short_term_debt=150,
    )
    org = {"orgnr": "999999999", "navn": "Healthy AS"}
    result = derive_simple_risk(org, regn)

    assert "score" in result
    assert "altman_z" in result
    assert result["altman_z"] is not None
    assert result["altman_z"]["zone"] == "safe"
    # Rule-based still works independently
    assert isinstance(result["score"], int)


def test_derive_simple_risk_altman_is_none_for_bank_regn():
    """When the extraction can't fill current assets (typical for banks),
    altman_z should be None but rule-based score still computes."""
    regn = {
        "sum_eiendeler": 1_000_000_000_000,
        "sum_gjeld": 900_000_000_000,
        "sum_egenkapital": 100_000_000_000,
        "driftsresultat": 50_000_000_000,
        "sum_opptjent_egenkapital": 80_000_000_000,
        "sum_driftsinntekter": 100_000_000_000,
        # Banks omit these two:
        "sum_omloepsmidler": None,
        "short_term_debt": None,
    }
    org = {"orgnr": "984851006", "navn": "DNB Bank ASA"}
    result = derive_simple_risk(org, regn)

    assert result["altman_z"] is None
    assert result["score"] >= 0  # rule-based still fires
