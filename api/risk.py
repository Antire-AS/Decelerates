import logging
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Thresholds ────────────────────────────────────────────────────────────────
VERY_HIGH_TURNOVER_THRESHOLD = 1_000_000_000  # 1 BNOK
HIGH_TURNOVER_THRESHOLD = 100_000_000  # 100 MNOK
MID_TURNOVER_THRESHOLD = 10_000_000  # 10 MNOK
MIN_EQUITY_RATIO = 0.20  # 20 %

# NACE sections by risk tier (letter = section from NACE code prefix)
HIGH_RISK_NACE = {"F", "H", "K", "N"}  # Construction, Transport, Finance, Rental
MED_RISK_NACE = {"C", "G", "I", "J"}  # Manufacturing, Trade, Hospitality, ICT

CATEGORY_COLORS = {
    "Selskapsstatus": "🔴",
    "Økonomi": "🟠",
    "Bransje": "🟡",
    "Historikk": "🔵",
    "Eksponering": "🟣",
}

# Canonical risk band definitions — the single source of truth for both
# the backend (risk narrative, PDF reports) and frontend (portfolio charts,
# company profile legend). The frontend reads these via GET /risk/config
# so changes here propagate everywhere without a frontend redeploy.
RISK_BANDS = [
    {"label": "Lav", "min": 0, "max": 5, "color": "#27AE60"},
    {"label": "Moderat", "min": 6, "max": 10, "color": "#C8A951"},
    {"label": "Høy", "min": 11, "max": 15, "color": "#E67E22"},
    {"label": "Svært høy", "min": 16, "max": 20, "color": "#C0392B"},
]

_AddFn = Callable[[str, int, str, str], None]


def _nace_section(nace_code: Optional[str]) -> Optional[str]:
    """Return the NACE section letter (A–S) from a NACE code like '49.20'."""
    if not nace_code:
        return None
    prefixes = {
        "01": "A",
        "02": "A",
        "03": "A",
        "05": "B",
        "06": "B",
        "07": "B",
        "08": "B",
        "09": "B",
        "10": "C",
        "11": "C",
        "12": "C",
        "13": "C",
        "14": "C",
        "15": "C",
        "16": "C",
        "17": "C",
        "18": "C",
        "19": "C",
        "20": "C",
        "21": "C",
        "22": "C",
        "23": "C",
        "24": "C",
        "25": "C",
        "26": "C",
        "27": "C",
        "28": "C",
        "29": "C",
        "30": "C",
        "31": "C",
        "32": "C",
        "33": "C",
        "35": "D",
        "36": "E",
        "37": "E",
        "38": "E",
        "39": "E",
        "41": "F",
        "42": "F",
        "43": "F",
        "45": "G",
        "46": "G",
        "47": "G",
        "49": "H",
        "50": "H",
        "51": "H",
        "52": "H",
        "53": "H",
        "55": "I",
        "56": "I",
        "58": "J",
        "59": "J",
        "60": "J",
        "61": "J",
        "62": "J",
        "63": "J",
        "64": "K",
        "65": "K",
        "66": "K",
        "68": "L",
        "69": "M",
        "70": "M",
        "71": "M",
        "72": "M",
        "73": "M",
        "74": "M",
        "75": "M",
        "77": "N",
        "78": "N",
        "79": "N",
        "80": "N",
        "81": "N",
        "82": "N",
        "84": "O",
        "85": "P",
        "86": "Q",
        "87": "Q",
        "88": "Q",
        "90": "R",
        "91": "R",
        "92": "R",
        "93": "R",
        "94": "S",
        "95": "S",
        "96": "S",
        "97": "T",
        "98": "T",
        "99": "U",
    }
    prefix = nace_code.replace(".", "")[:2]
    return prefixes.get(prefix)


