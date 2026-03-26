"""Named-portfolio company table, charts, benchmarks, alerts, and concentration."""
import pandas as pd
import requests
import streamlit as st

from ui.config import API_BASE
from ui.views.portfolio_helpers import _delete, _fetch, _fmt_mnok, _post, _risk_badge

_EK_THRESHOLD = 0.20  # 20% — generally considered minimum healthy equity ratio
_SEVERITY_ICON = {"Kritisk": "🚨", "Høy": "🔴", "Moderat": "🟡"}


def _render_portfolio_selector() -> int | None:
    portfolios = _fetch("/portfolio")

    col_sel, col_new = st.columns([3, 1])
    with col_new:
        if st.button("+ Ny portefølje", width="stretch"):
            st.session_state["show_new_portfolio_form"] = True

    if st.session_state.get("show_new_portfolio_form"):
        with st.form("new_portfolio_form", clear_on_submit=True):
            pname = st.text_input("Navn", placeholder="f.eks. Bygg & Anlegg Q1")
            pdesc = st.text_area("Beskrivelse (valgfri)", height=60)
            if st.form_submit_button("Opprett"):
                if pname.strip():
                    result = _post("/portfolio", {"name": pname.strip(), "description": pdesc.strip()})
                    if result:
                        st.session_state["show_new_portfolio_form"] = False
                        st.session_state["selected_portfolio_id"] = result["id"]
                        st.rerun()
                else:
                    st.warning("Navn er påkrevd.")

    if not portfolios:
        with col_sel:
            st.info("Ingen porteføljer ennå. Klikk '+ Ny portefølje' for å komme i gang.")
        return None

    options = {p["name"]: p["id"] for p in portfolios}
    current_id = st.session_state.get("selected_portfolio_id")
    current_name = next((p["name"] for p in portfolios if p["id"] == current_id), list(options.keys())[0])

    with col_sel:
        selected_name = st.selectbox(
            "Velg portefølje", list(options.keys()),
            index=list(options.keys()).index(current_name),
            key="portfolio_select_box",
        )

    selected_id = options[selected_name]
    st.session_state["selected_portfolio_id"] = selected_id

    selected_meta = next((p for p in portfolios if p["id"] == selected_id), None)
    if selected_meta and selected_meta.get("description"):
        st.caption(selected_meta["description"])

    return selected_id


def _render_risk_table(portfolio_id: int) -> list:
    rows = _fetch(f"/portfolio/{portfolio_id}/risk")
    if not rows:
        st.info("Ingen selskaper i porteføljen ennå. Legg til selskaper nedenfor.")
        return []

    scores = [r["risk_score"] for r in rows if r.get("risk_score") is not None]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Selskaper", len(rows))
    m2.metric("Gj.snitt risiko", round(sum(scores) / len(scores), 1) if scores else "–")
    m3.metric("Høy risiko (≥8)", sum(1 for s in scores if s >= 8))
    m4.metric("Ingen data", sum(1 for r in rows if r.get("risk_score") is None))

    df = pd.DataFrame(rows)
    df_display = pd.DataFrame({
        "Risikonivå": df["risk_score"].apply(_risk_badge),
        "Selskap": df["navn"],
        "Orgnr": df["orgnr"],
        "Bransje": df.get("naeringskode", pd.Series(["–"] * len(df))).fillna("–"),
        "Omsetning": df["revenue"].apply(_fmt_mnok) if "revenue" in df.columns else pd.Series(["–"] * len(df)),
        "EK-andel %": (df["equity_ratio"].apply(lambda x: f"{round(x * 100, 1)}" if x else "–")
                       if "equity_ratio" in df.columns else pd.Series(["–"] * len(df))),
        "År": df.get("regnskapsår", pd.Series(["–"] * len(df))).fillna("–").astype(str),
        "Score": df["risk_score"].fillna(0).astype(int),
    })
    st.dataframe(df_display.sort_values("Score", ascending=False), width="stretch", hide_index=True)

    with st.expander("Fjern selskaper", expanded=False):
        for r in rows:
            col_name, col_btn = st.columns([5, 1])
            col_name.write(f"{r['navn']} ({r['orgnr']})")
            if col_btn.button("Fjern", key=f"rm_{portfolio_id}_{r['orgnr']}"):
                _delete(f"/portfolio/{portfolio_id}/companies/{r['orgnr']}")
                st.rerun()

    return rows


