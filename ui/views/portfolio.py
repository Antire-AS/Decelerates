"""Portfolio tab — named company lists with risk analysis and AI chat.

Sub-modules:
  portfolio_helpers    — shared HTTP helpers and formatting utilities
  portfolio_overview   — all-companies dashboard (risk distribution, industry breakdown)
  portfolio_company    — named portfolio: risk table, charts, benchmarks, alerts
  portfolio_ingest     — live BRREG lookup, add company, CSV import, PDF enrichment
  portfolio_chat       — AI financial analysis chat and NL-to-SQL query
  portfolio_prospecting — filter and browse all companies in the database
"""
import streamlit as st

from ui.views.portfolio_helpers import _fetch
from ui.views.portfolio_overview import _render_overview
from ui.views.portfolio_company import (
    _render_portfolio_selector,
    _render_risk_table,
    _render_charts,
    _render_benchmarks,
    _render_pdf_download,
    _render_alerts,
    _render_premium_analytics,
    _render_concentration,
    _render_comparison_charts,
)
from ui.views.portfolio_ingest import (
    _render_seed_norway,
    _render_add_company,
    _render_pdf_enrichment,
    _render_live_ingest,
)
from ui.views.portfolio_chat import _render_portfolio_chat, _render_nl_query
from ui.views.portfolio_prospecting import _render_prospecting


def render_portfolio_tab() -> None:
    overview_tab, named_tab, prospect_tab = st.tabs(["Oversikt", "Mine porteføljer", "🎯 Prospekter"])

    with overview_tab:
        companies = _fetch("/companies", params={"limit": 200})
        all_slas = _fetch("/sla")
        if not companies:
            st.info("Ingen selskaper analysert ennå. Søk opp et selskap i Selskapsøk-fanen.")
        else:
            _render_overview(companies, all_slas)

    with named_tab:
        portfolio_id = _render_portfolio_selector()
        if portfolio_id:
            p_oversikt, p_ai, p_admin = st.tabs(["Oversikt", "AI-analyse", "Administrer"])
            portfolio_name = st.session_state.get("portfolio_select_box", f"portefolje_{portfolio_id}")

            with p_oversikt:
                rows = _render_risk_table(portfolio_id)
                if rows:
                    _render_pdf_download(portfolio_id, portfolio_name)
                    _render_alerts(portfolio_id)
                    _render_charts(rows)
                    _render_benchmarks(rows)
                    _render_comparison_charts(rows)
                    _render_premium_analytics(portfolio_id)
                    _render_concentration(portfolio_id)

            with p_ai:
                rows_ai = _fetch(f"/portfolio/{portfolio_id}/risk")
                if not rows_ai:
                    st.info("Legg til selskaper i Administrer-fanen først.")
                else:
                    _render_portfolio_chat(portfolio_id)
                    st.markdown("---")
                    _render_nl_query()

            with p_admin:
                rows_admin = _fetch(f"/portfolio/{portfolio_id}/risk")
                existing_orgnrs_admin = {r["orgnr"] for r in rows_admin}
                _render_seed_norway(portfolio_id)
                _render_add_company(portfolio_id, existing_orgnrs_admin)
                if rows_admin:
                    st.markdown("---")
                    _render_pdf_enrichment(portfolio_id, rows_admin)
                st.markdown("---")
                _render_live_ingest(portfolio_id, rows_admin)

    with prospect_tab:
        _render_prospecting()
