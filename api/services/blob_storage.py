"""Azure Blob Storage service — upload, download, and delete blobs."""
import os
from typing import Optional


def _blob_endpoint() -> Optional[str]:
    return os.getenv("AZURE_BLOB_ENDPOINT")


class BlobStorageService:
    """Wraps Azure Blob Storage using DefaultAzureCredential (managed identity)."""

    def __init__(self) -> None:
        self._client = None
        endpoint = _blob_endpoint()
        if endpoint:
            try:
                from azure.storage.blob import BlobServiceClient
                from azure.identity import DefaultAzureCredential
                self._client = BlobServiceClient(
                    account_url=endpoint,
                    credential=DefaultAzureCredential(),
                )
            except Exception:
                self._client = None

    def is_configured(self) -> bool:
        """Return True if the blob endpoint env var is set."""
        return bool(_blob_endpoint())

    def upload(self, container: str, blob_name: str, data: bytes) -> Optional[str]:
        """Upload bytes to a blob. Returns the blob URL, or None if not configured."""
        if not self.is_configured() or self._client is None:
            return None
        try:
            blob = self._client.get_blob_client(container=container, blob=blob_name)
            blob.upload_blob(data, overwrite=True)
            return blob.url
        except Exception:
            return None

    def download(self, container: str, blob_name: str) -> Optional[bytes]:
        """Download a blob and return its bytes, or None if not configured/found."""
        if not self.is_configured() or self._client is None:
            return None
        try:
            blob = self._client.get_blob_client(container=container, blob=blob_name)
            return blob.download_blob().readall()
        except Exception:
            return None

    def delete(self, container: str, blob_name: str) -> bool:
        """Delete a blob. Returns True on success, False otherwise."""
        if not self.is_configured() or self._client is None:
            return False
        try:
            blob = self._client.get_blob_client(container=container, blob=blob_name)
            blob.delete_blob()
            return True
        except Exception:
            return False
