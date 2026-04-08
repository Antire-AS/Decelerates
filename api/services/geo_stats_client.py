"""Kartverket geocoding, SSB industry benchmarks, and Norges Bank exchange rates."""
import logging
import threading
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import requests

from api.constants import KARTVERKET_ADRESSE_URL, NACE_BENCHMARKS, _NACE_SECTION_MAP

_log = logging.getLogger(__name__)


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
    except Exception as exc:
        _log.warning("fetch_koordinater failed: %s", exc)
        return None


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
_SSB_CACHE_LOCK = threading.Lock()
_SSB_TTL = 86400  # 24 h


def _fetch_ssb_live(section: str) -> Optional[Dict[str, Any]]:
    """Try to fetch live equity ratio + profit margin from SSB PxWebAPI."""
    now = datetime.now(timezone.utc).timestamp()
    with _SSB_CACHE_LOCK:
        cached = _SSB_CACHE.get(section)
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
                with _SSB_CACHE_LOCK:
                    _SSB_CACHE[section] = {"data": result, "ts": now}
                return result
        except Exception as exc:
            _log.warning("_fetch_ssb_live(%s, table=%s) failed: %s", section, table_id, exc)
            continue

    with _SSB_CACHE_LOCK:
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
_NB_RATE_CACHE_LOCK = threading.Lock()
_NB_TTL = 3600  # 1 h


def fetch_norgesbank_rate(currency: str) -> float:
    """Return current NOK rate for 1 unit of currency (Norges Bank open API)."""
    if not currency or currency.upper() == "NOK":
        return 1.0
    ccy = currency.upper()
    now = datetime.now(timezone.utc).timestamp()
    with _NB_RATE_CACHE_LOCK:
        cached = _NB_RATE_CACHE.get(ccy)
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
            with _NB_RATE_CACHE_LOCK:
                _NB_RATE_CACHE[ccy] = {"rate": rate, "ts": now}
            return rate
    except Exception as exc:
        _log.warning("fetch_norgesbank_rate(%s) failed: %s", ccy, exc)
    return 1.0
