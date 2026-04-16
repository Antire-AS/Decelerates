"""Unit tests for api/services/pdf_base.py — shared PDF utilities."""
import sys
from unittest.mock import MagicMock

sys.modules.setdefault("api.rag_chain", MagicMock())
sys.modules.setdefault("api.services.pdf_background", MagicMock())

import pytest

from api.services.pdf_base import (
    _safe,
    _section_title,
    _DARK_BLUE,
    _MID_BLUE,
    _LIGHT_BLUE,
    _MUST_RED,
    _REC_ORG,
    _OPT_GRY,
)


# ── _safe ────────────────────────────────────────────────────────────────────


class TestSafe:
    def test_empty_input_returns_empty(self):
        assert _safe("") == ""

    def test_none_input_returns_empty(self):
        assert _safe(None) == ""

    def test_plain_ascii_unchanged(self):
        assert _safe("Hello world") == "Hello world"

    def test_replaces_en_dash(self):
        assert _safe("2020\u20132024") == "2020-2024"

    def test_replaces_em_dash(self):
        assert _safe("foo\u2014bar") == "foo-bar"

    def test_replaces_smart_quotes(self):
        result = _safe("\u201cHello\u201d \u2018world\u2019")
        assert '"Hello"' in result
        assert "'world'" in result

    def test_replaces_ellipsis(self):
        assert _safe("wait\u2026") == "wait..."

    def test_replaces_degree_sign(self):
        assert _safe("90\u00b0") == "90 "

    def test_non_latin1_chars_replaced(self):
        # Chinese characters are not latin-1 encodable
        result = _safe("Hello \u4e16\u754c")
        assert "Hello" in result
        # Non-encodable chars become '?'
        assert "?" in result

    def test_integer_input_converted(self):
        assert _safe(42) == "42"


# ── _section_title ───────────────────────────────────────────────────────────


class TestSectionTitle:
    def test_calls_pdf_methods(self):
        pdf = MagicMock()
        pdf.l_margin = 10
        pdf.r_margin = 10
        pdf.w = 210
        pdf.get_y.return_value = 50.0

        _section_title(pdf, "Test Section")

        pdf.set_font.assert_any_call("Helvetica", "B", 13)
        pdf.cell.assert_called_once()
        pdf.line.assert_called_once()
        # Verify it resets font back to normal
        pdf.set_font.assert_any_call("Helvetica", "", 11)


# ── Color constants ──────────────────────────────────────────────────────────


class TestColorConstants:
    def test_dark_blue_is_rgb_tuple(self):
        assert isinstance(_DARK_BLUE, tuple)
        assert len(_DARK_BLUE) == 3
        assert all(0 <= c <= 255 for c in _DARK_BLUE)

    def test_mid_blue_is_rgb_tuple(self):
        assert isinstance(_MID_BLUE, tuple)
        assert len(_MID_BLUE) == 3

    def test_light_blue_is_rgb_tuple(self):
        assert isinstance(_LIGHT_BLUE, tuple)
        assert len(_LIGHT_BLUE) == 3

    def test_must_red_is_rgb_tuple(self):
        assert isinstance(_MUST_RED, tuple)
        assert len(_MUST_RED) == 3

    def test_rec_org_is_rgb_tuple(self):
        assert isinstance(_REC_ORG, tuple)
        assert len(_REC_ORG) == 3

    def test_opt_gry_is_rgb_tuple(self):
        assert isinstance(_OPT_GRY, tuple)
        assert len(_OPT_GRY) == 3
