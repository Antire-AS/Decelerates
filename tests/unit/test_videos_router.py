"""Unit tests for api/routers/videos.py — video upload, list, and stream endpoints.

Uses a minimal FastAPI app with the router mounted; BlobStorageService is
patched — no real Azure Blob Storage or network required.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Stub heavy transitive deps before any api.* import
sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.dependencies import get_db
from api.routers.videos import router


# -- App fixture ---------------------------------------------------------------

_app = FastAPI()
_app.include_router(router)


@pytest.fixture
def client():
    _app.dependency_overrides[get_db] = lambda: MagicMock()
    yield TestClient(_app)
    _app.dependency_overrides.clear()


# -- POST /videos/upload -------------------------------------------------------


@patch("api.routers.videos.BlobStorageService")
def test_upload_video_success(mock_cls, client):
    svc = mock_cls.return_value
    svc.is_configured.return_value = True
    svc.upload.return_value = "https://blob/video.mp4"
    resp = client.post(
        "/videos/upload", files={"file": ("test.mp4", b"\x00" * 10, "video/mp4")}
    )
    assert resp.status_code == 200
    assert resp.json()["filename"] == "test.mp4"


@patch("api.routers.videos.BlobStorageService")
def test_upload_rejects_unsupported_type(mock_cls, client):
    resp = client.post(
        "/videos/upload", files={"file": ("test.txt", b"hello", "text/plain")}
    )
    assert resp.status_code == 400


@patch("api.routers.videos.BlobStorageService")
def test_upload_rejects_when_blob_not_configured(mock_cls, client):
    svc = mock_cls.return_value
    svc.is_configured.return_value = False
    resp = client.post(
        "/videos/upload", files={"file": ("v.mp4", b"\x00", "video/mp4")}
    )
    assert resp.status_code == 503


@patch("api.routers.videos.BlobStorageService")
def test_upload_returns_502_when_upload_fails(mock_cls, client):
    svc = mock_cls.return_value
    svc.is_configured.return_value = True
    svc.upload.return_value = None
    resp = client.post(
        "/videos/upload", files={"file": ("v.mp4", b"\x00", "video/mp4")}
    )
    assert resp.status_code == 502


# -- GET /videos ---------------------------------------------------------------


@patch("api.routers.videos.BlobStorageService")
def test_list_videos_returns_empty_when_not_configured(mock_cls, client):
    svc = mock_cls.return_value
    svc.is_configured.return_value = False
    resp = client.get("/videos")
    assert resp.status_code == 200
    assert resp.json() == []


@patch("api.routers.videos.BlobStorageService")
def test_list_videos_returns_mp4_entries(mock_cls, client):
    svc = mock_cls.return_value
    svc.is_configured.return_value = True
    svc.list_blobs.return_value = ["demo_fast.mp4"]
    svc.generate_sas_url.return_value = "https://blob/demo_fast.mp4?sas=1"
    svc.download_json.return_value = None
    resp = client.get("/videos")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@patch("api.routers.videos.BlobStorageService")
def test_list_videos_prefers_fast_over_subs(mock_cls, client):
    svc = mock_cls.return_value
    svc.is_configured.return_value = True
    svc.list_blobs.return_value = ["ffs080524_subs.mp4", "ffs080524_fast.mp4"]
    svc.generate_sas_url.return_value = "https://blob/url?sas=1"
    svc.download_json.return_value = None
    resp = client.get("/videos")
    body = resp.json()
    assert len(body) == 1
    assert "_fast" in body[0]["blob_name"]


# -- GET /videos/stream --------------------------------------------------------


@patch("api.routers.videos.BlobStorageService")
def test_stream_video_returns_404_when_blob_missing(mock_cls, client):
    svc = mock_cls.return_value
    svc.is_configured.return_value = True
    svc.get_blob_size.return_value = None
    resp = client.get("/videos/stream", params={"blob": "missing.mp4"})
    assert resp.status_code == 404


@patch("api.routers.videos.BlobStorageService")
def test_stream_video_returns_503_when_not_configured(mock_cls, client):
    svc = mock_cls.return_value
    svc.is_configured.return_value = False
    resp = client.get("/videos/stream", params={"blob": "test.mp4"})
    assert resp.status_code == 503


@patch("api.routers.videos.BlobStorageService")
def test_stream_video_full_response(mock_cls, client):
    svc = mock_cls.return_value
    svc.is_configured.return_value = True
    svc.get_blob_size.return_value = 1000
    svc.stream_range.return_value = iter([b"\x00" * 1000])
    resp = client.get("/videos/stream", params={"blob": "test.mp4"})
    assert resp.status_code == 200
    assert resp.headers["content-length"] == "1000"


@patch("api.routers.videos.BlobStorageService")
def test_stream_video_range_request(mock_cls, client):
    svc = mock_cls.return_value
    svc.is_configured.return_value = True
    svc.get_blob_size.return_value = 5000
    svc.stream_range.return_value = iter([b"\x00" * 500])
    resp = client.get(
        "/videos/stream", params={"blob": "v.mp4"}, headers={"range": "bytes=0-499"}
    )
    assert resp.status_code == 206
    assert "Content-Range" in resp.headers
