"""Unit tests for api/adapters/blob_storage_adapter.py — AzureBlobStorageAdapter.

All Azure SDK calls are mocked; conftest.py already stubs azure.storage.blob.
"""
import os
from unittest.mock import MagicMock, patch


from api.adapters.blob_storage_adapter import AzureBlobStorageAdapter, BlobStorageConfig
from api.services.blob_storage import BlobStorageService


def _adapter(endpoint="https://test.blob.core.windows.net"):
    """Return a configured adapter whose _client is a MagicMock."""
    return AzureBlobStorageAdapter(BlobStorageConfig(endpoint=endpoint))


def _unconfigured():
    return AzureBlobStorageAdapter(BlobStorageConfig(endpoint=None))


# ── is_configured ─────────────────────────────────────────────────────────────

def test_is_configured_true_when_endpoint_set():
    assert _adapter().is_configured() is True


def test_is_configured_false_when_no_endpoint():
    assert _unconfigured().is_configured() is False


# ── upload ────────────────────────────────────────────────────────────────────

def test_upload_returns_none_when_not_configured():
    assert _unconfigured().upload("container", "blob.pdf", b"data") is None


def test_upload_returns_blob_url_on_success():
    adapter = _adapter()
    mock_blob = MagicMock()
    mock_blob.url = "https://test.blob.core.windows.net/container/blob.pdf"
    adapter._client.get_blob_client.return_value = mock_blob
    result = adapter.upload("container", "blob.pdf", b"data")
    assert result == "https://test.blob.core.windows.net/container/blob.pdf"
    mock_blob.upload_blob.assert_called_once_with(b"data", overwrite=True)


def test_upload_returns_none_on_exception():
    adapter = _adapter()
    adapter._client.get_blob_client.side_effect = Exception("upload error")
    assert adapter.upload("container", "blob.pdf", b"data") is None


# ── download ──────────────────────────────────────────────────────────────────

def test_download_returns_none_when_not_configured():
    assert _unconfigured().download("container", "blob.pdf") is None


def test_download_returns_bytes_on_success():
    adapter = _adapter()
    mock_blob = MagicMock()
    mock_blob.download_blob.return_value.readall.return_value = b"pdf content"
    adapter._client.get_blob_client.return_value = mock_blob
    assert adapter.download("container", "blob.pdf") == b"pdf content"


def test_download_returns_none_on_exception():
    adapter = _adapter()
    adapter._client.get_blob_client.side_effect = Exception("not found")
    assert adapter.download("container", "blob.pdf") is None


# ── delete ────────────────────────────────────────────────────────────────────

def test_delete_returns_false_when_not_configured():
    assert _unconfigured().delete("container", "blob.pdf") is False


def test_delete_returns_true_on_success():
    adapter = _adapter()
    adapter._client.get_blob_client.return_value.delete_blob.return_value = None
    assert adapter.delete("container", "blob.pdf") is True


def test_delete_returns_false_on_exception():
    adapter = _adapter()
    adapter._client.get_blob_client.return_value.delete_blob.side_effect = Exception("not found")
    assert adapter.delete("container", "blob.pdf") is False


# ── list_blobs ────────────────────────────────────────────────────────────────

def test_list_blobs_returns_empty_when_not_configured():
    assert _unconfigured().list_blobs("container") == []


def test_list_blobs_returns_names():
    adapter = _adapter()
    b1, b2 = MagicMock(), MagicMock()
    b1.name, b2.name = "file1.pdf", "file2.json"
    adapter._client.get_container_client.return_value.list_blobs.return_value = [b1, b2]
    assert adapter.list_blobs("container") == ["file1.pdf", "file2.json"]


def test_list_blobs_returns_empty_on_exception():
    adapter = _adapter()
    adapter._client.get_container_client.side_effect = Exception("auth error")
    assert adapter.list_blobs("container") == []


# ── download_json ─────────────────────────────────────────────────────────────

def test_download_json_returns_none_when_download_fails():
    adapter = _adapter()
    with patch.object(adapter, "download", return_value=None):
        assert adapter.download_json("container", "data.json") is None


def test_download_json_parses_valid_json():
    adapter = _adapter()
    with patch.object(adapter, "download", return_value=b'{"key": "value", "num": 42}'):
        result = adapter.download_json("container", "data.json")
    assert result == {"key": "value", "num": 42}


def test_download_json_returns_none_on_invalid_json():
    adapter = _adapter()
    with patch.object(adapter, "download", return_value=b"not json {{"):
        assert adapter.download_json("container", "bad.json") is None


def test_download_json_parses_list():
    adapter = _adapter()
    with patch.object(adapter, "download", return_value=b'[{"a": 1}, {"b": 2}]'):
        result = adapter.download_json("container", "list.json")
    assert result == [{"a": 1}, {"b": 2}]


# ── get_blob_size ─────────────────────────────────────────────────────────────

def test_get_blob_size_returns_none_when_not_configured():
    assert _unconfigured().get_blob_size("container", "file.pdf") is None


def test_get_blob_size_returns_size():
    adapter = _adapter()
    props = MagicMock()
    props.size = 1_048_576
    adapter._client.get_blob_client.return_value.get_blob_properties.return_value = props
    assert adapter.get_blob_size("container", "file.pdf") == 1_048_576


def test_get_blob_size_returns_none_on_exception():
    adapter = _adapter()
    adapter._client.get_blob_client.side_effect = Exception("not found")
    assert adapter.get_blob_size("container", "file.pdf") is None


# ── stream_range ──────────────────────────────────────────────────────────────

def test_stream_range_returns_none_when_not_configured():
    assert _unconfigured().stream_range("container", "video.mp4") is None


def test_stream_range_returns_chunks_iterator():
    adapter = _adapter()
    mock_chunks = iter([b"chunk1", b"chunk2"])
    adapter._client.get_blob_client.return_value.download_blob.return_value.chunks.return_value = mock_chunks
    result = adapter.stream_range("container", "video.mp4", offset=0, length=1024)
    assert result is mock_chunks


def test_stream_range_passes_offset_and_length():
    adapter = _adapter()
    mock_blob_client = MagicMock()
    adapter._client.get_blob_client.return_value = mock_blob_client
    adapter.stream_range("container", "video.mp4", offset=512, length=2048)
    mock_blob_client.download_blob.assert_called_once_with(offset=512, length=2048)


def test_stream_range_omits_length_when_none():
    adapter = _adapter()
    mock_blob_client = MagicMock()
    adapter._client.get_blob_client.return_value = mock_blob_client
    adapter.stream_range("container", "video.mp4", offset=0)
    mock_blob_client.download_blob.assert_called_once_with(offset=0)


def test_stream_range_returns_none_on_exception():
    adapter = _adapter()
    adapter._client.get_blob_client.side_effect = Exception("error")
    assert adapter.stream_range("container", "video.mp4") is None


# ── BlobStorageService wrapper ────────────────────────────────────────────────

def test_blob_storage_service_reads_endpoint_from_env():
    with patch.dict(os.environ, {"AZURE_BLOB_ENDPOINT": "https://sttest.blob.core.windows.net"}):
        svc = BlobStorageService()
    assert svc.is_configured() is True


def test_blob_storage_service_not_configured_when_no_env():
    env = {k: v for k, v in os.environ.items() if k != "AZURE_BLOB_ENDPOINT"}
    with patch.dict(os.environ, env, clear=True):
        svc = BlobStorageService()
    assert svc.is_configured() is False
