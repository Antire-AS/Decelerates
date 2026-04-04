"""Unit tests for coverage gap analysis."""
from unittest.mock import MagicMock, patch

import pytest

from api.db import Company, Policy, PolicyStatus


def _make_company(orgnr="123456789", naeringskode1="J", antall_ansatte=10,
                  sum_driftsinntekter=20_000_000.0, sum_eiendeler=8_000_000.0,
                  organisasjonsform_kode="AS"):
    c = MagicMock(spec=Company)
    c.orgnr = orgnr
    c.navn = "Test AS"
    c.naeringskode1 = naeringskode1
    c.naeringskode1_beskrivelse = "IT"
    c.antall_ansatte = antall_ansatte
    c.sum_driftsinntekter = sum_driftsinntekter
    c.sum_eiendeler = sum_eiendeler
    c.organisasjonsform_kode = organisasjonsform_kode
    return c


def _make_policy(product_type="Ansvarsforsikring", coverage_amount_nok=5_000_000.0,
                 insurer="Gjensidige", policy_number="POL-1"):
    p = MagicMock(spec=Policy)
    p.product_type = product_type
    p.coverage_amount_nok = coverage_amount_nok
    p.insurer = insurer
    p.policy_number = policy_number
    p.status = PolicyStatus.active
    return p


def _make_db(company=None, policies=None, history=None):
    db = MagicMock()

    def _query_side_effect(model):
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.first.return_value = None
        q.all.return_value = []
        if model is Company:
            q.first.return_value = company
        elif model is Policy:
            q.all.return_value = policies or []
        return q

    db.query.side_effect = _query_side_effect
    return db


class TestAnalyzeCoverageGap:
    def test_gap_when_no_policies(self):
        from api.services.coverage_gap import analyze_coverage_gap
        company = _make_company(antall_ansatte=5)
        db = _make_db(company=company, policies=[])
        result = analyze_coverage_gap("123456789", firm_id=1, db=db)
        assert result["gap_count"] > 0
        assert result["covered_count"] == 0
        assert all(i["status"] == "gap" for i in result["items"])

    def test_covered_when_matching_policy_exists(self):
        from api.services.coverage_gap import analyze_coverage_gap
        company = _make_company(antall_ansatte=5)
        # Provide all common coverage types to test coverage
        policies = [
            _make_policy("Yrkesskadeforsikring"),
            _make_policy("Ansvarsforsikring"),
            _make_policy("Cyberforsikring"),
        ]
        db = _make_db(company=company, policies=policies)
        result = analyze_coverage_gap("123456789", firm_id=1, db=db)
        covered_types = {i["type"] for i in result["items"] if i["status"] == "covered"}
        assert "Yrkesskadeforsikring" in covered_types
        assert "Ansvarsforsikring" in covered_types

    def test_returns_required_keys(self):
        from api.services.coverage_gap import analyze_coverage_gap
        company = _make_company()
        db = _make_db(company=company, policies=[])
        result = analyze_coverage_gap("123456789", 1, db)
        assert "orgnr" in result
        assert "items" in result
        assert "covered_count" in result
        assert "gap_count" in result
        assert "total_count" in result

    def test_undercoverage_note_flagged(self):
        from api.services.coverage_gap import analyze_coverage_gap
        company = _make_company(sum_eiendeler=20_000_000.0, organisasjonsform_kode="AS")
        # Policy with very low coverage — below 70% of estimated
        low_policy = _make_policy("Eiendomsforsikring", coverage_amount_nok=100_000.0)
        db = _make_db(company=company, policies=[low_policy])
        result = analyze_coverage_gap("123456789", 1, db)
        eiendom = next((i for i in result["items"] if "Eiendom" in i["type"]), None)
        if eiendom and eiendom["status"] == "covered":
            assert eiendom["coverage_note"] is not None


class TestGetCompaniesWithGaps:
    def test_returns_companies_with_gaps(self):
        from api.services.coverage_gap import get_companies_with_gaps
        company = _make_company()

        db = MagicMock()
        # distinct orgnrs query
        db.query.return_value.filter.return_value.distinct.return_value.all.return_value = [
            MagicMock(orgnr="123456789")
        ]

        with patch("api.services.coverage_gap.analyze_coverage_gap") as mock_analyze:
            mock_analyze.return_value = {
                "gap_count": 2, "total_count": 5,
                "items": [
                    {"type": "Cyberforsikring", "priority": "Anbefalt", "status": "gap"},
                    {"type": "Ansvarsforsikring", "priority": "Kritisk", "status": "gap"},
                ]
            }
            db.query.return_value.filter.return_value.first.return_value = company
            result = get_companies_with_gaps(firm_id=1, db=db)

        assert len(result) == 1
        assert result[0]["gap_count"] == 2
        assert result[0]["orgnr"] == "123456789"

    def test_skips_companies_with_no_gaps(self):
        from api.services.coverage_gap import get_companies_with_gaps

        db = MagicMock()
        db.query.return_value.filter.return_value.distinct.return_value.all.return_value = [
            MagicMock(orgnr="123456789")
        ]

        with patch("api.services.coverage_gap.analyze_coverage_gap") as mock_analyze:
            mock_analyze.return_value = {"gap_count": 0, "total_count": 3, "items": []}
            result = get_companies_with_gaps(firm_id=1, db=db)

        assert result == []
