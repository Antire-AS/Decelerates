"""Forsikringstilbud PDF generation + offer summary extraction."""

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from fpdf import FPDF

from api.services.pdf_base import (
    _DARK_BLUE,
    _MID_BLUE,
    _LIGHT_BLUE,
    _MUST_RED,
    _REC_ORG,
    _OPT_GRY,
)
from api.services.llm import _llm_answer_raw, _parse_json_from_llm_response
import logging

logger = logging.getLogger(__name__)


# ── Priority colour helper ────────────────────────────────────────────────────


def _priority_color(p: str) -> tuple:
    p = (p or "").lower()
    if "må" in p:
        return _MUST_RED
    if "anbefalt" in p:
        return _REC_ORG
    return _OPT_GRY


# ── Offer summary extraction ──────────────────────────────────────────────────


def _extract_offer_summary(insurer: str, extracted_text: str) -> dict:
    """Use LLM to extract key terms from a stored insurance offer."""
    if not extracted_text:
        return {
            "selskap": insurer,
            "premie": "–",
            "dekning": "–",
            "egenandel": "–",
            "vilkaar": "–",
            "styrker": "–",
            "svakheter": "–",
        }
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
    return {
        "selskap": insurer,
        "premie": "–",
        "dekning": extracted_text[:120] + "…",
        "egenandel": "–",
        "vilkaar": "–",
        "styrker": "–",
        "svakheter": "–",
    }


# ── Forsikringstilbud page builders ──────────────────────────────────────────


def _build_tilbud_broker_header(
    pdf: Any,
    broker_name: str,
    broker_contact: str,
    broker_email: str,
    broker_phone: str,
    DARK_BLUE: tuple,
) -> None:
    pdf.set_fill_color(*DARK_BLUE)
    pdf.rect(0, 0, 210, 28, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_xy(18, 8)
    pdf.cell(0, 10, broker_name.upper(), ln=False)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(18, 19)
    if broker_contact:
        pdf.cell(
            0, 5, f"{broker_contact}  |  {broker_email}  |  {broker_phone}", ln=True
        )
    pdf.set_text_color(0, 0, 0)
    pdf.set_xy(18, 38)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(*DARK_BLUE)
    pdf.cell(0, 14, "FORSIKRINGSTILBUD", ln=True)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 7, f"Utarbeidet av {broker_name}", ln=True)


def _build_client_company_info(
    pdf: Any,
    navn: str,
    orgnr: str,
    org_form: Optional[str],
    nace: Optional[str],
    nace_desc: Optional[str],
    kommune: Optional[str],
    DARK_BLUE: tuple,
    LIGHT_BLUE: tuple,
) -> None:
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


def _build_client_summary_and_premium(
    pdf: Any,
    today_str: str,
    valid_str: str,
    n_dekninger: int,
    sammendrag: str,
    total_premie: str,
    DARK_BLUE: tuple,
    MID_BLUE: tuple,
) -> None:
    pdf.set_y(pdf.get_y() + 14)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(55, 6, f"Tilbudsdato: {today_str}")
    pdf.cell(70, 6, f"Gyldig til: {valid_str}")
    pdf.cell(0, 6, f"Antall dekninger: {n_dekninger}", ln=True)
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
    pdf.cell(
        0,
        5,
        "Alle premier er veiledende estimater og kan variere ved endelig tegning.",
        ln=True,
    )


def _build_tilbud_client_box(
    pdf: Any,
    navn: str,
    orgnr: str,
    org_form: Optional[str],
    nace: Optional[str],
    nace_desc: Optional[str],
    kommune: Optional[str],
    today_str: str,
    valid_str: str,
    n_dekninger: int,
    sammendrag: str,
    total_premie: str,
    DARK_BLUE: tuple,
    MID_BLUE: tuple,
    LIGHT_BLUE: tuple,
) -> None:
    _build_client_company_info(
        pdf, navn, orgnr, org_form, nace, nace_desc, kommune, DARK_BLUE, LIGHT_BLUE
    )
    _build_client_summary_and_premium(
        pdf,
        today_str,
        valid_str,
        n_dekninger,
        sammendrag,
        total_premie,
        DARK_BLUE,
        MID_BLUE,
    )


