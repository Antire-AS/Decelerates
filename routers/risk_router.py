import io
import json
import re
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from fpdf import FPDF
from fastapi import APIRouter, Query, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from db import Company, CompanyHistory, InsuranceOffer, BrokerSettings, InsuranceDocument
from domain.exceptions import LlmUnavailableError, QuotaError
from services import (
    fetch_ssb_benchmark,
    _llm_answer_raw,
    _save_to_rag,
    fetch_board_members,
    _generate_risk_narrative,
    _fmt_nok,
    _extract_offer_summary,
)
from schemas import ForsikringstilbudRequest
from dependencies import get_db
from risk import derive_simple_risk
from prompts import RISK_OFFER_PROMPT, RISK_OFFER_PROMPT_EN
from google import genai as google_genai
import os

router = APIRouter()


_RISK_OFFER_PROMPT_EN = RISK_OFFER_PROMPT_EN  # backward-compat alias
_RISK_OFFER_PROMPT = RISK_OFFER_PROMPT        # backward-compat alias


@router.post("/org/{orgnr}/risk-offer")
def generate_risk_offer(orgnr: str, lang: str = Query("no"), db: Session = Depends(get_db)):
    """Generate LLM-based insurance recommendations from the company's risk profile."""
    db_obj = db.query(Company).filter(Company.orgnr == orgnr).first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Company not in database — call /org/{orgnr} first")

    org = {
        "orgnr": db_obj.orgnr,
        "navn": db_obj.navn,
        "organisasjonsform_kode": db_obj.organisasjonsform_kode,
        "kommune": db_obj.kommune,
        "naeringskode1": db_obj.naeringskode1,
        "naeringskode1_beskrivelse": db_obj.naeringskode1_beskrivelse,
        "stiftelsesdato": (db_obj.regnskap_raw or {}).get("stiftelsesdato"),
        "konkurs": False,
        "under_konkursbehandling": False,
        "under_avvikling": False,
    }
    regn = db_obj.regnskap_raw or {}  # JSON column, always dict at runtime
    pep = db_obj.pep_raw or {}        # JSON column, always dict at runtime

    risk = derive_simple_risk(org, regn, pep)  # type: ignore[arg-type]
    benchmark = fetch_ssb_benchmark(db_obj.naeringskode1 or "")  # type: ignore[arg-type]

    def fmt_mnok(v):
        if v is None:
            return "ukjent"
        return f"{v/1e6:.1f} MNOK"

    eq_ratio = risk.get("equity_ratio")
    eq_str = f"{eq_ratio*100:.1f}%" if eq_ratio is not None else "ukjent"
    company_info = (
        f"Navn: {db_obj.navn}\n"
        f"Orgnr: {db_obj.orgnr}\n"
        f"Organisasjonsform: {db_obj.organisasjonsform_kode}\n"
        f"Bransje: {db_obj.naeringskode1_beskrivelse} (NACE {db_obj.naeringskode1})\n"
        f"Kommune: {db_obj.kommune}\n"
        f"Omsetning: {fmt_mnok(db_obj.sum_driftsinntekter)}\n"
        f"Egenkapital: {fmt_mnok(db_obj.sum_egenkapital)}\n"
        f"Sum eiendeler: {fmt_mnok(db_obj.sum_eiendeler)}\n"
        f"Ansatte: {regn.get('antall_ansatte', 'ukjent')}\n"
        f"Årsresultat: {fmt_mnok(regn.get('aarsresultat'))}\n"
        f"Egenkapitalandel: {eq_str}"
    )

    factors_text = "\n".join(
        f"- {f['label']} (+{f['points']}p, {f['category']}): {f.get('detail', '')}"
        for f in risk["factors"]
    ) or "Ingen spesifikke risikofaktorer identifisert"

    benchmark_text = (
        f"Typisk egenkapitalandel for bransjen: {benchmark.get('equity_ratio_low', 0)*100:.0f}%–{benchmark.get('equity_ratio_high', 0)*100:.0f}%\n"
        f"Typisk fortjenestemargin: {benchmark.get('profit_margin_low', 0)*100:.0f}%–{benchmark.get('profit_margin_high', 0)*100:.0f}%"
        if benchmark else "Ingen bransjebenchmark tilgjengelig"
    )

    _prompt_tmpl = _RISK_OFFER_PROMPT_EN if lang == "en" else _RISK_OFFER_PROMPT
    prompt = _prompt_tmpl.format(
        company_info=company_info,
        score=risk["score"],
        factors=factors_text,
        benchmark=benchmark_text,
    )

    try:
        raw = _llm_answer_raw(prompt)
    except QuotaError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except LlmUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    if not raw:
        raise HTTPException(status_code=503, detail="Ingen LLM tilgjengelig — legg til GEMINI_API_KEY eller ANTHROPIC_API_KEY i .env")

    # Parse JSON
    try:
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        result = json.loads(json_match.group(0)) if json_match else json.loads(raw)
    except Exception:
        result = {"sammendrag": raw, "anbefalinger": [], "total_premieanslag": "ukjent"}

    # Save to RAG so the analyst chat can reference this recommendation
    _rag_text = result.get("sammendrag", "")
    if result.get("anbefalinger"):
        _recs = "\n".join(
            f"- {a.get('type','')}: {a.get('anbefalt_sum','')} ({a.get('prioritet','')}) — {a.get('begrunnelse','')}"
            for a in result["anbefalinger"]
        )
        _rag_text = (_rag_text + "\n\nAnbefalinger:\n" + _recs).strip()
    if _rag_text:
        _save_to_rag(orgnr, "Forsikringsanbefaling", _rag_text, db)

    return {
        "orgnr": orgnr,
        "navn": db_obj.navn,
        "risk_score": risk["score"],
        "risk_factors": risk["factors"],
        **result,
    }


