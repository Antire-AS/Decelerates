"""Shared PDF infrastructure — colour constants, _safe(), _section_title()."""

from typing import Any
import logging

logger = logging.getLogger(__name__)


# ── Forsikringstilbud colour palette ─────────────────────────────────────────
_DARK_BLUE = (20, 50, 120)
_MID_BLUE = (50, 90, 170)
_LIGHT_BLUE = (220, 230, 250)
_MUST_RED = (200, 50, 50)
_REC_ORG = (220, 100, 30)
_OPT_GRY = (100, 100, 100)


def _safe(s: Any) -> str:
    """Sanitize text for fpdf2 latin-1 Helvetica font — replace non-latin-1 chars."""
    if not s:
        return ""
    return (
        str(s)
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2026", "...")
        .replace("\u00b0", " ")
        .encode("latin-1", errors="replace")
        .decode("latin-1")
    )


def _section_title(pdf: Any, title: str) -> None:
    pdf.set_font("Helvetica", "B", 13)
    pdf.ln(6)
    pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(0, 0, 0)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 11)
