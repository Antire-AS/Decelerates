"""Azure Blob Storage adapter — implements BlobStoragePort."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from api.ports.driven.blob_storage_port import BlobStoragePort

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BlobStorageConfig:
    endpoint: Optional[str] = None  # AZURE_BLOB_ENDPOINT


class AzureBlobStorageAdapter(BlobStoragePort):
    def __init__(self, config: BlobStorageConfig) -> None:
        self._config = config
        self._client = None
        if config.endpoint:
            try:
                from azure.identity import DefaultAzureCredential
                from azure.storage.blob import BlobServiceClient

                self._client = BlobServiceClient(
                    account_url=config.endpoint,
                    credential=DefaultAzureCredential(),
                )
            except Exception:
                self._client = None

    def is_configured(self) -> bool:
        return self._config.endpoint is not None

    def upload(self, container: str, blob_name: str, data: bytes) -> Optional[str]:
        if not self.is_configured() or self._client is None:
            return None
        try:
            blob = self._client.get_blob_client(container=container, blob=blob_name)
            blob.upload_blob(data, overwrite=True)
            return blob.url
        except Exception:
            return None

    def download(self, container: str, blob_name: str) -> Optional[bytes]:
        if not self.is_configured() or self._client is None:
            return None
        try:
            blob = self._client.get_blob_client(container=container, blob=blob_name)
            return blob.download_blob().readall()
        except Exception:
            return None

    def delete(self, container: str, blob_name: str) -> bool:
        if not self.is_configured() or self._client is None:
            return False
        try:
            self._client.get_blob_client(
                container=container, blob=blob_name
            ).delete_blob()
            return True
        except Exception:
            return False

    def list_blobs(self, container: str) -> list[str]:
        if not self.is_configured() or self._client is None:
            return []
        try:
            return [
                b.name
                for b in self._client.get_container_client(container).list_blobs()
            ]
        except Exception:
            return []

    def generate_sas_url(
        self, container: str, blob_name: str, hours: int = 2
    ) -> Optional[str]:
        if not self.is_configured() or self._client is None:
            return None
        try:
            from azure.storage.blob import BlobSasPermissions, generate_blob_sas

            now = datetime.now(timezone.utc)
            expiry = now + timedelta(hours=hours)
            udk = self._client.get_user_delegation_key(
                key_start_time=now - timedelta(minutes=5), key_expiry_time=expiry
            )
            endpoint = self._config.endpoint or ""
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
        data = self.download(container, blob_name)
        if not data:
            return None
        try:
            return json.loads(data.decode("utf-8"))
        except Exception:
            return None

    def get_blob_size(self, container: str, blob_name: str) -> Optional[int]:
        if not self.is_configured() or self._client is None:
            return None
        try:
            return (
                self._client.get_blob_client(container=container, blob=blob_name)
                .get_blob_properties()
                .size
            )
        except Exception:
            return None

    def stream_range(
        self,
        container: str,
        blob_name: str,
        offset: int = 0,
        length: Optional[int] = None,
    ):
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