def _render_charts(rows: list) -> None:
    df = pd.DataFrame(rows)
    col_left, col_right = st.columns(2)
    with col_left:
        if "risk_score" in df.columns and df["risk_score"].notna().any():
            st.markdown("#### Risikoscore")
            st.bar_chart(
                df[df["risk_score"].notna()].set_index("navn")[["risk_score"]]
                .rename(columns={"risk_score": "Score"})
                .sort_values("Score", ascending=False)
            )
    with col_right:
        if "revenue" in df.columns and df["revenue"].notna().any():
            st.markdown("#### Omsetning (MNOK)")
            rev = df[df["revenue"].notna()].copy()
            rev["MNOK"] = (rev["revenue"] / 1_000_000).round(1)
            st.bar_chart(rev.set_index("navn")[["MNOK"]].sort_values("MNOK", ascending=False))


def _render_benchmarks(rows: list) -> None:
    df = pd.DataFrame(rows)
    if "equity_ratio" not in df.columns or df["equity_ratio"].isna().all():
        return

    ek = df[df["equity_ratio"].notna()].copy()
    if ek.empty:
        return

    ek["EK-andel %"] = (ek["equity_ratio"] * 100).round(1)
    avg_ek = ek["equity_ratio"].mean()
    below_threshold = (ek["equity_ratio"] < _EK_THRESHOLD).sum()

    st.markdown("#### Egenkapitalbenchmark")
    b1, b2, b3 = st.columns(3)
    b1.metric("Porteføljesnitt EK-andel", f"{avg_ek * 100:.1f}%")
    b2.metric("Under 20%-grensen", int(below_threshold))
    b3.metric("Selskapr med data", len(ek))

    chart_df = ek[["navn", "EK-andel %"]].sort_values("EK-andel %", ascending=True).set_index("navn")
    st.bar_chart(chart_df, height=280)

    def _ek_flag(v):
        if v < 10:
            return f"🔴 {v:.1f}%"
        if v < 20:
            return f"🟡 {v:.1f}%"
        return f"🟢 {v:.1f}%"

    tbl = ek[["navn", "orgnr", "EK-andel %", "revenue", "risk_score"]].copy()
    tbl["EK-status"] = tbl["EK-andel %"].apply(_ek_flag)
    tbl["Omsetning"] = tbl["revenue"].apply(_fmt_mnok)
    tbl["Risikoscore"] = tbl["risk_score"].fillna("–").astype(str)
    st.dataframe(
        tbl.sort_values("EK-andel %")[["navn", "orgnr", "EK-status", "Omsetning", "Risikoscore"]]
        .rename(columns={"navn": "Selskap", "orgnr": "Orgnr"}),
        width="stretch",
        hide_index=True,
    )


def _render_pdf_download(portfolio_id: int, portfolio_name: str) -> None:
    if st.button("Last ned porteføljerapport (PDF)", key=f"pdf_dl_{portfolio_id}"):
        with st.spinner("Genererer PDF…"):
            try:
                r = requests.get(f"{API_BASE}/portfolio/{portfolio_id}/pdf", timeout=60)
                if r.ok:
                    safe_name = portfolio_name.replace(" ", "_")
                    st.download_button(
                        label="Klikk for å laste ned PDF",
                        data=r.content,
                        file_name=f"portefoeljerapport_{safe_name}.pdf",
                        mime="application/pdf",
                        key=f"pdf_dl_btn_{portfolio_id}",
                    )
                else:
                    st.error(f"Klarte ikke generere PDF: {r.status_code}")
            except Exception as e:
                st.error(f"PDF-feil: {e}")


def _render_alerts(portfolio_id: int) -> None:
    alerts = _fetch(f"/portfolio/{portfolio_id}/alerts")
    if not alerts:
        return
    with st.expander(f"⚠️ Vekstalerts ({len(alerts)})", expanded=True):
        for sev in ("Kritisk", "Høy", "Moderat"):
            group = [a for a in alerts if a.get("severity") == sev]
            if not group:
                continue
            st.markdown(f"**{_SEVERITY_ICON.get(sev, '')} {sev}**")
            for a in group:
                col_a, col_b = st.columns([4, 1])
                col_a.markdown(
                    f"**{a['navn']}** — {a['alert_type']}: {a['detail']} "
                    f"({a.get('year_from')}→{a.get('year_to')})"
                )
                if col_b.button("Åpne profil", key=f"alert_open_{a['orgnr']}_{a['alert_type']}"):
                    st.session_state["selected_orgnr"] = a["orgnr"]
                    st.session_state["_goto_tab"] = "search"
                    st.rerun()