@router.post("/org/{orgnr}/coverage-gap")
def coverage_gap_analysis(orgnr: str, lang: str = Query("no"), db: Session = Depends(get_db)):
    """Compare uploaded insurance offers against the company's risk profile to identify coverage gaps."""
    db_obj = db.query(Company).filter(Company.orgnr == orgnr).first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Company not in database — call /org/{orgnr} first")

    offers = db.query(InsuranceOffer).filter(InsuranceOffer.orgnr == orgnr).all()
    if not offers:
        return {"status": "no_offers", "message": "Ingen tilbud lastet opp for dette selskapet."}

    org = {
        "orgnr": db_obj.orgnr,
        "navn": db_obj.navn,
        "organisasjonsform_kode": db_obj.organisasjonsform_kode,
        "naeringskode1": db_obj.naeringskode1,
        "naeringskode1_beskrivelse": db_obj.naeringskode1_beskrivelse,
        "stiftelsesdato": (db_obj.regnskap_raw or {}).get("stiftelsesdato"),
        "konkurs": False, "under_konkursbehandling": False, "under_avvikling": False,
    }
    regn = db_obj.regnskap_raw or {}
    pep = db_obj.pep_raw or {}
    risk = derive_simple_risk(org, regn, pep)  # type: ignore[arg-type]

    factors_text = "\n".join(
        f"- {f['label']} (+{f['points']}p): {f.get('detail', '')}"
        for f in risk["factors"]
    ) or "Ingen spesifikke risikofaktorer identifisert"

    offers_text = ""
    for i, offer in enumerate(offers, 1):
        text = (offer.extracted_text or "")[:3000]
        offers_text += f"\n=== Tilbud {i}: {offer.insurer_name or offer.filename} ===\n{text}\n"

    if lang == "en":
        prompt = f"""You are an expert insurance broker. Analyze the match between the company's risk profile and the uploaded insurance offers to identify coverage gaps.

COMPANY: {db_obj.navn} (orgnr {db_obj.orgnr})
INDUSTRY: {db_obj.naeringskode1_beskrivelse} (NACE {db_obj.naeringskode1})

RISK FACTORS:
{factors_text}

UPLOADED OFFERS:
{offers_text}

Return ONLY valid JSON:
{{
  "dekket": ["coverage 1 included in the offers", "coverage 2", ...],
  "mangler": ["risk/coverage missing from the offers", ...],
  "anbefaling": "2-3 sentences with concrete recommendations for the broker"
}}"""
    else:
        prompt = f"""Du er en norsk forsikringsekspert. Analyser samsvar mellom selskapets risikoprofil og de opplastede forsikringstilbudene.

SELSKAP: {db_obj.navn} (orgnr {db_obj.orgnr})
BRANSJE: {db_obj.naeringskode1_beskrivelse} (NACE {db_obj.naeringskode1})

RISIKOFAKTORER:
{factors_text}

OPPLASTEDE TILBUD:
{offers_text}

Returner KUN gyldig JSON:
{{
  "dekket": ["dekning 1 som er inkludert i tilbudene", "dekning 2", ...],
  "mangler": ["risiko/dekning som mangler i tilbudene", ...],
  "anbefaling": "2-3 setninger med konkrete anbefalinger til megleren"
}}"""

    try:
        raw = _llm_answer_raw(prompt)
    except QuotaError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except LlmUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    if not raw:
        return {"status": "error", "dekket": [], "mangler": [], "anbefaling": "Ingen LLM tilgjengelig."}

    try:
        import re as _re
        m = _re.search(r"\{.*\}", raw, _re.DOTALL)
        result = json.loads(m.group(0)) if m else json.loads(raw)
    except Exception:
        result = {"dekket": [], "mangler": [], "anbefaling": raw}

    # Save to RAG
    _gap_parts = []
    if result.get("dekket"):
        _gap_parts.append("Dekket: " + "; ".join(result["dekket"]))
    if result.get("mangler"):
        _gap_parts.append("Mangler: " + "; ".join(result["mangler"]))
    if result.get("anbefaling"):
        _gap_parts.append("Anbefaling: " + result["anbefaling"])
    if _gap_parts:
        _save_to_rag(orgnr, "Dekningstomme analyse", "\n".join(_gap_parts), db)

    return {"status": "ok", **result}


