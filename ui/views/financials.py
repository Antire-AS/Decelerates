"""Financial Mode — cross-company comparison and portfolio financial analysis."""
import requests
import streamlit as st
import pandas as pd

from ui.config import API_BASE


def _fmt_nok(v) -> str:
    if v is None:
        return "–"
    b = abs(v)
    if b >= 1_000_000_000:
        return f"{v/1_000_000_000:.1f} mrd"
    if b >= 1_000_000:
        return f"{v/1_000_000:.0f} MNOK"
    return f"{v/1_000:.0f} TNOK"


@st.cache_data(ttl=120)
def _fetch_portfolios() -> list:
    try:
        r = requests.get(f"{API_BASE}/portfolios", timeout=8)
        return r.json() if r.ok else []
    except Exception:
        return []


@st.cache_data(ttl=60)
def _fetch_portfolio_rows(portfolio_id: int) -> list:
    try:
        r = requests.get(f"{API_BASE}/portfolio/{portfolio_id}/risk", timeout=15)
        return r.json() if r.ok else []
    except Exception:
        return []


def _build_df(rows: list) -> pd.DataFrame:
    records = []
    for r in rows:
        records.append({
            "Selskap": r.get("navn", r.get("orgnr", "–")),
            "Orgnr": r.get("orgnr", ""),
            "Omsetning": r.get("revenue"),
            "Egenkapital": r.get("equity"),
            "EK-andel %": round(r.get("equity_ratio") * 100, 1) if r.get("equity_ratio") is not None else None,
            "Risikoscore": r.get("risk_score"),
            "Bransje": (r.get("naeringskode") or "–")[:35],
            "År": r.get("regnskapsår"),
        })
    return pd.DataFrame(records)


def _render_kpi_row(rows: list) -> None:
    revenues = [r["revenue"] for r in rows if r.get("revenue")]
    risk_scores = [r["risk_score"] for r in rows if r.get("risk_score") is not None]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Selskaper med data", f"{len(revenues)} / {len(rows)}")
    c2.metric("Total omsetning", _fmt_nok(sum(revenues)) if revenues else "–")
    c3.metric("Gj.snitt risikoscore",
              f"{sum(risk_scores)/len(risk_scores):.1f}" if risk_scores else "–")
    c4.metric("Høyeste risiko",
              f"{max(risk_scores):.0f}" if risk_scores else "–")


def _render_comparison_table(df: pd.DataFrame, sort_col: str) -> None:
    display = df.copy()
    display["Omsetning"] = df["Omsetning"].apply(_fmt_nok)
    display["Egenkapital"] = df["Egenkapital"].apply(_fmt_nok)
    display["EK-andel %"] = df["EK-andel %"].apply(lambda x: f"{x:.1f} %" if x is not None else "–")
    display["Risikoscore"] = df["Risikoscore"].apply(lambda x: f"{x:.0f}" if x is not None else "–")
    display["År"] = df["År"].apply(lambda x: str(int(x)) if x else "–")
    cols = ["Selskap", "Omsetning", "Egenkapital", "EK-andel %", "Risikoscore", "Bransje", "År"]
    st.dataframe(display[cols], use_container_width=True, hide_index=True)


def _render_revenue_chart(df: pd.DataFrame) -> None:
    chart_df = df[df["Omsetning"].notna()].copy()
    if chart_df.empty:
        st.caption("Ingen omsetningsdata tilgjengelig.")
        return
    chart_df = chart_df.sort_values("Omsetning", ascending=False).head(15)
    chart_df["Omsetning MNOK"] = chart_df["Omsetning"] / 1_000_000
    st.bar_chart(chart_df.set_index("Selskap")["Omsetning MNOK"], height=280)


def _render_risk_chart(df: pd.DataFrame) -> None:
    chart_df = df[df["Risikoscore"].notna()].copy()
    if chart_df.empty:
        st.caption("Ingen risikoscoredata tilgjengelig.")
        return
    chart_df = chart_df.sort_values("Risikoscore", ascending=False)
    st.bar_chart(chart_df.set_index("Selskap")["Risikoscore"], height=280)


def render_financial_tab() -> None:
    st.markdown("## Finansiell analyse")

    portfolios = _fetch_portfolios()
    if not portfolios:
        st.info("Ingen porteføljer funnet. Opprett en i Portefølje-fanen.")
        return

    names = [p["name"] for p in portfolios]
    chosen = st.selectbox("Velg portefølje", names, key="fin_portfolio_sel")
    pid = next(p["id"] for p in portfolios if p["name"] == chosen)

    rows = _fetch_portfolio_rows(pid)
    if not rows:
        st.info("Ingen selskaper i denne porteføljen, eller data ikke hentet ennå.")
        return

    st.markdown("---")
    _render_kpi_row(rows)
    st.markdown("---")

    df = _build_df(rows)
    sort_options = ["Omsetning", "Risikoscore", "EK-andel %", "Selskap"]
    sort_col = st.selectbox("Sorter etter", sort_options, key="fin_sort_col")
    numeric_sort = df[sort_col] if sort_col in df.columns else df["Selskap"]
    df = df.sort_values(
        sort_col,
        ascending=(sort_col == "Selskap"),
        na_position="last",
    )

    _render_comparison_table(df, sort_col)

    st.markdown("---")
    rev_col, risk_col = st.columns(2)
    with rev_col:
        st.markdown("**Omsetning (MNOK)**")
        _render_revenue_chart(df)
    with risk_col:
        st.markdown("**Risikoscore**")
        _render_risk_chart(df)

    st.markdown("---")
    buf = df.drop(columns=["Orgnr"]).to_csv(index=False).encode()
    st.download_button(
        "⬇️ Eksporter til CSV",
        data=buf,
        file_name=f"finans_{chosen.replace(' ', '_')}.csv",
        mime="text/csv",
    )
