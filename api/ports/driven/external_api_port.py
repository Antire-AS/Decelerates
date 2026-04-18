"""Abstract port for external API calls — BRREG, OpenSanctions, Kartverket, etc."""

from abc import ABC, abstractmethod
from typing import Optional


class ExternalApiPort(ABC):
    @abstractmethod
    def search(self, query: str, size: int = 10) -> list:
        """Search BRREG Enhetsregisteret."""

    @abstractmethod
    def fetch_enhet(self, orgnr: str) -> Optional[dict]:
        """Fetch a single company from BRREG."""

    @abstractmethod
    def fetch_regnskap(self, orgnr: str) -> Optional[dict]:
        """Fetch financial statements from BRREG Regnskapsregisteret."""

    @abstractmethod
    def pep_screen(self, name: str) -> Optional[dict]:
        """Screen a name against OpenSanctions PEP/sanctions lists."""
