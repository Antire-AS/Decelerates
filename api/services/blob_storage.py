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

    def list_blobs(self, container: str) -> list:
        """Return a list of all blob names in a container."""
        if not self.is_configured() or self._client is None:
            return []
        try:
            return [b.name for b in self._client.get_container_client(container).list_blobs()]
        except Exception:
            return []

    def generate_sas_url(self, container: str, blob_name: str, hours: int = 2) -> Optional[str]:
        """Generate a user-delegation SAS URL valid for `hours`. Requires Storage Blob Delegator role."""
        if not self.is_configured() or self._client is None:
            return None
        try:
            from datetime import datetime, timedelta, timezone
            from azure.storage.blob import generate_blob_sas, BlobSasPermissions
            now = datetime.now(timezone.utc)
            expiry = now + timedelta(hours=hours)
            udk = self._client.get_user_delegation_key(
                key_start_time=now - timedelta(minutes=5), key_expiry_time=expiry
            )
            endpoint = _blob_endpoint() or ""
            account_name = endpoint.split("//")[-1].split(".")[0]
            token = generate_blob_sas(
                account_name=account_name,
                container_name=container,
                blob_name=blob_name,
                user_delegation_key=udk,
                permission=BlobSasPermissions(read=True),
                expiry=expiry,
            )
            return f"{endpoint}/{container}/{blob_name}?{token}"
        except Exception:
            return None

    def download_json(self, container: str, blob_name: str) -> Optional[dict]:
        """Download and JSON-parse a blob. Returns None if not found or not valid JSON."""
        data = self.download(container, blob_name)
        if not data:
            return None
        try:
            import json
            return json.loads(data.decode("utf-8"))
        except Exception:
            return None

    def get_blob_size(self, container: str, blob_name: str) -> Optional[int]:
        """Return the byte size of a blob, or None if not found."""
        if not self.is_configured() or self._client is None:
            return None
        try:
            return self._client.get_blob_client(
                container=container, blob=blob_name
            ).get_blob_properties().size
        except Exception:
            return None

    def stream_range(self, container: str, blob_name: str, offset: int = 0, length: Optional[int] = None):
        """Yield byte chunks of a blob range. Returns None on failure."""
        if not self.is_configured() or self._client is None:
            return None
        try:
            blob = self._client.get_blob_client(container=container, blob=blob_name)
            kw: dict = {"offset": offset}
            if length is not None:
                kw["length"] = length
            return blob.download_blob(**kw).chunks()
        except Exception:
            return None
