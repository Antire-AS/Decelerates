from datetime import date, datetime
from typing import Any, Dict, List, Optional

# ── Thresholds ────────────────────────────────────────────────────────────────
VERY_HIGH_TURNOVER_THRESHOLD = 1_000_000_000  # 1 BNOK
HIGH_TURNOVER_THRESHOLD      =   100_000_000  # 100 MNOK
MID_TURNOVER_THRESHOLD       =    10_000_000  # 10 MNOK
MIN_EQUITY_RATIO             = 0.20           # 20 %

# NACE sections by risk tier (letter = section from NACE code prefix)
HIGH_RISK_NACE = {"F", "H", "K", "N"}  # Construction, Transport, Finance, Rental
MED_RISK_NACE  = {"C", "G", "I", "J"}  # Manufacturing, Trade, Hospitality, ICT

CATEGORY_COLORS = {
    "Selskapsstatus": "🔴",
    "Økonomi":        "🟠",
    "Bransje":        "🟡",
    "Historikk":      "🔵",
    "Eksponering":    "🟣",
}


def _nace_section(nace_code: Optional[str]) -> Optional[str]:
    """Return the NACE section letter (A–S) from a NACE code like '49.20'."""
    if not nace_code:
        return None
    prefixes = {
        "01": "A", "02": "A", "03": "A",
        "05": "B", "06": "B", "07": "B", "08": "B", "09": "B",
        "10": "C", "11": "C", "12": "C", "13": "C", "14": "C",
        "15": "C", "16": "C", "17": "C", "18": "C", "19": "C",
        "20": "C", "21": "C", "22": "C", "23": "C", "24": "C",
        "25": "C", "26": "C", "27": "C", "28": "C", "29": "C",
        "30": "C", "31": "C", "32": "C", "33": "C",
        "35": "D",
        "36": "E", "37": "E", "38": "E", "39": "E",
        "41": "F", "42": "F", "43": "F",
        "45": "G", "46": "G", "47": "G",
        "49": "H", "50": "H", "51": "H", "52": "H", "53": "H",
        "55": "I", "56": "I",
        "58": "J", "59": "J", "60": "J", "61": "J", "62": "J", "63": "J",
        "64": "K", "65": "K", "66": "K",
        "68": "L",
        "69": "M", "70": "M", "71": "M", "72": "M", "73": "M", "74": "M", "75": "M",
        "77": "N", "78": "N", "79": "N", "80": "N", "81": "N", "82": "N",
        "84": "O",
        "85": "P",
        "86": "Q", "87": "Q", "88": "Q",
        "90": "R", "91": "R", "92": "R", "93": "R",
        "94": "S", "95": "S", "96": "S",
        "97": "T", "98": "T",
        "99": "U",
    }
    prefix = nace_code.replace(".", "")[:2]
    return prefixes.get(prefix)


def _check_company_status(org: Dict[str, Any], add) -> None:
    """Risk factors from company registry status and legal form."""
    if org.get("konkurs") or org.get("under_konkursbehandling"):
        add("Konkursbehandling", 5, "Selskapsstatus", "Selskapet er under konkursbehandling")
    elif org.get("under_avvikling"):
        add("Under avvikling", 3, "Selskapsstatus", "Selskapet er under avvikling")

    if org.get("organisasjonsform_kode") in {"AS", "ASA"}:
        add("Aksjeselskap (AS/ASA)", 1, "Selskapsstatus", "Begrenset ansvar øker eksponering")

    land = (org.get("land") or "").upper()
    if land and land not in {"NOR", "NORGE", "NORWAY", "NO"}:
        add("Utenlandskregistrert enhet", 1, "Selskapsstatus",
            f"Registrert i: {org.get('land')}")