def _check_company_status(org: Dict[str, Any], add: _AddFn) -> None:
    """Risk factors from company registry status and legal form."""
    if org.get("konkurs") or org.get("under_konkursbehandling"):
        add(
            "Konkursbehandling",
            5,
            "Selskapsstatus",
            "Selskapet er under konkursbehandling",
        )
    elif org.get("under_avvikling"):
        add("Under avvikling", 3, "Selskapsstatus", "Selskapet er under avvikling")

    if org.get("organisasjonsform_kode") in {"AS", "ASA"}:
        add(
            "Aksjeselskap (AS/ASA)",
            1,
            "Selskapsstatus",
            "Begrenset ansvar øker eksponering",
        )

    land = (org.get("land") or "").upper()
    if land and land not in {"NOR", "NORGE", "NORWAY", "NO"}:
        add(
            "Utenlandskregistrert enhet",
            1,
            "Selskapsstatus",
            f"Registrert i: {org.get('land')}",
        )


def _check_turnover(driftsinntekter: float, add: _AddFn) -> None:
    if driftsinntekter > VERY_HIGH_TURNOVER_THRESHOLD:
        add(
            "Svært stor virksomhet (>1 MNOK)",
            2,
            "Økonomi",
            f"Omsetning: {driftsinntekter / 1e9:.1f} BNOK",
        )
    elif driftsinntekter > HIGH_TURNOVER_THRESHOLD:
        add(
            "Høy omsetning (>100 MNOK)",
            1,
            "Økonomi",
            f"Omsetning: {driftsinntekter / 1e6:.0f} MNOK",
        )
    elif driftsinntekter > MID_TURNOVER_THRESHOLD:
        add(
            "Middels omsetning (>10 MNOK)",
            1,
            "Økonomi",
            f"Omsetning: {driftsinntekter / 1e6:.1f} MNOK",
        )


def _check_equity_ratio(
    egenkapital: float, sum_eiendeler: float, add: _AddFn
) -> Optional[float]:
    if not sum_eiendeler:
        return None
    eq_ratio = egenkapital / sum_eiendeler
    if eq_ratio < -0.20:
        add(
            "Kraftig negativ egenkapital (<-20%)",
            4,
            "Økonomi",
            f"Egenkapitalandel: {eq_ratio * 100:.1f}%",
        )
    elif eq_ratio < 0:
        add(
            "Negativ egenkapital",
            2,
            "Økonomi",
            f"Egenkapitalandel: {eq_ratio * 100:.1f}%",
        )
    elif eq_ratio < MIN_EQUITY_RATIO:
        add(
            "Lav egenkapitalandel (<20%)",
            1,
            "Økonomi",
            f"Egenkapitalandel: {eq_ratio * 100:.1f}%",
        )
    return eq_ratio


def _check_profit(regn: Dict[str, Any], driftsinntekter: float, add: _AddFn) -> None:
    aarsresultat = regn.get("aarsresultat")
    if aarsresultat is not None and aarsresultat < 0:
        add(
            "Negativt årsresultat",
            1,
            "Økonomi",
            f"Årsresultat: {aarsresultat / 1e6:.1f} MNOK",
        )
    driftsresultat = regn.get("driftsresultat")
    if driftsresultat is not None and driftsresultat < 0 and driftsinntekter > 0:
        add(
            "Negativt driftsresultat (EBIT)",
            1,
            "Økonomi",
            f"Driftsresultat: {driftsresultat / 1e6:.1f} MNOK",
        )


def _check_debt_ratio(regn: Dict[str, Any], sum_eiendeler: float, add: _AddFn) -> None:
    sum_gjeld = regn.get("sum_gjeld")
    if sum_gjeld is not None and sum_eiendeler:
        gjeldsgrad = sum_gjeld / sum_eiendeler
        if gjeldsgrad > 0.80:
            add(
                "Svært høy gjeldsgrad (>80%)",
                2,
                "Økonomi",
                f"Gjeldsgrad: {gjeldsgrad * 100:.0f}%",
            )
        elif gjeldsgrad > 0.60:
            add(
                "Høy gjeldsgrad (>60%)",
                1,
                "Økonomi",
                f"Gjeldsgrad: {gjeldsgrad * 100:.0f}%",
            )


