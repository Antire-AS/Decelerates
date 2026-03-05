import io
import json
import os
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import anthropic
import pdfplumber
import voyageai
from google import genai as google_genai
from google.genai import types as genai_types
import requests
from fastapi import FastAPI, Query, HTTPException, Depends, BackgroundTasks, File, UploadFile, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import SessionLocal, Company, CompanyNote, CompanyHistory, CompanyPdfSource, BrokerSettings, SlaAgreement, InsuranceOffer, InsuranceDocument, init_db
from risk import derive_simple_risk, build_risk_summary

app = FastAPI(title="Broker Accelerator API")

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
VOYAGE_MODEL = os.getenv("VOYAGE_MODEL", "voyage-3-lite")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ======================
# PDF Seed Data
# Annual report PDFs for listed companies with stable public URLs.
# ======================
PDF_SEED_DATA: Dict[str, List[Dict[str, Any]]] = {
    "984851006": [   # DNB Bank ASA
        {
            "year": 2024,
            "pdf_url": "https://www.ir.dnb.no/sites/default/files/pr/202503192798-2-1.pdf",
            "label": "DNB Annual Report 2024",
        },
        {
            "year": 2023,
            "pdf_url": "https://www.ir.dnb.no/sites/default/files/Annual%20Report%202023.pdf",
            "label": "DNB Annual Report 2023",
        },
        {
            "year": 2022,
            "pdf_url": "https://www.ir.dnb.no/sites/default/files/pr/202303097878-2.pdf",
            "label": "DNB Annual Report 2022",
        },
        {
            "year": 2021,
            "pdf_url": "https://www.ir.dnb.no/sites/default/files/Annual%20Report%202021.pdf",
            "label": "DNB Annual Report 2021",
        },
        {
            "year": 2020,
            "pdf_url": "https://www.ir.dnb.no/sites/default/files/results/DNB_Bank_annual_report_2020.pdf",
            "label": "DNB Annual Report 2020",
        },
        {
            "year": 2019,
            "pdf_url": "https://www.ir.dnb.no/sites/default/files/Annual%20Report%20DNB%20Bank%202019.pdf",
            "label": "DNB Annual Report 2019",
        },
    ],
    "995568217": [   # Gjensidige Forsikring ASA
        {
            "year": 2024,
            "pdf_url": "https://www.gjensidige.com/files/content-innhold/konsern-filer/annual-reports/Annual%20report%202024.pdf",
            "label": "Gjensidige Annual Report 2024",
        },
        {
            "year": 2023,
            "pdf_url": "https://www.gjensidige.com/files/content-innhold/konsern-filer/annual-reports/Annual%20report%202023%20Gjensidige.pdf",
            "label": "Gjensidige Annual Report 2023",
        },
        {
            "year": 2022,
            "pdf_url": "https://www.gjensidige.com/files/content-files/group-files/Gjensidige%20Forsikring%20Annual%20Report%202022.pdf",
            "label": "Gjensidige Annual Report 2022",
        },
        {
            "year": 2021,
            "pdf_url": "https://mb.cision.com/Public/1122/3508195/afe168b161d05b93.pdf",
            "label": "Gjensidige Annual Report 2021",
        },
        {
            "year": 2020,
            "pdf_url": "https://mb.cision.com/Public/1122/3285601/8353111a7aca0ddf.pdf",
            "label": "Gjensidige Annual Report 2020",
        },
        {
            "year": 2019,
            "pdf_url": "https://mb.cision.com/Main/1122/3035389/1193913.pdf",
            "label": "Gjensidige Annual Report 2019",
        },
    ],
    "979981344": [   # Søderberg & Partners Norge AS
        {
            "year": 2023,
            "pdf_url": "https://mb.cision.com/Main/6558/3945675/2668201.pdf",
            "label": "Söderberg & Partners Group Annual Report 2023 (SEK)",
        },
    ],
}


def _seed_pdf_sources(db: Session) -> None:
    """Upsert hardcoded PDF sources into company_pdf_sources table on startup.
    Always updates the URL/label in case PDF_SEED_DATA was corrected."""
    for orgnr, entries in PDF_SEED_DATA.items():
        for entry in entries:
            existing = (
                db.query(CompanyPdfSource)
                .filter(CompanyPdfSource.orgnr == orgnr, CompanyPdfSource.year == entry["year"])
                .first()
            )
            if not existing:
                existing = CompanyPdfSource(
                    orgnr=orgnr,
                    year=entry["year"],
                    added_at=datetime.now(timezone.utc).isoformat(),
                )
                db.add(existing)
            # Always sync URL and label from seed data
            existing.pdf_url = entry["pdf_url"]
            existing.label = entry.get("label", "")
    db.commit()


@app.on_event("startup")
def on_startup():
    init_db()
    db = SessionLocal()
    try:
        _seed_pdf_sources(db)
    finally:
        db.close()


# --- BRREG ---
BRREG_ENHETER_URL = "https://data.brreg.no/enhetsregisteret/api/enheter"

# --- Finanstilsynet ---
FINANSTILSYNET_REGISTRY_URL = "https://api.finanstilsynet.no/registry/api/v2/entities"

# --- OpenSanctions (PEP/sanctions) ---
OPENSANCTIONS_SEARCH_URL = "https://api.opensanctions.org/search/peps"