def _render_premium_analytics(portfolio_id: int) -> None:
    data = _fetch(f"/portfolio/{portfolio_id}/analytics")
    if not data or data.get("active_policy_count", 0) == 0:
        return

    st.markdown("#### Forsikringsbok")
    total = data.get("total_annual_premium_nok", 0)
    count = data.get("active_policy_count", 0)
    r90 = data.get("upcoming_renewals_90d", 0)
    r30 = data.get("upcoming_renewals_30d", 0)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total årspremie", f"{total / 1_000_000:.1f} MNOK" if total else "–")
    m2.metric("Aktive poliser", count)
    m3.metric("Fornyelser (90d)", r90)
    m4.metric("Fornyelser (30d)", r30, delta=f"-{r30}" if r30 else None, delta_color="inverse")

    col_ins, col_prod = st.columns(2)
    with col_ins:
        ins = data.get("insurer_concentration", [])
        if ins:
            st.caption("**Fordeling per forsikringsselskap**")
            df_ins = pd.DataFrame(ins)[["insurer", "premium_nok", "share_pct"]].copy()
            df_ins["premium_nok"] = (df_ins["premium_nok"] / 1_000_000).round(2)
            df_ins.rename(columns={"insurer": "Forsikringsselskap", "premium_nok": "Premie (MNOK)", "share_pct": "Andel %"}, inplace=True)
            st.dataframe(df_ins, width="stretch", hide_index=True)

    with col_prod:
        prod = data.get("product_concentration", [])
        if prod:
            st.caption("**Fordeling per produkttype**")
            df_prod = pd.DataFrame(prod)[["product_type", "count", "premium_nok"]].copy()
            df_prod["premium_nok"] = (df_prod["premium_nok"] / 1_000_000).round(2)
            df_prod.rename(columns={"product_type": "Produkttype", "count": "Antall", "premium_nok": "Premie (MNOK)"}, inplace=True)
            st.dataframe(df_prod, width="stretch", hide_index=True)


def _render_concentration(portfolio_id: int) -> None:
    data = _fetch(f"/portfolio/{portfolio_id}/concentration")
    if not data or not data.get("total_companies"):
        st.info("Ingen konsentrasjonsdata tilgjengelig.")
        return

    total_rev = data.get("total_revenue", 0)
    st.caption(
        f"{data['total_companies']} selskaper · "
        f"Total eksponert omsetning: **{total_rev/1e9:.1f} BNOK**"
    )

    cc1, cc2, cc3 = st.columns(3)
    with cc1:
        st.markdown("**Bransjefordeling**")
        ind = data.get("by_industry", [])
        if ind:
            st.bar_chart(pd.DataFrame(ind)[["label", "count"]].set_index("label"))

    with cc2:
        st.markdown("**Geografisk spredning (topp 10)**")
        geo = data.get("by_geography", [])
        if geo:
            st.bar_chart(pd.DataFrame(geo).set_index("kommune"))

    with cc3:
        st.markdown("**Størrelsesfordeling**")
        sz = data.get("by_size", [])
        if sz:
            _ORDER = ["<10 MNOK", "10–100 MNOK", "100 MNOK–1 BNOK", ">1 BNOK", "Ukjent"]
            sz_sorted = sorted(sz, key=lambda x: _ORDER.index(x["band"]) if x["band"] in _ORDER else 99)
            st.bar_chart(pd.DataFrame(sz_sorted).set_index("band"))


def _render_comparison_charts(rows: list) -> None:
    if len(rows) < 2:
        return

    st.markdown("#### Sammenlign selskaper")
    names = [r.get("navn") or r.get("orgnr", "?") for r in rows]
    selected = st.multiselect(
        "Velg selskaper å sammenligne (2–6)",
        names,
        default=names[:min(4, len(names))],
        key="comparison_select",
    )
    if len(selected) < 2:
        st.caption("Velg minst 2 selskaper.")
        return

    subset = [r for r in rows if (r.get("navn") or r.get("orgnr")) in selected]

    col_eq, col_rev, col_risk = st.columns(3)
    with col_eq:
        st.caption("**EK-andel %**")
        st.bar_chart(
            {(r.get("navn") or r.get("orgnr")): round((r.get("equity_ratio") or 0) * 100, 1) for r in subset},
            height=200,
        )
    with col_rev:
        st.caption("**Omsetning (MNOK)**")
        st.bar_chart(
            {(r.get("navn") or r.get("orgnr")): round((r.get("revenue") or 0) / 1_000_000, 1) for r in subset},
            height=200,
        )
    with col_risk:
        st.caption("**Risikoscore (1–10)**")
        st.bar_chart(
            {(r.get("navn") or r.get("orgnr")): r.get("risk_score") or 0 for r in subset},
            height=200,
        )