def _check_financial_health(regn: Dict[str, Any], add: _AddFn) -> Optional[float]:
    """Risk factors from financial statements. Returns computed equity_ratio or None."""
    driftsinntekter = regn.get("sum_driftsinntekter") or 0
    _check_turnover(driftsinntekter, add)
    eq_ratio = _check_equity_ratio(
        regn.get("sum_egenkapital") or 0,
        regn.get("sum_eiendeler") or 0,
        add,
    )
    _check_profit(regn, driftsinntekter, add)
    _check_debt_ratio(regn, regn.get("sum_eiendeler") or 0, add)
    return eq_ratio


def _check_nace_risk(org: Dict[str, Any], add: _AddFn) -> None:
    nace_section = _nace_section(org.get("naeringskode1"))
    nace_desc = org.get("naeringskode1_beskrivelse", "")
    if nace_section in HIGH_RISK_NACE:
        add(
            "Høyrisikonæring", 2, "Bransje", f"NACE-seksjon {nace_section}: {nace_desc}"
        )
    elif nace_section in MED_RISK_NACE:
        add(
            "Moderat bransjerisiko",
            1,
            "Bransje",
            f"NACE-seksjon {nace_section}: {nace_desc}",
        )


def _check_company_age(org: Dict[str, Any], add: _AddFn) -> None:
    stiftelsesdato = org.get("stiftelsesdato")
    if not stiftelsesdato:
        return
    try:
        founded = datetime.strptime(str(stiftelsesdato)[:10], "%Y-%m-%d").date()
        age_years = (date.today() - founded).days / 365.25
        if age_years < 1:
            add(
                "Svært nystartet selskap (<1 år)",
                4,
                "Historikk",
                f"Stiftet: {stiftelsesdato}",
            )
        elif age_years < 2:
            add(
                "Nystartet selskap (<2 år)",
                3,
                "Historikk",
                f"Stiftet: {stiftelsesdato}",
            )
        elif age_years < 5:
            add(
                "Relativt nytt selskap (<5 år)",
                1,
                "Historikk",
                f"Stiftet: {stiftelsesdato}",
            )
    except Exception as exc:
        logger.warning("Could not parse stiftelsesdato %r: %s", stiftelsesdato, exc)


def _check_employee_exposure(regn: Dict[str, Any], add: _AddFn) -> None:
    antall_ansatte = regn.get("antall_ansatte")
    if antall_ansatte:
        if antall_ansatte > 1000:
            add(
                "Svært stor arbeidsgiveransvar-eksponering (>1000 ansatte)",
                2,
                "Eksponering",
                f"Antall ansatte: {antall_ansatte}",
            )
        elif antall_ansatte > 200:
            add(
                "Høy arbeidsgiveransvar-eksponering (>200 ansatte)",
                1,
                "Eksponering",
                f"Antall ansatte: {antall_ansatte}",
            )


def _check_pep_exposure(pep: Optional[Dict[str, Any]], add: _AddFn) -> None:
    pep_hits = (pep or {}).get("hit_count", 0)
    if pep_hits and pep_hits > 0:
        add(
            "PEP/sanksjoner funnet",
            2,
            "Eksponering",
            f"{pep_hits} treff i OpenSanctions",
        )


def _check_industry_age_exposure(
    org: Dict[str, Any],
    regn: Dict[str, Any],
    pep: Optional[Dict[str, Any]],
    add: _AddFn,
) -> None:
    """Risk factors from industry classification, company age, size, and PEP screening."""
    _check_nace_risk(org, add)
    _check_company_age(org, add)
    _check_employee_exposure(regn, add)
    _check_pep_exposure(pep, add)


