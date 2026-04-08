"""External API helpers — backward-compatible re-export shim.

All implementations have been split by source:
  brreg_client.py     — BRREG Enhetsregisteret + Regnskapsregisteret + board members + structure
  screening_client.py — PEP/OpenSanctions + Finanstilsynet + Løsøreregisteret
  geo_stats_client.py — Kartverket + SSB benchmarks + Norges Bank

All existing imports from this module continue to work unchanged.
"""

from api.services.brreg_client import (  # noqa: F401
    _build_enhet_dict,
    _pick_latest_regnskap,
    _extract_periode,
    _extract_virksomhet,
    _extract_resultat,
    _extract_balanse,
    _extract_eiendeler,
    _deduplicate_by_year,
    _build_regnskap_row,
    fetch_enhetsregisteret,
    fetch_enhet_by_orgnr,
    fetch_regnskap_keyfigures,
    fetch_regnskap_history,
    fetch_company_struktur,
    fetch_board_members,
)

from api.services.screening_client import (  # noqa: F401
    pep_screen_name,
    fetch_finanstilsynet_licenses,
    fetch_losore,
)

from api.services.geo_stats_client import (  # noqa: F401
    _nace_to_section,
    _fetch_ssb_live,
    _SSB_CACHE,
    _NB_RATE_CACHE,
    fetch_koordinater,
    fetch_ssb_benchmark,
    fetch_norgesbank_rate,
)


class ExternalApiService:
    """Thin class wrapper around module-level external API helpers."""

    def search(self, name: str, kommunenummer=None, size: int = 20):
        return fetch_enhetsregisteret(name=name, kommunenummer=kommunenummer, size=size)

    def fetch_enhet(self, orgnr: str):
        return fetch_enhet_by_orgnr(orgnr)

    def fetch_regnskap(self, orgnr: str):
        return fetch_regnskap_keyfigures(orgnr)

    def fetch_regnskap_history(self, orgnr: str):
        return fetch_regnskap_history(orgnr)

    def pep_screen(self, name: str):
        return pep_screen_name(name)

    def fetch_licenses(self, orgnr: str):
        return fetch_finanstilsynet_licenses(orgnr)

    def fetch_koordinater(self, org: dict):
        return fetch_koordinater(org)

    def fetch_board_members(self, orgnr: str):
        return fetch_board_members(orgnr)

    def fetch_ssb_benchmark(self, nace_code: str):
        return fetch_ssb_benchmark(nace_code)
