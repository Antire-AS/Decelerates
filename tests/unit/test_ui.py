"""Basic smoke tests for UI modules — no running server required.

Streamlit is stubbed in conftest.py so these tests run without a Streamlit
runtime and without importing google.protobuf.
"""
import importlib
import json
import os
import pathlib
from unittest.mock import patch


# ── Helper ────────────────────────────────────────────────────────────────────

def _reload_config():
    """Return a freshly imported ui.config (forces module-level code to rerun)."""
    import ui.config as cfg
    importlib.reload(cfg)
    return cfg


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_config_api_base_reads_env():
    """API_BASE should read from API_BASE_URL env var."""
    with patch.dict(os.environ, {"API_BASE_URL": "http://test-host:9000"}):
        cfg = _reload_config()
        assert cfg.API_BASE == "http://test-host:9000"
    # Restore
    _reload_config()


def test_config_api_base_default():
    """API_BASE should default to localhost:8000 when env var is absent."""
    env_clean = {k: v for k, v in os.environ.items() if k != "API_BASE_URL"}
    with patch.dict(os.environ, env_clean, clear=True):
        cfg = _reload_config()
        assert cfg.API_BASE == "http://127.0.0.1:8000"
    _reload_config()


def test_translations_load():
    """translations.json must be loadable and have Norwegian keys."""
    raw = pathlib.Path("ui/translations.json").read_text(encoding="utf-8")
    translations = json.loads(raw)
    assert isinstance(translations, dict)
    assert len(translations) > 0
    # Every entry should be a dict with at least a 'no' or 'en' key
    for key, value in list(translations.items())[:5]:
        assert isinstance(value, dict), f"Translation entry for {key!r} is not a dict"
        assert "no" in value or "en" in value, (
            f"Translation entry for {key!r} has neither 'no' nor 'en' key"
        )


def test_fmt_mnok():
    """fmt_mnok should format numbers correctly."""
    from ui.config import fmt_mnok
    assert fmt_mnok(None) == "–"
    assert fmt_mnok(1_000_000) == "1 MNOK"
    assert fmt_mnok(5_500_000) == "6 MNOK"
    assert fmt_mnok(0) == "0 MNOK"


def test_T_function_fallback():
    """T() should return the key if translation is missing."""
    import streamlit as st
    st.session_state = {"lang": "no"}
    from ui.config import T
    result = T("__nonexistent_key_xyz__")
    assert result == "__nonexistent_key_xyz__"


def test_T_function_returns_norwegian():
    """T() should return the Norwegian translation when lang=no."""
    import streamlit as st
    st.session_state = {"lang": "no"}
    from ui.config import T
    # Load translations directly to find a testable key
    raw = pathlib.Path("ui/translations.json").read_text(encoding="utf-8")
    translations = json.loads(raw)
    key, entry = next((k, v) for k, v in translations.items() if "no" in v)
    assert T(key) == entry["no"]


def test_T_function_returns_english():
    """T() should return the English translation when lang=en."""
    import streamlit as st
    st.session_state = {"lang": "en"}
    from ui.config import T
    raw = pathlib.Path("ui/translations.json").read_text(encoding="utf-8")
    translations = json.loads(raw)
    key, entry = next((k, v) for k, v in translations.items() if "en" in v)
    assert T(key) == entry["en"]


def test_ui_view_modules_importable():
    """All UI view modules must be importable without a running server."""
    view_modules = [
        "ui.views.search",
        "ui.views.profile_core",
        "ui.views.profile_financials",
        "ui.views.portfolio",
        "ui.views.documents",
        "ui.views.sla",
        "ui.views.knowledge",
    ]
    for module_name in view_modules:
        mod = importlib.import_module(module_name)
        assert mod is not None, f"Could not import {module_name}"


def test_ui_view_render_functions_exist():
    """Each UI view module must expose its expected render_* function."""
    expected = {
        "ui.views.search": "render_search_tab",
        "ui.views.profile_core": "render_profile_core",
        "ui.views.profile_financials": "render_profile_financials",
        "ui.views.portfolio": "render_portfolio_tab",
        "ui.views.documents": "render_documents_tab",
        "ui.views.sla": "render_sla_tab",
        "ui.views.knowledge": "render_knowledge_tab",
    }
    for module_name, fn_name in expected.items():
        mod = importlib.import_module(module_name)
        assert hasattr(mod, fn_name), (
            f"{module_name} is missing expected function {fn_name!r}"
        )
        assert callable(getattr(mod, fn_name)), (
            f"{module_name}.{fn_name} is not callable"
        )