# ── Altman Z''-Score (bankruptcy prediction) ─────────────────────────────────
#
# Non-manufacturing, non-listed variant (Altman 2000). Validated against
# thousands of real-world bankruptcies. Returns a probabilistic distress
# signal — unlike the additive rule-based score above, this one actually
# predicts bankruptcy within 2 years with measured accuracy.
#
#   Z'' = 6.56·(WC/TA) + 3.26·(RE/TA) + 6.72·(EBIT/TA) + 1.05·(BE/TL)
#
# Zones (Altman 2000):
#   Z'' > 2.60           → Safe
#   1.10 ≤ Z'' ≤ 2.60    → Grey
#   Z'' < 1.10           → Distress
#
# We map Z'' to the broker 0-20 risk scale via piecewise linear interpolation.
# Anchored so the zone boundaries land on the Lav/Moderat/Høy/Svært høy
# RISK_BANDS boundaries from above.

Z_SAFE = 3.50
Z_GREY_TOP = 2.60
Z_GREY_MID = 1.85
Z_DISTRESS_TOP = 1.10
Z_CRITICAL = 0.0


def _safe_div(num: Optional[float], den: Optional[float]) -> Optional[float]:
    """Divide that tolerates None/zero inputs. Returns None if either input
    is missing or denominator is zero — caller falls back to the rule-based
    score for partial extractions."""
    if num is None or den is None or not den:
        return None
    return num / den


def _map_z_to_risk_score(z: float) -> int:
    """Piecewise-linear mapping from Altman Z'' to the 0-20 broker risk scale.

    Anchored so:
      score  0 = Z'' ≥ 3.50 (very safe)
      score  5 = boundary of Safe zone (Lav → Moderat)
      score 10 = centre of Grey zone
      score 15 = boundary of Distress zone (Høy → Svært høy)
      score 20 = Z'' ≤ 0 (severe distress)
    """
    if z >= Z_SAFE:
        return 0
    if z >= Z_GREY_TOP:
        return round(5 * (Z_SAFE - z) / (Z_SAFE - Z_GREY_TOP))
    if z >= Z_GREY_MID:
        return round(5 + 5 * (Z_GREY_TOP - z) / (Z_GREY_TOP - Z_GREY_MID))
    if z >= Z_DISTRESS_TOP:
        return round(10 + 5 * (Z_GREY_MID - z) / (Z_GREY_MID - Z_DISTRESS_TOP))
    if z >= Z_CRITICAL:
        return round(15 + 5 * (Z_DISTRESS_TOP - z) / (Z_DISTRESS_TOP - Z_CRITICAL))
    return 20


def _z_zone(z: float) -> str:
    """Zone label (safe/grey/distress) matching Altman 2000 thresholds."""
    if z > Z_GREY_TOP:
        return "safe"
    if z >= Z_DISTRESS_TOP:
        return "grey"
    return "distress"


def _altman_ratios(
    regn: Dict[str, Any],
) -> Optional[Dict[str, float]]:
    """Compute the four Altman Z'' input ratios, or None if any input is
    missing. Banks + insurers lack the current/non-current split, so their
    working-capital ratio is undefined and we bail here."""
    total_assets = regn.get("sum_eiendeler") or regn.get("total_assets")
    total_liab = regn.get("sum_gjeld")
    equity = regn.get("sum_egenkapital") or regn.get("equity")
    current_assets = regn.get("sum_omloepsmidler")
    short_term_debt = regn.get("short_term_debt")
    working_capital: Optional[float] = None
    if current_assets is not None and short_term_debt is not None:
        working_capital = current_assets - short_term_debt
    x1 = _safe_div(working_capital, total_assets)
    x2 = _safe_div(regn.get("sum_opptjent_egenkapital"), total_assets)
    x3 = _safe_div(regn.get("driftsresultat"), total_assets)
    x4 = _safe_div(equity, total_liab)
    if None in (x1, x2, x3, x4):
        return None
    return {"x1": x1, "x2": x2, "x3": x3, "x4": x4}


