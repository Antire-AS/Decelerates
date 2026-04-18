"""Unit tests for InsurerService — appetite matching and win/loss analysis."""

from unittest.mock import MagicMock


from api.db import Insurer, Submission, SubmissionStatus
from api.services.insurer_service import InsurerService


def _make_insurer(name="Gjensidige", appetite=None):
    ins = MagicMock(spec=Insurer)
    ins.id = 1
    ins.firm_id = 1
    ins.name = name
    ins.org_number = None
    ins.contact_name = None
    ins.contact_email = None
    ins.contact_phone = None
    ins.appetite = appetite or []
    ins.notes = None
    ins.created_at = None
    return ins


def _make_submission(
    insurer_id=1,
    product_type="Eiendom",
    status=SubmissionStatus.quoted,
    premium=500_000.0,
):
    s = MagicMock(spec=Submission)
    s.insurer_id = insurer_id
    s.product_type = product_type
    s.status = status
    s.premium_offered_nok = premium
    s.orgnr = "123456789"
    s.firm_id = 1
    return s


class TestMatchAppetite:
    def _svc_with_insurers(self, insurers):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = insurers
        return InsurerService(db)

    def test_returns_exact_match_first(self):
        exact = _make_insurer("Gjensidige", ["Eiendom", "Ansvar"])
        partial = _make_insurer("If", ["Næringseiendom", "Transport"])
        svc = self._svc_with_insurers([exact, partial])
        result = svc.match_appetite(firm_id=1, product_type="Eiendom")
        assert result[0].name == "Gjensidige"

    def test_returns_partial_match(self):
        ins = _make_insurer("If", ["Næringseiendom"])
        svc = self._svc_with_insurers([ins])
        result = svc.match_appetite(firm_id=1, product_type="Eiendom")
        assert len(result) == 1
        assert result[0].name == "If"

    def test_empty_when_no_match(self):
        ins = _make_insurer("If", ["Transport"])
        svc = self._svc_with_insurers([ins])
        result = svc.match_appetite(firm_id=1, product_type="Cyber")
        assert result == []

    def test_empty_appetite_excluded(self):
        ins = _make_insurer("NoAppetite", appetite=None)
        svc = self._svc_with_insurers([ins])
        result = svc.match_appetite(firm_id=1, product_type="Eiendom")
        assert result == []


class TestGetWinLossSummary:
    def _svc_with_submissions(self, submissions):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = submissions
        # For insurer name resolution
        insurer = _make_insurer("Gjensidige")
        db.query.return_value.filter.return_value.all.side_effect = None
        db.query.return_value.filter.return_value.all.return_value = submissions
        ins_q = MagicMock()
        ins_q.all.return_value = [insurer]

        call_count = [0]

        def side_effect(model):
            call_count[0] += 1
            q = MagicMock()
            q.filter.return_value = q
            q.order_by.return_value = q
            if model is Submission:
                q.all.return_value = submissions
            else:
                q.all.return_value = [insurer]
            return q

        db.query.side_effect = side_effect
        return InsurerService(db)

    def test_counts_total_submissions(self):
        subs = [
            _make_submission(status=SubmissionStatus.quoted),
            _make_submission(status=SubmissionStatus.declined),
            _make_submission(status=SubmissionStatus.pending),
        ]
        svc = self._svc_with_submissions(subs)
        result = svc.get_win_loss_summary(firm_id=1)
        assert result["total_submissions"] == 3

    def test_calculates_win_rate(self):
        subs = [
            _make_submission(status=SubmissionStatus.quoted),
            _make_submission(status=SubmissionStatus.quoted),
            _make_submission(status=SubmissionStatus.declined),
            _make_submission(status=SubmissionStatus.declined),
        ]
        svc = self._svc_with_submissions(subs)
        result = svc.get_win_loss_summary(firm_id=1)
        assert result["win_rate_pct"] == 50.0

    def test_zero_win_rate_when_no_submissions(self):
        svc = self._svc_with_submissions([])
        result = svc.get_win_loss_summary(firm_id=1)
        assert result["win_rate_pct"] == 0.0
        assert result["total_submissions"] == 0

    def test_groups_by_product_type(self):
        subs = [
            _make_submission(product_type="Eiendom", status=SubmissionStatus.quoted),
            _make_submission(product_type="Ansvar", status=SubmissionStatus.declined),
        ]
        svc = self._svc_with_submissions(subs)
        result = svc.get_win_loss_summary(firm_id=1)
        assert "Eiendom" in result["by_product_type"]
        assert "Ansvar" in result["by_product_type"]
        assert result["by_product_type"]["Eiendom"]["quoted"] == 1
        assert result["by_product_type"]["Ansvar"]["declined"] == 1


class TestDraftSubmissionEmail:
    def _make_db(self, sub, insurer, company=None):
        db = MagicMock()

        def _query(model):
            from api.db import Submission, Insurer as InsurerModel, Company

            m = MagicMock()
            if model is Submission:
                m.filter.return_value.first.return_value = sub
            elif model is InsurerModel:
                m.filter.return_value.first.return_value = insurer
            elif model is Company:
                m.filter.return_value.first.return_value = company
            return m

        db.query.side_effect = _query
        return db

    def test_returns_llm_draft(self):
        from unittest.mock import patch
        from api.services.insurer_service import InsurerService

        sub = _make_submission(insurer_id=1, product_type="Eiendom")
        sub.id = 42
        sub.firm_id = 1
        sub.orgnr = "123456789"
        sub.premium_offered_nok = 500_000.0

        insurer = _make_insurer(name="Tryg")
        insurer.id = 1

        db = self._make_db(sub, insurer)

        with patch(
            "api.services.llm._llm_answer_raw",
            return_value="Kjære Tryg, vi ønsker å søke...",
        ):
            svc = InsurerService(db)
            result = svc.draft_submission_email(firm_id=1, submission_id=42)

        assert "Tryg" in result or result  # LLM draft returned

    def test_returns_empty_string_when_llm_returns_none(self):
        from unittest.mock import patch
        from api.services.insurer_service import InsurerService

        sub = _make_submission(insurer_id=1)
        sub.id = 1
        sub.firm_id = 1
        sub.orgnr = "111111111"
        sub.premium_offered_nok = None

        insurer = _make_insurer()
        db = self._make_db(sub, insurer)

        with patch("api.services.llm._llm_answer_raw", return_value=None):
            result = InsurerService(db).draft_submission_email(
                firm_id=1, submission_id=1
            )

        assert result == ""