def _build_tilbud_forside(
    pdf: Any,
    navn: str,
    orgnr: str,
    org_form: Optional[str],
    nace: Optional[str],
    nace_desc: Optional[str],
    kommune: Optional[str],
    broker_name: str,
    broker_contact: str,
    broker_email: str,
    broker_phone: str,
    today_str: str,
    valid_str: str,
    anbefalinger: List[Dict[str, Any]],
    sammendrag: str,
    total_premie: str,
    DARK_BLUE: tuple,
    MID_BLUE: tuple,
    LIGHT_BLUE: tuple,
) -> None:
    pdf.add_page()
    _build_tilbud_broker_header(
        pdf, broker_name, broker_contact, broker_email, broker_phone, DARK_BLUE
    )
    _build_tilbud_client_box(
        pdf,
        navn,
        orgnr,
        org_form,
        nace,
        nace_desc,
        kommune,
        today_str,
        valid_str,
        len(anbefalinger),
        sammendrag,
        total_premie,
        DARK_BLUE,
        MID_BLUE,
        LIGHT_BLUE,
    )


def _build_offers_comparison_table(
    pdf: Any,
    offer_summaries: List[Dict[str, Any]],
    today_str: str,
    DARK_BLUE: tuple,
) -> None:
    col_w = [38, 32, 38, 28, 38]
    headers = [
        "Forsikringsselskap",
        "Premie/år",
        "Dekning",
        "Egenandel",
        "Særlige vilkår",
    ]
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
        pdf.cell(
            col_w[3], 7, str(s.get("egenandel") or "–")[:16], border="TB", fill=fill
        )
        pdf.cell(col_w[4], 7, str(s.get("vilkaar") or "–")[:25], border="TB", fill=fill)
        pdf.ln()


def _build_offers_strengths_section(
    pdf: Any,
    offer_summaries: List[Dict[str, Any]],
    DARK_BLUE: tuple,
    MID_BLUE: tuple,
) -> None:
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


def _build_tilbud_offers_page(
    pdf: Any,
    offer_summaries: List[Dict[str, Any]],
    today_str: str,
    DARK_BLUE: tuple,
    MID_BLUE: tuple,
) -> None:
    pdf.add_page()
    pdf.set_text_color(*DARK_BLUE)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Innhentede tilbud fra forsikringsselskaper", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(
        0,
        5,
        f"{len(offer_summaries)} tilbud mottatt og analysert  ·  {today_str}",
        ln=True,
    )
    pdf.ln(5)
    _build_offers_comparison_table(pdf, offer_summaries, today_str, DARK_BLUE)
    _build_offers_strengths_section(pdf, offer_summaries, DARK_BLUE, MID_BLUE)


def _build_coverage_table_header(
    pdf: Any,
    navn: str,
    orgnr: str,
    today_str: str,
    DARK_BLUE: tuple,
) -> None:
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


def _build_coverage_table_rows(
    pdf: Any,
    anbefalinger: List[Dict[str, Any]],
    priority_color: Any,
) -> None:
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
        pdf.cell(
            40, row_h, str(rec.get("anbefalt_sum") or "")[:25], border="TB", fill=fill
        )
        pdf.cell(54, row_h, beg, border="TB", fill=fill, ln=True)


