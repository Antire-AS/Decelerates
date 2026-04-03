"""Recommendation letter PDF generation."""
from datetime import date
from typing import Any, List, Optional

from fpdf import FPDF

from api.services.pdf_base import _safe, _section_title, _DARK_BLUE, _LIGHT_BLUE, _MID_BLUE


def _fmt_nok(v: Any) -> str:
    if v is None:
        return "–"
    try:
        return f"{float(v):,.0f} kr".replace(",", " ")
    except (TypeError, ValueError):
        return str(v)


def generate_recommendation_pdf(
    orgnr: str,
    company_name: str,
    recommended_insurer: str,
    rationale_text: str,
    submissions: List[dict],
    broker: dict,
    created_by_email: Optional[str] = None,
) -> bytes:
    """Generate a formal recommendation letter PDF."""
    pdf = FPDF()
    pdf.set_margins(20, 20, 20)
    pdf.add_page()

    # ── Header bar ────────────────────────────────────────────────────────────
    pdf.set_fill_color(*_DARK_BLUE)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 13, _safe(broker.get("firm_name", "Forsikringsmegler")), fill=True, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 7, "Forsikringsanbefaling", fill=True, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(8)

    # ── Metadata block ────────────────────────────────────────────────────────
    pdf.set_fill_color(*_LIGHT_BLUE)
    pdf.set_font("Helvetica", "", 10)
    meta_rows = [
        ("Klient",        f"{_safe(company_name)}  (org.nr {orgnr})"),
        ("Dato",          date.today().isoformat()),
        ("Utarbeidet av", _safe(created_by_email or broker.get("contact_name", ""))),
        ("Megler",        _safe(broker.get("firm_name", ""))),
    ]
    for label, value in meta_rows:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(42, 6, label + ":", fill=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 6, value, fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)

    # ── Recommendation box ────────────────────────────────────────────────────
    pdf.set_fill_color(230, 245, 230)
    pdf.set_draw_color(60, 140, 60)
    pdf.set_line_width(0.5)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Anbefalt forsikringsselskap", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(20, 100, 20)
    pdf.cell(0, 10, _safe(recommended_insurer), fill=True, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(8)

    # ── Rationale ─────────────────────────────────────────────────────────────
    _section_title(pdf, "Begrunnelse")
    pdf.set_font("Helvetica", "", 10)
    for paragraph in (rationale_text or "").split("\n\n"):
        stripped = paragraph.strip()
        if stripped:
            pdf.multi_cell(0, 5.5, _safe(stripped))
            pdf.ln(3)

    # ── Submissions comparison table ──────────────────────────────────────────
    if submissions:
        pdf.ln(4)
        _section_title(pdf, "Innhentede tilbud — sammenligning")

        col_w = [48, 38, 32, 22, 30]
        headers = ["Forsikringsselskap", "Produkt", "Premie/år", "Status", "Dato"]
        status_no = {
            "quoted":    "Tilbud mottatt",
            "declined":  "Avslått",
            "pending":   "Avventer",
            "withdrawn": "Trukket",
        }

        pdf.set_fill_color(*_LIGHT_BLUE)
        pdf.set_font("Helvetica", "B", 8)
        for w, h in zip(col_w, headers):
            pdf.cell(w, 7, h, border=1, fill=True)
        pdf.ln()

        pdf.set_font("Helvetica", "", 8)
        fill = False
        for s in submissions:
            is_rec = s.get("insurer_name", "") == recommended_insurer
            if is_rec:
                pdf.set_fill_color(230, 245, 230)
            else:
                pdf.set_fill_color(248, 248, 248) if fill else pdf.set_fill_color(255, 255, 255)

            row_vals = [
                _safe(s.get("insurer_name", "–")),
                _safe(s.get("product_type", "–")),
                _fmt_nok(s.get("premium_offered_nok")),
                status_no.get(s.get("status", ""), s.get("status", "–")),
                _safe(s.get("requested_at", "") or "–"),
            ]
            for w, val in zip(col_w, row_vals):
                pdf.set_font("Helvetica", "B" if is_rec else "", 8)
                pdf.cell(w, 6, val[:24] if len(val) > 24 else val, border=1, fill=True)
            pdf.ln()
            fill = not fill

    # ── Signature block ───────────────────────────────────────────────────────
    pdf.ln(12)
    _section_title(pdf, "Signatur")
    pdf.set_font("Helvetica", "", 10)
    sig_rows = [
        ("Megler",    _safe(broker.get("firm_name", ""))),
        ("Kontakt",   _safe(broker.get("contact_name", ""))),
        ("E-post",    _safe(broker.get("contact_email", ""))),
        ("Telefon",   _safe(broker.get("contact_phone", ""))),
    ]
    for label, value in sig_rows:
        if value:
            pdf.cell(40, 6, f"{label}:")
            pdf.cell(0, 6, value, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(14)
    pdf.set_draw_color(0, 0, 0)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + 70, pdf.get_y())
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 5, "Signatur megler / dato", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(14)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + 70, pdf.get_y())
    pdf.ln(2)
    pdf.cell(0, 5, "Signatur klient / dato", new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())
