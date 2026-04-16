"""Portfolio PDF generation."""
import io
from datetime import date
from typing import Any

from fpdf import FPDF

from api.services.pdf_base import _safe, _section_title, _DARK_BLUE, _LIGHT_BLUE
import logging

logger = logging.getLogger(__name__)



def _portfolio_cover(pdf: Any, portfolio_name: str, broker: dict, generated_at: str) -> None:
    pdf.add_page()
    pdf.set_fill_color(*_DARK_BLUE)
    pdf.rect(0, 0, pdf.w, 60, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_y(18)
    pdf.cell(0, 10, _safe(broker.get("firm_name", "Forsikringsmegler")), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 13)
    pdf.cell(0, 8, "Portefoeljerapport", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(76)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, _safe(portfolio_name), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Generert: {generated_at}", align="C", new_x="LMARGIN", new_y="NEXT")
    if broker.get("contact_name"):
        pdf.cell(0, 8, _safe(f"Ansvarlig megler: {broker['contact_name']}"), align="C", new_x="LMARGIN", new_y="NEXT")


def _portfolio_risk_table(pdf: Any, companies: list) -> None:
    _section_title(pdf, "Selskapsoversikt og risiko")
    col_w = [55, 25, 28, 22, 28, 30]
    headers = ["Selskap", "Orgnr", "Omsetning", "Ansatte", "EK-andel", "Risikoscore"]
    pdf.set_fill_color(*_LIGHT_BLUE)
    pdf.set_font("Helvetica", "B", 9)
    for h, w in zip(headers, col_w):
        pdf.cell(w, 7, h, border=1, fill=True, align="C")
    pdf.ln()
    pdf.set_font("Helvetica", "", 9)
    for c in companies:
        score = c.get("risk_score")
        fill = False
        if score is not None:
            for lo, hi, color in [(0, 3, None), (4, 7, (255, 249, 196)),
                                   (8, 12, (255, 224, 178)), (13, 999, (255, 205, 210))]:
                if lo <= score <= hi:
                    if color:
                        pdf.set_fill_color(*color)
                        fill = True
                    break
        rev = c.get("omsetning") or c.get("sum_driftsinntekter")
        eq = c.get("egenkapitalandel") or c.get("equity_ratio")
        cells = [
            (_safe((c.get("navn") or "")[:28]), col_w[0], "L"),
            (_safe(c.get("orgnr", "")), col_w[1], "C"),
            (f"{rev/1e6:.0f} MNOK" if rev else "–", col_w[2], "R"),
            (str(c.get("antall_ansatte") or "–"), col_w[3], "C"),
            (f"{eq*100:.1f}%" if eq is not None else "–", col_w[4], "C"),
            (str(score) if score is not None else "–", col_w[5], "C"),
        ]
        for text, w, align in cells:
            pdf.cell(w, 6, text, border=1, fill=fill, align=align)
        pdf.set_fill_color(255, 255, 255)
        pdf.ln()


def _portfolio_alerts_section(pdf: Any, alerts: list) -> None:
    if not alerts:
        return
    _section_title(pdf, f"Vekstalerts ({len(alerts)})")
    _SEV_COLORS = {"Kritisk": (183, 28, 28), "Hoy": (230, 81, 0), "Moderat": (249, 168, 37)}
    col_w = [22, 52, 35, 65]
    headers = ["Alvorlighet", "Selskap", "Varselstype", "Detalj"]
    pdf.set_fill_color(*_LIGHT_BLUE)
    pdf.set_font("Helvetica", "B", 9)
    for h, w in zip(headers, col_w):
        pdf.cell(w, 7, h, border=1, fill=True, align="C")
    pdf.ln()
    pdf.set_font("Helvetica", "", 9)
    for a in alerts:
        sev = a.get("severity", "")
        color = _SEV_COLORS.get(sev.replace("ø", "o").replace("H\xf8y", "Hoy"), None)
        if color:
            pdf.set_fill_color(*color)
            pdf.set_text_color(255, 255, 255)
        cells = [
            (_safe(sev), col_w[0], "C"),
            (_safe((a.get("navn") or "")[:30]), col_w[1], "L"),
            (_safe(a.get("alert_type", "")), col_w[2], "L"),
            (_safe((a.get("detail") or "")[:50]), col_w[3], "L"),
        ]
        for text, w, align in cells:
            pdf.cell(w, 6, text, border=1, fill=bool(color), align=align)
        pdf.set_fill_color(255, 255, 255)
        pdf.set_text_color(0, 0, 0)
        pdf.ln()


def _portfolio_concentration_section(pdf: Any, concentration: dict) -> None:
    _section_title(pdf, "Porteföljekonsentrasjon")
    pdf.set_font("Helvetica", "", 10)
    total_rev = concentration.get("total_revenue", 0)
    pdf.cell(0, 7, f"Totalt eksponert omsetning: {total_rev/1e9:.1f} BNOK", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Bransjefordeling (topp 8):", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    for row in (concentration.get("by_industry") or [])[:8]:
        rev = row.get("revenue", 0)
        pdf.cell(0, 5,
            f"  {_safe(row.get('section','?'))} — {_safe(row.get('label','')[:30])}: "
            f"{row['count']} selskaper, {rev/1e6:.0f} MNOK",
            new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Geografisk spredning (topp 5):", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    for row in (concentration.get("by_geography") or [])[:5]:
        pdf.cell(0, 5, f"  {_safe(row.get('kommune',''))}: {row['count']} selskaper",
            new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Störrelsesfordeling:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    for row in (concentration.get("by_size") or []):
        pdf.cell(0, 5, f"  {_safe(row.get('band',''))}: {row['count']} selskaper",
            new_x="LMARGIN", new_y="NEXT")


def generate_portfolio_pdf(
    portfolio_name: str,
    companies: list,
    alerts: list,
    concentration: dict,
    broker: dict,
) -> bytes:
    """Generate a portfolio report PDF."""
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=15)
    generated_at = date.today().strftime("%d.%m.%Y")
    _portfolio_cover(pdf, portfolio_name, broker, generated_at)
    pdf.add_page()
    _portfolio_risk_table(pdf, companies)
    if alerts:
        if pdf.get_y() > 160:
            pdf.add_page()
        _portfolio_alerts_section(pdf, alerts)
    if concentration:
        pdf.add_page()
        _portfolio_concentration_section(pdf, concentration)
    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()
