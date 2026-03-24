"""Render renewal pipeline tab — upcoming policy renewals across all companies."""
import io
from datetime import date

import pandas as pd
import requests
import streamlit as st

from ui.config import API_BASE, get_auth_headers

_STAGES = ["not_started", "ready_to_quote", "quoted", "accepted", "declined"]

_STAGE_LABELS = {
    "not_started":    "Ikke startet",
    "ready_to_quote": "Klar for tilbud",
    "quoted":         "Tilbud sendt",
    "accepted":       "Akseptert",
    "declined":       "Avslått",
}

_STAGE_COLORS = {
    "not_started":    "#888888",
    "ready_to_quote": "#e67e22",
    "quoted":         "#2980b9",
    "accepted":       "#27ae60",
    "declined":       "#c0392b",
}


def _stage_badge(stage: str) -> str:
    label = _STAGE_LABELS.get(stage, stage)
    color = _STAGE_COLORS.get(stage, "#888")
    return (
        f"<span style='background:{color};color:#fff;padding:2px 10px;"
        f"border-radius:12px;font-size:12px;font-weight:600'>{label}</span>"
    )


def _advance_stage(policy_id: int, new_stage: str, notify_email: str | None = None) -> bool:
    payload: dict = {"stage": new_stage}
    if notify_email:
        payload["notify_email"] = notify_email
    try:
        resp = requests.post(
            f"{API_BASE}/policies/{policy_id}/renewal/advance",
            json=payload,
            headers=get_auth_headers(),
            timeout=10,
        )
        return resp.ok
    except Exception:
        return False


def render_renewals_tab() -> None:
    st.subheader("Fornyelsespipeline")
    st.caption("Oversikt over forsikringsavtaler som forfaller innen valgt tidsperiode.")

    col_days, col_stage = st.columns([3, 2])
    days = col_days.slider("Vis fornyelser innen (dager)", 7, 365, 90, key="renewal_days_slider")
    filter_stage = col_stage.selectbox(
        "Filtrer på steg",
        ["Alle"] + [_STAGE_LABELS[s] for s in _STAGES],
        key="renewal_stage_filter",
    )

    try:
        resp = requests.get(
            f"{API_BASE}/renewals",
            params={"days": days},
            headers=get_auth_headers(),
            timeout=10,
        )
        renewals = resp.json() if resp.ok else []
    except Exception:
        renewals = []
        st.warning("Kunne ikke hente fornyelsesdata fra API.")

    if filter_stage != "Alle":
        target = next(k for k, v in _STAGE_LABELS.items() if v == filter_stage)
        renewals = [r for r in renewals if r.get("renewal_stage", "not_started") == target]

    if not renewals:
        st.info(f"Ingen aktive avtaler forfaller innen {days} dager.")
        return

    # ── Summary metrics ────────────────────────────────────────────────────────
    total_premium = sum(r.get("annual_premium_nok") or 0 for r in renewals)
    stage_counts = {}
    for r in renewals:
        s = r.get("renewal_stage", "not_started")
        stage_counts[s] = stage_counts.get(s, 0) + 1

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Totalt", len(renewals))
    m2.metric("Ikke startet",    stage_counts.get("not_started", 0))
    m3.metric("Klar for tilbud", stage_counts.get("ready_to_quote", 0))
    m4.metric("Tilbud sendt",    stage_counts.get("quoted", 0))
    m5.metric("Akseptert",       stage_counts.get("accepted", 0))

    st.markdown("---")

    # ── Pipeline cards ─────────────────────────────────────────────────────────
    view_mode = st.radio("Visning", ["Tabell", "Pipeline-kort"], horizontal=True, key="renewal_view_mode")

    if view_mode == "Pipeline-kort":
        for r in sorted(renewals, key=lambda x: x.get("days_to_renewal", 999)):
            days_left = r.get("days_to_renewal", 0)
            days_color = "#c0392b" if days_left <= 30 else "#e67e22" if days_left <= 60 else "#27ae60"
            stage = r.get("renewal_stage", "not_started")

            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 2])
                with c1:
                    st.markdown(
                        f"**{r.get('insurer', '')}** · {r.get('product_type', '')}"
                    )
                    st.caption(f"Orgnr: {r.get('orgnr', '')} · Avtalenr: {r.get('policy_number') or '–'}")
                    if r.get("annual_premium_nok"):
                        st.caption(f"Premie: kr {r['annual_premium_nok']:,.0f}")
                with c2:
                    st.markdown(
                        f"<span style='color:{days_color};font-weight:700;font-size:22px'>{days_left}</span>"
                        f" <span style='color:#888;font-size:13px'>dager · {r.get('renewal_date', '')}</span>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(_stage_badge(stage), unsafe_allow_html=True)
                with c3:
                    next_stages = [s for s in _STAGES if s != stage]
                    chosen = st.selectbox(
                        "Flytt til",
                        ["–"] + [_STAGE_LABELS[s] for s in next_stages],
                        key=f"stage_select_{r['id']}",
                        label_visibility="collapsed",
                    )
                    notify = st.text_input(
                        "E-post for varsling (valgfri)",
                        key=f"notify_{r['id']}",
                        placeholder="kontakt@selskap.no",
                        label_visibility="collapsed",
                    )
                    if chosen != "–" and st.button("Oppdater", key=f"advance_{r['id']}", type="primary"):
                        target_stage = next(k for k, v in _STAGE_LABELS.items() if v == chosen)
                        ok = _advance_stage(r["id"], target_stage, notify_email=notify or None)
                        if ok:
                            st.success(f"Oppdatert til «{chosen}»")
                            st.rerun()
                        else:
                            st.error("Kunne ikke oppdatere steg.")
    else:
        # ── Flat table view ────────────────────────────────────────────────────
        rows = []
        for r in renewals:
            rows.append({
                "Dager igjen":       r.get("days_to_renewal", 0),
                "Orgnr":             r.get("orgnr", ""),
                "Forsikringsselskap": r.get("insurer", ""),
                "Produkt":           r.get("product_type", ""),
                "Premie (kr)":       r.get("annual_premium_nok"),
                "Fornyelsesdato":    r.get("renewal_date", ""),
                "Steg":              _STAGE_LABELS.get(r.get("renewal_stage", "not_started"), "–"),
                "Status":            r.get("status", ""),
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

        st.dataframe(styled, width="stretch", hide_index=True)
        st.caption(
            f"Totalt {len(renewals)} avtaler · "
            f"Samlet premie: kr {total_premium:,.0f}"
        )

    buf = io.BytesIO()
    export_rows = [
        {
            "Dager igjen":       r.get("days_to_renewal", 0),
            "Orgnr":             r.get("orgnr", ""),
            "Forsikringsselskap": r.get("insurer", ""),
            "Produkt":           r.get("product_type", ""),
            "Premie (kr)":       r.get("annual_premium_nok"),
            "Fornyelsesdato":    r.get("renewal_date", ""),
            "Steg":              _STAGE_LABELS.get(r.get("renewal_stage", "not_started"), "–"),
        }
        for r in renewals
    ]
    pd.DataFrame(export_rows).to_excel(buf, index=False, sheet_name="Fornyelser")
    st.download_button(
        label="Last ned Excel",
        data=buf.getvalue(),
        file_name=f"fornyelser_{date.today().isoformat()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
