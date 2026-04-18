"""Azure Key Vault secret adapter — retrieves secrets with fallback to env vars.

In production: reads from Azure Key Vault using DefaultAzureCredential.
In development: falls back to os.getenv() when AZURE_KEYVAULT_URL is not set.
"""

import logging
import os
from dataclasses import dataclass
from typing import Optional

from api.ports.driven.secret_port import SecretPort

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SecretConfig:
    vault_url: Optional[str] = None  # e.g. "https://kv-broker-prod.vault.azure.net"


class KeyVaultSecretAdapter(SecretPort):
    """Reads secrets from Azure Key Vault with os.getenv() fallback."""

    def __init__(self, config: SecretConfig):
        self._config = config
        self._client = None
        if config.vault_url:
            try:
                from azure.identity import DefaultAzureCredential
                from azure.keyvault.secrets import SecretClient

                self._client = SecretClient(
                    vault_url=config.vault_url,
                    credential=DefaultAzureCredential(),
                )
                logger.info("Key Vault connected: %s", config.vault_url)
            except Exception as exc:
                logger.warning(
                    "Key Vault init failed — falling back to env vars: %s", exc
                )

    def is_configured(self) -> bool:
        return self._client is not None

    def get_secret(self, name: str) -> Optional[str]:
        """Try Key Vault first, then fall back to env var.

        Key Vault secret names use hyphens (azure-foundry-api-key),
        env vars use underscores (AZURE_FOUNDRY_API_KEY). We try both.
        """
        if self._client:
            try:
                # Key Vault names: lowercase with hyphens
                kv_name = name.lower().replace("_", "-")
                secret = self._client.get_secret(kv_name)
                if secret and secret.value:
                    return secret.value
            except Exception:
                pass  # Fall through to env var

        # Fallback: os.getenv() (always works in dev)
        return os.getenv(name)


class EnvOnlySecretAdapter(SecretPort):
    """Development-only adapter — reads all secrets from environment variables."""

    def is_configured(self) -> bool:
        return True

    def get_secret(self, name: str) -> Optional[str]:
        return os.getenv(name)
