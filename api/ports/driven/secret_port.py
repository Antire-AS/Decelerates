"""Abstract port for secret retrieval — decouples business logic from secret store."""

from abc import ABC, abstractmethod
from typing import Optional


class SecretPort(ABC):
    @abstractmethod
    def get_secret(self, name: str) -> Optional[str]:
        """Retrieve a secret by name. Returns None if not found."""

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if the secret backend is available."""
