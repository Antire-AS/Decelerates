"""Portfolio prospecting — filter and browse all companies in the database."""
import pandas as pd
import streamlit as st

from ui.views.portfolio_helpers import _fetch, _fmt_mnok, _risk_badge

_NACE_SECTIONS = {
    "A": "Jordbruk/skogbruk/fiske", "B": "Bergverksdrift", "C": "Industri",
    "D": "Kraft/gass", "E": "Vann/avfall", "F": "Bygg og anlegg",
    "G": "Handel", "H": "Transport/lagring", "I": "Overnatting/servering",
    "J": "Informasjon/kommunikasjon", "K": "Finans/forsikring",
    "L": "Eiendom", "M": "Faglig/vitenskapelig", "N": "Forretningsmessig",
    "O": "Offentlig forvaltning", "P": "Undervisning",
    "Q": "Helse/sosialtjenester", "R": "Kultur/underholdning", "S": "Andre tjenester",
}


def _render_prospecting() -> None:
    st.caption("Finn nye kunder blant alle selskaper i databasen.")
    with st.expander("🔽 Filtre", expanded=True):
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            section_opts = ["(alle)"] + [f"{k} — {v}" for k, v in _NACE_SECTIONS.items()]
            selected_section = st.selectbox("Bransje (NACE-seksjon)", section_opts, key="prosp_section")
            nace_section = selected_section.split(" —")[0] if selected_section != "(alle)" else None
        with col_f2:
            rev_min, rev_max = st.slider("Omsetning (MNOK)", 0, 2000, (0, 2000), step=10, key="prosp_rev")
        with col_f3:
            risk_min, risk_max = st.slider("Risikoscore", 0, 20, (0, 20), key="prosp_risk")
        sort_opts = {"Omsetning (høyest)": "revenue", "Risikoscore (høyest)": "risk_score", "Navn (A–Å)": "navn"}
        sort_label = st.selectbox("Sorter etter", list(sort_opts.keys()), key="prosp_sort")

    params: dict = {
        "limit": 300,
        "sort_by": sort_opts[sort_label],
        "min_risk": risk_min,
        "max_risk": risk_max,
    }
    if nace_section:
        params["nace_section"] = nace_section
    if rev_min > 0:
        params["min_revenue"] = rev_min * 1_000_000
    if rev_max < 2000:
        params["max_revenue"] = rev_max * 1_000_000

    companies = _fetch("/companies", params=params)
    st.caption(f"**{len(companies)} selskaper** matcher filtrene.")
    if not companies:
        st.info("Ingen selskaper funnet med valgte filtre.")
        return

    rows = [
        {
            "Orgnr": c["orgnr"],
            "Selskap": c["navn"],
            "Bransje": (c.get("naeringskode1_beskrivelse") or "")[:40],
            "Omsetning": _fmt_mnok(c.get("omsetning")),
            "Risiko": _risk_badge(c.get("risk_score")),
            "Kommune": c.get("kommune") or "–",
        }
        for c in companies
    ]
    df = pd.DataFrame(rows)
    selected = st.dataframe(
        df, width="stretch", hide_index=True,
        on_select="rerun", selection_mode="single-row",
    )
    sel_rows = (selected.get("selection") or {}).get("rows", [])
    if sel_rows:
        chosen = companies[sel_rows[0]]
        st.session_state["selected_orgnr"] = chosen["orgnr"]
        st.session_state["_goto_tab"] = "search"
        st.rerun()
