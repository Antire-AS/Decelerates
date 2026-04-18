"""Port (driven) — abstract interface for file / blob storage."""

from abc import ABC, abstractmethod
from typing import Optional


class BlobStoragePort(ABC):
    @abstractmethod
    def is_configured(self) -> bool: ...

    @abstractmethod
    def upload(self, container: str, blob_name: str, data: bytes) -> Optional[str]: ...

    @abstractmethod
    def download(self, container: str, blob_name: str) -> Optional[bytes]: ...

    @abstractmethod
    def delete(self, container: str, blob_name: str) -> bool: ...

    @abstractmethod
    def list_blobs(self, container: str) -> list[str]: ...

    @abstractmethod
    def generate_sas_url(
        self, container: str, blob_name: str, hours: int = 2
    ) -> Optional[str]: ...

    @abstractmethod
    def download_json(self, container: str, blob_name: str) -> Optional[dict]: ...

    @abstractmethod
    def get_blob_size(self, container: str, blob_name: str) -> Optional[int]: ...

    @abstractmethod
    def stream_range(
        self,
        container: str,
        blob_name: str,
        offset: int = 0,
        length: Optional[int] = None,
    ): ...
