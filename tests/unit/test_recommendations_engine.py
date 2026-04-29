"""Tests for the recommendations engine."""

from datetime import datetime, timedelta, timezone


def test_no_data_yields_empty_list():
    """Engine returns [] when nothing fires."""
    from api.services.recommendations_engine import compute_recommendations

    result = compute_recommendations(
        companies=[],
        claims_index={},
        last_narrative_at={},
        peer_overage_orgnrs=set(),
    )
    assert result == []


def test_pep_hit_triggers_pep_recommendation():
    from api.services.recommendations_engine import compute_recommendations

    companies = [
        {"orgnr": "111", "navn": "Foo AS", "pep_hit_count": 1},
    ]
    result = compute_recommendations(
        companies=companies,
        claims_index={},
        last_narrative_at={},
        peer_overage_orgnrs=set(),
    )
    assert any(r["kind"] == "pep" and r["orgnr"] == "111" for r in result)


def test_aggregate_peer_overage_appears_when_three_or_more():
    from api.services.recommendations_engine import compute_recommendations

    result = compute_recommendations(
        companies=[],
        claims_index={},
        last_narrative_at={},
        peer_overage_orgnrs={"a", "b", "c", "d", "e", "f"},
    )
    aggregate = next(r for r in result if r["kind"] == "peer_overage")
    assert "6" in aggregate["headline"]


def test_two_peer_overage_companies_dont_aggregate():
    """Below threshold of 3 → no aggregate recommendation."""
    from api.services.recommendations_engine import compute_recommendations

    result = compute_recommendations(
        companies=[],
        claims_index={},
        last_narrative_at={},
        peer_overage_orgnrs={"a", "b"},
    )
    assert not any(r["kind"] == "peer_overage" for r in result)


def test_stale_narrative_triggers_update_recommendation():
    from api.services.recommendations_engine import compute_recommendations

    companies = [{"orgnr": "222", "navn": "Bar AS", "pep_hit_count": 0}]
    old = datetime.now(tz=timezone.utc) - timedelta(days=60)
    new_claim = datetime.now(tz=timezone.utc) - timedelta(days=2)
    result = compute_recommendations(
        companies=companies,
        claims_index={"222": new_claim},
        last_narrative_at={"222": old},
        peer_overage_orgnrs=set(),
    )
    assert any(r["kind"] == "stale_narrative" and r["orgnr"] == "222" for r in result)


def test_capped_at_five():
    """If many companies trigger rules, output is capped at 5."""
    from api.services.recommendations_engine import compute_recommendations

    companies = [
        {"orgnr": str(i), "navn": f"Co {i}", "pep_hit_count": 1} for i in range(10)
    ]
    result = compute_recommendations(
        companies=companies,
        claims_index={},
        last_narrative_at={},
        peer_overage_orgnrs=set(),
    )
    assert len(result) == 5
