"""External API helpers — BRREG, SSB, Norges Bank, Kartverket, OpenSanctions, Finanstilsynet."""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import requests

from api.constants import (
    BRREG_ENHETER_URL, FINANSTILSYNET_REGISTRY_URL, OPENSANCTIONS_SEARCH_URL,
    KARTVERKET_ADRESSE_URL, NACE_BENCHMARKS, _NACE_SECTION_MAP,
)


# ── BRREG Enhetsregisteret ────────────────────────────────────────────────────

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


# ── PEP / Sanctions ──────────────────────────────────────────────────────────

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


# ── Kartverket ────────────────────────────────────────────────────────────────

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
        return {"error": str(exc), "count": None, "pledges": []}


# ── SSB industry benchmarks ───────────────────────────────────────────────────

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


_SSB_CACHE: Dict[str, Any] = {}
_SSB_TTL = 86400  # 24 h


def _fetch_ssb_live(section: str) -> Optional[Dict[str, Any]]:
    """Try to fetch live equity ratio + profit margin from SSB PxWebAPI."""
    cached = _SSB_CACHE.get(section)
    now = datetime.now(timezone.utc).timestamp()
    if cached and now - cached["ts"] < _SSB_TTL:
        return cached["data"]

    for table_id in ["12813", "12814"]:
        try:
            payload = {
                "query": [
                    {"code": "Næring",        "selection": {"filter": "item", "values": [section]}},
                    {"code": "ContentsCode",  "selection": {"filter": "item", "values": ["Egenkapitalprosent", "Driftsmargin"]}},
                    {"code": "Tid",           "selection": {"filter": "top",  "values": ["1"]}},
                ],
                "response": {"format": "json-stat2"},
            }
            resp = requests.post(
                f"https://data.ssb.no/api/v0/no/table/{table_id}",
                json=payload, timeout=8,
            )
            if not resp.ok:
                continue
            data = resp.json()
            values = data.get("value") or []
            if len(values) >= 2 and values[0] is not None and values[1] is not None:
                tid_labels = list(
                    ((data.get("dimension") or {}).get("Tid", {}).get("category", {}).get("label") or {}).values()
                )
                year = tid_labels[-1] if tid_labels else "?"
                result: Dict[str, Any] = {
                    "eq_ratio": float(values[0]) / 100,
                    "margin":   float(values[1]) / 100,
                    "year":     year,
                    "table":    table_id,
                }
                _SSB_CACHE[section] = {"data": result, "ts": now}
                return result
        except Exception:
            continue

    _SSB_CACHE[section] = {"data": None, "ts": now}
    return None


def fetch_ssb_benchmark(nace_code: str) -> Optional[Dict[str, Any]]:
    section = _nace_to_section(nace_code)
    if not section:
        return None
    bench = NACE_BENCHMARKS.get(section)
    if not bench:
        return None

    result: Dict[str, Any] = {
        "section": section,
        "industry": bench["industry"],
        "typical_equity_ratio_min": bench["eq_ratio_min"],
        "typical_equity_ratio_max": bench["eq_ratio_max"],
        "typical_profit_margin_min": bench["margin_min"],
        "typical_profit_margin_max": bench["margin_max"],
        "source": "SSB / NACE industry averages",
        "live": False,
    }

    live = _fetch_ssb_live(section)
    if live:
        half_eq = (bench["eq_ratio_max"] - bench["eq_ratio_min"]) / 2
        half_mg = (bench["margin_max"] - bench["margin_min"]) / 2
        result["typical_equity_ratio_min"] = max(0.0, live["eq_ratio"] - half_eq)
        result["typical_equity_ratio_max"] = live["eq_ratio"] + half_eq
        result["typical_profit_margin_min"] = max(-0.5, live["margin"] - half_mg)
        result["typical_profit_margin_max"] = live["margin"] + half_mg
        result["source"] = f"SSB live ({live['year']}, tabell {live['table']})"
        result["live"] = True

    return result


# ── Norges Bank exchange rate ─────────────────────────────────────────────────

_NB_RATE_CACHE: Dict[str, Any] = {}
_NB_TTL = 3600  # 1 h


def fetch_norgesbank_rate(currency: str) -> float:
    """Return current NOK rate for 1 unit of currency (Norges Bank open API)."""
    if not currency or currency.upper() == "NOK":
        return 1.0
    ccy = currency.upper()
    cached = _NB_RATE_CACHE.get(ccy)
    now = datetime.now(timezone.utc).timestamp()
    if cached and now - cached["ts"] < _NB_TTL:
        return cached["rate"]
    try:
        resp = requests.get(
            f"https://data.norges-bank.no/api/data/EXR/B.{ccy}.NOK.SP",
            params={"format": "sdmx-json", "lastNObservations": 1},
            timeout=8,
        )
        if resp.ok:
            sets = resp.json()["data"]["dataSets"][0]["series"]
            series = next(iter(sets.values()))
            obs = series["observations"]
            rate = float(obs[max(obs.keys(), key=int)][0])
            _NB_RATE_CACHE[ccy] = {"rate": rate, "ts": now}
            return rate
    except Exception:
        pass
    return 1.0


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
    except Exception:
        pass

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
    except Exception:
        pass

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


# ── Service class wrapper ──────────────────────────────────────────────────────

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
