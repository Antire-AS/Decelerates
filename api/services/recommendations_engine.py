"""Pure-rule recommendation engine — emits a ranked list of suggested
broker actions based on portfolio state.

Inputs are explicit dicts/sets so the engine has zero I/O and is fully
testable without a DB."""

from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional


def _pep_recommendation(orgnr: Optional[str], navn: str) -> dict:
    return {
        "kind": "pep",
        "orgnr": orgnr,
        "headline": f"{navn}: PEP-treff funnet",
        "body": "OpenSanctions har 1+ treff. Gjennomgå før neste klientmøte.",
        "cta_label": "Se PEP-rapport",
        "cta_href": f"/search/{orgnr}?tab=risiko",
    }


def _stale_narrative_recommendation(orgnr: Optional[str], navn: str) -> dict:
    return {
        "kind": "stale_narrative",
        "orgnr": orgnr,
        "headline": f"{navn}: oppdater risikoanalyse",
        "body": "Skadehistorikk har endret seg siden siste vurdering. Generer ny narrativ.",
        "cta_label": "Generer narrativ",
        "cta_href": f"/search/{orgnr}?tab=oversikt",
    }


def _peer_overage_recommendation(n: int) -> dict:
    return {
        "kind": "peer_overage",
        "orgnr": None,
        "headline": f"{n} kunder over forventet risiko",
        "body": "Disse selskapene har overskredet bransjebenchmark for soliditet.",
        "cta_label": "Vis liste",
        "cta_href": "/portfolio?filter=peer_overage",
    }


def _is_stale(
    orgnr: Optional[str],
    claims_index: dict[str, datetime],
    last_narrative_at: dict[str, datetime],
    fresh_claim_threshold: datetime,
    stale_threshold: datetime,
) -> bool:
    last_claim = claims_index.get(orgnr or "")
    last_narr = last_narrative_at.get(orgnr or "")
    return bool(
        last_claim
        and last_claim >= fresh_claim_threshold
        and (not last_narr or last_narr < stale_threshold)
    )


def compute_recommendations(
    *,
    companies: Iterable[dict],
    claims_index: dict[str, datetime],
    last_narrative_at: dict[str, datetime],
    peer_overage_orgnrs: set[str],
) -> list[dict]:
    """Return a list of {kind, orgnr, headline, body, cta_label, cta_href}.

    Rules:
      1. PEP hit since last review → kind="pep"
      2. Fresh claim (≤30d) and stale narrative (>30d) → kind="stale_narrative"
      3. ≥3 companies above expected risk → single aggregate kind="peer_overage"
    """
    out: list[dict] = []
    now = datetime.now(tz=timezone.utc)
    stale = now - timedelta(days=30)
    fresh = now - timedelta(days=30)

    for c in companies:
        orgnr = c.get("orgnr")
        navn = c.get("navn") or orgnr or ""
        if (c.get("pep_hit_count") or 0) > 0:
            out.append(_pep_recommendation(orgnr, navn))
        if _is_stale(orgnr, claims_index, last_narrative_at, fresh, stale):
            out.append(_stale_narrative_recommendation(orgnr, navn))

    if len(peer_overage_orgnrs) >= 3:
        out.append(_peer_overage_recommendation(len(peer_overage_orgnrs)))

    return out[:5]
