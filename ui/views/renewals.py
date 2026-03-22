"""Render renewal pipeline tab — upcoming policy renewals across all companies."""
from datetime import date

import pandas as pd
import requests
import streamlit as st

from ui.config import API_BASE


def render_renewals_tab() -> None:
    st.subheader("🔔 Fornyelsespipeline")
    st.caption("Oversikt over forsikringsavtaler som forfaller innen valgt tidsperiode.")

    days = st.slider("Vis fornyelser innen (dager)", 7, 365, 90, key="renewal_days_slider")

    try:
        resp = requests.get(f"{API_BASE}/renewals", params={"days": days}, timeout=10)
        renewals = resp.json() if resp.ok else []
    except Exception:
        renewals = []
        st.warning("Kunne ikke hente fornyelsesdata fra API.")

    if not renewals:
        st.info(f"Ingen aktive avtaler forfaller innen {days} dager.")
        return

    today = date.today()
    rows = []
    for r in renewals:
        d = r.get("days_to_renewal", 0)
        rows.append({
            "Dager igjen": d,
            "Orgnr": r.get("orgnr", ""),
            "Forsikringsselskap": r.get("insurer", ""),
            "Produkt": r.get("product_type", ""),
            "Premie (kr)": r.get("annual_premium_nok"),
            "Fornyelsesdato": r.get("renewal_date", ""),
            "Status": r.get("status", ""),
        })

    df = pd.DataFrame(rows).sort_values("Dager igjen")

    def _color_days(val):
        if val <= 30:
            return "color: #c0392b; font-weight: bold"
        if val <= 60:
            return "color: #e67e22; font-weight: bold"
        return "color: #27ae60"

    styled = (
        df.style
        .applymap(_color_days, subset=["Dager igjen"])
        .format({"Premie (kr)": lambda v: f"kr {v:,.0f}" if v else "–"})
    )

    st.dataframe(styled, use_container_width=True, hide_index=True)
    st.caption(f"Totalt {len(renewals)} avtaler · "
               f"Samlet premie: kr {sum(r.get('annual_premium_nok') or 0 for r in renewals):,.0f}")