@router.get("/org/{orgnr}/risk-report/pdf")
def download_risk_report(orgnr: str, db: Session = Depends(get_db)):
    """Generate and return a PDF risk assessment report."""

    db_obj = db.query(Company).filter(Company.orgnr == orgnr).first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Company not in database")

    org = {
        "orgnr": db_obj.orgnr,
        "navn": db_obj.navn,
        "organisasjonsform_kode": db_obj.organisasjonsform_kode,
        "kommune": db_obj.kommune,
        "naeringskode1": db_obj.naeringskode1,
        "naeringskode1_beskrivelse": db_obj.naeringskode1_beskrivelse,
        "stiftelsesdato": (db_obj.regnskap_raw or {}).get("stiftelsesdato"),
        "konkurs": False,
        "under_konkursbehandling": False,
        "under_avvikling": False,
    }
    regn = db_obj.regnskap_raw or {}
    pep = db_obj.pep_raw or {}
    risk = derive_simple_risk(org, regn, pep)  # type: ignore[arg-type]

    def fmt_mnok(v):
        if v is None:
            return "–"
        return f"{v/1e6:,.1f} MNOK"

    def score_label(s):
        if s <= 3:
            return "Lav"
        if s <= 7:
            return "Moderat"
        if s <= 11:
            return "Høy"
        return "Svært høy"

    today = date.today().strftime("%d.%m.%Y")

    class RiskPDF(FPDF):
        def header(self):
            self.set_font("Helvetica", "B", 9)
            self.set_text_color(120, 120, 120)
            self.cell(0, 8, f"Risikovurdering — {db_obj.navn}", align="L")
            self.ln(0)

        def footer(self):
            self.set_y(-15)
            self.set_font("Helvetica", "", 8)
            self.set_text_color(150, 150, 150)
            self.cell(0, 10, f"Side {self.page_no()} | Generert {today}", align="C")

    pdf = RiskPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(20, 20, 20)
    pdf.add_page()

    def section_title(title):
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(30, 60, 120)
        pdf.cell(0, 8, title, ln=True)
        pdf.set_draw_color(30, 60, 120)
        pdf.line(20, pdf.get_y(), 190, pdf.get_y())
        pdf.ln(4)
        pdf.set_text_color(0, 0, 0)

    def row(label, value, bold_value=False):
        pdf.set_font("Helvetica", "", 10)
        pdf.set_fill_color(245, 247, 252)
        pdf.cell(70, 7, label, border=0)
        pdf.set_font("Helvetica", "B" if bold_value else "", 10)
        pdf.cell(0, 7, str(value), border=0, ln=True)
        pdf.set_font("Helvetica", "", 10)

    # ── Forside ──
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(30, 60, 120)
    pdf.ln(10)
    pdf.cell(0, 12, "Risikovurdering", ln=True)
    pdf.cell(0, 12, "og forsikringsanbefaling", ln=True)
    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 8, db_obj.navn, ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, f"Orgnr: {db_obj.orgnr}  |  Dato: {today}", ln=True)
    pdf.ln(6)

    # Score-boks
    s = risk["score"]
    lbl = score_label(s)
    color = {
        "Lav": (34, 139, 34),
        "Moderat": (255, 140, 0),
        "Høy": (220, 80, 0),
        "Svært høy": (180, 0, 0),
    }.get(lbl, (0, 0, 0))
    pdf.set_fill_color(*color)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(60, 14, f"Risikoscore: {s}  ({lbl})", fill=True, ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(8)

    # ── Selskapsprofil ──
    section_title("Selskapsprofil")
    row("Navn", db_obj.navn)
    row("Orgnr", db_obj.orgnr)
    row("Organisasjonsform", db_obj.organisasjonsform_kode or "–")
    row("Bransje", f"{db_obj.naeringskode1_beskrivelse or '–'} ({db_obj.naeringskode1 or '–'})")
    row("Kommune", db_obj.kommune or "–")
    row("Stiftelsesdato", org.get("stiftelsesdato") or "–")
    pdf.ln(6)

    # ── Finansiell analyse ──
    section_title("Finansielle nøkkeltall")
    row("Omsetning", fmt_mnok(db_obj.sum_driftsinntekter))
    row("Årsresultat", fmt_mnok(regn.get("aarsresultat")))
    row("Egenkapital", fmt_mnok(db_obj.sum_egenkapital))
    row("Sum eiendeler", fmt_mnok(db_obj.sum_eiendeler))
    row("Sum gjeld", fmt_mnok(regn.get("sum_gjeld")))
    eq = risk.get("equity_ratio")
    row("Egenkapitalandel", f"{eq*100:.1f}%" if eq is not None else "–")
    row("Antall ansatte", str(regn.get("antall_ansatte") or "–"))
    pdf.ln(6)

    # ── Risikofaktorer ──
    section_title("Risikofaktorer")
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
    pdf.cell(115, 7, f"Total risikoscore: {s} ({lbl})", border=1, ln=True)
    pdf.ln(6)

    pdf_bytes = bytes(pdf.output())
    filename = f"risikorapport_{orgnr}_{date.today().isoformat()}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/org/{orgnr}/forsikringstilbud/pdf")