# ======================
# BRREG – Enhetsregisteret
# ======================
def fetch_enhetsregisteret(
    name: str,
    kommunenummer: Optional[str] = None,
    size: int = 20,
) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {"navn": name, "size": size}
    if kommunenummer:
        params["kommunenummer"] = kommunenummer

    resp = requests.get(BRREG_ENHETER_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    enheter = (data.get("_embedded") or {}).get("enheter", [])
    results: List[Dict[str, Any]] = []

    for e in enheter:
        addr = e.get("forretningsadresse") or {}
        orgform = e.get("organisasjonsform") or {}
        naeringskode1 = e.get("naeringskode1") or {}

        results.append(
            {
                "orgnr": e.get("organisasjonsnummer"),
                "navn": e.get("navn"),
                "organisasjonsform": orgform.get("beskrivelse"),
                "organisasjonsform_kode": orgform.get("kode"),
                "kommune": addr.get("kommune"),
                "postnummer": addr.get("postnummer"),
                "land": addr.get("land"),
                "naeringskode1": naeringskode1.get("kode"),
                "naeringskode1_beskrivelse": naeringskode1.get("beskrivelse"),
            }
        )

    return results


def fetch_enhet_by_orgnr(orgnr: str) -> Optional[Dict[str, Any]]:
    params = {"organisasjonsnummer": orgnr}
    resp = requests.get(BRREG_ENHETER_URL, params=params, timeout=10)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    data = resp.json()
    enheter = (data.get("_embedded") or {}).get("enheter", [])
    if not enheter:
        return None

    e = enheter[0]
    addr = e.get("forretningsadresse") or {}
    orgform = e.get("organisasjonsform") or {}
    naeringskode1 = e.get("naeringskode1") or {}

    return {
        "orgnr": e.get("organisasjonsnummer"),
        "navn": e.get("navn"),
        "organisasjonsform": orgform.get("beskrivelse"),
        "organisasjonsform_kode": orgform.get("kode"),
        "kommune": addr.get("kommune"),
        "kommunenummer": addr.get("kommunenummer"),
        "postnummer": addr.get("postnummer"),
        "poststed": addr.get("poststed"),
        "adresse": addr.get("adresse") or [],
        "land": addr.get("land"),
        "naeringskode1": naeringskode1.get("kode"),
        "naeringskode1_beskrivelse": naeringskode1.get("beskrivelse"),
        "stiftelsesdato": e.get("stiftelsesdato"),
        "hjemmeside": e.get("hjemmeside"),
        "konkurs": e.get("konkurs", False),
        "under_konkursbehandling": e.get("underKonkursbehandling", False),
        "under_avvikling": e.get("underAvvikling", False),
    }


# ======================
# BRREG – Regnskapsregisteret (åpen del, siste år)
# ======================
def _pick_latest_regnskap(regnskaper: List[Dict[str, Any]]) -> Dict[str, Any]:
    def year_key(r: Dict[str, Any]) -> int:
        periode = r.get("regnskapsperiode") or {}
        til_dato = periode.get("tilDato")
        if isinstance(til_dato, str) and len(til_dato) >= 4:
            try:
                return int(til_dato[:4])
            except ValueError:
                pass
        return 0

    return sorted(regnskaper, key=year_key)[-1]


def _extract_periode(chosen: Dict[str, Any]) -> Dict[str, Any]:
    periode = chosen.get("regnskapsperiode") or {}
    periode_år = None
    til_dato = periode.get("tilDato")
    if isinstance(til_dato, str) and len(til_dato) >= 4:
        try:
            periode_år = int(til_dato[:4])
        except ValueError:
            pass
    return {
        "regnskapsår": periode_år,
        "fra_dato": periode.get("fraDato"),
        "til_dato": til_dato,
        "valuta": chosen.get("valuta"),
        "oppstillingsplan": chosen.get("oppstillingsplan"),
        "avviklingsregnskap": chosen.get("avviklingsregnskap"),
        "regnskapstype": chosen.get("regnskapstype"),
        "id": chosen.get("id"),
        "journalnr": chosen.get("journalnr"),
    }


def _extract_virksomhet(chosen: Dict[str, Any]) -> Dict[str, Any]:
    virksomhet = chosen.get("virksomhet") or {}
    regnskapsprinsipper = (
        chosen.get("regnkapsprinsipper") or chosen.get("regnskapsprinsipper") or {}
    )
    return {
        "virksomhet_organisasjonsnummer": virksomhet.get("organisasjonsnummer"),
        "virksomhet_organisasjonsform": virksomhet.get("organisasjonsform"),
        "virksomhet_morselskap": virksomhet.get("morselskap"),
        "antall_ansatte": virksomhet.get("antallAnsatte"),
        "smaa_foretak": regnskapsprinsipper.get("smaaForetak"),
        "regnskapsregler": regnskapsprinsipper.get("regnskapsregler"),
    }


def _extract_resultat(chosen: Dict[str, Any]) -> Dict[str, Any]:
    resultat = chosen.get("resultatregnskapResultat") or {}
    driftsres = resultat.get("driftsresultat") or {}
    driftsinntekter = driftsres.get("driftsinntekter") or {}
    driftskostnad = driftsres.get("driftskostnad") or {}
    finansres = resultat.get("finansresultat") or {}
    finansinntekt = finansres.get("finansinntekt") or {}
    finanskostnad = finansres.get("finanskostnad") or {}
    return {
        "salgsinntekter": driftsinntekter.get("salgsinntekter"),
        "sum_driftsinntekter": driftsinntekter.get("sumDriftsinntekter"),
        "loennskostnad": driftskostnad.get("loennskostnad"),
        "sum_driftskostnad": driftskostnad.get("sumDriftskostnad"),
        "driftsresultat": driftsres.get("driftsresultat"),
        "sum_finansinntekt": finansinntekt.get("sumFinansinntekter"),
        "rentekostnad_samme_konsern": finanskostnad.get("rentekostnadSammeKonsern"),
        "annen_rentekostnad": finanskostnad.get("annenRentekostnad"),
        "sum_finanskostnad": finanskostnad.get("sumFinanskostnad"),
        "netto_finans": finansres.get("nettoFinans"),
        "ordinaert_resultat_foer_skattekostnad": resultat.get("ordinaertResultatFoerSkattekostnad"),
        "ordinaert_resultat_skattekostnad": resultat.get("ordinaertResultatSkattekostnad"),
        "ekstraordinaere_poster": resultat.get("ekstraordinaerePoster"),
        "skattekostnad_ekstraord_resultat": resultat.get("skattekostnadEkstraordinaertResultat"),
        "aarsresultat": resultat.get("aarsresultat"),
        "totalresultat": resultat.get("totalresultat"),
    }


def _extract_balanse(chosen: Dict[str, Any]) -> Dict[str, Any]:
    balanse = chosen.get("egenkapitalGjeld") or {}
    egenkapital_obj = balanse.get("egenkapital") or {}
    innskutt_ek = egenkapital_obj.get("innskuttEgenkapital") or {}
    opptjent_ek = egenkapital_obj.get("opptjentEgenkapital") or {}
    gjeld_oversikt = balanse.get("gjeldOversikt") or {}
    kortsiktig = gjeld_oversikt.get("kortsiktigGjeld") or {}
    langsiktig = gjeld_oversikt.get("langsiktigGjeld") or {}
    return {
        "sum_egenkapital_gjeld": balanse.get("sumEgenkapitalGjeld"),
        "sum_egenkapital": egenkapital_obj.get("sumEgenkapital"),
        "sum_innskutt_egenkapital": innskutt_ek.get("sumInnskuttEgenkapital"),
        "sum_opptjent_egenkapital": opptjent_ek.get("sumOpptjentEgenkapital"),
        "sum_gjeld": gjeld_oversikt.get("sumGjeld"),
        "sum_kortsiktig_gjeld": kortsiktig.get("sumKortsiktigGjeld"),
        "sum_langsiktig_gjeld": langsiktig.get("sumLangsiktigGjeld"),
    }


def _extract_eiendeler(chosen: Dict[str, Any]) -> Dict[str, Any]:
    eiendeler_obj = chosen.get("eiendeler") or {}
    omloepsmidler = eiendeler_obj.get("omloepsmidler") or {}
    anleggsmidler = eiendeler_obj.get("anleggsmidler") or {}
    return {
        "sum_eiendeler": eiendeler_obj.get("sumEiendeler"),
        "sum_omloepsmidler": omloepsmidler.get("sumOmloepsmidler"),
        "sum_anleggsmidler": anleggsmidler.get("sumAnleggsmidler"),
        "sum_varer": eiendeler_obj.get("sumVarer"),
        "sum_fordringer": eiendeler_obj.get("sumFordringer"),
        "sum_investeringer": eiendeler_obj.get("sumInvesteringer"),
        "sum_bankinnskudd_og_kontanter": eiendeler_obj.get("sumBankinnskuddOgKontanter"),
        "goodwill": eiendeler_obj.get("goodwill"),
    }


def fetch_regnskap_keyfigures(orgnr: str) -> Dict[str, Any]:
    url = f"https://data.brreg.no/regnskapsregisteret/regnskap/{orgnr}"
    resp = requests.get(url, timeout=10)

    if resp.status_code == 404:
        return {}

    resp.raise_for_status()
    data = resp.json()

    regnskaper = data if isinstance(data, list) else [data]
    if not regnskaper:
        return {}

    chosen = _pick_latest_regnskap(regnskaper)

    return {
        **_extract_periode(chosen),
        **_extract_virksomhet(chosen),
        **_extract_resultat(chosen),
        **_extract_balanse(chosen),
        **_extract_eiendeler(chosen),
    }


def fetch_regnskap_history(orgnr: str) -> List[Dict[str, Any]]:
    url = f"https://data.brreg.no/regnskapsregisteret/regnskap/{orgnr}"
    resp = requests.get(url, timeout=10)
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    data = resp.json()

    regnskaper = data if isinstance(data, list) else [data]

    # Deduplicate: prefer SELSKAP type, one entry per year
    by_year: Dict[int, Dict[str, Any]] = {}
    for r in regnskaper:
        periode = r.get("regnskapsperiode") or {}
        til_dato = periode.get("tilDato")
        if not (isinstance(til_dato, str) and len(til_dato) >= 4):
            continue
        try:
            year = int(til_dato[:4])
        except ValueError:
            continue
        existing = by_year.get(year)
        if existing is None or r.get("regnskapstype") == "SELSKAP":
            by_year[year] = r

    rows: List[Dict[str, Any]] = []
    for year, r in sorted(by_year.items()):
        res = _extract_resultat(r)
        bal = _extract_balanse(r)
        eid = _extract_eiendeler(r)
        vir = _extract_virksomhet(r)
        equity = bal.get("sum_egenkapital")
        assets = eid.get("sum_eiendeler")
        equity_ratio = (equity / assets) if (equity is not None and assets) else None
        rows.append(
            {
                "year": year,
                # Summary (used for charts + comparison table)
                "revenue": res.get("sum_driftsinntekter"),
                "net_result": res.get("aarsresultat"),
                "equity": equity,
                "total_assets": assets,
                "equity_ratio": equity_ratio,
                "short_term_debt": bal.get("sum_kortsiktig_gjeld"),
                "long_term_debt": bal.get("sum_langsiktig_gjeld"),
                "antall_ansatte": vir.get("antall_ansatte"),
                # Full P&L (used for year drill-down)
                "salgsinntekter": res.get("salgsinntekter"),
                "loennskostnad": res.get("loennskostnad"),
                "sum_driftskostnad": res.get("sum_driftskostnad"),
                "driftsresultat": res.get("driftsresultat"),
                "sum_finansinntekt": res.get("sum_finansinntekt"),
                "sum_finanskostnad": res.get("sum_finanskostnad"),
                "netto_finans": res.get("netto_finans"),
                "ordinaert_resultat_foer_skattekostnad": res.get("ordinaert_resultat_foer_skattekostnad"),
                "ordinaert_resultat_skattekostnad": res.get("ordinaert_resultat_skattekostnad"),
                "ekstraordinaere_poster": res.get("ekstraordinaere_poster"),
                "totalresultat": res.get("totalresultat"),
                # Full balance sheet (used for year drill-down)
                "sum_innskutt_egenkapital": bal.get("sum_innskutt_egenkapital"),
                "sum_opptjent_egenkapital": bal.get("sum_opptjent_egenkapital"),
                "sum_gjeld": bal.get("sum_gjeld"),
                "sum_omloepsmidler": eid.get("sum_omloepsmidler"),
                "sum_anleggsmidler": eid.get("sum_anleggsmidler"),
                "sum_varer": eid.get("sum_varer"),
                "sum_fordringer": eid.get("sum_fordringer"),
                "sum_investeringer": eid.get("sum_investeringer"),
                "sum_bankinnskudd_og_kontanter": eid.get("sum_bankinnskudd_og_kontanter"),
                "goodwill": eid.get("goodwill"),
            }
        )
    return rows


# ======================
# PDF History Agent
# ======================

GEMINI_PDF_MODELS = ["gemini-2.5-flash", "gemini-1.5-flash"]

_FINANCIALS_PROMPT = """You are extracting financial data from a corporate annual report PDF.
Company orgnr: {orgnr}, Report year: {year}

CRITICAL RULES:
1. Return ALL monetary values as ABSOLUTE numbers in the base currency unit (not millions).
   Example: "66,115" with note "amounts in NOK millions" → return 66115000000
   Example: "32,861 TNOK" (thousands) → return 32861000. Plain NOK/USD → return as-is.
2. Return null for any field genuinely not found — do NOT guess or leave as 0.
3. This may be a BANK, insurance company, or standard company — adapt accordingly.
   - BANK income statements start with "Net interest income" + "Net fee and commission income".
     Sum these to get "revenue". Operating profit is often called "profit before loan impairment charges".
   - INSURANCE income statements start with "Net premiums earned" / "Gross written premiums".
   - STANDARD companies have "operating revenues" / "total revenues".

Extract ALL of these fields and return a single valid JSON object.
Each field shows the standard name AND common insurance/bank alternatives to look for:

{{
  "revenue": <FOR BANKS: net interest income + net fee and commission income + net other income (sum the top-line items) / FOR INSURANCE: net premiums earned / gross written premiums / FOR STANDARD: total operating revenues — ABSOLUTE>,
  "salgsinntekter": <product/sales revenue / gross premiums written / gross interest income — ABSOLUTE or null>,
  "loennskostnad": <wage costs / salaries / personnel expenses / staff costs / salary and administration expenses — ABSOLUTE or null>,
  "sum_driftskostnad": <total operating costs / total expenses / claims incurred + expenses / operating expenses excl. loan losses — ABSOLUTE or null>,
  "driftsresultat": <operating result / EBIT / technical result / underwriting result / profit before loan impairment charges / net profit before impairment — ABSOLUTE or null>,
  "sum_finansinntekt": <financial income / investment income / interest received / net interest income (banks) — ABSOLUTE or null>,
  "sum_finanskostnad": <financial costs / interest expense / finance costs / loan impairment charges / net losses on loans (banks) — ABSOLUTE or null>,
  "netto_finans": <net financial items / net investment result / net interest and fee income — ABSOLUTE or null>,
  "ordinaert_resultat_foer_skattekostnad": <profit before tax / result before tax / pre-tax profit — ABSOLUTE or null>,
  "ordinaert_resultat_skattekostnad": <income tax expense / tax charge — ABSOLUTE or null>,
  "aarsresultat": <net profit or loss for the year / profit after tax / annual result / profit for the year — ABSOLUTE>,
  "totalresultat": <total comprehensive income — ABSOLUTE or null>,
  "net_result": <same as aarsresultat — ABSOLUTE>,
  "equity": <total equity / total shareholders equity / equity attributable to shareholders — ABSOLUTE>,
  "sum_innskutt_egenkapital": <share capital + premium / paid-in capital — ABSOLUTE or null>,
  "sum_opptjent_egenkapital": <retained earnings / other equity / other reserves — ABSOLUTE or null>,
  "total_assets": <total assets — ABSOLUTE>,
  "sum_omloepsmidler": <current assets / short-term assets — null for banks (not applicable)>,
  "sum_anleggsmidler": <non-current assets / fixed assets — null for banks (not applicable)>,
  "sum_varer": <inventories — ABSOLUTE or null>,
  "sum_fordringer": <receivables / accounts receivable / premiums receivable / net loans to customers / loans and advances to customers (banks) — ABSOLUTE or null>,
  "sum_investeringer": <investments / financial assets / investment portfolio / financial instruments at fair value / securities / bonds (banks) — ABSOLUTE or null>,
  "sum_bankinnskudd_og_kontanter": <cash and bank / cash and equivalents / cash and balances with central banks — ABSOLUTE or null>,
  "goodwill": <goodwill / intangible assets — ABSOLUTE or null>,
  "sum_gjeld": <total liabilities / total debt — ABSOLUTE>,
  "short_term_debt": <current liabilities / short-term debt / technical provisions (insurance) / deposits from customers / customer deposits (banks) — ABSOLUTE or null>,
  "long_term_debt": <non-current liabilities / long-term debt / debt securities issued / covered bonds issued / subordinated loans (banks) — ABSOLUTE or null>,
  "antall_ansatte": <number of employees / headcount / FTEs as integer — or null>,
  "currency": <"NOK", "USD", "SEK", or "EUR">,
  "reporting_unit": <e.g. "NOK millions", "TNOK", "NOK" — as stated in the report>
}}

Return ONLY the JSON object. No explanation, no markdown, no code fences."""


def _parse_json_financials(raw: str) -> Optional[Dict[str, Any]]:
    """Parse and validate the JSON financial dict returned by any LLM."""
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group())
        except (json.JSONDecodeError, ValueError):
            return None
    eq = data.get("equity")
    assets = data.get("total_assets")
    data["equity_ratio"] = (eq / assets) if (eq and assets) else None
    return data