def _check_financial_health(regn: Dict[str, Any], add) -> Optional[float]:
    """Risk factors from financial statements. Returns computed equity_ratio or None."""
    driftsinntekter = regn.get("sum_driftsinntekter") or 0
    if driftsinntekter > VERY_HIGH_TURNOVER_THRESHOLD:
        add("Svært stor virksomhet (>1 MNOK)", 2, "Økonomi",
            f"Omsetning: {driftsinntekter/1e9:.1f} BNOK")
    elif driftsinntekter > HIGH_TURNOVER_THRESHOLD:
        add("Høy omsetning (>100 MNOK)", 1, "Økonomi",
            f"Omsetning: {driftsinntekter/1e6:.0f} MNOK")
    elif driftsinntekter > MID_TURNOVER_THRESHOLD:
        add("Middels omsetning (>10 MNOK)", 1, "Økonomi",
            f"Omsetning: {driftsinntekter/1e6:.1f} MNOK")

    egenkapital  = regn.get("sum_egenkapital") or 0
    sum_eiendeler = regn.get("sum_eiendeler") or 0
    eq_ratio: Optional[float] = None
    if sum_eiendeler:
        eq_ratio = egenkapital / sum_eiendeler
        if eq_ratio < -0.20:
            add("Kraftig negativ egenkapital (<-20%)", 4, "Økonomi",
                f"Egenkapitalandel: {eq_ratio*100:.1f}%")
        elif eq_ratio < 0:
            add("Negativ egenkapital", 2, "Økonomi",
                f"Egenkapitalandel: {eq_ratio*100:.1f}%")
        elif eq_ratio < MIN_EQUITY_RATIO:
            add("Lav egenkapitalandel (<20%)", 1, "Økonomi",
                f"Egenkapitalandel: {eq_ratio*100:.1f}%")

    aarsresultat = regn.get("aarsresultat")
    if aarsresultat is not None and aarsresultat < 0:
        add("Negativt årsresultat", 1, "Økonomi",
            f"Årsresultat: {aarsresultat/1e6:.1f} MNOK")

    driftsresultat = regn.get("driftsresultat")
    if driftsresultat is not None and driftsresultat < 0 and driftsinntekter > 0:
        add("Negativt driftsresultat (EBIT)", 1, "Økonomi",
            f"Driftsresultat: {driftsresultat/1e6:.1f} MNOK")

    sum_gjeld = regn.get("sum_gjeld")
    if sum_gjeld is not None and sum_eiendeler:
        gjeldsgrad = sum_gjeld / sum_eiendeler
        if gjeldsgrad > 0.80:
            add("Svært høy gjeldsgrad (>80%)", 2, "Økonomi",
                f"Gjeldsgrad: {gjeldsgrad*100:.0f}%")
        elif gjeldsgrad > 0.60:
            add("Høy gjeldsgrad (>60%)", 1, "Økonomi",
                f"Gjeldsgrad: {gjeldsgrad*100:.0f}%")

    return eq_ratio


