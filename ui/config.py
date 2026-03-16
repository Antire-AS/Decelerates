"""Shared config, translations, and cached data-fetch helper."""
import json
import pathlib
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import streamlit as st

API_BASE = "http://127.0.0.1:8000"

_TRANSLATIONS = json.loads(pathlib.Path("ui/translations.json").read_text(encoding="utf-8"))


def T(key: str) -> str:
    """Return translated label for current language."""
    lang = st.session_state.get("lang", "no")
    entry = _TRANSLATIONS.get(key)
    if entry:
        return entry.get(lang, entry.get("en", key))
    return key


def fmt_mnok(value) -> str:
    if value is None:
        return "–"
    try:
        return f"{value/1_000_000:,.0f} MNOK".replace(",", " ")
    except Exception:
        return str(value)


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_company_data(orgnr: str) -> dict:
    """Fetch all company data in parallel. Cached for 5 minutes."""
    def _get(path, timeout=10):
        try:
            r = requests.get(f"{API_BASE}/{path}", timeout=timeout)
            if r.ok:
                return r.json()
        except Exception:
            pass
        return None

    tasks = {
        "prof":        (f"org/{orgnr}",             10),
        "lic":         (f"org/{orgnr}/licenses",     10),
        "roles":       (f"org/{orgnr}/roles",        10),
        "history":     (f"org/{orgnr}/history",      10),
        "konkurs":     (f"org/{orgnr}/bankruptcy",   10),
        "struktur":    (f"org/{orgnr}/struktur",      8),
        "koordinater": (f"org/{orgnr}/koordinater",  10),
        "benchmark":   (f"org/{orgnr}/benchmark",    10),
    }

    results = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_key = {
            executor.submit(_get, path, timeout): key
            for key, (path, timeout) in tasks.items()
        }
        for future in as_completed(future_to_key):
            results[future_to_key[future]] = future.result()

    return results
