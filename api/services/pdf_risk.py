"""Risk report PDF generation."""
from datetime import date
from typing import Any, Dict, Optional

from fpdf import FPDF



# ── Helpers ───────────────────────────────────────────────────────────────────

def _score_label(s: int) -> str:
    if s <= 3:
        return "Lav"
    if s <= 7:
        return "Moderat"
    if s <= 11:
        return "Høy"
    return "Svært høy"


def _fmt_mnok(v: Any) -> str:
    if v is None:
        return "–"
    return f"{v/1e6:,.1f} MNOK"


def _risk_section_title(pdf: Any, title: str) -> None:
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(30, 60, 120)
    pdf.cell(0, 8, title, ln=True)
    pdf.set_draw_color(30, 60, 120)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(4)
    pdf.set_text_color(0, 0, 0)


def _risk_row(pdf: Any, label: str, value: Any, bold_value: bool = False) -> None:
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(70, 7, label, border=0)
    pdf.set_font("Helvetica", "B" if bold_value else "", 10)
    pdf.cell(0, 7, str(value), border=0, ln=True)
    pdf.set_font("Helvetica", "", 10)


def _add_risk_cover(pdf: Any, navn: str, orgnr: str, today: str, score: int, lbl: str) -> None:
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(30, 60, 120)
    pdf.ln(10)
    pdf.cell(0, 12, "Risikovurdering", ln=True)
    pdf.cell(0, 12, "og forsikringsanbefaling", ln=True)
    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 8, navn, ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, f"Orgnr: {orgnr}  |  Dato: {today}", ln=True)
    pdf.ln(6)
    color = {"Lav": (34, 139, 34), "Moderat": (255, 140, 0), "Høy": (220, 80, 0), "Svært høy": (180, 0, 0)}.get(lbl, (0, 0, 0))
    pdf.set_fill_color(*color)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(60, 14, f"Risikoscore: {score}  ({lbl})", fill=True, ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(8)


def _add_risk_company_profile(
    pdf: Any, navn: str, orgnr: str,
    org_form: Optional[str], nace: Optional[str], nace_desc: Optional[str],
    kommune: Optional[str], stiftelsesdato: Optional[str],
) -> None:
    _risk_section_title(pdf, "Selskapsprofil")
    _risk_row(pdf, "Navn", navn)
    _risk_row(pdf, "Orgnr", orgnr)
    _risk_row(pdf, "Organisasjonsform", org_form or "–")
    _risk_row(pdf, "Bransje", f"{nace_desc or '–'} ({nace or '–'})")
    _risk_row(pdf, "Kommune", kommune or "–")
    _risk_row(pdf, "Stiftelsesdato", stiftelsesdato or "–")
    pdf.ln(6)


def _add_risk_financials(
    pdf: Any, sum_driftsinntekter: Any, sum_egenkapital: Any,
    sum_eiendeler: Any, regn: dict, risk: dict,
) -> None:
    _risk_section_title(pdf, "Finansielle nøkkeltall")
    _risk_row(pdf, "Omsetning", _fmt_mnok(sum_driftsinntekter))
    _risk_row(pdf, "Årsresultat", _fmt_mnok(regn.get("aarsresultat")))
    _risk_row(pdf, "Egenkapital", _fmt_mnok(sum_egenkapital))
    _risk_row(pdf, "Sum eiendeler", _fmt_mnok(sum_eiendeler))
    _risk_row(pdf, "Sum gjeld", _fmt_mnok(regn.get("sum_gjeld")))
    eq = risk.get("equity_ratio")
    _risk_row(pdf, "Egenkapitalandel", f"{eq*100:.1f}%" if eq is not None else "–")
    _risk_row(pdf, "Antall ansatte", str(regn.get("antall_ansatte") or "–"))
    pdf.ln(6)


def _add_risk_factors_table(pdf: Any, risk: dict, score: int, lbl: str) -> None:
    _risk_section_title(pdf, "Risikofaktorer")
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(220, 230, 250)
    pdf.cell(75, 7, "Faktor", border=1, fill=True)
    pdf.cell(40, 7, "Kategori", border=1, fill=True)
    pdf.cell(20, 7, "Poeng", border=1, fill=True, ln=True)
    pdf.set_font("Helvetica", "", 9)
    for i, f in enumerate(risk["factors"]):
        fill = i % 2 == 0
        pdf.set_fill_color(245, 247, 252) if fill else pdf.set_fill_color(255, 255, 255)
        pdf.cell(75, 6, f["label"][:50], border=1, fill=fill)
        pdf.cell(40, 6, f["category"], border=1, fill=fill)
        pdf.cell(20, 6, f"+{f['points']}", border=1, fill=fill, ln=True)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(115, 7, f"Total risikoscore: {score} ({lbl})", border=1, ln=True)


class _RiskPDF(FPDF):
    def __init__(self, navn: str, today: str) -> None:
        super().__init__()
        self.navn = navn
        self.today = today

    def header(self) -> None:
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Risikovurdering — {self.navn}", align="L")
        self.ln(0)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Side {self.page_no()} | Generert {self.today}", align="C")


# ── Public API ────────────────────────────────────────────────────────────────

def generate_risk_report_pdf(
    orgnr: str,
    navn: str,
    organisasjonsform_kode: Optional[str],
    kommune: Optional[str],
    naeringskode1: Optional[str],
    naeringskode1_beskrivelse: Optional[str],
    stiftelsesdato: Optional[str],
    sum_driftsinntekter: Optional[float],
    sum_egenkapital: Optional[float],
    sum_eiendeler: Optional[float],
    regn: Dict[str, Any],
    risk: Dict[str, Any],
) -> bytes:
    """Build and return PDF bytes for a risk assessment report."""
    today = date.today().strftime("%d.%m.%Y")
    s = risk["score"]
    lbl = _score_label(s)
    pdf = _RiskPDF(navn, today)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(20, 20, 20)
    pdf.add_page()
    _add_risk_cover(pdf, navn, orgnr, today, s, lbl)
    _add_risk_company_profile(pdf, navn, orgnr, organisasjonsform_kode, naeringskode1,
                              naeringskode1_beskrivelse, kommune, stiftelsesdato)
    _add_risk_financials(pdf, sum_driftsinntekter, sum_egenkapital, sum_eiendeler, regn, risk)
    _add_risk_factors_table(pdf, risk, s, lbl)
    return bytes(pdf.output())
