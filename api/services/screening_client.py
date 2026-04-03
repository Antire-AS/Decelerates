"""PEP / sanctions screening, Finanstilsynet licences, and Løsøreregisteret."""
import logging
from typing import Optional, List, Dict, Any

import requests

from api.constants import FINANSTILSYNET_REGISTRY_URL, OPENSANCTIONS_SEARCH_URL

_log = logging.getLogger(__name__)


# ── PEP / Sanctions ───────────────────────────────────────────────────────────

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


# ── Finanstilsynet ────────────────────────────────────────────────────────────

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


# ── Løsøreregisteret ─────────────────────────────────────────────────────────

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
        _log.warning("fetch_losore(%s) failed: %s", orgnr, exc)
        return {"error": str(exc), "count": None, "pledges": []}