def compute_altman_z_score(regn: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Compute Altman Z''-Score + component breakdown from extracted financials.

    Returns None if any required input is missing. The component dict lets
    the UI explain *why* a score is what it is: a company scoring 12 because
    of negative EBIT reads differently from one scoring 12 because of leverage.
    """
    ratios = _altman_ratios(regn)
    if ratios is None:
        return None
    x1, x2, x3, x4 = ratios["x1"], ratios["x2"], ratios["x3"], ratios["x4"]
    z = 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4
    return {
        "z_score": round(z, 2),
        "zone": _z_zone(z),
        "score_20": _map_z_to_risk_score(z),
        "components": {
            "working_capital_ratio": round(x1, 4),
            "retained_earnings_ratio": round(x2, 4),
            "ebit_ratio": round(x3, 4),
            "equity_to_liab_ratio": round(x4, 4),
        },
        "formula": "Altman Z'' (2000) — non-manufacturing private firms",
    }


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
        factors.append(
            {"label": label, "points": points, "category": category, "detail": detail}
        )

    if not regn:
        add(
            "Ingen finansdata tilgjengelig",
            1,
            "Økonomi",
            "Kan ikke vurdere finansiell risiko — ingen regnskapsdata funnet",
        )

    _check_company_status(org, add)
    eq_ratio = _check_financial_health(regn, add)
    _check_industry_age_exposure(org, regn, pep, add)

    # Altman Z'' is an augmentation, not a replacement — returns None for
    # companies missing the required balance-sheet detail (banks, insurers,
    # incomplete PDFs) and the caller falls back to the rule-based score.
    altman = compute_altman_z_score(regn) if regn else None

    return {
        "score": score,
        "factors": factors,
        "reasons": [f["label"] for f in factors],  # backwards-compatible
        "equity_ratio": eq_ratio,
        "altman_z": altman,
    }


def build_risk_summary(
    org: Dict[str, Any],
    regn: Dict[str, Any],
    risk: Dict[str, Any],
    pep: Dict[str, Any],
) -> Dict[str, Any]:
    equity_ratio = risk.get("equity_ratio") if risk else None
    risk_flags = risk.get("reasons") if risk else []
    risk_factors = risk.get("factors") if risk else []
    pep_hits = pep.get("hit_count", 0) if pep else 0

    return {
        "orgnr": org.get("orgnr"),
        "navn": org.get("navn"),
        "organisasjonsform": org.get("organisasjonsform"),
        "organisasjonsform_kode": org.get("organisasjonsform_kode"),
        "kommune": org.get("kommune"),
        "land": org.get("land"),
        "naeringskode1": org.get("naeringskode1"),
        "naeringskode1_beskrivelse": org.get("naeringskode1_beskrivelse"),
        "stiftelsesdato": org.get("stiftelsesdato"),
        "regnskapsår": regn.get("regnskapsår"),
        "omsetning": regn.get("sum_driftsinntekter"),
        "aarsresultat": regn.get("aarsresultat"),
        "antall_ansatte": regn.get("antall_ansatte"),
        "sum_eiendeler": regn.get("sum_eiendeler"),
        "sum_egenkapital": regn.get("sum_egenkapital"),
        "sum_gjeld": regn.get("sum_gjeld"),
        "egenkapitalandel": equity_ratio,
        "risk_score": risk.get("score") if risk else None,
        "risk_flags": risk_flags,
        "risk_factors": risk_factors,
        "altman_z": risk.get("altman_z") if risk else None,
        "pep_hits": pep_hits,
        "konkurs": org.get("konkurs", False),
        "under_konkursbehandling": org.get("under_konkursbehandling", False),
        "under_avvikling": org.get("under_avvikling", False),
    }
