"""Certificate of Insurance (Forsikringsbevis / Dekningsoversikt) PDF generation."""
from datetime import date
from typing import Any, List

from fpdf import FPDF

from api.services.pdf_base import _safe, _section_title, _DARK_BLUE, _LIGHT_BLUE


def _fmt_nok(v: Any) -> str:
    if v is None:
        return "–"
    try:
        return f"{float(v):,.0f} kr".replace(",", " ")
    except (TypeError, ValueError):
        return str(v)


def generate_certificate_pdf(
    orgnr: str,
    company_name: str,
    policies: List[dict],
    broker: dict,
) -> bytes:
    """Generate a Forsikringsbevis PDF listing all active policies for a client."""
    pdf = FPDF()
    pdf.set_margins(20, 20, 20)
    pdf.add_page()

    # ── Header ────────────────────────────────────────────────────────────────
    pdf.set_fill_color(*_DARK_BLUE)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 14, "Forsikringsbevis", fill=True, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, "Dekningsoversikt", fill=True, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(6)

    # ── Client + broker block ─────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(90, 7, "Klient", new_x="RIGHT", new_y="TMARGIN")
    pdf.cell(0, 7, "Megler", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 10)
    client_lines = [_safe(company_name), f"Org.nr: {orgnr}"]
    broker_lines = [
        _safe(broker.get("firm_name", "")),
        _safe(broker.get("contact_name", "")),
        _safe(broker.get("contact_email", "")),
        _safe(broker.get("contact_phone", "")),
    ]
    for cl, bl in zip(client_lines + ["", ""], broker_lines + ["", ""]):
        if cl or bl:
            pdf.cell(90, 6, cl, new_x="RIGHT", new_y="TMARGIN")
            pdf.cell(0, 6, bl, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, f"Generert: {date.today().isoformat()}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(6)

    # ── Policy table ──────────────────────────────────────────────────────────
    _section_title(pdf, "Aktive forsikringer")

    # Column widths: product, insurer, policy_nr, coverage, premium, period
    col_w = [38, 32, 28, 28, 24, 20]
    headers = ["Produkt", "Forsikringsselskap", "Polisenr.", "Dekning", "Premie/år", "Utløper"]

    pdf.set_fill_color(*_LIGHT_BLUE)
    pdf.set_font("Helvetica", "B", 8)
    for w, h in zip(col_w, headers):
        pdf.cell(w, 7, h, border=1, fill=True)
    pdf.ln()

    pdf.set_font("Helvetica", "", 8)
    fill = False
    for p in policies:
        if p.get("status", "active") != "active":
            continue
        row = [
            _safe(p.get("product_type", "")),
            _safe(p.get("insurer", "")),
            _safe(p.get("policy_number", "") or "–"),
            _fmt_nok(p.get("coverage_amount_nok")),
            _fmt_nok(p.get("annual_premium_nok")),
            _safe(p.get("renewal_date", "") or "–"),
        ]
        pdf.set_fill_color(245, 247, 252) if fill else pdf.set_fill_color(255, 255, 255)
        for w, val in zip(col_w, row):
            pdf.cell(w, 6, val[:22] if len(val) > 22 else val, border=1, fill=True)
        pdf.ln()
        fill = not fill

    if not any(p.get("status", "active") == "active" for p in policies):
        pdf.set_font("Helvetica", "I", 9)
        pdf.cell(0, 8, "Ingen aktive forsikringer registrert.", new_x="LMARGIN", new_y="NEXT")

    # ── Footer disclaimer ─────────────────────────────────────────────────────
    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(140, 140, 140)
    pdf.multi_cell(
        0, 5,
        "Dette dokumentet er en oversikt generert av forsikringsmegler og er ikke et "
        "forsikringsbevis utstedt av forsikringsselskapet. For bindende dekningsinformasjon, "
        "se de enkelte forsikringsavtalene.",
    )

    return bytes(pdf.output())
