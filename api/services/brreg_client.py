"""BRREG Enhetsregisteret + Regnskapsregisteret + board members + corporate structure."""
import logging
from typing import Optional, List, Dict, Any

import requests

from api.constants import BRREG_ENHETER_URL

_log = logging.getLogger(__name__)


# ── BRREG Enhetsregisteret ────────────────────────────────────────────────────

def _build_enhet_dict(e: dict) -> dict:
    """Extract the common fields shared by both enhet list and detail responses."""
    addr = e.get("forretningsadresse") or {}
    orgform = e.get("organisasjonsform") or {}
    naeringskode1 = e.get("naeringskode1") or {}
    return {
        "orgnr": e.get("organisasjonsnummer"),
        "navn": e.get("navn"),
        "organisasjonsform": orgform.get("beskrivelse"),
        "organisasjonsform_kode": orgform.get("kode"),
        "kommune": addr.get("kommune"),
        "postnummer": addr.get("postnummer"),
        "land": addr.get("land"),
        "naeringskode1": naeringskode1.get("kode"),
        "naeringskode1_beskrivelse": naeringskode1.get("beskrivelse"),
        "_addr": addr,  # kept private for fetch_enhet_by_orgnr to read extra fields
    }


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
        row = _build_enhet_dict(e)
        row.pop("_addr", None)
        results.append(row)

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
    row = _build_enhet_dict(e)
    addr = row.pop("_addr")
    return {
        **row,
        "kommunenummer": addr.get("kommunenummer"),
        "poststed": addr.get("poststed"),
        "adresse": addr.get("adresse") or [],
        "stiftelsesdato": e.get("stiftelsesdato"),
        "hjemmeside": e.get("hjemmeside"),
        "konkurs": e.get("konkurs", False),
        "under_konkursbehandling": e.get("underKonkursbehandling", False),
        "under_avvikling": e.get("underAvvikling", False),
    }


# ── BRREG Regnskapsregisteret ─────────────────────────────────────────────────

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


def _deduplicate_by_year(regnskaper: list) -> Dict[int, Dict[str, Any]]:
    """Deduplicate regnskaper list to one entry per year, preferring SELSKAP type."""
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
        if by_year.get(year) is None or r.get("regnskapstype") == "SELSKAP":
            by_year[year] = r
    return by_year


def _build_regnskap_row(year: int, r: Dict[str, Any]) -> Dict[str, Any]:
    """Build a flat history dict from a single regnskap entry."""
    res = _extract_resultat(r)
    bal = _extract_balanse(r)
    eid = _extract_eiendeler(r)
    vir = _extract_virksomhet(r)
    equity = bal.get("sum_egenkapital")
    assets = eid.get("sum_eiendeler")
    return {
        "year": year,
        "revenue": res.get("sum_driftsinntekter"),
        "net_result": res.get("aarsresultat"),
        "equity": equity,
        "total_assets": assets,
        "equity_ratio": (equity / assets) if (equity is not None and assets) else None,
        "short_term_debt": bal.get("sum_kortsiktig_gjeld"),
        "long_term_debt": bal.get("sum_langsiktig_gjeld"),
        "antall_ansatte": vir.get("antall_ansatte"),
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


def fetch_regnskap_history(orgnr: str) -> List[Dict[str, Any]]:
    url = f"https://data.brreg.no/regnskapsregisteret/regnskap/{orgnr}"
    resp = requests.get(url, timeout=10)
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    data = resp.json()
    regnskaper = data if isinstance(data, list) else [data]
    by_year = _deduplicate_by_year(regnskaper)
    return [_build_regnskap_row(year, r) for year, r in sorted(by_year.items())]


# ── BRREG corporate structure ─────────────────────────────────────────────────

def fetch_company_struktur(orgnr: str) -> Dict[str, Any]:
    """Fetch parent company and sub-units from BRREG open API."""
    result: Dict[str, Any] = {"parent": None, "sub_units": [], "total_sub_units": 0}

    try:
        resp = requests.get(f"{BRREG_ENHETER_URL}/{orgnr}", timeout=8)
        if resp.ok:
            e = resp.json()
            parent_orgnr = e.get("overordnetEnhet")
            if parent_orgnr:
                p_resp = requests.get(f"{BRREG_ENHETER_URL}/{parent_orgnr}", timeout=8)
                if p_resp.ok:
                    p = p_resp.json()
                    result["parent"] = {
                        "orgnr": p.get("organisasjonsnummer"),
                        "navn":  p.get("navn"),
                        "organisasjonsform": (p.get("organisasjonsform") or {}).get("beskrivelse"),
                        "kommune": (p.get("forretningsadresse") or {}).get("kommune"),
                    }
    except Exception as exc:
        _log.warning("fetch_company_struktur(%s) parent lookup failed: %s", orgnr, exc)

    try:
        resp = requests.get(f"{BRREG_ENHETER_URL}/{orgnr}/underenheter", timeout=8)
        if resp.ok:
            data = resp.json()
            units = (data.get("_embedded") or {}).get("underenheter", [])
            result["total_sub_units"] = (data.get("page") or {}).get("totalElements", len(units))
            result["sub_units"] = [
                {
                    "orgnr":         u.get("organisasjonsnummer"),
                    "navn":          u.get("navn"),
                    "kommune":       (u.get("beliggenhetsadresse") or {}).get("kommune"),
                    "antall_ansatte": u.get("antallAnsatte"),
                }
                for u in units[:25]
            ]
    except Exception as exc:
        _log.warning("fetch_company_struktur(%s) sub-units lookup failed: %s", orgnr, exc)

    return result


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
