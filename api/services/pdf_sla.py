"""SLA agreement PDF generation."""
from typing import Any, List

from fpdf import FPDF

from api.constants import STANDARD_VILKAAR, BROKER_TASKS
from api.db import SlaAgreement
from api.services.pdf_base import _safe, _section_title
import logging

logger = logging.getLogger(__name__)



# ── Page-builder helpers ──────────────────────────────────────────────────────

def _add_cover_page(pdf: Any, agreement: SlaAgreement, broker: dict, firm_label: str) -> None:
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 28)
    pdf.ln(20)
    pdf.cell(0, 12, _safe(broker.get("firm_name", "Forsikringsmegler")), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    pdf.set_font("Helvetica", "", 16)
    pdf.cell(0, 10, "Tjenesteavtale - Forsikringsmegling", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(16)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, _safe(f"Klient: {agreement.client_navn or ''}"), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, f"Org.nr: {agreement.client_orgnr or ''}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    pdf.cell(0, 8, f"Avtaledato: {agreement.created_at[:10] if agreement.created_at else ''}", align="C", new_x="LMARGIN", new_y="NEXT")


def _add_section_oppdrag(pdf: Any, agreement: SlaAgreement, broker: dict, firm_name: str) -> None:
    pdf.add_page()
    _section_title(pdf, "Oppdragsavtale")
    rows = [
        ("Megler", f"{firm_name}  |  Org.nr: {_safe(broker.get('orgnr', ''))}"),
        ("Meglers adresse", _safe(broker.get("address", ""))),
        ("Kundeansvarlig", _safe(f"{agreement.account_manager or ''}  |  {broker.get('contact_email', '')}  |  {broker.get('contact_phone', '')}")),
        ("Klient", _safe(f"{agreement.client_navn or ''}  |  Org.nr: {agreement.client_orgnr or ''}")),
        ("Klientens adresse", _safe(agreement.client_adresse or "")),
        ("Kontaktperson klient", _safe(agreement.client_kontakt or "")),
        ("Avtalens startdato", _safe(agreement.start_date or "")),
    ]
    for label, value in rows:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, _safe(label) + ":", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, _safe(value) or "")
        pdf.ln(1)


def _add_vedlegg_a(pdf: Any, agreement: SlaAgreement, form: dict, lines: List[str]) -> None:
    pdf.add_page()
    _section_title(pdf, "Vedlegg A - Forsikringslinjer som megles")
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(0, 8, "Forsikringslinje", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    for line in lines:
        pdf.cell(0, 7, f"  {_safe(line)}", new_x="LMARGIN", new_y="NEXT")
    if form.get("other_lines"):
        pdf.cell(0, 7, f"  Annet: {_safe(form['other_lines'])}", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(6)
    _section_title(pdf, "Vedlegg A Del 2 - Meglers oppgaver")
    for task_title, task_text in BROKER_TASKS:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, _safe(task_title), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, _safe(task_text))
        pdf.ln(3)


def _add_vedlegg_b(pdf: Any, fees: List[dict]) -> None:
    pdf.add_page()
    _section_title(pdf, "Vedlegg B - Honorar")
    col_w = [80, 50, 40]
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_fill_color(230, 230, 230)
    for header, w in zip(["Forsikringslinje", "Honorartype", "Sats / Belop"], col_w):
        pdf.cell(w, 8, header, border=1, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 11)
    for fee in fees:
        fee_type = fee.get("type", "")
        rate = fee.get("rate", "")
        if fee_type == "provisjon" and rate:
            rate_str = f"{rate} %"
        elif fee_type == "fast" and rate:
            rate_str = f"NOK {int(rate):,}".replace(",", " ")
        else:
            rate_str = "Ikke avklart"
        type_label = {"provisjon": "Provisjon", "fast": "Fast honorar (NOK/ar)", "ikke_avklart": "Ikke avklart"}.get(fee_type, fee_type)
        pdf.cell(col_w[0], 7, _safe(fee.get("line", "")), border=1)
        pdf.cell(col_w[1], 7, _safe(type_label), border=1)
        pdf.cell(col_w[2], 7, _safe(rate_str), border=1)
        pdf.ln()


def _add_standardvilkar(pdf: Any) -> None:
    pdf.add_page()
    _section_title(pdf, "Standardvilkar")
    for title, text in STANDARD_VILKAAR:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, _safe(title), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, _safe(text))
        pdf.ln(3)


def _add_vedlegg_e(pdf: Any, form: dict) -> None:
    pdf.add_page()
    _section_title(pdf, "Vedlegg E - Kundekontroll (KYC/AML)")
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(
        0, 6,
        "I henhold til hvitvaskingsloven er megler forpliktet til a gjennomfore kundekontroll "
        "for etablering av kundeforhold. Folgende kontroll er gjennomfort:"
    )
    pdf.ln(4)
    kyc_rows = [
        ("Signatar (den som signerer)", form.get("kyc_signatory", "")),
        ("Type legitimasjon fremvist", form.get("kyc_id_type", "")),
        ("Dokumentreferanse / ID-nummer", form.get("kyc_id_ref", "")),
        ("Firmaattest dato", form.get("kyc_firmadato", "")),
    ]
    for label, value in kyc_rows:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, _safe(label) + ":", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, _safe(value) if value else "-")
        pdf.ln(1)
    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 10)
    pdf.multi_cell(
        0, 6,
        "Megler bekrefter at kundekontroll er gjennomfort i samsvar med hvitvaskingsloven "
        "og at kopi av legitimasjon og firmaattest er arkivert."
    )


def _add_signature_page(pdf: Any, agreement: SlaAgreement, firm_name: str) -> None:
    pdf.add_page()
    _section_title(pdf, "Meglerfullmakt og signatur")
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(
        0, 6,
        _safe(
            f"Klienten gir herved {firm_name} fullmakt til a opptre som forsikringsmegler "
            "for de avtalte forsikringsdekninger overfor forsikringsgivere."
        ),
    )
    pdf.ln(16)
    for party in [("For megler", firm_name), ("For klient", _safe(agreement.client_navn or ""))]:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, _safe(party[0]) + ":", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 7, _safe(party[1]), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(14)
        pdf.set_draw_color(0, 0, 0)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + 90, pdf.get_y())
        pdf.ln(5)
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(0, 6, "Signatur / dato", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(10)


# ── Main orchestrator ─────────────────────────────────────────────────────────

def generate_sla_pdf(agreement: SlaAgreement) -> bytes:
    """Generate a PDF for the given SLA agreement using fpdf2."""
    broker = agreement.broker_snapshot or {}
    form = agreement.form_data or {}
    lines = agreement.insurance_lines or []
    fees = (agreement.fee_structure or {}).get("lines", [])
    firm_label = _safe(broker.get("firm_name", "Megler"))

    class _PDF(FPDF):
        def footer(self):
            self.set_y(-13)
            self.set_font("Helvetica", "I", 9)
            self.cell(0, 6, f"{firm_label}  |  Side {self.page_no()}", align="C")

    pdf = _PDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(20, 20, 20)

    _add_cover_page(pdf, agreement, broker, firm_label)
    _add_section_oppdrag(pdf, agreement, broker, firm_label)
    _add_vedlegg_a(pdf, agreement, form, lines)
    _add_vedlegg_b(pdf, fees)
    _add_standardvilkar(pdf)
    _add_vedlegg_e(pdf, form)
    _add_signature_page(pdf, agreement, firm_label)

    return bytes(pdf.output())
