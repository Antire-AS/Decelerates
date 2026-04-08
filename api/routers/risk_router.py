from datetime import date
from typing import Any, Dict

from fastapi import APIRouter, Query, HTTPException, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

import os

import logging

from api.auth import CurrentUser, get_current_user
from api.container import resolve
from api.db import Company, InsuranceOffer, BrokerSettings
from api.domain.exceptions import LlmUnavailableError, QuotaError
from api.ports.driven.notification_port import NotificationPort


def _get_notification() -> NotificationPort:
    return resolve(NotificationPort)  # type: ignore[return-value]
from api.services.audit import log_audit
from api.services.client_token_service import get_or_create_active_token
from api.services.llm import _llm_answer_raw, _parse_json_from_llm_response
from api.services.rag import _save_to_rag
from api.services.company import _generate_risk_narrative
from api.services.external_apis import fetch_ssb_benchmark, fetch_board_members
from api.services.pdf_generate import (
    _extract_offer_summary,
    generate_risk_report_pdf,
    generate_forsikringstilbud_pdf,
)
from api.services.pdf_sources import save_insurance_document
from api.schemas import ForsikringstilbudRequest, RiskOfferOut, NarrativeOut
from api.dependencies import get_db
from api.risk import derive_simple_risk
from api.prompts import RISK_OFFER_PROMPT, RISK_OFFER_PROMPT_EN

_log = logging.getLogger(__name__)

router = APIRouter()


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


def _fmt_mnok(v) -> str:
    return "ukjent" if v is None else f"{v/1e6:.1f} MNOK"


def _build_company_info_text(db_obj: Company, risk: dict, regn: dict) -> str:
    eq_ratio = risk.get("equity_ratio")
    eq_str = f"{eq_ratio*100:.1f}%" if eq_ratio is not None else "ukjent"
    return (
        f"Navn: {db_obj.navn}\n"
        f"Orgnr: {db_obj.orgnr}\n"
        f"Organisasjonsform: {db_obj.organisasjonsform_kode}\n"
        f"Bransje: {db_obj.naeringskode1_beskrivelse} (NACE {db_obj.naeringskode1})\n"
        f"Kommune: {db_obj.kommune}\n"
        f"Omsetning: {_fmt_mnok(db_obj.sum_driftsinntekter)}\n"
        f"Egenkapital: {_fmt_mnok(db_obj.sum_egenkapital)}\n"
        f"Sum eiendeler: {_fmt_mnok(db_obj.sum_eiendeler)}\n"
        f"Ansatte: {regn.get('antall_ansatte', 'ukjent')}\n"
        f"Årsresultat: {_fmt_mnok(regn.get('aarsresultat'))}\n"
        f"Egenkapitalandel: {eq_str}"
    )


def _build_factors_text(factors: list) -> str:
    return "\n".join(
        f"- {f['label']} (+{f['points']}p, {f['category']}): {f.get('detail', '')}"
        for f in factors
    ) or "Ingen spesifikke risikofaktorer identifisert"


def _build_benchmark_text(benchmark) -> str:
    if not benchmark:
        return "Ingen bransjebenchmark tilgjengelig"
    return (
        f"Typisk egenkapitalandel for bransjen: {benchmark.get('equity_ratio_low', 0)*100:.0f}%–{benchmark.get('equity_ratio_high', 0)*100:.0f}%\n"
        f"Typisk fortjenestemargin: {benchmark.get('profit_margin_low', 0)*100:.0f}%–{benchmark.get('profit_margin_high', 0)*100:.0f}%"
    )


def _save_offer_recommendation_to_rag(orgnr: str, result: dict, db) -> None:
    rag_text = result.get("sammendrag", "")
    if result.get("anbefalinger"):
        recs = "\n".join(
            f"- {a.get('type','')}: {a.get('anbefalt_sum','')} ({a.get('prioritet','')}) — {a.get('begrunnelse','')}"
            for a in result["anbefalinger"]
        )
        rag_text = (rag_text + "\n\nAnbefalinger:\n" + recs).strip()
    if rag_text:
        _save_to_rag(orgnr, "Forsikringsanbefaling", rag_text, db)


