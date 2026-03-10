"""PDF generation helpers — SLA PDF, risk report PDF, forsikringstilbud PDF, offer summary extraction."""
import io
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fpdf import FPDF

from db import SlaAgreement
from constants import STANDARD_VILKAAR, BROKER_TASKS
from services.llm import _llm_answer_raw, _parse_json_from_llm_response


def _extract_offer_summary(insurer: str, extracted_text: str) -> dict:
    """Use LLM to extract key terms from a stored insurance offer."""
    if not extracted_text:
        return {"selskap": insurer, "premie": "–", "dekning": "–", "egenandel": "–", "vilkaar": "–", "styrker": "–", "svakheter": "–"}
    snippet = extracted_text[:6000]
    prompt = (
        f"Du er en forsikringsekspert. Trekk ut nøkkeltall fra dette forsikringstilbudet fra {insurer}.\n\n"
        f"{snippet}\n\n"
        "Returner KUN gyldig JSON:\n"
        '{"premie": "beløp per år", "dekning": "viktigste dekningstypene kort", '
        '"egenandel": "egenandel/selvrisiko", "vilkaar": "særlige vilkår eller unntak", '
        '"styrker": "1-2 styrker ved tilbudet", "svakheter": "1-2 svakheter ved tilbudet"}'
    )
    raw = _llm_answer_raw(prompt)
    if raw:
        data = _parse_json_from_llm_response(raw)
        if data:
            data["selskap"] = insurer
            return data
    return {"selskap": insurer, "premie": "–", "dekning": extracted_text[:120] + "…", "egenandel": "–", "vilkaar": "–", "styrker": "–", "svakheter": "–"}


def _safe(s: Any) -> str:
    """Sanitize text for fpdf2 latin-1 Helvetica font — replace non-latin-1 chars."""
    if not s:
        return ""
    return (
        str(s)
        .replace("\u2013", "-").replace("\u2014", "-")
        .replace("\u2018", "'").replace("\u2019", "'")
        .replace("\u201c", '"').replace("\u201d", '"')
        .replace("\u2026", "...").replace("\u00b0", " ")
        .encode("latin-1", errors="replace").decode("latin-1")
    )


# ── Page-builder helpers ──────────────────────────────────────────────────────

def _section_title(pdf: Any, title: str) -> None:
    pdf.set_font("Helvetica", "B", 13)
    pdf.ln(6)
    pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(0, 0, 0)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 11)


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


# ── Risk report PDF ───────────────────────────────────────────────────────────

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

    class RiskPDF(FPDF):
        def header(self):
            self.set_font("Helvetica", "B", 9)
            self.set_text_color(120, 120, 120)
            self.cell(0, 8, f"Risikovurdering — {navn}", align="L")
            self.ln(0)

        def footer(self):
            self.set_y(-15)
            self.set_font("Helvetica", "", 8)
            self.set_text_color(150, 150, 150)
            self.cell(0, 10, f"Side {self.page_no()} | Generert {today}", align="C")

    s = risk["score"]
    lbl = _score_label(s)
    pdf = RiskPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(20, 20, 20)
    pdf.add_page()
    _add_risk_cover(pdf, navn, orgnr, today, s, lbl)
    _add_risk_company_profile(pdf, navn, orgnr, organisasjonsform_kode, naeringskode1, naeringskode1_beskrivelse, kommune, stiftelsesdato)
    _add_risk_financials(pdf, sum_driftsinntekter, sum_egenkapital, sum_eiendeler, regn, risk)
    _add_risk_factors_table(pdf, risk, s, lbl)
    return bytes(pdf.output())


