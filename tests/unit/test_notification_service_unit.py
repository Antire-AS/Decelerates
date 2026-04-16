"""Unit tests for api/services/notification_service.py — NotificationService wrapper."""
import sys
from unittest.mock import MagicMock, patch

sys.modules.setdefault("api.rag_chain", MagicMock())
sys.modules.setdefault("api.services.pdf_background", MagicMock())

import pytest


class TestNotificationServiceInit:
    def test_reads_env_vars_on_init(self):
        with patch.dict("os.environ", {
            "AZURE_COMMUNICATION_CONNECTION_STRING": "endpoint=test;key=abc",
            "ACS_SENDER_ADDRESS": "sender@example.com",
        }):
            from api.services.notification_service import NotificationService
            svc = NotificationService()
        assert svc._config.conn_str == "endpoint=test;key=abc"
        assert svc._config.sender == "sender@example.com"

    def test_defaults_sender_when_not_set(self):
        with patch.dict("os.environ", {
            "AZURE_COMMUNICATION_CONNECTION_STRING": "endpoint=test;key=abc",
        }, clear=False):
            import os
            os.environ.pop("ACS_SENDER_ADDRESS", None)
            from api.services.notification_service import NotificationService
            svc = NotificationService()
        assert "azurecomm.net" in svc._config.sender


class TestNotificationServiceIsConfigured:
    def test_configured_when_conn_str_set(self):
        with patch.dict("os.environ", {
            "AZURE_COMMUNICATION_CONNECTION_STRING": "endpoint=real;key=123",
        }):
            from api.services.notification_service import NotificationService
            svc = NotificationService()
        assert svc.is_configured() is True

    def test_not_configured_when_conn_str_empty(self):
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("AZURE_COMMUNICATION_CONNECTION_STRING", None)
            from api.services.notification_service import NotificationService
            svc = NotificationService()
        assert svc.is_configured() is False

    def test_not_configured_when_placeholder_value(self):
        with patch.dict("os.environ", {
            "AZURE_COMMUNICATION_CONNECTION_STRING": "your_connection_string_here",
        }):
            from api.services.notification_service import NotificationService
            svc = NotificationService()
        assert svc.is_configured() is False


class TestNotificationServiceSendEmail:
    def test_send_email_returns_false_when_not_configured(self):
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("AZURE_COMMUNICATION_CONNECTION_STRING", None)
            from api.services.notification_service import NotificationService
            svc = NotificationService()
        result = svc.send_email("to@example.com", "subject", "<p>body</p>")
        assert result is False

    def test_send_sla_generated_returns_false_when_not_configured(self):
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("AZURE_COMMUNICATION_CONNECTION_STRING", None)
            from api.services.notification_service import NotificationService
            svc = NotificationService()
        result = svc.send_sla_generated("to@example.com", "Client AS")
        assert result is False


class TestNotificationServicePortExport:
    def test_notification_port_is_exported(self):
        from api.services.notification_service import NotificationPort
        assert NotificationPort is not None

    def test_notification_service_is_exported(self):
        from api.services.notification_service import NotificationService
        assert NotificationService is not None
