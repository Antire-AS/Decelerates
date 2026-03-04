from typing import Any, Dict, List, Optional

HIGH_TURNOVER_THRESHOLD = 100_000_000  # 100 MNOK
MID_TURNOVER_THRESHOLD = 10_000_000    # 10 MNOK
MIN_EQUITY_RATIO = 0.2                 # 20%


def derive_simple_risk(org: Dict[str, Any], regn: Dict[str, Any]) -> Dict[str, Any]:
    score = 0
    reasons: List[str] = []

    if org.get("konkurs") or org.get("under_konkursbehandling"):
        score += 5
        reasons.append("Company is in bankruptcy proceedings")
    elif org.get("under_avvikling"):
        score += 3
        reasons.append("Company is under liquidation")

    if org.get("organisasjonsform_kode") in {"AS", "ASA"}:
        score += 1
        reasons.append("Limited liability company (AS/ASA)")

    driftsinntekter = regn.get("sum_driftsinntekter") or 0
    if driftsinntekter > HIGH_TURNOVER_THRESHOLD:
        score += 2
        reasons.append("High turnover (>100 MNOK)")
    elif driftsinntekter > MID_TURNOVER_THRESHOLD:
        score += 1
        reasons.append("Medium turnover (>10 MNOK)")

    egenkapital = regn.get("sum_egenkapital") or 0
    sum_eiendeler = regn.get("sum_eiendeler") or 0
    eq_ratio: Optional[float] = None
    if sum_eiendeler:
        eq_ratio = egenkapital / sum_eiendeler
        if eq_ratio < 0:
            score += 2
            reasons.append("Negative equity")
        elif eq_ratio < MIN_EQUITY_RATIO:
            score += 1
            reasons.append("Low equity ratio (<20%)")

    return {
        "score": score,
        "reasons": reasons,
        "equity_ratio": eq_ratio,
    }


def build_risk_summary(
    org: Dict[str, Any],
    regn: Dict[str, Any],
    risk: Dict[str, Any],
    pep: Dict[str, Any],
) -> Dict[str, Any]:
    equity_ratio = risk.get("equity_ratio") if risk else None
    risk_flags = risk.get("reasons") if risk else []
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

        "regnskapsår": regn.get("regnskapsår"),
        "omsetning": regn.get("sum_driftsinntekter"),
        "aarsresultat": regn.get("aarsresultat"),
        "antall_ansatte": regn.get("antall_ansatte"),
        "sum_eiendeler": regn.get("sum_eiendeler"),
        "sum_egenkapital": regn.get("sum_egenkapital"),
        "egenkapitalandel": equity_ratio,

        "risk_score": risk.get("score") if risk else None,
        "risk_flags": risk_flags,
        "pep_hits": pep_hits,

        "konkurs": org.get("konkurs", False),
        "under_konkursbehandling": org.get("under_konkursbehandling", False),
        "under_avvikling": org.get("under_avvikling", False),
    }
