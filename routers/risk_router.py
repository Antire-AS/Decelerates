import io
import json
import re
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, HTTPException, Depends
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel

from db import Company, CompanyHistory, InsuranceOffer, BrokerSettings
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
from services.pdf_generate import generate_risk_report_pdf, generate_forsikringstilbud_pdf
from services.pdf_sources import save_insurance_document
from schemas import ForsikringstilbudRequest
from dependencies import get_db
from risk import derive_simple_risk
from prompts import RISK_OFFER_PROMPT, RISK_OFFER_PROMPT_EN
import os

router = APIRouter()


_RISK_OFFER_PROMPT_EN = RISK_OFFER_PROMPT_EN  # backward-compat alias
_RISK_OFFER_PROMPT = RISK_OFFER_PROMPT        # backward-compat alias


def _org_dict_from_db(db_obj: Company) -> dict:
    return {
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


@router.post("/org/{orgnr}/risk-offer")
def generate_risk_offer(orgnr: str, lang: str = Query("no"), db: Session = Depends(get_db)):
    """Generate LLM-based insurance recommendations from the company's risk profile."""
    db_obj = db.query(Company).filter(Company.orgnr == orgnr).first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Company not in database — call /org/{orgnr} first")

    org = _org_dict_from_db(db_obj)
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

    org = _org_dict_from_db(db_obj)
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

    org = _org_dict_from_db(db_obj)
    regn = db_obj.regnskap_raw or {}
    pep = db_obj.pep_raw or {}
    risk = derive_simple_risk(org, regn, pep)  # type: ignore[arg-type]

    pdf_bytes = generate_risk_report_pdf(
        orgnr=db_obj.orgnr,
        navn=db_obj.navn,
        organisasjonsform_kode=db_obj.organisasjonsform_kode,
        kommune=db_obj.kommune,
        naeringskode1=db_obj.naeringskode1,
        naeringskode1_beskrivelse=db_obj.naeringskode1_beskrivelse,
        stiftelsesdato=org.get("stiftelsesdato"),
        sum_driftsinntekter=db_obj.sum_driftsinntekter,
        sum_egenkapital=db_obj.sum_egenkapital,
        sum_eiendeler=db_obj.sum_eiendeler,
        regn=regn,
        risk=risk,
    )
    filename = f"risikorapport_{orgnr}_{date.today().isoformat()}.pdf"
    return Response(
        content=pdf_bytes,
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
    db_obj = db.query(Company).filter(Company.orgnr == orgnr).first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Company not in database")

    stored_offers = db.query(InsuranceOffer).filter(InsuranceOffer.orgnr == orgnr).all()
    offer_summaries = [
        _extract_offer_summary(row.insurer_name or row.filename, row.extracted_text or "")
        for row in stored_offers
    ]

    broker_row = db.query(BrokerSettings).filter(BrokerSettings.id == 1).first()
    broker_name = broker_row.firm_name if broker_row and broker_row.firm_name else "Forsikringsmegler AS"
    broker_contact = broker_row.contact_name if broker_row and broker_row.contact_name else ""
    broker_email = broker_row.contact_email if broker_row and broker_row.contact_email else ""
    broker_phone = broker_row.contact_phone if broker_row and broker_row.contact_phone else ""

    anbefalinger = body.anbefalinger or []
    total_premie = body.total_premieanslag or "–"
    sammendrag = body.sammendrag or ""

    pdf_bytes = generate_forsikringstilbud_pdf(
        orgnr=db_obj.orgnr,
        navn=db_obj.navn,
        organisasjonsform_kode=db_obj.organisasjonsform_kode,
        naeringskode1=db_obj.naeringskode1,
        naeringskode1_beskrivelse=db_obj.naeringskode1_beskrivelse,
        kommune=db_obj.kommune,
        broker_name=broker_name,
        broker_contact=broker_contact,
        broker_email=broker_email,
        broker_phone=broker_phone,
        anbefalinger=anbefalinger,
        total_premie=total_premie,
        sammendrag=sammendrag,
        offer_summaries=offer_summaries,
    )
    filename = f"forsikringstilbud_{orgnr}_{date.today().isoformat()}.pdf"

    if save:
        save_insurance_document(orgnr, db_obj.navn, filename, pdf_bytes, db)

    return Response(
        content=pdf_bytes,
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