def _build_coverage_table_total(pdf: Any, total_premie: str, DARK_BLUE: tuple) -> None:
    pdf.set_fill_color(*DARK_BLUE)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(120, 9, "Estimert totalpremie", fill=True, border=0)
    pdf.cell(54, 9, total_premie, fill=True, border=0, ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(6)


def _build_tilbud_coverage_table(
    pdf: Any,
    navn: str,
    orgnr: str,
    anbefalinger: List[Dict[str, Any]],
    total_premie: str,
    today_str: str,
    DARK_BLUE: tuple,
    priority_color: Any,
) -> None:
    pdf.add_page()
    _build_coverage_table_header(pdf, navn, orgnr, today_str, DARK_BLUE)
    _build_coverage_table_rows(pdf, anbefalinger, priority_color)
    _build_coverage_table_total(pdf, total_premie, DARK_BLUE)


def _build_detail_header(
    pdf: Any,
    rec: Dict[str, Any],
    MID_BLUE: tuple,
    priority_color: Any,
) -> None:
    pri = str(rec.get("prioritet") or "")
    pdf.set_fill_color(*MID_BLUE)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 12, f"  {rec.get('type', '')}", fill=True, ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)
    pdf.set_fill_color(*priority_color(pri))
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(35, 7, f"  {pri}", fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(8)


def _build_detail_content(pdf: Any, rec: Dict[str, Any]) -> None:
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
        0,
        5,
        "Dekningsomfang og vilkår fastsettes endelig ved tegning. "
        "Premier er estimater basert på oppgitte nøkkeltall og kan avvike fra endelig premie. "
        "Forsikringsselskap og produktvalg klargjøres i endelig tilbud.",
        border=1,
        fill=True,
    )


def _build_tilbud_coverage_detail(
    pdf: Any,
    rec: Dict[str, Any],
    MID_BLUE: tuple,
    priority_color: Any,
) -> None:
    pdf.add_page()
    _build_detail_header(pdf, rec, MID_BLUE, priority_color)
    _build_detail_content(pdf, rec)


def _build_terms_bullets(pdf: Any, broker_name: str, today_str: str) -> None:
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


def _build_tilbud_terms_page(
    pdf: Any,
    navn: str,
    orgnr: str,
    broker_name: str,
    broker_contact: str,
    broker_phone: str,
    today_str: str,
    DARK_BLUE: tuple,
    MID_BLUE: tuple,
) -> None:
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*DARK_BLUE)
    pdf.cell(0, 10, "Betingelser og gyldighet", ln=True)
    pdf.ln(3)
    _build_terms_bullets(pdf, broker_name, today_str)
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
    pdf.cell(
        0,
        5,
        f"Generert {today_str} av Broker Accelerator  ·  Ikke bindende uten signatur fra begge parter.",
        ln=True,
    )


# ── Public API ────────────────────────────────────────────────────────────────


def _cover_header_band(pdf: Any, tender_title: str, DARK_BLUE: tuple) -> None:
    pdf.add_page()
    pdf.set_fill_color(*DARK_BLUE)
    pdf.rect(0, 0, 210, 55, style="F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_xy(18, 18)
    pdf.cell(0, 10, "Tilbudsfremstilling", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_xy(18, 32)
    pdf.cell(0, 6, tender_title, ln=True)


def _cover_client_and_products(
    pdf: Any,
    company_name: str,
    orgnr: str,
    product_types: List[str],
    MID_BLUE: tuple,
) -> None:
    pdf.set_xy(18, 70)
    pdf.set_text_color(30, 30, 30)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, f"Til: {company_name}", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 6, f"Org.nr: {orgnr}", ln=True)
    pdf.ln(4)
    pdf.set_text_color(*MID_BLUE)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Forsikringsprodukter vurdert", ln=True)
    pdf.set_text_color(30, 30, 30)
    pdf.set_font("Helvetica", "", 10)
    for prod in product_types:
        pdf.cell(0, 5, f"  •  {prod}", ln=True)
    pdf.ln(4)


def _cover_meta(
    pdf: Any,
    deadline_str: str,
    broker_name: str,
    broker_email: str,
    today_str: str,
) -> None:
    if deadline_str:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(40, 6, "Anbudsfrist:")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, deadline_str, ln=True)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(40, 6, "Utarbeidet av:")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"{broker_name} ({broker_email})", ln=True)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(40, 6, "Dato:")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, today_str, ln=True)


