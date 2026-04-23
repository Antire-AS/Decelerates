"""Unit tests for the Serper news query builder.

Pins the query shape so accidental edits to MATERIAL_KEYWORDS_QUERY
don't silently broaden or narrow the results the broker sees.
"""

from __future__ import annotations

from api.services.news_service import MATERIAL_KEYWORDS_QUERY, _build_news_query


def test_query_includes_company_name_and_norway_locator():
    q = _build_news_query("DNB Bank ASA")
    assert "DNB Bank ASA" in q
    assert " Norge " in q


def test_query_includes_material_keyword_block():
    """The keyword block is what filters out analyst coverage + marketing
    noise at the Serper level — before we spend Foundry calls classifying."""
    q = _build_news_query("DNB Bank ASA")
    assert MATERIAL_KEYWORDS_QUERY in q


def test_material_keywords_cover_underwriter_relevant_events():
    """If we ever drop one of these, the regression test tells us which."""
    for keyword in ("konkurs", "rettssak", "ledelsesbytte", "nedskrivning", "oppkjøp"):
        assert keyword in MATERIAL_KEYWORDS_QUERY


def test_query_tolerates_special_characters_in_company_name():
    q = _build_news_query("Søderberg & Partners Norge AS")
    assert "Søderberg & Partners Norge AS" in q