def generate_forsikringstilbud_pdf(
    orgnr: str,
    navn: str,
    organisasjonsform_kode: Optional[str],
    naeringskode1: Optional[str],
    naeringskode1_beskrivelse: Optional[str],
    kommune: Optional[str],
    broker_name: str,
    broker_contact: str,
    broker_email: str,
    broker_phone: str,
    anbefalinger: List[Dict[str, Any]],
    total_premie: str,
    sammendrag: str,
    offer_summaries: List[Dict[str, Any]],
) -> bytes:
    """Build and return PDF bytes for an insurance offer (Forsikringstilbud)."""
    import datetime as _dt

    today_str = date.today().strftime("%d.%m.%Y")
    valid_str = (_dt.date.today() + _dt.timedelta(days=30)).strftime("%d.%m.%Y")

    DARK_BLUE  = (20,  50, 120)
    MID_BLUE   = (50,  90, 170)
    LIGHT_BLUE = (220, 230, 250)
    MUST_RED   = (200,  50,  50)
    REC_ORG    = (220, 100,  30)
    OPT_GRY    = (100, 100, 100)

    def priority_color(p: str) -> tuple:
        p = (p or "").lower()
        if "må" in p:
            return MUST_RED
        if "anbefalt" in p:
            return REC_ORG
        return OPT_GRY

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(18, 15, 18)

    _build_tilbud_forside(pdf, navn, orgnr, organisasjonsform_kode, naeringskode1,
                          naeringskode1_beskrivelse, kommune, broker_name, broker_contact,
                          broker_email, broker_phone, today_str, valid_str, anbefalinger,
                          sammendrag, total_premie, DARK_BLUE, MID_BLUE, LIGHT_BLUE)
    if offer_summaries:
        _build_tilbud_offers_page(pdf, offer_summaries, today_str, DARK_BLUE, MID_BLUE)
    _build_tilbud_coverage_table(pdf, navn, orgnr, anbefalinger, total_premie, today_str,
                                 DARK_BLUE, priority_color)
    for rec in anbefalinger:
        _build_tilbud_coverage_detail(pdf, rec, MID_BLUE, priority_color)
    _build_tilbud_terms_page(pdf, navn, orgnr, broker_name, broker_contact, broker_phone,
                             today_str, DARK_BLUE, MID_BLUE)

    return bytes(pdf.output())


def _build_tilbud_forside(
    pdf: Any, navn: str, orgnr: str, org_form: Optional[str],
    nace: Optional[str], nace_desc: Optional[str], kommune: Optional[str],
    broker_name: str, broker_contact: str, broker_email: str, broker_phone: str,
    today_str: str, valid_str: str, anbefalinger: List[Dict[str, Any]],
    sammendrag: str, total_premie: str,
    DARK_BLUE: tuple, MID_BLUE: tuple, LIGHT_BLUE: tuple,
) -> None:
    pdf.add_page()
    pdf.set_fill_color(*DARK_BLUE)
    pdf.rect(0, 0, 210, 28, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_xy(18, 8)
    pdf.cell(0, 10, broker_name.upper(), ln=False)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(18, 19)
    if broker_contact:
        pdf.cell(0, 5, f"{broker_contact}  |  {broker_email}  |  {broker_phone}", ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_xy(18, 38)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(*DARK_BLUE)
    pdf.cell(0, 14, "FORSIKRINGSTILBUD", ln=True)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 7, f"Utarbeidet av {broker_name}", ln=True)
    pdf.ln(8)
    pdf.set_fill_color(*LIGHT_BLUE)
    pdf.rect(18, pdf.get_y(), 174, 42, "F")
    y0 = pdf.get_y() + 4
    pdf.set_xy(22, y0)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*DARK_BLUE)
    pdf.cell(0, 8, navn or "–", ln=True)
    pdf.set_xy(22, pdf.get_y())
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 6, f"Org.nr: {orgnr}", ln=True)
    pdf.set_xy(22, pdf.get_y())
    pdf.cell(0, 6, f"Bransje: {nace_desc or '–'} (NACE {nace or '–'})", ln=True)
    pdf.set_xy(22, pdf.get_y())
    pdf.cell(0, 6, f"Kommune: {kommune or '–'}  |  Form: {org_form or '–'}", ln=True)
    pdf.set_y(pdf.get_y() + 14)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(55, 6, f"Tilbudsdato: {today_str}")
    pdf.cell(70, 6, f"Gyldig til: {valid_str}")
    pdf.cell(0, 6, f"Antall dekninger: {len(anbefalinger)}", ln=True)
    pdf.ln(8)
    if sammendrag:
        pdf.set_fill_color(240, 248, 255)
        pdf.set_draw_color(*MID_BLUE)
        pdf.set_line_width(0.4)
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(50, 50, 50)
        pdf.multi_cell(174, 5, sammendrag, border=1, fill=True)
        pdf.set_draw_color(0, 0, 0)
        pdf.set_line_width(0.2)
    pdf.ln(6)
    pdf.set_fill_color(*DARK_BLUE)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(174, 12, f"  Estimert totalpremie: {total_premie}", fill=True, ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 5, "Alle premier er veiledende estimater og kan variere ved endelig tegning.", ln=True)