def _check_industry_age_exposure(
    org: Dict[str, Any], regn: Dict[str, Any], pep: Optional[Dict[str, Any]], add
) -> None:
    """Risk factors from industry classification, company age, size, and PEP screening."""
    nace_section = _nace_section(org.get("naeringskode1"))
    nace_desc    = org.get("naeringskode1_beskrivelse", "")
    if nace_section in HIGH_RISK_NACE:
        add("Høyrisikonæring", 2, "Bransje",
            f"NACE-seksjon {nace_section}: {nace_desc}")
    elif nace_section in MED_RISK_NACE:
        add("Moderat bransjerisiko", 1, "Bransje",
            f"NACE-seksjon {nace_section}: {nace_desc}")

    stiftelsesdato = org.get("stiftelsesdato")
    if stiftelsesdato:
        try:
            founded   = datetime.strptime(str(stiftelsesdato)[:10], "%Y-%m-%d").date()
            age_years = (date.today() - founded).days / 365.25
            if age_years < 1:
                add("Svært nystartet selskap (<1 år)", 4, "Historikk",
                    f"Stiftet: {stiftelsesdato}")
            elif age_years < 2:
                add("Nystartet selskap (<2 år)", 3, "Historikk",
                    f"Stiftet: {stiftelsesdato}")
            elif age_years < 5:
                add("Relativt nytt selskap (<5 år)", 1, "Historikk",
                    f"Stiftet: {stiftelsesdato}")
        except Exception:
            pass

    antall_ansatte = regn.get("antall_ansatte")
    if antall_ansatte:
        if antall_ansatte > 1000:
            add("Svært stor arbeidsgiveransvar-eksponering (>1000 ansatte)", 2, "Eksponering",
                f"Antall ansatte: {antall_ansatte}")
        elif antall_ansatte > 200:
            add("Høy arbeidsgiveransvar-eksponering (>200 ansatte)", 1, "Eksponering",
                f"Antall ansatte: {antall_ansatte}")

    pep_hits = (pep or {}).get("hit_count", 0)
    if pep_hits and pep_hits > 0:
        add("PEP/sanksjoner funnet", 2, "Eksponering",
            f"{pep_hits} treff i OpenSanctions")


def derive_simple_risk(
    org: Dict[str, Any],
    regn: Dict[str, Any],
    pep: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    score = 0
    factors: List[Dict[str, Any]] = []

    def add(label: str, points: int, category: str, detail: str = "") -> None:
        nonlocal score
        score += points
        factors.append({"label": label, "points": points, "category": category, "detail": detail})

    if not regn:
        add("Ingen finansdata tilgjengelig", 1, "Økonomi",
            "Kan ikke vurdere finansiell risiko — ingen regnskapsdata funnet")

    _check_company_status(org, add)
    eq_ratio = _check_financial_health(regn, add)
    _check_industry_age_exposure(org, regn, pep, add)

    return {
        "score": score,
        "factors": factors,
        "reasons": [f["label"] for f in factors],  # backwards-compatible
        "equity_ratio": eq_ratio,
    }


def build_risk_summary(
    org: Dict[str, Any],
    regn: Dict[str, Any],
    risk: Dict[str, Any],
    pep: Dict[str, Any],
) -> Dict[str, Any]:
    equity_ratio = risk.get("equity_ratio") if risk else None
    risk_flags   = risk.get("reasons") if risk else []
    risk_factors = risk.get("factors") if risk else []
    pep_hits     = pep.get("hit_count", 0) if pep else 0

    return {
        "orgnr":                      org.get("orgnr"),
        "navn":                       org.get("navn"),
        "organisasjonsform":          org.get("organisasjonsform"),
        "organisasjonsform_kode":     org.get("organisasjonsform_kode"),
        "kommune":                    org.get("kommune"),
        "land":                       org.get("land"),
        "naeringskode1":              org.get("naeringskode1"),
        "naeringskode1_beskrivelse":  org.get("naeringskode1_beskrivelse"),
        "stiftelsesdato":             org.get("stiftelsesdato"),

        "regnskapsår":    regn.get("regnskapsår"),
        "omsetning":      regn.get("sum_driftsinntekter"),
        "aarsresultat":   regn.get("aarsresultat"),
        "antall_ansatte": regn.get("antall_ansatte"),
        "sum_eiendeler":  regn.get("sum_eiendeler"),
        "sum_egenkapital": regn.get("sum_egenkapital"),
        "sum_gjeld":      regn.get("sum_gjeld"),
        "egenkapitalandel": equity_ratio,

        "risk_score":   risk.get("score") if risk else None,
        "risk_flags":   risk_flags,
        "risk_factors": risk_factors,
        "pep_hits":     pep_hits,

        "konkurs":                  org.get("konkurs", False),
        "under_konkursbehandling":  org.get("under_konkursbehandling", False),
        "under_avvikling":          org.get("under_avvikling", False),
    }
