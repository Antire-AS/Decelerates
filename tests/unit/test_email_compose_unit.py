"""Unit tests for api/services/email_compose_service.py — EmailComposeService."""

import sys
from unittest.mock import MagicMock, patch

sys.modules.setdefault("api.rag_chain", MagicMock())
sys.modules.setdefault("api.services.pdf_background", MagicMock())

import pytest

from api.services.email_compose_service import EmailComposeService


class TestComposeAndSend:
    def _make_svc(self):
        db = MagicMock()
        email_port = MagicMock()
        email_port.send_email.return_value = "msg-id-123"
        return EmailComposeService(db=db, email_port=email_port), db, email_port

    def test_sends_email_via_port(self):
        svc, db, email_port = self._make_svc()
        svc.compose_and_send(
            orgnr="123456789",
            firm_id=1,
            to="client@example.com",
            subject="Tilbud",
            body_html="<p>Hello</p>",
            author_email="broker@firm.no",
        )
        email_port.send_email.assert_called_once_with(
            to="client@example.com",
            subject="Tilbud",
            body_html="<p>Hello</p>",
        )

    def test_returns_activity_object(self):
        svc, db, email_port = self._make_svc()
        svc.compose_and_send(
            orgnr="123456789",
            firm_id=1,
            to="client@example.com",
            subject="Test",
            body_html="<p>Hi</p>",
            author_email="broker@firm.no",
        )
        # db.add is called for both Activity and AuditLog
        assert db.add.call_count >= 1
        # First call is the Activity
        added = db.add.call_args_list[0][0][0]
        assert added.orgnr == "123456789"
        assert added.completed is True

    def test_activity_subject_has_emoji_prefix(self):
        svc, db, _ = self._make_svc()
        svc.compose_and_send(
            orgnr="123456789",
            firm_id=1,
            to="c@e.com",
            subject="Forsikring",
            body_html="<p>x</p>",
            author_email="b@f.no",
        )
        added = db.add.call_args_list[0][0][0]
        assert added.subject.startswith("\U0001f4e7")  # envelope emoji

    def test_long_body_is_trimmed_for_activity(self):
        svc, db, _ = self._make_svc()
        long_body = "<p>" + "A" * 500 + "</p>"
        svc.compose_and_send(
            orgnr="123456789",
            firm_id=1,
            to="c@e.com",
            subject="Sub",
            body_html=long_body,
            author_email="b@f.no",
        )
        added = db.add.call_args_list[0][0][0]
        assert len(added.body) <= 305

    def test_short_body_is_not_trimmed(self):
        svc, db, _ = self._make_svc()
        short_body = "<p>Short</p>"
        svc.compose_and_send(
            orgnr="123456789",
            firm_id=1,
            to="c@e.com",
            subject="Sub",
            body_html=short_body,
            author_email="b@f.no",
        )
        added = db.add.call_args_list[0][0][0]
        assert added.body == short_body

    def test_commits_and_refreshes_activity(self):
        svc, db, _ = self._make_svc()
        svc.compose_and_send(
            orgnr="123456789",
            firm_id=1,
            to="c@e.com",
            subject="Sub",
            body_html="<p>x</p>",
            author_email="b@f.no",
        )
        db.commit.assert_called()
        db.refresh.assert_called_once()

    def test_rollback_on_commit_failure(self):
        svc, db, _ = self._make_svc()
        db.commit.side_effect = RuntimeError("DB down")
        with pytest.raises(RuntimeError, match="DB down"):
            svc.compose_and_send(
                orgnr="123456789",
                firm_id=1,
                to="c@e.com",
                subject="Sub",
                body_html="<p>x</p>",
                author_email="b@f.no",
            )
        db.rollback.assert_called_once()

    def test_logs_audit_entry(self):
        svc, db, _ = self._make_svc()
        with patch("api.services.email_compose_service.log_audit") as mock_audit:
            svc.compose_and_send(
                orgnr="123456789",
                firm_id=1,
                to="client@e.com",
                subject="Test",
                body_html="<p>x</p>",
                author_email="broker@f.no",
            )
        mock_audit.assert_called_once()
        _, kwargs = mock_audit.call_args
        assert kwargs["orgnr"] == "123456789"
        assert kwargs["actor_email"] == "broker@f.no"
        assert kwargs["detail"]["to"] == "client@e.com"
        assert kwargs["detail"]["message_id"] == "msg-id-123"