def _build_tilbud_offers_page(
    pdf: Any, offer_summaries: List[Dict[str, Any]], today_str: str,
    DARK_BLUE: tuple, MID_BLUE: tuple,
) -> None:
    pdf.add_page()
    pdf.set_text_color(*DARK_BLUE)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Innhentede tilbud fra forsikringsselskaper", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, f"{len(offer_summaries)} tilbud mottatt og analysert  ·  {today_str}", ln=True)
    pdf.ln(5)
    col_w = [38, 32, 38, 28, 38]
    headers = ["Forsikringsselskap", "Premie/år", "Dekning", "Egenandel", "Særlige vilkår"]
    pdf.set_fill_color(*DARK_BLUE)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 8)
    for h, w in zip(headers, col_w):
        pdf.cell(w, 8, h, border=0, fill=True)
    pdf.ln()
    for i, s in enumerate(offer_summaries):
        fill = i % 2 == 0
        pdf.set_fill_color(245, 247, 252) if fill else pdf.set_fill_color(255, 255, 255)
        pdf.set_text_color(30, 30, 30)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(col_w[0], 7, str(s.get("selskap") or "")[:22], border="TB", fill=fill)
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(col_w[1], 7, str(s.get("premie") or "–")[:18], border="TB", fill=fill)
        pdf.cell(col_w[2], 7, str(s.get("dekning") or "–")[:25], border="TB", fill=fill)
        pdf.cell(col_w[3], 7, str(s.get("egenandel") or "–")[:16], border="TB", fill=fill)
        pdf.cell(col_w[4], 7, str(s.get("vilkaar") or "–")[:25], border="TB", fill=fill)
        pdf.ln()
    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*DARK_BLUE)
    pdf.cell(0, 8, "Styrker og svakheter per tilbud", ln=True)
    pdf.ln(2)
    for s in offer_summaries:
        pdf.set_fill_color(*MID_BLUE)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 7, f"  {s.get('selskap', '')}", fill=True, ln=True)
        pdf.set_text_color(30, 30, 30)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(20, 6, "Styrker:")
        pdf.set_font("Helvetica", "", 8)
        pdf.multi_cell(0, 6, str(s.get("styrker") or "–"))
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(20, 6, "Svakheter:")
        pdf.set_font("Helvetica", "", 8)
        pdf.multi_cell(0, 6, str(s.get("svakheter") or "–"))
        pdf.ln(2)


