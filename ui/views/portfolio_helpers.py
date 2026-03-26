"""Shared helpers for portfolio view modules."""
import requests
import streamlit as st  # noqa: F401 — imported here so sub-modules can re-use session_state pattern

from ui.config import API_BASE


def _risk_badge(score) -> str:
    if score is None:
        return "–"
    if score <= 3:
        return "🟢 Lav"
    if score <= 7:
        return "🟡 Moderat"
    if score <= 11:
        return "🔴 Høy"
    return "🚨 Svært høy"


def _fmt_mnok(val) -> str:
    if val is None:
        return "–"
    return f"{round(val / 1_000_000, 1)} MNOK"


def _fetch(path: str, params: dict | None = None):
    try:
        r = requests.get(f"{API_BASE}{path}", params=params, timeout=10)
        return r.json() if r.ok else []
    except Exception:
        return []


def _post(path: str, json: dict) -> dict | None:
    try:
        r = requests.post(f"{API_BASE}{path}", json=json, timeout=30)
        return r.json() if r.ok else None
    except Exception:
        return None


def _delete(path: str) -> bool:
    try:
        r = requests.delete(f"{API_BASE}{path}", timeout=30)
        return r.ok
    except Exception:
        return False
