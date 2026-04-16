"""Backward-compatible wrapper around AzureEmailNotificationAdapter.

New code should resolve NotificationPort from the DI container:
    from api.container import resolve
    from api.ports.driven.notification_port import NotificationPort
    notification = resolve(NotificationPort)
"""
import os

from api.adapters.notification_adapter import (
    AzureEmailNotificationAdapter,
    NotificationConfig,
    _DEFAULT_SENDER,
)
from api.ports.driven.notification_port import NotificationPort
import logging

logger = logging.getLogger(__name__)



class NotificationService(AzureEmailNotificationAdapter):
    """Legacy no-arg constructor — reads ACS env vars from environment."""

    def __init__(self) -> None:  # antire-cq: exception-init-body
        super().__init__(NotificationConfig(
            conn_str=os.getenv("AZURE_COMMUNICATION_CONNECTION_STRING"),
            sender=os.getenv("ACS_SENDER_ADDRESS", _DEFAULT_SENDER),
        ))


__all__ = ["NotificationService", "NotificationPort"]