def _build_tilbud_coverage_table(
    pdf: Any, navn: str, orgnr: str, anbefalinger: List[Dict[str, Any]],
    total_premie: str, today_str: str, DARK_BLUE: tuple, priority_color: Any,
) -> None:
    pdf.add_page()
    pdf.set_text_color(*DARK_BLUE)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Forsikringsdekning — oversikt", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, f"{navn}  ·  Org.nr {orgnr}  ·  {today_str}", ln=True)
    pdf.ln(4)
    pdf.set_fill_color(*DARK_BLUE)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(58, 8, "Forsikringstype", border=0, fill=True)
    pdf.cell(22, 8, "Prioritet", border=0, fill=True)
    pdf.cell(40, 8, "Anbefalt sum", border=0, fill=True)
    pdf.cell(54, 8, "Begrunnelse (kort)", border=0, fill=True, ln=True)
    for i, rec in enumerate(anbefalinger):
        fill = i % 2 == 0
        pdf.set_fill_color(245, 247, 252) if fill else pdf.set_fill_color(255, 255, 255)
        pdf.set_text_color(30, 30, 30)
        beg = str(rec.get("begrunnelse") or "")[:80]
        row_h = 6
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(58, row_h, str(rec.get("type") or "")[:30], border="TB", fill=fill)
        pri = str(rec.get("prioritet") or "")
        pdf.set_text_color(*priority_color(pri))
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(22, row_h, pri, border="TB", fill=fill)
        pdf.set_text_color(30, 30, 30)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(40, row_h, str(rec.get("anbefalt_sum") or "")[:25], border="TB", fill=fill)
        pdf.cell(54, row_h, beg, border="TB", fill=fill, ln=True)
    pdf.set_fill_color(*DARK_BLUE)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(120, 9, "Estimert totalpremie", fill=True, border=0)
    pdf.cell(54, 9, total_premie, fill=True, border=0, ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(6)


def _build_tilbud_coverage_detail(
    pdf: Any, rec: Dict[str, Any], MID_BLUE: tuple, priority_color: Any,
) -> None:
    pdf.add_page()
    pri = str(rec.get("prioritet") or "")
    pri_color = priority_color(pri)
    pdf.set_fill_color(*MID_BLUE)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 12, f"  {rec.get('type', '')}", fill=True, ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)
    pdf.set_fill_color(*pri_color)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(35, 7, f"  {pri}", fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(8)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(60, 60, 100)
    pdf.cell(52, 7, "Dekningssum:")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 7, str(rec.get("anbefalt_sum") or "–"), ln=True)
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(20, 50, 120)
    pdf.cell(0, 6, "Begrunnelse", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(50, 50, 50)
    pdf.multi_cell(0, 5, str(rec.get("begrunnelse") or "–"))
    pdf.ln(4)
    pdf.set_fill_color(245, 247, 252)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(
        0, 5,
        "Dekningsomfang og vilkår fastsettes endelig ved tegning. "
        "Premier er estimater basert på oppgitte nøkkeltall og kan avvike fra endelig premie. "
        "Forsikringsselskap og produktvalg klargjøres i endelig tilbud.",
        border=1, fill=True,
    )


def _build_tilbud_terms_page(
    pdf: Any, navn: str, orgnr: str, broker_name: str,
    broker_contact: str, broker_phone: str, today_str: str,
    DARK_BLUE: tuple, MID_BLUE: tuple,
) -> None:
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*DARK_BLUE)
    pdf.cell(0, 10, "Betingelser og gyldighet", ln=True)
    pdf.ln(3)
    terms = [
        f"Dette tilbudet er utarbeidet av {broker_name} og er gyldig i 30 dager fra tilbudsdato ({today_str}).",
        "Tilbudet er basert på opplysninger hentet fra offentlige registre (Brønnøysundregisteret, BRREG Regnskapsregisteret) og risikoscoring utarbeidet av megler.",
        "Endelig forsikringsavtale inngås etter aksept fra forsikringstaker og tegning hos valgt forsikringsselskap.",
        "Premier og dekningssummer er veiledende og kan endres ved endelig tegning basert på fullstendig risikovurdering.",
        "Forsikringene er i henhold til norsk forsikringsavtalelov (FAL) og de til enhver tid gjeldende vilkår fra det aktuelle forsikringsselskap.",
    ]
    for t in terms:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(5, 5, "•")
        pdf.multi_cell(0, 5, t)
        pdf.ln(1)
    pdf.ln(10)
    pdf.set_draw_color(*MID_BLUE)
    pdf.set_line_width(0.4)
    pdf.line(18, pdf.get_y(), 105, pdf.get_y())
    pdf.line(120, pdf.get_y(), 192, pdf.get_y())
    pdf.ln(1)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(87, 5, f"Megler: {broker_name}")
    pdf.cell(33, 5, "")
    pdf.cell(0, 5, f"Kunde: {navn}", ln=True)
    pdf.cell(87, 5, f"Kontakt: {broker_contact}  {broker_phone}")
    pdf.cell(33, 5, "")
    pdf.cell(0, 5, f"Org.nr: {orgnr}", ln=True)
    pdf.ln(3)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 5, f"Generert {today_str} av Broker Accelerator  ·  Ikke bindende uten signatur fra begge parter.", ln=True)


# ── Main orchestrator ─────────────────────────────────────────────────────────

def _generate_sla_pdf(agreement: SlaAgreement) -> bytes:
    """Generate a PDF for the given SLA agreement using fpdf2."""
    from fpdf import FPDF

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