def download_forsikringstilbud(
    orgnr: str,
    body: ForsikringstilbudRequest,
    save: bool = Query(False),
    db: Session = Depends(get_db),
):
    """Generate a professional Norwegian insurance offer (Forsikringstilbud) PDF."""
    import datetime as _dt

    db_obj = db.query(Company).filter(Company.orgnr == orgnr).first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Company not in database")

    # Fetch stored insurance offers for this company
    stored_offers: list = db.query(InsuranceOffer).filter(InsuranceOffer.orgnr == orgnr).all()
    offer_summaries: list[dict] = []
    for offer_row in stored_offers:
        summary = _extract_offer_summary(
            offer_row.insurer_name or offer_row.filename,
            offer_row.extracted_text or "",
        )
        offer_summaries.append(summary)

    # Fetch broker settings
    broker_row = db.query(BrokerSettings).filter(BrokerSettings.id == 1).first()
    broker_name = (broker_row.firm_name if broker_row and broker_row.firm_name else "Forsikringsmegler AS")
    broker_contact = (broker_row.contact_name if broker_row and broker_row.contact_name else "")
    broker_email = (broker_row.contact_email if broker_row and broker_row.contact_email else "")
    broker_phone = (broker_row.contact_phone if broker_row and broker_row.contact_phone else "")

    today_str = date.today().strftime("%d.%m.%Y")
    valid_str = (_dt.date.today() + _dt.timedelta(days=30)).strftime("%d.%m.%Y")

    anbefalinger = body.anbefalinger or []
    total_premie = body.total_premieanslag or "–"
    sammendrag = body.sammendrag or ""

    DARK_BLUE  = (20,  50, 120)
    MID_BLUE   = (50,  90, 170)
    LIGHT_BLUE = (220, 230, 250)
    ACCENT     = (0,  150, 136)
    MUST_RED   = (200,  50,  50)
    REC_ORG    = (220, 100,  30)
    OPT_GRY    = (100, 100, 100)

    def priority_color(p: str):
        p = (p or "").lower()
        if "må" in p:   return MUST_RED
        if "anbefalt" in p: return REC_ORG
        return OPT_GRY

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(18, 15, 18)

    # ── FORSIDE ──────────────────────────────────────────────────────────────
    pdf.add_page()

    # Top bar
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

    # "FORSIKRINGSTILBUD" heading
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(*DARK_BLUE)
    pdf.cell(0, 14, "FORSIKRINGSTILBUD", ln=True)

    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 7, f"Utarbeidet av {broker_name}", ln=True)
    pdf.ln(8)

    # Company info box
    pdf.set_fill_color(*LIGHT_BLUE)
    pdf.rect(18, pdf.get_y(), 174, 42, "F")
    y0 = pdf.get_y() + 4
    pdf.set_xy(22, y0)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*DARK_BLUE)
    pdf.cell(0, 8, db_obj.navn or "–", ln=True)
    pdf.set_xy(22, pdf.get_y())
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 6, f"Org.nr: {db_obj.orgnr}", ln=True)
    pdf.set_xy(22, pdf.get_y())
    pdf.cell(0, 6, f"Bransje: {db_obj.naeringskode1_beskrivelse or '–'} (NACE {db_obj.naeringskode1 or '–'})", ln=True)
    pdf.set_xy(22, pdf.get_y())
    pdf.cell(0, 6, f"Kommune: {db_obj.kommune or '–'}  |  Form: {db_obj.organisasjonsform_kode or '–'}", ln=True)

    pdf.set_y(pdf.get_y() + 14)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(55, 6, f"Tilbudsdato: {today_str}")
    pdf.cell(70, 6, f"Gyldig til: {valid_str}")
    pdf.cell(0, 6, f"Antall dekninger: {len(anbefalinger)}", ln=True)
    pdf.ln(8)

    # Sammendrag
    if sammendrag:
        pdf.set_fill_color(240, 248, 255)
        pdf.set_draw_color(*MID_BLUE)
        pdf.set_line_width(0.4)
        x = pdf.get_x(); y = pdf.get_y()
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(50, 50, 50)
        pdf.multi_cell(174, 5, sammendrag, border=1, fill=True)
        pdf.set_draw_color(0, 0, 0)
        pdf.set_line_width(0.2)
    pdf.ln(6)

    # Premium highlight box
    pdf.set_fill_color(*DARK_BLUE)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(174, 12, f"  Estimert totalpremie: {total_premie}", fill=True, ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 5, "Alle premier er veiledende estimater og kan variere ved endelig tegning.", ln=True)

    # ── INNHENTEDE TILBUD (hvis lagret) ──────────────────────────────────────
    if offer_summaries:
        pdf.add_page()
        pdf.set_text_color(*DARK_BLUE)
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "Innhentede tilbud fra forsikringsselskaper", ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 5, f"{len(offer_summaries)} tilbud mottatt og analysert  ·  {today_str}", ln=True)
        pdf.ln(5)

        # Comparison table header
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

        # Strengths / weaknesses per offer
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

    # ── DEKNINGSTABEL ─────────────────────────────────────────────────────────
    pdf.add_page()

    pdf.set_text_color(*DARK_BLUE)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Forsikringsdekning — oversikt", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, f"{db_obj.navn}  ·  Org.nr {db_obj.orgnr}  ·  {today_str}", ln=True)
    pdf.ln(4)

    # Table header
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
        pdf.set_font("Helvetica", "B" if i == 0 else "", 9)

        # row height based on text length
        beg = str(rec.get("begrunnelse") or "")[:80]
        row_h = 6

        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(58, row_h, str(rec.get("type") or "")[:30], border="TB", fill=fill)

        # Priority with colour
        pri = str(rec.get("prioritet") or "")
        pdf.set_text_color(*priority_color(pri))
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(22, row_h, pri, border="TB", fill=fill)

        pdf.set_text_color(30, 30, 30)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(40, row_h, str(rec.get("anbefalt_sum") or "")[:25], border="TB", fill=fill)
        pdf.cell(54, row_h, beg, border="TB", fill=fill, ln=True)

    # Total row
    pdf.set_fill_color(*DARK_BLUE)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(120, 9, "Estimert totalpremie", fill=True, border=0)
    pdf.cell(54, 9, total_premie, fill=True, border=0, ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(6)

    # ── INDIVIDUELLE DEKNINGSSIDER ────────────────────────────────────────────
    for rec in anbefalinger:
        pdf.add_page()

        pri = str(rec.get("prioritet") or "")
        pri_color = priority_color(pri)

        # Section header bar
        pdf.set_fill_color(*MID_BLUE)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 12, f"  {rec.get('type', '')}", fill=True, ln=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(4)

        # Priority badge
        pdf.set_fill_color(*pri_color)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(35, 7, f"  {pri}", fill=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(8)

        def detail_row(label, value):
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(60, 60, 100)
            pdf.cell(52, 7, label)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(30, 30, 30)
            pdf.cell(0, 7, str(value), ln=True)

        detail_row("Dekningssum:", rec.get("anbefalt_sum") or "–")

        # Begrunnelse (full text)
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*DARK_BLUE)
        pdf.cell(0, 6, "Begrunnelse", ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(50, 50, 50)
        pdf.multi_cell(0, 5, str(rec.get("begrunnelse") or "–"))
        pdf.ln(4)

        # Standard vilkår note
        pdf.set_fill_color(245, 247, 252)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(100, 100, 100)
        pdf.multi_cell(0, 5,
            "Dekningsomfang og vilkår fastsettes endelig ved tegning. "
            "Premier er estimater basert på oppgitte nøkkeltall og kan avvike fra endelig premie. "
            "Forsikringsselskap og produktvalg klargjøres i endelig tilbud.",
            border=1, fill=True,
        )

    # ── BETINGELSER OG SIGNATUR ───────────────────────────────────────────────
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

    # Signature block
    pdf.set_draw_color(*MID_BLUE)
    pdf.set_line_width(0.4)
    pdf.line(18, pdf.get_y(), 105, pdf.get_y())
    pdf.line(120, pdf.get_y(), 192, pdf.get_y())
    pdf.ln(1)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(87, 5, f"Megler: {broker_name}")
    pdf.cell(33, 5, "")
    pdf.cell(0, 5, f"Kunde: {db_obj.navn}", ln=True)
    pdf.cell(87, 5, f"Kontakt: {broker_contact}  {broker_phone}")
    pdf.cell(33, 5, "")
    pdf.cell(0, 5, f"Org.nr: {db_obj.orgnr}", ln=True)
    pdf.ln(3)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 5, f"Generert {today_str} av Broker Accelerator  ·  Ikke bindende uten signatur fra begge parter.", ln=True)

    pdf_bytes = bytes(pdf.output())
    filename = f"forsikringstilbud_{orgnr}_{date.today().isoformat()}.pdf"

    if save:
        _doc = InsuranceDocument(
            title=f"Forsikringstilbud — {db_obj.navn}",
            category="anbefaling",
            insurer="AI-generert",
            year=date.today().year,
            period="aktiv",
            orgnr=orgnr,
            filename=filename,
            pdf_content=pdf_bytes,
            extracted_text=None,
            uploaded_at=datetime.now(timezone.utc).isoformat(),
        )
        db.add(_doc)
        db.commit()

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/org/{orgnr}/narrative")
def generate_narrative(orgnr: str, lang: str = Query("no"), db: Session = Depends(get_db)):
    db_obj = db.query(Company).filter(Company.orgnr == orgnr).first()
    if not db_obj:
        raise HTTPException(
            status_code=404,
            detail="Company not in database — call /org/{orgnr} first",
        )
    org = {
        "navn": db_obj.navn,
        "organisasjonsform": db_obj.organisasjonsform_kode,
        "organisasjonsform_kode": db_obj.organisasjonsform_kode,
        "naeringskode1": db_obj.naeringskode1,
        "naeringskode1_beskrivelse": db_obj.naeringskode1_beskrivelse,
        "kommune": db_obj.kommune,
    }
    regn: Dict[str, Any] = dict(db_obj.regnskap_raw) if db_obj.regnskap_raw else {}
    risk_data = None
    if regn:
        risk_data = derive_simple_risk(org, regn)
    pep: Dict[str, Any] = dict(db_obj.pep_raw) if db_obj.pep_raw else {}

    try:
        members = fetch_board_members(orgnr)
    except Exception:
        members = []

    narrative = _generate_risk_narrative(org, regn, risk_data, pep, members, lang=lang)
    if narrative is None:
        raise HTTPException(
            status_code=503,
            detail="No LLM API key configured (ANTHROPIC_API_KEY or GEMINI_API_KEY)",
        )

    # Save to RAG so the analyst chat can reference this narrative
    _save_to_rag(orgnr, "AI Risikoanalyse", narrative, db)

    return {"orgnr": orgnr, "narrative": narrative}
