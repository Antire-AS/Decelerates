"""Backward-compatible wrapper around AzureBlobStorageAdapter.

Existing code calls BlobStorageService() with no arguments. This wrapper reads
AZURE_BLOB_ENDPOINT from the environment so legacy callers continue to work
during the Phase 1 → Phase 2 migration.

New code should resolve BlobStoragePort from the DI container instead:
    from api.container import resolve
    from api.ports.driven.blob_storage_port import BlobStoragePort
    blob = resolve(BlobStoragePort)
"""
import os

from api.adapters.blob_storage_adapter import AzureBlobStorageAdapter, BlobStorageConfig
from api.ports.driven.blob_storage_port import BlobStoragePort


class BlobStorageService(AzureBlobStorageAdapter):
    """Legacy no-arg constructor — reads AZURE_BLOB_ENDPOINT from environment."""

    def __init__(self) -> None:  # antire-cq: exception-init-body
        super().__init__(BlobStorageConfig(endpoint=os.getenv("AZURE_BLOB_ENDPOINT")))


__all__ = ["BlobStorageService", "BlobStoragePort"]