def _tender_presentation_cover(
    pdf: Any,
    tender_title: str,
    company_name: str,
    orgnr: str,
    product_types: List[str],
    deadline_str: str,
    today_str: str,
    broker_name: str,
    broker_email: str,
    DARK_BLUE: tuple,
    MID_BLUE: tuple,
) -> None:
    """Cover page for a tender presentation (anbud tilbudsfremstilling)."""
    _cover_header_band(pdf, tender_title, DARK_BLUE)
    _cover_client_and_products(pdf, company_name, orgnr, product_types, MID_BLUE)
    _cover_meta(pdf, deadline_str, broker_name, broker_email, today_str)


def _tender_presentation_recommendation(
    pdf: Any,
    recommendation: str,
    DARK_BLUE: tuple,
    LIGHT_BLUE: tuple,
) -> None:
    """Broker's recommendation section + signature block."""
    pdf.add_page()
    pdf.set_text_color(*DARK_BLUE)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Meglerens anbefaling", ln=True)
    pdf.ln(2)
    pdf.set_fill_color(*LIGHT_BLUE)
    pdf.set_text_color(30, 30, 30)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(
        0, 6, recommendation or "Anbefaling fylles inn av megleren.", fill=True
    )
    pdf.ln(12)
    pdf.set_text_color(*DARK_BLUE)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Godkjenning av kunde", ln=True)
    pdf.ln(4)
    pdf.set_draw_color(80, 80, 80)
    pdf.set_text_color(100, 100, 100)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(90, 6, "Signatur:", ln=False)
    pdf.cell(90, 6, "Dato:", ln=True)
    pdf.line(18, pdf.get_y() + 10, 98, pdf.get_y() + 10)
    pdf.line(108, pdf.get_y() + 10, 192, pdf.get_y() + 10)


def generate_tender_presentation_pdf(
    tender_title: str,
    company_name: str,
    orgnr: str,
    product_types: List[str],
    deadline: Optional[str],
    broker_name: str,
    broker_email: str,
    offer_summaries: List[Dict[str, Any]],
    recommendation: str,
) -> bytes:
    """Client-facing tilbudsfremstilling PDF — compares insurer responses to an anbud.

    Distinct from `generate_forsikringstilbud_pdf` which presents one broker
    recommendation; this one presents MULTIPLE insurer quotes side-by-side
    (the output of a tender/anbud cycle) with the broker's recommendation.
    """
    today_str = date.today().strftime("%d.%m.%Y")
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(18, 15, 18)
    _tender_presentation_cover(
        pdf,
        tender_title,
        company_name,
        orgnr,
        product_types,
        deadline or "",
        today_str,
        broker_name,
        broker_email,
        _DARK_BLUE,
        _MID_BLUE,
    )
    _build_tilbud_offers_page(pdf, offer_summaries, today_str, _DARK_BLUE, _MID_BLUE)
    _tender_presentation_recommendation(pdf, recommendation, _DARK_BLUE, _LIGHT_BLUE)
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
    today_str = date.today().strftime("%d.%m.%Y")
    valid_str = (date.today() + timedelta(days=30)).strftime("%d.%m.%Y")
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(18, 15, 18)
    _build_tilbud_forside(
        pdf,
        navn,
        orgnr,
        organisasjonsform_kode,
        naeringskode1,
        naeringskode1_beskrivelse,
        kommune,
        broker_name,
        broker_contact,
        broker_email,
        broker_phone,
        today_str,
        valid_str,
        anbefalinger,
        sammendrag,
        total_premie,
        _DARK_BLUE,
        _MID_BLUE,
        _LIGHT_BLUE,
    )
    if offer_summaries:
        _build_tilbud_offers_page(
            pdf, offer_summaries, today_str, _DARK_BLUE, _MID_BLUE
        )
    _build_tilbud_coverage_table(
        pdf,
        navn,
        orgnr,
        anbefalinger,
        total_premie,
        today_str,
        _DARK_BLUE,
        _priority_color,
    )
    for rec in anbefalinger:
        _build_tilbud_coverage_detail(pdf, rec, _MID_BLUE, _priority_color)
    _build_tilbud_terms_page(
        pdf,
        navn,
        orgnr,
        broker_name,
        broker_contact,
        broker_phone,
        today_str,
        _DARK_BLUE,
        _MID_BLUE,
    )
    return bytes(pdf.output())