@router.post("/org/{orgnr}/risk-offer", response_model=RiskOfferOut)
def generate_risk_offer(orgnr: str, lang: str = Query("no"), db: Session = Depends(get_db)) -> dict:
    """Generate LLM-based insurance recommendations from the company's risk profile."""
    db_obj = db.query(Company).filter(Company.orgnr == orgnr).first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Company not in database — call /org/{orgnr} first")

    org = _org_dict_from_db(db_obj)
    regn = db_obj.regnskap_raw or {}
    pep = db_obj.pep_raw or {}
    risk = derive_simple_risk(org, regn, pep)  # type: ignore[arg-type]

    prompt = (RISK_OFFER_PROMPT_EN if lang == "en" else RISK_OFFER_PROMPT).format(
        company_info=_build_company_info_text(db_obj, risk, regn),
        score=risk["score"],
        factors=_build_factors_text(risk["factors"]),
        benchmark=_build_benchmark_text(fetch_ssb_benchmark(db_obj.naeringskode1 or "")),  # type: ignore[arg-type]
    )

    try:
        raw = _llm_answer_raw(prompt)
    except QuotaError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except LlmUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    if not raw:
        raise HTTPException(
            status_code=503,
            detail="Ingen LLM tilgjengelig — sett AZURE_FOUNDRY_BASE_URL og AZURE_FOUNDRY_API_KEY i .env",
        )

    result = _parse_json_from_llm_response(raw) or {"sammendrag": raw, "anbefalinger": [], "total_premieanslag": "ukjent"}
    _save_offer_recommendation_to_rag(orgnr, result, db)
    return {"orgnr": orgnr, "navn": db_obj.navn, "risk_score": risk["score"], "risk_factors": risk["factors"], **result}


def _build_offers_text(offers: list) -> str:
    return "".join(
        f"\n=== Tilbud {i}: {o.insurer_name or o.filename} ===\n{(o.extracted_text or '')[:3000]}\n"
        for i, o in enumerate(offers, 1)
    )


def _build_gap_prompt(db_obj: Company, factors_text: str, offers_text: str, lang: str) -> str:
    if lang == "en":
        return (
            f"You are an expert insurance broker. Analyze the match between the company's risk profile and the uploaded insurance offers to identify coverage gaps.\n\n"
            f"COMPANY: {db_obj.navn} (orgnr {db_obj.orgnr})\n"
            f"INDUSTRY: {db_obj.naeringskode1_beskrivelse} (NACE {db_obj.naeringskode1})\n\n"
            f"RISK FACTORS:\n{factors_text}\n\nUPLOADED OFFERS:\n{offers_text}\n\n"
            f'Return ONLY valid JSON:\n{{"dekket": [...], "mangler": [...], "anbefaling": "2-3 sentences"}}'
        )
    return (
        f"Du er en norsk forsikringsekspert. Analyser samsvar mellom selskapets risikoprofil og de opplastede forsikringstilbudene.\n\n"
        f"SELSKAP: {db_obj.navn} (orgnr {db_obj.orgnr})\n"
        f"BRANSJE: {db_obj.naeringskode1_beskrivelse} (NACE {db_obj.naeringskode1})\n\n"
        f"RISIKOFAKTORER:\n{factors_text}\n\nOPPLASTEDE TILBUD:\n{offers_text}\n\n"
        f'Returner KUN gyldig JSON:\n{{"dekket": [...], "mangler": [...], "anbefaling": "2-3 setninger"}}'
    )


def _broker_info_from_db(db) -> tuple:
    """Return (broker_name, broker_contact, broker_email, broker_phone) from DB."""
    row = db.query(BrokerSettings).filter(BrokerSettings.id == 1).first()
    name    = row.firm_name      if row and row.firm_name      else "Forsikringsmegler AS"
    contact = row.contact_name   if row and row.contact_name   else ""
    email   = row.contact_email  if row and row.contact_email  else ""
    phone   = row.contact_phone  if row and row.contact_phone  else ""
    return name, contact, email, phone


def _save_gap_to_rag(orgnr: str, result: dict, db) -> None:
    parts = []
    if result.get("dekket"):
        parts.append("Dekket: " + "; ".join(result["dekket"]))
    if result.get("mangler"):
        parts.append("Mangler: " + "; ".join(result["mangler"]))
    if result.get("anbefaling"):
        parts.append("Anbefaling: " + result["anbefaling"])
    if parts:
        _save_to_rag(orgnr, "Dekningstomme analyse", "\n".join(parts), db)


