"""Dependency injection container — punq-based wiring of ports to adapters.

Usage
-----
Call ``configure(config)`` once at application startup (in ``api/main.py``).
Routers resolve ports via ``Depends(_get_<port>)`` factory functions.

    from api.container import resolve
    from api.ports.driven.notification_port import NotificationPort

    def _get_notification() -> NotificationPort:
        return resolve(NotificationPort)  # type: ignore[return-value]
"""
from __future__ import annotations

from dataclasses import dataclass, field

import punq

from api.adapters.blob_storage_adapter import AzureBlobStorageAdapter, BlobStorageConfig
from api.adapters.foundry_llm_adapter import FoundryConfig, FoundryLlmAdapter
from api.adapters.msgraph_email_adapter import MsGraphConfig, MsGraphEmailAdapter
from api.adapters.notification_adapter import AzureEmailNotificationAdapter, NotificationConfig
from api.adapters.secret_adapter import KeyVaultSecretAdapter, SecretConfig
from api.ports.driven.blob_storage_port import BlobStoragePort
from api.ports.driven.email_outbound_port import EmailOutboundPort
from api.ports.driven.llm_port import LlmPort
from api.ports.driven.notification_port import NotificationPort
from api.ports.driven.secret_port import SecretPort


@dataclass(frozen=True)
class AppConfig:
    blob: BlobStorageConfig = field(default_factory=BlobStorageConfig)
    notification: NotificationConfig = field(default_factory=NotificationConfig)
    msgraph: MsGraphConfig = field(default_factory=MsGraphConfig)
    foundry: FoundryConfig = field(default_factory=FoundryConfig)
    secret: SecretConfig = field(default_factory=SecretConfig)


class ContainerFactory:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self.container = punq.Container()

    def _make_blob_adapter(self) -> BlobStoragePort:
        return AzureBlobStorageAdapter(self._config.blob)

    def _make_notification_adapter(self) -> NotificationPort:
        return AzureEmailNotificationAdapter(self._config.notification)

    def _make_email_outbound_adapter(self) -> EmailOutboundPort:
        return MsGraphEmailAdapter(self._config.msgraph)

    def _make_foundry_llm_adapter(self) -> LlmPort:
        return FoundryLlmAdapter(self._config.foundry)

    def _make_secret_adapter(self) -> SecretPort:
        return KeyVaultSecretAdapter(self._config.secret)

    def build(self) -> punq.Container:
        self.container.register(
            BlobStoragePort,
            factory=self._make_blob_adapter,
            scope=punq.Scope.singleton,
        )
        self.container.register(
            NotificationPort,
            factory=self._make_notification_adapter,
            scope=punq.Scope.singleton,
        )
        self.container.register(
            EmailOutboundPort,
            factory=self._make_email_outbound_adapter,
            scope=punq.Scope.singleton,
        )
        self.container.register(
            LlmPort,
            factory=self._make_foundry_llm_adapter,
            scope=punq.Scope.singleton,
        )
        self.container.register(
            SecretPort,
            factory=self._make_secret_adapter,
            scope=punq.Scope.singleton,
        )
        return self.container

    def __enter__(self) -> punq.Container:
        return self.build()

    def __exit__(self, *_) -> None:
        pass


# ── Module-level singleton ───────────────────────────────────────────────────

_container: punq.Container | None = None


def configure(config: AppConfig) -> None:
    """Build and store the DI container. Call once during application startup."""
    global _container
    with ContainerFactory(config) as c:
        _container = c


def resolve(port_type: type):
    """Resolve a registered port from the container."""
    if _container is None:
        raise RuntimeError("Container not configured — call container.configure() first")
    return _container.resolve(port_type)