def _extract_pdf_text(pdf_url: str) -> str:
    """Download a PDF and extract all text using pdfplumber (up to 60 pages)."""
    resp = requests.get(
        pdf_url, timeout=60, headers={"User-Agent": "BrokerAccelerator/1.0"}
    )
    resp.raise_for_status()
    with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages[:60])


def _parse_financials_from_text(
    text: str, orgnr: str, year: int
) -> Optional[Dict[str, Any]]:
    """Ask LLM (Claude or Gemini) to extract key financial figures from annual report text.
    Used as fallback when Gemini native PDF parsing is unavailable."""
    prompt = _FINANCIALS_PROMPT.format(orgnr=orgnr, year=year) + f"\n\nAnnual report text (first portion):\n{text[:12000]}"
    raw = _llm_answer_raw(prompt)
    if not raw:
        return None
    return _parse_json_financials(raw)


def _parse_financials_from_pdf(
    pdf_url: str, orgnr: str, year: int
) -> Optional[Dict[str, Any]]:
    """Extract key financials from an annual report PDF.

    Primary path: Gemini native PDF understanding (preserves table structure,
    no page cap, no text garbling). Falls back to pdfplumber text extraction
    + text-based LLM parsing if Gemini is unavailable or fails.
    """
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key and gemini_key != "your_key_here":
        try:
            resp = requests.get(
                pdf_url, timeout=60, headers={"User-Agent": "BrokerAccelerator/1.0"}
            )
            resp.raise_for_status()
            pdf_bytes = resp.content

            client = google_genai.Client(api_key=gemini_key)
            prompt = _FINANCIALS_PROMPT.format(orgnr=orgnr, year=year)

            # Choose upload method based on file size.
            # Inline is simpler (no cleanup) but limited to ~20 MB.
            # Files API handles any size but requires a temp file and explicit delete.
            INLINE_LIMIT = 18 * 1024 * 1024  # 18 MB to be safe
            use_files_api = len(pdf_bytes) > INLINE_LIMIT

            def _call_gemini(model_name: str) -> Optional[str]:
                if not use_files_api:
                    pdf_part = genai_types.Part.from_bytes(
                        data=pdf_bytes, mime_type="application/pdf"
                    )
                    resp = client.models.generate_content(
                        model=model_name, contents=[pdf_part, prompt]
                    )
                    return resp.text
                else:
                    import tempfile, os as _os
                    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                        tmp.write(pdf_bytes)
                        tmp_path = tmp.name
                    try:
                        uploaded = client.files.upload(
                            file=tmp_path,
                            config=genai_types.UploadFileConfig(
                                mime_type="application/pdf",
                                display_name=f"annual_{orgnr}_{year}.pdf",
                            ),
                        )
                        try:
                            resp = client.models.generate_content(
                                model=model_name, contents=[uploaded, prompt]
                            )
                            return resp.text
                        finally:
                            try:
                                client.files.delete(name=uploaded.name)
                            except Exception:
                                pass
                    finally:
                        _os.unlink(tmp_path)

            raw: Optional[str] = None
            for model_name in GEMINI_PDF_MODELS:
                try:
                    raw = _call_gemini(model_name)
                    if raw:
                        break
                except Exception as exc:
                    msg = str(exc)
                    if "quota" in msg.lower() or "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                        continue  # try next model on quota errors
                    break  # other errors — fall through to text fallback

            if raw:
                result = _parse_json_financials(raw)
                if result:
                    return result
        except Exception:
            pass  # fall through to text-based fallback

    # Fallback: pdfplumber text extraction → text-based LLM parsing (Claude or Gemini text)
    try:
        text = _extract_pdf_text(pdf_url)
        return _parse_financials_from_text(text, orgnr, year)
    except Exception:
        return None


def fetch_history_from_pdf(
    orgnr: str, pdf_url: str, year: int, label: str, db: Session
) -> Dict[str, Any]:
    """Download PDF, parse financials via Gemini native PDF (with LLM text fallback), upsert into company_history."""
    parsed = _parse_financials_from_pdf(pdf_url, orgnr, year)
    if not parsed:
        raise ValueError(f"Could not parse financials from PDF: {pdf_url}")

    existing = (
        db.query(CompanyHistory)
        .filter(CompanyHistory.orgnr == orgnr, CompanyHistory.year == year)
        .first()
    )
    if not existing:
        existing = CompanyHistory(orgnr=orgnr, year=year)
        db.add(existing)

    existing.source = "pdf"
    existing.pdf_url = pdf_url
    existing.revenue = parsed.get("revenue")
    existing.net_result = parsed.get("net_result")
    existing.equity = parsed.get("equity")
    existing.total_assets = parsed.get("total_assets")
    existing.equity_ratio = parsed.get("equity_ratio")
    existing.short_term_debt = parsed.get("short_term_debt")
    existing.long_term_debt = parsed.get("long_term_debt")
    existing.antall_ansatte = parsed.get("antall_ansatte")
    existing.currency = parsed.get("currency", "NOK")
    existing.raw = parsed
    db.commit()

    return {
        "year": year,
        "source": "pdf",
        "pdf_url": pdf_url,
        "label": label,
        "currency": existing.currency,
        "revenue": existing.revenue,
        "net_result": existing.net_result,
        "equity": existing.equity,
        "total_assets": existing.total_assets,
        "equity_ratio": existing.equity_ratio,
        "short_term_debt": existing.short_term_debt,
        "long_term_debt": existing.long_term_debt,
        "antall_ansatte": existing.antall_ansatte,
    }


def _get_full_history(orgnr: str, db: Session) -> List[Dict[str, Any]]:
    """Return merged history: DB rows (PDF/manual) + BRREG, deduped by year, sorted desc."""
    # 1. All DB-stored history rows
    db_rows = (
        db.query(CompanyHistory)
        .filter(CompanyHistory.orgnr == orgnr)
        .order_by(CompanyHistory.year.desc())
        .all()
    )
    by_year: Dict[int, Dict[str, Any]] = {}
    for row in db_rows:
        # Start with all detail fields stored in the raw JSON (full P&L + balance sheet)
        base = dict(row.raw) if row.raw else {}
        # Always override/add the typed DB columns (authoritative for charts/metrics)
        base.update({
            "year": row.year,
            "source": row.source,
            "currency": row.currency or "NOK",
            "revenue": row.revenue,
            "net_result": row.net_result,
            "equity": row.equity,
            "total_assets": row.total_assets,
            "equity_ratio": row.equity_ratio,
            "short_term_debt": row.short_term_debt,
            "long_term_debt": row.long_term_debt,
            "antall_ansatte": row.antall_ansatte,
        })
        by_year[row.year] = base

    # 2. BRREG history (adds year not already in DB, doesn't override PDF data)
    try:
        brreg_rows = fetch_regnskap_history(orgnr)
    except Exception:
        brreg_rows = []

    for row in brreg_rows:
        year = row.get("year")
        if year and year not in by_year:
            by_year[year] = {**row, "source": "brreg", "currency": "NOK"}

    return sorted(by_year.values(), key=lambda r: r["year"], reverse=True)


# ======================
# Phase 2 – IR Discovery Agent
# Finds annual report PDFs for companies not in PDF_SEED_DATA.
# Uses DuckDuckGo HTML search (no JS, no API key) + Claude to identify valid PDFs.
# Falls back gracefully — Phase 1 seeds always win.
# ======================

def _search_for_pdfs(navn: str, hjemmeside: Optional[str], year: int) -> List[str]:
    """Search DuckDuckGo HTML for annual report PDF URLs for a given company + year."""

    def _extract_pdfs_from_html(html: str) -> List[str]:
        found = []
        # 1. Direct https://...pdf links in href/src attributes
        found += re.findall(r"https?://[^\s\"'<>]+\.pdf(?:[?#][^\s\"'<>]*)?", html)
        # 2. DuckDuckGo redirect-encoded URLs (uddg= param) that end in .pdf
        encoded = re.findall(r"uddg=(https?%3A%2F%2F[^&\"]+)", html)
        for u in encoded:
            decoded = requests.utils.unquote(u)
            if ".pdf" in decoded.lower():
                found.append(decoded)
        # 3. result__url div text — DuckDuckGo shows bare domain/path here for PDF results
        #    e.g. <a class="result__url" ...>www.sec.gov/Archives/.../file.pdf</a>
        result_url_texts = re.findall(
            r'class=["\']result__url["\'][^>]*>\s*([^\s<]+)', html
        )
        for u in result_url_texts:
            u = u.strip()
            if ".pdf" in u.lower():
                full = u if u.startswith("http") else f"https://{u}"
                found.append(full)
        return list(dict.fromkeys(found))  # deduplicate, preserve order

    queries = []
    if hjemmeside:
        domain = re.sub(r"^https?://", "", hjemmeside).rstrip("/").split("/")[0]
        queries.append(f'site:{domain} "annual report" {year} filetype:pdf')
    # Broader fallback: no site restriction, no filetype filter (DDG rarely honours filetype:)
    queries.append(f'{navn} annual report {year} filetype:pdf')

    all_urls: List[str] = []
    for query in queries:
        if len(all_urls) >= 8:
            break
        try:
            resp = requests.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": "Mozilla/5.0 (compatible; BrokerAccelerator/1.0)"},
                timeout=15,
            )
            all_urls += _extract_pdfs_from_html(resp.text)
            all_urls = list(dict.fromkeys(all_urls))  # keep deduplicated after each pass
        except Exception:
            continue

    return all_urls[:8]   # cap at 8 candidates per year


def _discover_ir_pdfs(
    orgnr: str, navn: str, hjemmeside: Optional[str], target_years: List[int]
) -> List[Dict[str, Any]]:
    """Phase 2: search for annual report PDFs for each target year, validate with Claude."""
    # Gather candidate URLs across all target years
    candidates: List[tuple] = []   # (year, url)
    for year in target_years:
        urls = _search_for_pdfs(navn, hjemmeside, year)
        for url in urls:
            candidates.append((year, url))

    if not candidates:
        return []

    # Ask Claude to identify which candidates are real annual report PDFs
    candidates_text = "\n".join(f"Year {yr}: {url}" for yr, url in candidates)
    prompt = f"""You are helping identify official annual report PDFs for a company.
Company: {navn}
Organisation number: {orgnr}

Below are candidate PDF URLs found via search, each tagged with the year we want.
Identify which URLs are the official annual report for that year.
Exclude duplicates, marketing documents, sustainability reports, press releases, or interim reports.

Return a JSON array of objects — one per confirmed annual report:
[{{"year": 2023, "pdf_url": "https://...", "label": "Company Annual Report 2023"}}]
Return ONLY the JSON array (no markdown, no commentary). Return [] if none are valid.

Candidates:
{candidates_text}
"""
    raw = _llm_answer_raw(prompt)
    if not raw:
        return []

    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
    try:
        result = json.loads(cleaned)
        if isinstance(result, list):
            return [r for r in result if r.get("pdf_url") and r.get("year")]
    except (json.JSONDecodeError, ValueError):
        match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
                if isinstance(result, list):
                    return [r for r in result if r.get("pdf_url") and r.get("year")]
            except (json.JSONDecodeError, ValueError):
                pass
    return []


# ======================
# OpenSanctions – PEP / sanctions screening
# ======================
def pep_screen_name(name: str) -> Optional[Dict[str, Any]]:
    if not name:
        return None

    params = {"q": name, "limit": 5}
    resp = requests.get(OPENSANCTIONS_SEARCH_URL, params=params, timeout=10)

    if resp.status_code == 404:
        return None

    resp.raise_for_status()
    data = resp.json()

    results = data.get("results") or data.get("entities") or []
    hits: List[Dict[str, Any]] = []

    for m in results:
        hits.append(
            {
                "id": m.get("id"),
                "name": m.get("name"),
                "schema": m.get("schema"),
                "datasets": m.get("datasets"),
                "topics": m.get("topics"),
            }
        )

    return {"query": name, "hit_count": len(hits), "hits": hits}