@router.post("/org/{orgnr}/coverage-gap")
def coverage_gap_analysis(orgnr: str, lang: str = Query("no"), db: Session = Depends(get_db)) -> dict:
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

    prompt = _build_gap_prompt(
        db_obj,
        factors_text=_build_factors_text(risk["factors"]),
        offers_text=_build_offers_text(offers),
        lang=lang,
    )

    try:
        raw = _llm_answer_raw(prompt)
    except QuotaError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except LlmUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    if not raw:
        return {"status": "error", "dekket": [], "mangler": [], "anbefaling": "Ingen LLM tilgjengelig."}

    result = _parse_json_from_llm_response(raw) or {"dekket": [], "mangler": [], "anbefaling": raw}
    _save_gap_to_rag(orgnr, result, db)
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


def _build_forsikringstilbud_pdf(db_obj: Company, body: ForsikringstilbudRequest,
                                  offer_summaries: list, broker_name: str,
                                  broker_contact: str, broker_email: str, broker_phone: str) -> bytes:
    return generate_forsikringstilbud_pdf(
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
        anbefalinger=body.anbefalinger or [],
        total_premie=body.total_premieanslag or "–",
        sammendrag=body.sammendrag or "",
        offer_summaries=offer_summaries,
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
    offer_summaries = []
    for row in stored_offers:
        if row.parsed_premie:
            offer_summaries.append({
                "selskap": row.insurer_name or row.filename,
                "premie": row.parsed_premie,
                "dekning": row.parsed_dekning or "–",
                "egenandel": row.parsed_egenandel or "–",
                "vilkaar": row.parsed_vilkaar or "–",
                "styrker": row.parsed_styrker or "–",
                "svakheter": row.parsed_svakheter or "–",
            })
        else:
            offer_summaries.append(
                _extract_offer_summary(row.insurer_name or row.filename, row.extracted_text or "")
            )
    broker_name, broker_contact, broker_email, broker_phone = _broker_info_from_db(db)
    pdf_bytes = _build_forsikringstilbud_pdf(db_obj, body, offer_summaries,
                                             broker_name, broker_contact, broker_email, broker_phone)
    filename = f"forsikringstilbud_{orgnr}_{date.today().isoformat()}.pdf"
    if save:
        save_insurance_document(orgnr, db_obj.navn, filename, pdf_bytes, db)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/org/{orgnr}/forsikringstilbud/email")
def email_forsikringstilbud(
    orgnr: str,
    body: dict,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    notification: NotificationPort = Depends(_get_notification),
) -> dict:
    """Email a shareable client-profile link for an existing forsikringstilbud.

    Body: {"recipient_email": "kontakt@firma.no"}
    """
    recipient_email = (body.get("recipient_email") or "").strip()
    if not recipient_email:
        raise HTTPException(status_code=400, detail="recipient_email is required")
    db_obj = db.query(Company).filter(Company.orgnr == orgnr).first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Company not in database")

    # Get or create a 30-day read-only token for this company
    token_row = get_or_create_active_token(
        orgnr, label=f"E-post til {recipient_email}", db=db
    )

    ui_base = os.getenv("UI_BASE_URL", "https://ca-ui.thankfulplant-2ef6e3b0.norwayeast.azurecontainerapps.io")
    share_url = f"{ui_base}/?token={token_row.token}"

    sent = notification.send_forsikringstilbud(
        to=recipient_email,
        client_navn=db_obj.navn or orgnr,
        orgnr=orgnr,
        share_url=share_url,
    )
    log_audit(db, "email_forsikringstilbud", orgnr=orgnr, actor_email=user.email,
              detail={"recipient": recipient_email, "sent": sent})
    return {"sent": sent, "recipient": recipient_email, "share_url": share_url}


@router.post("/org/{orgnr}/narrative", response_model=NarrativeOut)
def generate_narrative(orgnr: str, lang: str = Query("no"), db: Session = Depends(get_db)) -> dict:
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
            detail="No LLM provider configured (set AZURE_FOUNDRY_BASE_URL + AZURE_FOUNDRY_API_KEY)",
        )

    # Save to RAG so the analyst chat can reference this narrative
    _save_to_rag(orgnr, "AI Risikoanalyse", narrative, db)

    return {"orgnr": orgnr, "narrative": narrative}
