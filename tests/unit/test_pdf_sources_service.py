"""Unit tests for api/services/pdf_sources.py — PdfSourcesService.

Pure static tests — uses MagicMock DB; no real infrastructure required.
"""
import sys
from unittest.mock import MagicMock, patch

import pytest

# Stub api.services.pdf_background before importing pdf_sources to avoid
# playwright / heavy-dep import when upsert_pdf_source calls _upload_pdf_to_blob.
_pdf_bg_stub = MagicMock()
if "api.services.pdf_background" not in sys.modules:
    sys.modules["api.services.pdf_background"] = _pdf_bg_stub

from api.db import CompanyHistory, CompanyPdfSource, InsuranceDocument
from api.services.pdf_sources import (
    PdfSourcesService,
    delete_history_year,
    save_insurance_document,
    upsert_pdf_source,
)


def _mock_db():
    return MagicMock()


# ── PdfSourcesService.upsert_pdf_source ───────────────────────────────────────

def test_upsert_pdf_source_creates_new_row_when_not_found():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    _pdf_bg_stub._upload_pdf_to_blob.return_value = None

    PdfSourcesService(db).upsert_pdf_source("123456789", 2024, "http://example.com/r.pdf", "Årsrapport 2024")

    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_upsert_pdf_source_new_row_sets_orgnr_and_year():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    _pdf_bg_stub._upload_pdf_to_blob.return_value = None

    PdfSourcesService(db).upsert_pdf_source("111222333", 2022, "http://t.com/a.pdf", "Label")

    added = db.add.call_args[0][0]
    assert added.orgnr == "111222333"
    assert added.year == 2022


def test_upsert_pdf_source_updates_existing_row():
    existing = MagicMock(spec=CompanyPdfSource)
    existing.blob_url = "https://blob.example.com/existing.pdf"
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = existing

    PdfSourcesService(db).upsert_pdf_source("123456789", 2023, "http://new.com/r.pdf", "Updated")

    assert existing.pdf_url == "http://new.com/r.pdf"
    assert existing.label == "Updated"
    db.add.assert_not_called()
    db.commit.assert_called_once()


def test_upsert_pdf_source_sets_added_at():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    _pdf_bg_stub._upload_pdf_to_blob.return_value = None

    PdfSourcesService(db).upsert_pdf_source("123", 2024, "http://u.com/r.pdf", "lbl")

    added = db.add.call_args[0][0]
    assert added.added_at is not None


def test_upsert_pdf_source_skips_blob_upload_when_blob_url_already_set():
    existing = MagicMock(spec=CompanyPdfSource)
    existing.blob_url = "https://blob.example.com/already-stored.pdf"
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = existing

    _pdf_bg_stub._upload_pdf_to_blob.reset_mock()
    PdfSourcesService(db).upsert_pdf_source("123", 2022, "http://new.com/r.pdf", "label")

    _pdf_bg_stub._upload_pdf_to_blob.assert_not_called()


def test_upsert_pdf_source_commits():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    _pdf_bg_stub._upload_pdf_to_blob.return_value = None

    PdfSourcesService(db).upsert_pdf_source("123", 2024, "http://url.com/r.pdf", "lbl")

    db.commit.assert_called_once()


# ── PdfSourcesService.save_insurance_document ─────────────────────────────────

def test_save_insurance_document_adds_to_db():
    db = _mock_db()
    PdfSourcesService(db).save_insurance_document("123456789", "Test AS", "offer.pdf", b"pdf bytes")
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_save_insurance_document_title_contains_company_name():
    db = _mock_db()
    PdfSourcesService(db).save_insurance_document("123456789", "Firma AS", "f.pdf", b"bytes")
    added = db.add.call_args[0][0]
    assert "Firma AS" in added.title


def test_save_insurance_document_sets_orgnr():
    db = _mock_db()
    PdfSourcesService(db).save_insurance_document("987654321", "Navn", "f.pdf", b"bytes")
    added = db.add.call_args[0][0]
    assert added.orgnr == "987654321"


def test_save_insurance_document_sets_category_anbefaling():
    db = _mock_db()
    PdfSourcesService(db).save_insurance_document("123", "Navn", "f.pdf", b"bytes")
    added = db.add.call_args[0][0]
    assert added.category == "anbefaling"


def test_save_insurance_document_sets_insurer_ai_generert():
    db = _mock_db()
    PdfSourcesService(db).save_insurance_document("123", "Navn", "f.pdf", b"bytes")
    added = db.add.call_args[0][0]
    assert added.insurer == "AI-generert"


def test_save_insurance_document_stores_pdf_bytes():
    db = _mock_db()
    pdf = b"PDF bytes content here"
    PdfSourcesService(db).save_insurance_document("123", "Navn", "f.pdf", pdf)
    added = db.add.call_args[0][0]
    assert added.pdf_content == pdf


def test_save_insurance_document_sets_filename():
    db = _mock_db()
    PdfSourcesService(db).save_insurance_document("123", "Navn", "tilbud_2024.pdf", b"b")
    added = db.add.call_args[0][0]
    assert added.filename == "tilbud_2024.pdf"


def test_save_insurance_document_sets_period_aktiv():
    db = _mock_db()
    PdfSourcesService(db).save_insurance_document("123", "Navn", "f.pdf", b"b")
    added = db.add.call_args[0][0]
    assert added.period == "aktiv"


# ── PdfSourcesService.delete_history_year ─────────────────────────────────────

def test_delete_history_year_returns_deleted_count():
    db = _mock_db()
    db.query.return_value.filter.return_value.delete.return_value = 5
    count = PdfSourcesService(db).delete_history_year("123456789")
    assert count == 5


def test_delete_history_year_commits():
    db = _mock_db()
    db.query.return_value.filter.return_value.delete.return_value = 0
    PdfSourcesService(db).delete_history_year("123")
    db.commit.assert_called_once()


def test_delete_history_year_returns_zero_when_no_rows():
    db = _mock_db()
    db.query.return_value.filter.return_value.delete.return_value = 0
    count = PdfSourcesService(db).delete_history_year("999999999")
    assert count == 0


# ── Module-level backward-compat wrappers ─────────────────────────────────────

def test_module_upsert_pdf_source_delegates_to_service():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    _pdf_bg_stub._upload_pdf_to_blob.return_value = None

    upsert_pdf_source("123", 2024, "http://u.com/r.pdf", "lbl", db)

    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_module_save_insurance_document_delegates_to_service():
    db = _mock_db()
    save_insurance_document("123", "Navn", "f.pdf", b"bytes", db)
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_module_delete_history_year_delegates_to_service():
    db = _mock_db()
    db.query.return_value.filter.return_value.delete.return_value = 3
    count = delete_history_year("123", db)
    assert count == 3