# ======================
# Finanstilsynet – registry
# ======================
def fetch_finanstilsynet_licenses(orgnr: str) -> List[Dict[str, Any]]:
    params = {"organizationNumber": orgnr, "pageSize": 100, "pageIndex": 0}
    resp = requests.get(FINANSTILSYNET_REGISTRY_URL, params=params, timeout=10)
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    data = resp.json()

    entities = data.get("entities") or data.get("items") or []
    results: List[Dict[str, Any]] = []

    for e in entities:
        name = e.get("name")
        orgno = e.get("organizationNumber") or orgnr
        country = e.get("country")
        entity_type = e.get("entityType")

        for lic in e.get("licenses", []):
            results.append(
                {
                    "orgnr": orgno,
                    "name": name,
                    "country": country,
                    "entity_type": entity_type,
                    "license_id": lic.get("id"),
                    "license_type": lic.get("type"),
                    "license_status": lic.get("status"),
                    "license_from": lic.get("validFrom"),
                    "license_to": lic.get("validTo"),
                    "license_description": lic.get("description"),
                }
            )

    return results


# ======================
# Kartverket – geocoding
# ======================
KARTVERKET_ADRESSE_URL = "https://ws.geonorge.no/adresser/v1/sok"


def fetch_koordinater(org: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    adresse_lines = org.get("adresse") or []
    kommunenummer = org.get("kommunenummer") or ""
    postnummer = org.get("postnummer") or ""

    parts = []
    if adresse_lines:
        parts.append(adresse_lines[0])
    if postnummer:
        parts.append(postnummer)

    if not parts:
        return None

    params: Dict[str, Any] = {"sok": " ".join(parts), "treffPerSide": 1}
    if kommunenummer:
        params["kommunenummer"] = kommunenummer

    try:
        resp = requests.get(KARTVERKET_ADRESSE_URL, params=params, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
        addresses = data.get("adresser") or []
        if not addresses:
            return None
        rp = addresses[0].get("representasjonspunkt") or {}
        lat = rp.get("lat")
        lon = rp.get("lon")
        if lat is None or lon is None:
            return None
        return {
            "lat": lat,
            "lon": lon,
            "adressetekst": addresses[0].get("adressetekst", ""),
        }
    except Exception:
        return None


# ======================
# Løsøreregisteret – asset encumbrances
# ======================
def fetch_losore(orgnr: str) -> Dict[str, Any]:
    url = f"https://losoreregisteret.brreg.no/registerinfo/api/v2/rettsstiftelse/orgnr/{orgnr}"
    try:
        resp = requests.get(url, timeout=10, headers={"Accept": "application/json"})
        if resp.status_code in (401, 403):
            return {"auth_required": True, "count": None, "pledges": []}
        if resp.status_code == 404:
            return {"auth_required": False, "count": 0, "pledges": []}
        resp.raise_for_status()
        data = resp.json()
        count = data.get("antallRettsstiftelser", 0)
        pledges = []
        for r in (data.get("rettsstiftelse") or [])[:10]:
            pledges.append({
                "dokumentnummer": r.get("dokumentnummer"),
                "type": r.get("typeBeskrivelse"),
                "status": r.get("statusBeskrivelse"),
                "dato": r.get("innkomsttidspunkt", "")[:10] if r.get("innkomsttidspunkt") else None,
            })
        return {"auth_required": False, "count": count, "pledges": pledges}
    except Exception as exc:
        return {"error": str(exc), "count": None, "pledges": []}


# ======================
# SSB-informed industry benchmarks
# ======================
NACE_BENCHMARKS: Dict[str, Dict[str, Any]] = {
    "A": {"industry": "Agriculture / Forestry / Fishing",      "eq_ratio_min": 0.35, "eq_ratio_max": 0.55, "margin_min": 0.03, "margin_max": 0.10},
    "B": {"industry": "Mining / Quarrying",                     "eq_ratio_min": 0.30, "eq_ratio_max": 0.50, "margin_min": 0.10, "margin_max": 0.25},
    "C": {"industry": "Manufacturing",                          "eq_ratio_min": 0.30, "eq_ratio_max": 0.50, "margin_min": 0.03, "margin_max": 0.10},
    "D": {"industry": "Electricity / Gas / Steam",              "eq_ratio_min": 0.30, "eq_ratio_max": 0.50, "margin_min": 0.05, "margin_max": 0.15},
    "E": {"industry": "Water / Waste Management",               "eq_ratio_min": 0.30, "eq_ratio_max": 0.45, "margin_min": 0.05, "margin_max": 0.12},
    "F": {"industry": "Construction",                           "eq_ratio_min": 0.20, "eq_ratio_max": 0.38, "margin_min": 0.02, "margin_max": 0.07},
    "G": {"industry": "Wholesale / Retail Trade",               "eq_ratio_min": 0.25, "eq_ratio_max": 0.42, "margin_min": 0.01, "margin_max": 0.05},
    "H": {"industry": "Transport / Storage",                    "eq_ratio_min": 0.22, "eq_ratio_max": 0.38, "margin_min": 0.02, "margin_max": 0.07},
    "I": {"industry": "Accommodation / Food Service",           "eq_ratio_min": 0.15, "eq_ratio_max": 0.35, "margin_min": 0.01, "margin_max": 0.06},
    "J": {"industry": "Information / Communication / IT",       "eq_ratio_min": 0.40, "eq_ratio_max": 0.65, "margin_min": 0.08, "margin_max": 0.20},
    "K": {"industry": "Financial / Insurance Services",         "eq_ratio_min": 0.10, "eq_ratio_max": 0.25, "margin_min": 0.10, "margin_max": 0.30},
    "L": {"industry": "Real Estate",                            "eq_ratio_min": 0.30, "eq_ratio_max": 0.55, "margin_min": 0.15, "margin_max": 0.35},
    "M": {"industry": "Professional / Scientific / Technical",  "eq_ratio_min": 0.35, "eq_ratio_max": 0.60, "margin_min": 0.06, "margin_max": 0.15},
    "N": {"industry": "Administrative / Support Services",      "eq_ratio_min": 0.28, "eq_ratio_max": 0.45, "margin_min": 0.03, "margin_max": 0.10},
    "O": {"industry": "Public Administration",                  "eq_ratio_min": 0.30, "eq_ratio_max": 0.60, "margin_min": 0.00, "margin_max": 0.05},
    "P": {"industry": "Education",                              "eq_ratio_min": 0.30, "eq_ratio_max": 0.55, "margin_min": 0.02, "margin_max": 0.08},
    "Q": {"industry": "Health / Social Work",                   "eq_ratio_min": 0.28, "eq_ratio_max": 0.48, "margin_min": 0.02, "margin_max": 0.08},
    "R": {"industry": "Arts / Entertainment / Recreation",      "eq_ratio_min": 0.22, "eq_ratio_max": 0.45, "margin_min": 0.02, "margin_max": 0.08},
    "S": {"industry": "Other Service Activities",               "eq_ratio_min": 0.25, "eq_ratio_max": 0.45, "margin_min": 0.03, "margin_max": 0.09},
}

_NACE_SECTION_MAP: List[tuple] = [
    (range(1, 4),   "A"),
    (range(5, 10),  "B"),
    (range(10, 34), "C"),
    (range(35, 36), "D"),
    (range(36, 40), "E"),
    (range(41, 44), "F"),
    (range(45, 48), "G"),
    (range(49, 54), "H"),
    (range(55, 57), "I"),
    (range(58, 64), "J"),
    (range(64, 67), "K"),
    (range(68, 69), "L"),
    (range(69, 76), "M"),
    (range(77, 83), "N"),
    (range(84, 85), "O"),
    (range(85, 86), "P"),
    (range(86, 89), "Q"),
    (range(90, 94), "R"),
    (range(94, 97), "S"),
]


def _nace_to_section(nace_code: str) -> Optional[str]:
    if not nace_code:
        return None
    try:
        division = int(nace_code.split(".")[0])
    except (ValueError, AttributeError):
        return None
    for rng, section in _NACE_SECTION_MAP:
        if division in rng:
            return section
    return None


def fetch_ssb_benchmark(nace_code: str) -> Optional[Dict[str, Any]]:
    section = _nace_to_section(nace_code)
    if not section:
        return None
    bench = NACE_BENCHMARKS.get(section)
    if not bench:
        return None
    return {
        "section": section,
        "industry": bench["industry"],
        "typical_equity_ratio_min": bench["eq_ratio_min"],
        "typical_equity_ratio_max": bench["eq_ratio_max"],
        "typical_profit_margin_min": bench["margin_min"],
        "typical_profit_margin_max": bench["margin_max"],
        "source": "SSB / NACE industry averages",
    }


# ======================
# BRREG – board members / roles
# ======================
def fetch_board_members(orgnr: str) -> List[Dict[str, Any]]:
    url = f"https://data.brreg.no/enhetsregisteret/api/enheter/{orgnr}/roller"
    resp = requests.get(url, timeout=10)
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    data = resp.json()

    members: List[Dict[str, Any]] = []
    for group in data.get("rollegrupper") or []:
        group_desc = (group.get("type") or {}).get("beskrivelse", "")
        for role in group.get("roller") or []:
            role_desc = (role.get("type") or {}).get("beskrivelse", "")
            person = role.get("person") or {}
            navn = person.get("navn") or {}
            full_name = f"{navn.get('fornavn', '')} {navn.get('etternavn', '')}".strip()
            birth_year = None
            fdato = person.get("fodselsdato")
            if isinstance(fdato, str) and len(fdato) >= 4:
                try:
                    birth_year = int(fdato[:4])
                except ValueError:
                    pass
            members.append(
                {
                    "group": group_desc,
                    "role": role_desc,
                    "name": full_name,
                    "birth_year": birth_year,
                    "deceased": person.get("erDoed", False),
                    "resigned": role.get("fratraadt", False),
                }
            )
    return members


# ======================
# Service layer
# ======================
def _upsert_company(
    db: Session,
    orgnr: str,
    org: Dict[str, Any],
    regn: Dict[str, Any],
    risk: Optional[Dict[str, Any]],
    pep: Optional[Dict[str, Any]],
) -> None:
    db_obj = db.query(Company).filter(Company.orgnr == orgnr).first()
    if not db_obj:
        db_obj = Company(orgnr=orgnr)
        db.add(db_obj)

    db_obj.navn = org.get("navn")
    db_obj.organisasjonsform_kode = org.get("organisasjonsform_kode")
    db_obj.kommune = org.get("kommune")
    db_obj.land = org.get("land")
    db_obj.naeringskode1 = org.get("naeringskode1")
    db_obj.naeringskode1_beskrivelse = org.get("naeringskode1_beskrivelse")

    if regn:
        db_obj.regnskapsår = regn.get("regnskapsår")
        db_obj.sum_driftsinntekter = regn.get("sum_driftsinntekter")
        db_obj.sum_egenkapital = regn.get("sum_egenkapital")
        db_obj.sum_eiendeler = regn.get("sum_eiendeler")
        if risk:
            db_obj.equity_ratio = risk.get("equity_ratio")
            db_obj.risk_score = risk.get("score")
        db_obj.regnskap_raw = regn

    if pep:
        db_obj.pep_raw = pep

    db.commit()


def fetch_org_profile(orgnr: str, db: Session) -> Optional[Dict[str, Any]]:
    org = fetch_enhet_by_orgnr(orgnr)
    if not org:
        return None

    try:
        regn: Dict[str, Any] = fetch_regnskap_keyfigures(orgnr)
    except requests.HTTPError:
        regn = {}

    # Fallback: if BRREG has no financial data (e.g. banks with BANK accounting layout),
    # use the most recent PDF-extracted history row so metrics/risk score are not blank.
    if not regn:
        recent_hist = (
            db.query(CompanyHistory)
            .filter(CompanyHistory.orgnr == orgnr)
            .order_by(CompanyHistory.year.desc())
            .first()
        )
        if recent_hist:
            raw_fields = dict(recent_hist.raw) if recent_hist.raw else {}
            regn = {
                **raw_fields,
                "regnskapsår": recent_hist.year,
                "sum_driftsinntekter": recent_hist.revenue,
                "aarsresultat": recent_hist.net_result,
                "sum_egenkapital": recent_hist.equity,
                "sum_eiendeler": recent_hist.total_assets,
                "equity_ratio": recent_hist.equity_ratio,
                "antall_ansatte": recent_hist.antall_ansatte,
                "_source": "pdf_history",
            }

    risk = derive_simple_risk(org, regn) if regn else None

    try:
        pep = pep_screen_name(org.get("navn", ""))
    except requests.HTTPError:
        pep = None

    _upsert_company(db, orgnr, org, regn, risk, pep)

    return {
        "org": org,
        "regnskap": regn or None,
        "risk": risk,
        "pep": pep,
        "risk_summary": build_risk_summary(org, regn or {}, risk or {}, pep or {}),
    }


# ======================
# Chat helpers
# ======================
class ChatRequest(BaseModel):
    question: str


def _embed(text: str) -> List[float]:
    voyage_key = os.getenv("VOYAGE_API_KEY")
    if voyage_key and voyage_key != "your_key_here":
        try:
            vo = voyageai.Client(api_key=voyage_key)
            result = vo.embed([text], model=VOYAGE_MODEL)
            return result.embeddings[0] if result.embeddings else []
        except Exception:
            pass

    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key and gemini_key != "your_key_here":
        try:
            client = google_genai.Client(api_key=gemini_key)
            result = client.models.embed_content(
                model="text-embedding-004",
                contents=text,
                config=genai_types.EmbedContentConfig(output_dimensionality=512),
            )
            return result.embeddings[0].values
        except Exception:
            pass

    return []


def _fmt_nok(value) -> str:
    if value is None:
        return "–"
    try:
        return f"{value / 1_000_000:,.1f} MNOK".replace(",", " ")
    except Exception:
        return str(value)


def _llm_answer_raw(prompt: str) -> Optional[str]:
    """Call LLM with a plain user prompt. Used for narrative and synthetic data generation."""
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key and anthropic_key != "your_key_here":
        client = anthropic.Anthropic(api_key=anthropic_key)
        msg = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text

    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key and gemini_key != "your_key_here":
        client = google_genai.Client(api_key=gemini_key)
        models_to_try = ["gemma-3-12b-it", "gemma-3-27b-it", "gemini-2.5-flash", GEMINI_MODEL, "gemini-2.0-flash", "gemini-2.0-flash-lite"]
        # deduplicate while preserving order
        seen: set = set()
        ordered = [m for m in models_to_try if not (m in seen or seen.add(m))]
        last_exc: Optional[Exception] = None
        for model_name in ordered:
            try:
                response = client.models.generate_content(model=model_name, contents=prompt)
                return response.text
            except Exception as exc:
                msg = str(exc)
                if "quota" in msg.lower() or "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    last_exc = exc
                    continue  # try next model
                raise  # other errors (auth, not found) bubble up
        raise HTTPException(
            status_code=429,
            detail="Gemini free-tier quota exhausted on all models — wait a few minutes or enable billing.",
        )

    return None


def _generate_risk_narrative(
    org: Dict[str, Any],
    regn: Dict[str, Any],
    risk: Optional[Dict[str, Any]],
    pep: Optional[Dict[str, Any]],
    members: List[Dict[str, Any]],
) -> Optional[str]:
    eq_pct = (
        f"{risk['equity_ratio']*100:.1f}%"
        if risk and risk.get("equity_ratio") is not None
        else "unknown"
    )
    board_str = ", ".join(
        f"{m['name']} ({m['role']})" for m in members[:6] if m.get("name")
    ) or "Not available"
    flags_str = ", ".join(risk.get("reasons") or []) if risk else "none"
    synthetic_note = " (NOTE: financials are AI-estimated, no public data available)" if regn.get("synthetic") else ""

    prompt = f"""Write a concise 3-paragraph risk assessment for an insurance underwriter considering this Norwegian company as a client.{synthetic_note}

Company: {org.get('navn')} ({org.get('organisasjonsform')}, {org.get('organisasjonsform_kode')})
Industry: {org.get('naeringskode1')} – {org.get('naeringskode1_beskrivelse')}
Location: {org.get('kommune')}, Norway
Board / key roles: {board_str}

Financials ({regn.get('regnskapsår', 'estimated')}):
- Revenue: {_fmt_nok(regn.get('sum_driftsinntekter'))}
- Net result: {_fmt_nok(regn.get('aarsresultat'))}
- Total equity: {_fmt_nok(regn.get('sum_egenkapital'))}
- Total assets: {_fmt_nok(regn.get('sum_eiendeler'))}
- Equity ratio: {eq_pct}
- Employees: {regn.get('antall_ansatte', 'N/A')}

Risk score: {risk.get('score', 'N/A') if risk else 'N/A'} | Flags: {flags_str}
PEP/sanctions hits: {pep.get('hit_count', 0) if pep else 0}

Paragraph 1 – Business profile: Summarise what this company does, its scale, and financial position.
Paragraph 2 – Underwriting concerns: Identify the main risk factors (financial stability, governance quality, PEP exposure, industry risk).
Paragraph 3 – Recommendation: Overall risk stance and 2–3 specific questions to ask before binding coverage.

Be specific, professional, and concise. Do not make up data beyond what is provided."""

    return _llm_answer_raw(prompt)


def _generate_synthetic_financials(org: Dict[str, Any]) -> Dict[str, Any]:
    """Estimate key financial figures for companies with no public Regnskapsregisteret data."""
    prompt = f"""Estimate realistic financial figures for a Norwegian company. Return ONLY a valid JSON object, no explanation.

Company:
- Legal form: {org.get('organisasjonsform')} ({org.get('organisasjonsform_kode')})
- Industry: {org.get('naeringskode1')} – {org.get('naeringskode1_beskrivelse')}
- Municipality: {org.get('kommune')}

Use typical median values for this type of Norwegian company. All values in NOK as integers.
Return exactly this JSON structure:
{{"sum_driftsinntekter": 0, "aarsresultat": 0, "sum_egenkapital": 0, "sum_eiendeler": 0, "sum_gjeld": 0, "antall_ansatte": 0}}"""

    raw = _llm_answer_raw(prompt)
    if not raw:
        return {}

    match = re.search(r"\{[^{}]+\}", raw, re.DOTALL)
    if not match:
        return {}

    try:
        data = json.loads(match.group())
        equity = data.get("sum_egenkapital")
        assets = data.get("sum_eiendeler")
        equity_ratio = (equity / assets) if (equity and assets) else None
        return {
            "regnskapsår": None,
            "sum_driftsinntekter": data.get("sum_driftsinntekter"),
            "aarsresultat": data.get("aarsresultat"),
            "sum_egenkapital": equity,
            "sum_eiendeler": assets,
            "sum_gjeld": data.get("sum_gjeld"),
            "antall_ansatte": data.get("antall_ansatte"),
            "equity_ratio": equity_ratio,
            "synthetic": True,
        }
    except (json.JSONDecodeError, TypeError, ZeroDivisionError):
        return {}


def _build_company_context(db_obj: Company, relevant_notes: List) -> str:
    pep_raw = db_obj.pep_raw or {}
    pep_hits = pep_raw.get("hit_count", 0)

    lines = [
        f"Company: {db_obj.navn} (orgnr: {db_obj.orgnr})",
        f"Legal form: {db_obj.organisasjonsform_kode}",
        f"Municipality: {db_obj.kommune}, {db_obj.land}",
        f"Industry: {db_obj.naeringskode1} – {db_obj.naeringskode1_beskrivelse}",
        f"PEP/sanctions hits: {pep_hits}",
    ]

    if db_obj.regnskapsår:
        eq_pct = (
            f"{db_obj.equity_ratio * 100:.1f}%"
            if db_obj.equity_ratio is not None
            else "–"
        )
        lines += [
            f"\nFinancials ({db_obj.regnskapsår}):",
            f"  Turnover: {_fmt_nok(db_obj.sum_driftsinntekter)}",
            f"  Total equity: {_fmt_nok(db_obj.sum_egenkapital)}",
            f"  Total assets: {_fmt_nok(db_obj.sum_eiendeler)}",
            f"  Equity ratio: {eq_pct}",
            f"  Risk score: {db_obj.risk_score}",
        ]
        raw = db_obj.regnskap_raw or {}
        if raw.get("aarsresultat") is not None:
            lines.append(f"  Annual result: {_fmt_nok(raw.get('aarsresultat'))}")
        if raw.get("antall_ansatte") is not None:
            lines.append(f"  Employees: {raw.get('antall_ansatte')}")
        if raw.get("sum_langsiktig_gjeld") is not None:
            lines.append(f"  Long-term debt: {_fmt_nok(raw.get('sum_langsiktig_gjeld'))}")

    if relevant_notes:
        lines.append("\nRelevant analyst notes (retrieved by semantic similarity):")
        for note in relevant_notes:
            if note.orgnr == db_obj.orgnr:
                label = f"[{note.created_at[:10]}]"
            else:
                label = f"[{note.created_at[:10]}, re: orgnr {note.orgnr}]"
            lines.append(f"  {label} Q: {note.question}")
            lines.append(f"  A: {note.answer}")

    return "\n".join(lines)


# ======================
# FastAPI endpoints
# ======================
@app.get("/ping")
def ping():
    return {"status": "ok"}


@app.get("/search")
def search_orgs(
    name: str = Query(..., min_length=2),
    kommunenummer: Optional[str] = None,
    size: int = Query(20, ge=1, le=100),
):
    try:
        return fetch_enhetsregisteret(name=name, kommunenummer=kommunenummer, size=size)
    except requests.HTTPError as e:
        raise HTTPException(status_code=502, detail=str(e))


def _auto_extract_pdf_sources(orgnr: str, org: Optional[Dict[str, Any]] = None) -> None:
    """Background task: Phase 1 seeds + Phase 2 IR discovery fallback.

    Phase 1: process any PDF sources already seeded in company_pdf_sources.
    Phase 2: if no seeds exist for this org, search for PDFs via DuckDuckGo + Claude,
             cache discovered URLs in company_pdf_sources, then extract them.
    Phase 1 always runs first — seeded data is never overridden by discovery.
    """
    db = SessionLocal()
    try:
        sources = (
            db.query(CompanyPdfSource)
            .filter(CompanyPdfSource.orgnr == orgnr)
            .all()
        )

        # Phase 2: no seeds at all → try IR discovery using company name + website
        if not sources and org:
            navn = org.get("navn", "")
            hjemmeside = org.get("hjemmeside")
            current_year = datetime.now().year
            target_years = [current_year - i for i in range(1, 6)]  # last 5 full years

            discovered = _discover_ir_pdfs(orgnr, navn, hjemmeside, target_years)
            for item in discovered:
                # Only add if not already in DB (discovery can be called multiple times)
                existing = (
                    db.query(CompanyPdfSource)
                    .filter(
                        CompanyPdfSource.orgnr == orgnr,
                        CompanyPdfSource.year == item["year"],
                    )
                    .first()
                )
                if not existing:
                    db.add(CompanyPdfSource(
                        orgnr=orgnr,
                        year=item["year"],
                        pdf_url=item["pdf_url"],
                        label=item.get("label", ""),
                        added_at=datetime.now(timezone.utc).isoformat(),
                    ))
            if discovered:
                db.commit()
                # Reload sources to include newly discovered ones
                sources = (
                    db.query(CompanyPdfSource)
                    .filter(CompanyPdfSource.orgnr == orgnr)
                    .all()
                )

        # Phase 1 (+ newly discovered): extract any not-yet-processed PDF sources
        for src in sources:
            already_extracted = (
                db.query(CompanyHistory)
                .filter(
                    CompanyHistory.orgnr == orgnr,
                    CompanyHistory.year == src.year,
                )
                .first()
            )
            if not already_extracted:
                try:
                    fetch_history_from_pdf(
                        orgnr, src.pdf_url, src.year, src.label or "", db
                    )
                except Exception:
                    pass  # silently skip — don't block future loads
    finally:
        db.close()


@app.get("/org/{orgnr}")
def get_org_profile(
    orgnr: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        result = fetch_org_profile(orgnr, db)
    except requests.HTTPError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if result is None:
        raise HTTPException(status_code=404, detail="Organisation not found")

    # Phase 1 + Phase 2 background PDF extraction.
    # Pass org dict so Phase 2 discovery has access to navn + hjemmeside if needed.
    org = (result or {}).get("org")
    background_tasks.add_task(_auto_extract_pdf_sources, orgnr, org)

    return result


@app.get("/org/{orgnr}/licenses")
def get_org_licenses(orgnr: str):
    try:
        licenses = fetch_finanstilsynet_licenses(orgnr)
    except requests.HTTPError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return {"orgnr": orgnr, "licenses": licenses}


@app.get("/companies")
def list_companies(
    limit: int = Query(50, ge=1, le=500),
    kommune: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Company)
    if kommune:
        q = q.filter(Company.kommune == kommune)

    rows = q.order_by(Company.id.desc()).limit(limit).all()

    return [
        {
            "id": c.id,
            "orgnr": c.orgnr,
            "navn": c.navn,
            "organisasjonsform_kode": c.organisasjonsform_kode,
            "kommune": c.kommune,
            "land": c.land,
            "naeringskode1": c.naeringskode1,
            "naeringskode1_beskrivelse": c.naeringskode1_beskrivelse,
            "regnskapsår": c.regnskapsår,
            "omsetning": c.sum_driftsinntekter,
            "sum_eiendeler": c.sum_eiendeler,
            "sum_egenkapital": c.sum_egenkapital,
            "egenkapitalandel": c.equity_ratio,
            "risk_score": c.risk_score,
        }
        for c in rows
    ]


@app.get("/org-by-name")
def get_org_by_name(
    name: str = Query(..., min_length=2),
    kommunenummer: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Søk på navn, ta første treff, og returner samme som /org/{orgnr}.
    Brukes som komfort-endepunkt (ikke perfekt matching).
    """
    candidates = fetch_enhetsregisteret(name=name, kommunenummer=kommunenummer, size=1)
    if not candidates:
        raise HTTPException(status_code=404, detail="No organisation found for name")

    orgnr = candidates[0]["orgnr"]
    return get_org_profile(orgnr=orgnr, db=db)


SYSTEM_PROMPT = (
    "You are a risk analyst assistant for an insurance broker in Norway. "
    "Help underwriters assess company risk based on Norwegian public registry data. "
    "Be concise and factual. Flag concerns relevant to insurance underwriting "
    "such as negative equity, high leverage, PEP exposure, or unusual financial patterns. "
    "Answer only based on the provided company data. If data is missing, say so."
)


def _llm_answer(context: str, question: str) -> str:
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key and anthropic_key != "your_key_here":
        client = anthropic.Anthropic(api_key=anthropic_key)
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Company data:\n{context}\n\nQuestion: {question}"}],
        )
        return message.content[0].text

    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key and gemini_key != "your_key_here":
        client = google_genai.Client(api_key=gemini_key)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=f"Company data:\n{context}\n\nQuestion: {question}",
            config=genai_types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
        )
        return response.text

    raise HTTPException(status_code=503, detail="No LLM API key configured (ANTHROPIC_API_KEY or GEMINI_API_KEY)")


@app.post("/org/{orgnr}/chat")
def chat_about_org(orgnr: str, body: ChatRequest, db: Session = Depends(get_db)):
    db_obj = db.query(Company).filter(Company.orgnr == orgnr).first()
    if not db_obj:
        raise HTTPException(
            status_code=404,
            detail="Company not in database — call /org/{orgnr} first to load it",
        )

    # RAG: retrieve semantically relevant notes across all companies
    question_embedding = _embed(body.question)
    if question_embedding:
        relevant_notes = (
            db.query(CompanyNote)
            .filter(CompanyNote.embedding.isnot(None))
            .order_by(CompanyNote.embedding.cosine_distance(question_embedding))
            .limit(5)
            .all()
        )
    else:
        # Fallback if no embedding key: most recent notes for this company
        relevant_notes = (
            db.query(CompanyNote)
            .filter(CompanyNote.orgnr == orgnr)
            .order_by(CompanyNote.id.desc())
            .limit(5)
            .all()
        )[::-1]

    context = _build_company_context(db_obj, relevant_notes)
    answer = _llm_answer(context, body.question)

    # Embed the combined Q+A so future questions can retrieve this note
    note_embedding = _embed(f"{body.question} {answer}")

    note = CompanyNote(
        orgnr=orgnr,
        question=body.question,
        answer=answer,
        created_at=datetime.now(timezone.utc).isoformat(),
        embedding=note_embedding if note_embedding else None,
    )
    db.add(note)
    db.commit()

    return {"orgnr": orgnr, "question": body.question, "answer": answer}


@app.get("/org/{orgnr}/chat")
def get_chat_history(
    orgnr: str,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    notes = (
        db.query(CompanyNote)
        .filter(CompanyNote.orgnr == orgnr)
        .order_by(CompanyNote.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": n.id,
            "question": n.question,
            "answer": n.answer,
            "created_at": n.created_at,
        }
        for n in notes
    ]


@app.get("/org/{orgnr}/roles")
def get_org_roles(orgnr: str):
    try:
        members = fetch_board_members(orgnr)
    except requests.HTTPError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"orgnr": orgnr, "members": members}


@app.get("/org/{orgnr}/history")
def get_org_history(orgnr: str, db: Session = Depends(get_db)):
    history = _get_full_history(orgnr, db)
    return {"orgnr": orgnr, "years": history}


class PdfHistoryRequest(BaseModel):
    pdf_url: str
    year: int
    label: str = ""


@app.post("/org/{orgnr}/pdf-history")
def add_pdf_history(orgnr: str, body: PdfHistoryRequest, db: Session = Depends(get_db)):
    """Add a PDF annual report URL for an org, extract financials via Claude, store in DB."""
    # Upsert the source record
    existing_src = (
        db.query(CompanyPdfSource)
        .filter(CompanyPdfSource.orgnr == orgnr, CompanyPdfSource.year == body.year)
        .first()
    )
    if not existing_src:
        existing_src = CompanyPdfSource(orgnr=orgnr, year=body.year)
        db.add(existing_src)
    existing_src.pdf_url = body.pdf_url
    existing_src.label = body.label
    existing_src.added_at = datetime.now(timezone.utc).isoformat()
    db.commit()

    try:
        row = fetch_history_from_pdf(orgnr, body.pdf_url, body.year, body.label, db)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"PDF extraction failed: {e}")
    return {"orgnr": orgnr, "extracted": row}


@app.get("/org/{orgnr}/pdf-sources")
def get_pdf_sources(orgnr: str, db: Session = Depends(get_db)):
    """List known PDF annual report sources for an org."""
    sources = (
        db.query(CompanyPdfSource)
        .filter(CompanyPdfSource.orgnr == orgnr)
        .order_by(CompanyPdfSource.year.desc())
        .all()
    )
    return {
        "orgnr": orgnr,
        "sources": [
            {
                "year": s.year,
                "pdf_url": s.pdf_url,
                "label": s.label,
                "added_at": s.added_at,
            }
            for s in sources
        ],
    }


@app.delete("/org/{orgnr}/history")
def reset_history(orgnr: str, db: Session = Depends(get_db)):
    """Delete all company_history rows for this org so extraction re-runs on next /org/{orgnr} load."""
    deleted = (
        db.query(CompanyHistory)
        .filter(CompanyHistory.orgnr == orgnr)
        .delete()
    )
    db.commit()
    return {"orgnr": orgnr, "deleted_rows": deleted}


@app.post("/org/{orgnr}/offers/compare")
async def compare_offers(
    orgnr: str,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """Extract text from uploaded offer PDFs and return an AI comparison."""
    company = db.query(Company).filter(Company.orgnr == orgnr).first()
    company_ctx = ""
    if company:
        parts = [company.navn or orgnr]
        if company.naeringskode1_beskrivelse:
            parts.append(company.naeringskode1_beskrivelse)
        if company.risk_score is not None:
            parts.append(f"risikoscore {company.risk_score}")
        company_ctx = ", ".join(parts)
    else:
        company_ctx = orgnr

    offer_texts = []
    for f in files:
        raw = await f.read()
        try:
            with pdfplumber.open(io.BytesIO(raw)) as pdf:
                text = "\n".join(p.extract_text() or "" for p in pdf.pages[:40])
        except Exception:
            text = "(kunne ikke lese PDF)"
        offer_texts.append({"name": f.filename or f"Tilbud {len(offer_texts)+1}", "text": text[:10000]})

    offers_block = "\n\n".join(
        f"=== TILBUD {i+1}: {o['name']} ===\n{o['text']}"
        for i, o in enumerate(offer_texts)
    )

    prompt = f"""Du er en erfaren forsikringsmegler som analyserer {len(offer_texts)} forsikringstilbud for en norsk bedrift.

Bedrift: {company_ctx}

{offers_block}

Svar på norsk med disse seksjonene:

## Sammendrag
For hvert tilbud: 2-3 setninger om dekningsomfang, pris og særlige vilkår.

## Sammenligningstabell
Markdown-tabell med kolonnene: Selskap | Dekningstype | Premie/pris | Egenandel | Særlige vilkår | Styrker | Svakheter

## Anbefaling
Hvilket tilbud passer best for denne bedriften og hvorfor.

## Forhandlingspunkter
3-5 konkrete punkter megler bør ta opp med forsikringsselskapet."""

    gemini_key = os.getenv("GEMINI_API_KEY", "")
    gemini_client = google_genai.Client(api_key=gemini_key)
    resp = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )
    return {
        "orgnr": orgnr,
        "offers": [o["name"] for o in offer_texts],
        "comparison": resp.text,
    }


@app.post("/org/{orgnr}/offers")
async def save_offers(
    orgnr: str,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """Upload and persist offer PDFs for a company."""
    now = datetime.now(timezone.utc).isoformat()
    saved = []
    for f in files:
        raw = await f.read()
        try:
            with pdfplumber.open(io.BytesIO(raw)) as pdf:
                text_content = "\n".join(p.extract_text() or "" for p in pdf.pages[:40])
        except Exception:
            text_content = None

        # Guess insurer name from filename (strip extension, replace underscores)
        insurer_guess = (f.filename or "Ukjent").rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()

        row = InsuranceOffer(
            orgnr=orgnr,
            filename=f.filename or "offer.pdf",
            insurer_name=insurer_guess,
            uploaded_at=now,
            pdf_content=raw,
            extracted_text=text_content,
        )
        db.add(row)
        db.flush()
        saved.append({"id": row.id, "filename": row.filename, "insurer_name": row.insurer_name})

    db.commit()
    return {"orgnr": orgnr, "saved": saved}


@app.get("/org/{orgnr}/offers")
def list_offers(orgnr: str, db: Session = Depends(get_db)):
    """List stored offer PDFs for a company."""
    rows = db.query(InsuranceOffer).filter(InsuranceOffer.orgnr == orgnr).order_by(InsuranceOffer.id).all()
    return [
        {
            "id": r.id,
            "filename": r.filename,
            "insurer_name": r.insurer_name,
            "uploaded_at": r.uploaded_at,
            "has_text": bool(r.extracted_text),
        }
        for r in rows
    ]


@app.delete("/org/{orgnr}/offers/{offer_id}")
def delete_offer(orgnr: str, offer_id: int, db: Session = Depends(get_db)):
    row = db.query(InsuranceOffer).filter(
        InsuranceOffer.id == offer_id, InsuranceOffer.orgnr == orgnr
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Offer not found")
    db.delete(row)
    db.commit()
    return {"deleted": offer_id}


@app.get("/org/{orgnr}/offers/{offer_id}/pdf")
def download_offer_pdf(orgnr: str, offer_id: int, db: Session = Depends(get_db)):
    row = db.query(InsuranceOffer).filter(
        InsuranceOffer.id == offer_id, InsuranceOffer.orgnr == orgnr
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Offer not found")
    return StreamingResponse(
        io.BytesIO(row.pdf_content),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{row.filename}"'},
    )


@app.post("/org/{orgnr}/offers/compare-stored")
def compare_stored_offers(
    orgnr: str,
    offer_ids: List[int],
    db: Session = Depends(get_db),
):
    """Run AI comparison on already-stored offer PDFs."""
    rows = db.query(InsuranceOffer).filter(
        InsuranceOffer.orgnr == orgnr,
        InsuranceOffer.id.in_(offer_ids),
    ).all()
    if not rows:
        raise HTTPException(status_code=404, detail="No offers found")

    company = db.query(Company).filter(Company.orgnr == orgnr).first()
    company_ctx = company.navn if company else orgnr

    offers_block = "\n\n".join(
        f"=== TILBUD {i+1}: {r.insurer_name} ({r.filename}) ===\n{(r.extracted_text or '')[:10000]}"
        for i, r in enumerate(rows)
    )

    prompt = f"""Du er en erfaren forsikringsmegler som analyserer {len(rows)} forsikringstilbud for en norsk bedrift.

Bedrift: {company_ctx}

{offers_block}

Svar på norsk med disse seksjonene:

## Sammendrag
For hvert tilbud: 2-3 setninger om dekningsomfang, pris og særlige vilkår.

## Sammenligningstabell
Markdown-tabell med kolonnene: Selskap | Dekningstype | Premie/pris | Egenandel | Særlige vilkår | Styrker | Svakheter

## Anbefaling
Hvilket tilbud passer best for denne bedriften og hvorfor.

## Forhandlingspunkter
3-5 konkrete punkter megler bør ta opp med forsikringsselskapet."""

    gemini_key = os.getenv("GEMINI_API_KEY", "")
    gemini_client = google_genai.Client(api_key=gemini_key)
    resp = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )
    return {
        "orgnr": orgnr,
        "offers": [r.insurer_name for r in rows],
        "comparison": resp.text,
    }


# ---------------------------------------------------------------------------
# Insurance Document Library — upload, list, delete, chat, compare
# ---------------------------------------------------------------------------

class DocChatRequest(BaseModel):
    question: str

class DocCompareRequest(BaseModel):
    doc_ids: List[int]


@app.post("/insurance-documents")
async def upload_insurance_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    category: str = Form("annet"),
    insurer: str = Form(""),
    year: Optional[int] = Form(None),
    period: str = Form("aktiv"),
    orgnr: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Upload and store an insurance document PDF."""
    pdf_bytes = await file.read()
    extracted = ""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages = pdf.pages[:40]
            extracted = "\n".join(p.extract_text() or "" for p in pages)
    except Exception:
        pass

    doc = InsuranceDocument(
        title=title,
        category=category,
        insurer=insurer,
        year=year,
        period=period,
        orgnr=orgnr or None,
        filename=file.filename,
        pdf_content=pdf_bytes,
        extracted_text=extracted or None,
        uploaded_at=datetime.utcnow().isoformat(),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return {
        "id": doc.id,
        "title": doc.title,
        "filename": doc.filename,
        "category": doc.category,
        "insurer": doc.insurer,
        "year": doc.year,
        "period": doc.period,
    }


@app.get("/insurance-documents")
def list_insurance_documents(
    category: Optional[str] = None,
    year: Optional[int] = None,
    period: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List all insurance documents (no PDF bytes)."""
    q = db.query(InsuranceDocument)
    if category:
        q = q.filter(InsuranceDocument.category == category)
    if year:
        q = q.filter(InsuranceDocument.year == year)
    if period:
        q = q.filter(InsuranceDocument.period == period)
    docs = q.order_by(InsuranceDocument.uploaded_at.desc()).all()
    return [
        {
            "id": d.id,
            "title": d.title,
            "filename": d.filename,
            "category": d.category,
            "insurer": d.insurer,
            "year": d.year,
            "period": d.period,
            "orgnr": d.orgnr,
            "uploaded_at": d.uploaded_at,
        }
        for d in docs
    ]


@app.delete("/insurance-documents/{doc_id}")
def delete_insurance_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(InsuranceDocument).filter(InsuranceDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    db.delete(doc)
    db.commit()
    return {"deleted": doc_id}


@app.post("/insurance-documents/{doc_id}/chat")
def chat_with_document(doc_id: int, body: DocChatRequest, db: Session = Depends(get_db)):
    """Ask a question about an insurance document using Gemini native PDF understanding."""
    doc = db.query(InsuranceDocument).filter(InsuranceDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    prompt = (
        f"Du er en norsk forsikringsrådgiver. Svar alltid på norsk. "
        f"Svar kun basert på innholdet i dette forsikringsdokumentet. "
        f"Vær presis og konkret. Oppgi sidetall eller avsnitt hvis relevant.\n\n"
        f"Spørsmål: {body.question}"
    )

    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        try:
            client = google_genai.Client(api_key=gemini_key)
            pdf_part = genai_types.Part.from_bytes(data=doc.pdf_content, mime_type="application/pdf")
            for model in ["gemini-2.5-flash", "gemini-1.5-flash", GEMINI_MODEL]:
                try:
                    resp = client.models.generate_content(
                        model=model,
                        contents=[pdf_part, prompt],
                    )
                    return {"doc_id": doc_id, "question": body.question, "answer": resp.text}
                except Exception:
                    continue
        except Exception:
            pass

    # Fallback: use extracted text + LLM
    if doc.extracted_text is not None:
        fallback_prompt = (
            f"Du er en norsk forsikringsrådgiver. Svar alltid på norsk. "
            f"Svar kun basert på dette forsikringsdokumentets innhold:\n\n"
            f"{doc.extracted_text[:12000]}\n\n"
            f"Spørsmål: {body.question}"
        )
        answer = _llm_answer_raw(fallback_prompt)
        if answer:
            return {"doc_id": doc_id, "question": body.question, "answer": answer}

    raise HTTPException(status_code=503, detail="Ingen LLM tilgjengelig")


@app.post("/insurance-documents/compare")
def compare_insurance_documents(body: DocCompareRequest, db: Session = Depends(get_db)):
    """Compare two insurance documents using Gemini native PDF understanding."""
    if len(body.doc_ids) != 2:
        raise HTTPException(status_code=400, detail="Oppgi nøyaktig 2 dokument-IDer")

    docs = db.query(InsuranceDocument).filter(InsuranceDocument.id.in_(body.doc_ids)).all()
    if len(docs) != 2:
        raise HTTPException(status_code=404, detail="Ett eller begge dokumenter ikke funnet")

    # Sort to match input order
    id_order = {v: i for i, v in enumerate(body.doc_ids)}
    docs_sorted = sorted(docs, key=lambda d: id_order.get(d.id, 0))
    a, b = docs_sorted[0], docs_sorted[1]

    compare_prompt = (
        f"Du er en norsk forsikringsrådgiver som sammenligner to forsikringsdokumenter. "
        f"Svar alltid på norsk.\n\n"
        f"Dokument A: {a.title} ({a.insurer}, {a.year})\n"
        f"Dokument B: {b.title} ({b.insurer}, {b.year})\n\n"
        f"Lag en strukturert sammenligning med:\n"
        f"1. **Sammendrag** — hva er de viktigste forskjellene?\n"
        f"2. **Sammenligningstabell** — markdown-tabell med kolonner: Område | Dokument A | Dokument B | Endring\n"
        f"   Inkluder: dekningsomfang, selvsrisiko, forsikringssum, unntak/begrensninger, særlige vilkår\n"
        f"3. **Konklusjon** — hvilke endringer er til fordel for forsikringstaker?"
    )

    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        try:
            client = google_genai.Client(api_key=gemini_key)
            pdf_a = genai_types.Part.from_bytes(data=a.pdf_content, mime_type="application/pdf")
            pdf_b = genai_types.Part.from_bytes(data=b.pdf_content, mime_type="application/pdf")
            for model in ["gemini-2.5-flash", "gemini-1.5-flash", GEMINI_MODEL]:
                try:
                    resp = client.models.generate_content(
                        model=model,
                        contents=[pdf_a, pdf_b, compare_prompt],
                    )
                    return {
                        "doc_a": {"id": a.id, "title": a.title},
                        "doc_b": {"id": b.id, "title": b.title},
                        "comparison": resp.text,
                    }
                except Exception:
                    continue
        except Exception:
            pass

    # Fallback: use extracted text
    if a.extracted_text is not None and b.extracted_text is not None:
        fallback_prompt = (
            f"{compare_prompt}\n\n"
            f"--- DOKUMENT A ---\n{a.extracted_text[:8000]}\n\n"
            f"--- DOKUMENT B ---\n{b.extracted_text[:8000]}"
        )
        result = _llm_answer_raw(fallback_prompt)
        if result:
            return {
                "doc_a": {"id": a.id, "title": a.title},
                "doc_b": {"id": b.id, "title": b.title},
                "comparison": result,
            }

    raise HTTPException(status_code=503, detail="Ingen LLM tilgjengelig")


@app.post("/org/{orgnr}/narrative")
def generate_narrative(orgnr: str, db: Session = Depends(get_db)):
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
    regn = db_obj.regnskap_raw or {}
    risk_data = None
    if regn:
        risk_data = derive_simple_risk(org, regn)
    pep = db_obj.pep_raw or {}

    try:
        members = fetch_board_members(orgnr)
    except Exception:
        members = []

    narrative = _generate_risk_narrative(org, regn, risk_data, pep, members)
    if narrative is None:
        raise HTTPException(
            status_code=503,
            detail="No LLM API key configured (ANTHROPIC_API_KEY or GEMINI_API_KEY)",
        )
    return {"orgnr": orgnr, "narrative": narrative}


@app.get("/org/{orgnr}/estimate")
def get_synthetic_estimate(orgnr: str):
    org_data = fetch_enhet_by_orgnr(orgnr)
    if not org_data:
        raise HTTPException(status_code=404, detail="Organisation not found")
    result = _generate_synthetic_financials(org_data)
    if not result:
        raise HTTPException(
            status_code=503,
            detail="No LLM API key configured or generation failed",
        )
    return {"orgnr": orgnr, "estimated": result}


@app.get("/org/{orgnr}/bankruptcy")
def get_bankruptcy_status(orgnr: str):
    org = fetch_enhet_by_orgnr(orgnr)
    if not org:
        raise HTTPException(status_code=404, detail="Organisation not found")
    return {
        "orgnr": orgnr,
        "konkurs": org.get("konkurs", False),
        "under_konkursbehandling": org.get("under_konkursbehandling", False),
        "under_avvikling": org.get("under_avvikling", False),
    }


@app.get("/org/{orgnr}/koordinater")
def get_koordinater(orgnr: str):
    org = fetch_enhet_by_orgnr(orgnr)
    if not org:
        raise HTTPException(status_code=404, detail="Organisation not found")
    coords = fetch_koordinater(org)
    return {"orgnr": orgnr, "coordinates": coords}


@app.get("/org/{orgnr}/losore")
def get_losore(orgnr: str):
    result = fetch_losore(orgnr)
    return {"orgnr": orgnr, **result}


@app.get("/org/{orgnr}/benchmark")
def get_benchmark(orgnr: str):
    org = fetch_enhet_by_orgnr(orgnr)
    if not org:
        raise HTTPException(status_code=404, detail="Organisation not found")
    nace = org.get("naeringskode1") or ""
    benchmark = fetch_ssb_benchmark(nace)
    return {"orgnr": orgnr, "nace_code": nace, "benchmark": benchmark}


# ── SLA / Agreements ─────────────────────────────────────────────────────────

STANDARD_VILKAAR = [
    (
        "Avtalens varighet",
        "Avtalen gjelder for ett ar med automatisk fornyelse, med mindre den sies opp "
        "skriftlig av en av partene med fire maneders varsel for utlopsdato.",
    ),
    (
        "Kommunikasjon",
        "All skriftlig kommunikasjon mellom partene skjer elektronisk, som utgangspunkt pa norsk.",
    ),
    (
        "Kundens informasjonsplikt",
        "Kunden plikter a gi megler korrekt og fullstendig informasjon om forsikringsgjenstandene "
        "og risikoen, samt opplyse om tidligere forsikringsforhold og anmeldte skader. "
        "Kunden plikter a gjore lopende rede for endringer i risiko av betydning for forsikringsforholdene.",
    ),
    (
        "Premiebetaling",
        "Forsikringsselskapets premiefaktura sendes, etter kontroll av megler, til Kunden for "
        "betaling direkte til forsikringsselskapet. Kunden er selv ansvarlig for renter og "
        "purregebyr ved for sen betaling, med mindre forsinkelsen skyldes forhold megler har kontroll over.",
    ),
    (
        "Taushetsplikt",
        "Begge parter er forpliktet til a behandle konfidensiell informasjon med forsvarlig "
        "aktsomhet og ikke videreformidle denne til tredjeparter uten skriftlig samtykke.",
    ),
    (
        "Oppsigelse",
        "Avtalen kan sies opp av begge parter med fire maneders skriftlig varsel. "
        "Ved manglende betaling av utestaaende honorar kan megler varsle oppsigelse. "
        "Ved vesentlig mislighold kan avtalen heves med umiddelbar virkning.",
    ),
    (
        "Arlig avtalegjennomgang",
        "Partene skal gjennomga avtaleomfang og foreta nodvendige oppdateringer minimum en gang per ar.",
    ),
    (
        "Ansvarsbegrensning",
        "Meglers ansvar for radgivningsfeil er begrenset til NOK 25 000 000 per oppdrag og "
        "NOK 50 000 000 per kalenderaar. Det svares ikke erstatning for indirekte tap. "
        "Ansvarsbegrensningen omfatter ikke grov uaktsomhet og forsett.",
    ),
    (
        "Klageadgang og verneting",
        "Klager pa meglers tjenester rettes skriftlig til megler. Uloste tvister sokes lost "
        "i minnelighet, og kan bringes inn for Klagenemnda for forsikrings- og "
        "gjenforsikringsmeglingsvirksomhet. Oslo tingrett er verneting.",
    ),
    (
        "Konsesjon og eierskap",
        "Megler har konsesjon til a drive forsikringsmeglingsvirksomhet fra Finanstilsynet. "
        "Megler har verken direkte eller indirekte eierandel som utgjor mer enn 10 % av "
        "stemmeretten eller kapitalen i et forsikringsselskap, og tilsvarende gjelder motsatt vei.",
    ),
    (
        "Forholdet til forsikringsavtaleloven",
        "Med mindre forholdet er omtalt i denne avtalen, fravikes de bestemmelser i "
        "forsikringsavtaleloven som det er adgang til ved forsikringsmegling med andre enn "
        "forbrukere og ved avtale om store risikoer.",
    ),
]

BROKER_TASKS = [
    (
        "Forsikringsmegling av kundens forsikringsprogram",
        "Megler gir kunden rad pa basis av en objektiv analyse av tilgjengelige forsikringslosninger. "
        "Megler innhenter tilbud fra relevante forsikringsgivere, foretar sammenligning og anbefaler "
        "losning i samsvar med kundens behov og risikoeksponering.",
    ),
    (
        "Dokumentasjon og kontroll",
        "Megler kontrollerer at utstedte forsikringsdokumenter er i samsvar med avtalt dekning. "
        "Megler arkiverer og gjor forsikringsdokumentasjon tilgjengelig for kunden. "
        "Megler varsler kunden i god tid for forfall og ved vesentlige endringer i vilkar.",
    ),
    (
        "Skadebehandling",
        "Megler bistar kunden ved anmeldelse av skader til forsikringsselskapet. "
        "Megler folger opp skadebehandlingen og bistar ved uenighet om oppgjor. "
        "Megler dokumenterer alle skader pa vegne av kunden.",
    ),
    (
        "Tilleggstjenester",
        "Etter avtale kan megler yte tilleggstjenester som risikoanalyse, internasjonale "
        "forsikringsprogrammer, pensjonsradgivning og andre spesialtjenester. "
        "Slikt arbeid prises separat med mindre annet er avtalt.",
    ),
]


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

    # ── Cover page ────────────────────────────────────────────────────────────
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

    def _section_title(pdf: FPDF, title: str) -> None:
        pdf.set_font("Helvetica", "B", 13)
        pdf.ln(6)
        pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(0, 0, 0)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(4)
        pdf.set_font("Helvetica", "", 11)

    firm_name = firm_label

    # ── Section 1: Oppdragsavtale ────────────────────────────────────────────
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

    # ── Vedlegg A: Forsikringslinjer ─────────────────────────────────────────
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

    # ── Vedlegg A Del 2: Meglers oppgaver ─────────────────────────────────────
    pdf.ln(6)
    _section_title(pdf, "Vedlegg A Del 2 - Meglers oppgaver")
    for task_title, task_text in BROKER_TASKS:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, _safe(task_title), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, _safe(task_text))
        pdf.ln(3)

    # ── Vedlegg B: Honorar ───────────────────────────────────────────────────
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
        rate_str = ""
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

    # ── Standardvilkar ───────────────────────────────────────────────────────
    pdf.add_page()
    _section_title(pdf, "Standardvilkar")
    for title, text in STANDARD_VILKAAR:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, _safe(title), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, _safe(text))
        pdf.ln(3)

    # ── Vedlegg E: Kundekontroll (KYC/AML) ───────────────────────────────────
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

    # ── Meglerfullmakt / Signatur ────────────────────────────────────────────
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

    return bytes(pdf.output())


class BrokerSettingsIn(BaseModel):
    firm_name: str
    orgnr: Optional[str] = None
    address: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None


class SlaIn(BaseModel):
    form_data: Dict[str, Any]


@app.get("/broker/settings")
def get_broker_settings(db: Session = Depends(get_db)):
    row = db.query(BrokerSettings).filter(BrokerSettings.id == 1).first()
    if not row:
        return {}
    return {
        "firm_name": row.firm_name,
        "orgnr": row.orgnr,
        "address": row.address,
        "contact_name": row.contact_name,
        "contact_email": row.contact_email,
        "contact_phone": row.contact_phone,
        "updated_at": row.updated_at,
    }


@app.post("/broker/settings")
def save_broker_settings(body: BrokerSettingsIn, db: Session = Depends(get_db)):
    row = db.query(BrokerSettings).filter(BrokerSettings.id == 1).first()
    now = datetime.now(timezone.utc).isoformat()
    if row:
        row.firm_name = body.firm_name
        row.orgnr = body.orgnr
        row.address = body.address
        row.contact_name = body.contact_name
        row.contact_email = body.contact_email
        row.contact_phone = body.contact_phone
        row.updated_at = now
    else:
        row = BrokerSettings(
            id=1,
            firm_name=body.firm_name,
            orgnr=body.orgnr,
            address=body.address,
            contact_name=body.contact_name,
            contact_email=body.contact_email,
            contact_phone=body.contact_phone,
            updated_at=now,
        )
        db.add(row)
    db.commit()
    return {"status": "ok", "updated_at": now}


@app.post("/sla")
def create_sla(body: SlaIn, db: Session = Depends(get_db)):
    fd = body.form_data
    broker_row = db.query(BrokerSettings).filter(BrokerSettings.id == 1).first()
    broker_snap = {}
    if broker_row:
        broker_snap = {
            "firm_name": broker_row.firm_name,
            "orgnr": broker_row.orgnr,
            "address": broker_row.address,
            "contact_name": broker_row.contact_name,
            "contact_email": broker_row.contact_email,
            "contact_phone": broker_row.contact_phone,
        }
    now = datetime.now(timezone.utc).isoformat()
    agreement = SlaAgreement(
        created_at=now,
        broker_snapshot=broker_snap,
        client_orgnr=fd.get("client_orgnr"),
        client_navn=fd.get("client_navn"),
        client_adresse=fd.get("client_adresse"),
        client_kontakt=fd.get("client_kontakt"),
        start_date=fd.get("start_date"),
        account_manager=fd.get("account_manager"),
        insurance_lines=fd.get("insurance_lines", []),
        fee_structure=fd.get("fee_structure", {}),
        status="active",
        form_data=fd,
    )
    db.add(agreement)
    db.commit()
    db.refresh(agreement)
    return {"id": agreement.id, "created_at": agreement.created_at}


@app.get("/sla")
def list_slas(db: Session = Depends(get_db)):
    rows = db.query(SlaAgreement).order_by(SlaAgreement.id.desc()).all()
    return [
        {
            "id": r.id,
            "created_at": r.created_at,
            "client_navn": r.client_navn,
            "client_orgnr": r.client_orgnr,
            "start_date": r.start_date,
            "insurance_lines": r.insurance_lines,
            "status": r.status,
        }
        for r in rows
    ]


@app.get("/sla/{sla_id}")
def get_sla(sla_id: int, db: Session = Depends(get_db)):
    row = db.query(SlaAgreement).filter(SlaAgreement.id == sla_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="SLA not found")
    return {
        "id": row.id,
        "created_at": row.created_at,
        "broker_snapshot": row.broker_snapshot,
        "client_orgnr": row.client_orgnr,
        "client_navn": row.client_navn,
        "client_adresse": row.client_adresse,
        "client_kontakt": row.client_kontakt,
        "start_date": row.start_date,
        "account_manager": row.account_manager,
        "insurance_lines": row.insurance_lines,
        "fee_structure": row.fee_structure,
        "status": row.status,
        "form_data": row.form_data,
    }


@app.get("/sla/{sla_id}/pdf")
def download_sla_pdf(sla_id: int, db: Session = Depends(get_db)):
    row = db.query(SlaAgreement).filter(SlaAgreement.id == sla_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="SLA not found")
    pdf_bytes = _generate_sla_pdf(row)
    filename = f"tjenesteavtale_{row.client_orgnr or sla_id}_{(row.created_at or '')[:10]}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
