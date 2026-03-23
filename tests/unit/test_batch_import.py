"""Unit tests for the CSV batch import orgnr parser.

Pure static tests — no DB, no network, no API keys.
"""
import io

import pytest

from api.routers.portfolio_router import _parse_csv_orgnrs


def _csv(content: str) -> bytes:
    return content.encode("utf-8")


# ── Named orgnr column ────────────────────────────────────────────────────────

def test_named_orgnr_column():
    csv_bytes = _csv("orgnr\n984851006\n995568217\n")
    valid, invalid = _parse_csv_orgnrs(csv_bytes)
    assert valid == ["984851006", "995568217"]
    assert invalid == []


def test_column_name_case_insensitive():
    csv_bytes = _csv("ORGNR\n984851006\n")
    valid, invalid = _parse_csv_orgnrs(csv_bytes)
    assert "984851006" in valid


def test_column_with_orgnr_substring():
    csv_bytes = _csv("company_orgnr,name\n984851006,DNB\n")
    valid, invalid = _parse_csv_orgnrs(csv_bytes)
    assert "984851006" in valid


# ── No header fallback (first column) ─────────────────────────────────────────

def test_no_header_first_column():
    csv_bytes = _csv("984851006\n995568217\n")
    valid, invalid = _parse_csv_orgnrs(csv_bytes)
    assert "984851006" in valid
    assert "995568217" in valid


# ── Validation ────────────────────────────────────────────────────────────────

def test_invalid_orgnr_too_short():
    csv_bytes = _csv("orgnr\n12345\n984851006\n")
    valid, invalid = _parse_csv_orgnrs(csv_bytes)
    assert "984851006" in valid
    assert "12345" in invalid


def test_invalid_orgnr_non_numeric():
    csv_bytes = _csv("orgnr\nABC123456\n984851006\n")
    valid, invalid = _parse_csv_orgnrs(csv_bytes)
    assert "ABC123456" in invalid


def test_empty_rows_skipped():
    csv_bytes = _csv("orgnr\n984851006\n\n995568217\n")
    valid, invalid = _parse_csv_orgnrs(csv_bytes)
    assert len(valid) == 2


def test_deduplication():
    csv_bytes = _csv("orgnr\n984851006\n984851006\n984851006\n")
    valid, _ = _parse_csv_orgnrs(csv_bytes)
    assert valid.count("984851006") == 1


# ── Edge cases ────────────────────────────────────────────────────────────────

def test_empty_file():
    valid, invalid = _parse_csv_orgnrs(_csv(""))
    assert valid == []
    assert invalid == []


def test_whitespace_trimmed():
    csv_bytes = _csv("orgnr\n  984851006  \n")
    valid, _ = _parse_csv_orgnrs(csv_bytes)
    assert "984851006" in valid


def test_mixed_valid_and_invalid():
    csv_bytes = _csv("orgnr\n984851006\nbadvalue\n995568217\n1234\n")
    valid, invalid = _parse_csv_orgnrs(csv_bytes)
    assert "984851006" in valid
    assert "995568217" in valid
    assert "badvalue" in invalid
    assert "1234" in invalid
