"""Read-only client profile view rendered when a broker shares a ?client_token= URL."""
import requests
import streamlit as st

from ui.config import API_BASE


def _fmt_nok(v) -> str:
    if v is None:
        return "–"
    b = abs(v)
    if b >= 1_000_000_000:
        return f"{v/1_000_000_000:.1f} mrd NOK"
    if b >= 1_000_000:
        return f"{v/1_000_000:.0f} MNOK"
    return f"{v/1_000:.0f} TNOK"


def _risk_color(score) -> str:
    if score is None:
        return "#8A7F74"
    if score >= 70:
        return "#C0392B"
    if score >= 40:
        return "#E67E22"
    return "#27AE60"


def render_client_view(token: str) -> None:
    """Render a minimal read-only profile for the token's company."""
    try:
        r = requests.get(f"{API_BASE}/client/{token}", timeout=10)
    except Exception:
        st.error("Kunne ikke koble til serveren. Prøv igjen senere.")
        return

    if r.status_code == 404:
        st.error("Lenken er ikke gyldig.")
        return
    if r.status_code == 410:
        st.error("Lenken har utløpt. Kontakt megleren for en ny lenke.")
        return
    if not r.ok:
        st.error("Noe gikk galt ved lasting av profilen.")
        return

    data = r.json()
    navn = data.get("navn") or data["orgnr"]
    score = data.get("risk_score")
    color = _risk_color(score)

    st.markdown(
        f"<div style='background:#2C3E50;color:#D4C9B8;padding:16px 24px;"
        f"border-radius:8px;margin-bottom:16px'>"
        f"<div style='font-size:11px;letter-spacing:.1em;text-transform:uppercase;"
        f"color:#8A9BBB;margin-bottom:4px'>Forsikringsanalyse</div>"
        f"<div style='font-size:22px;font-weight:700'>{navn}</div>"
        f"<div style='font-size:12px;color:#8A9BBB;margin-top:2px'>"
        f"Org.nr {data['orgnr']} · {data.get('kommune', '')} · "
        f"{data.get('naeringskode1_beskrivelse', '')}</div></div>",
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Omsetning", _fmt_nok(data.get("sum_driftsinntekter")))
    c2.metric("Ansatte", str(data.get("antall_ansatte") or "–"))
    c3.markdown(
        f"<div style='text-align:center;padding:8px'>"
        f"<div style='font-size:11px;color:#8A7F74;margin-bottom:4px'>Risikoscore</div>"
        f"<div style='font-size:28px;font-weight:700;color:{color}'>"
        f"{score if score is not None else '–'}</div></div>",
        unsafe_allow_html=True,
    )

    reasons = data.get("risk_reasons") or []
    if reasons:
        st.markdown("**Risikofaktorer**")
        for r_txt in reasons:
            st.markdown(f"- {r_txt}")

    regn = data.get("regnskap") or {}
    if regn:
        st.markdown("---")
        st.markdown("**Nøkkeltall**")
        rc1, rc2, rc3 = st.columns(3)
        rc1.metric("Egenkapital", _fmt_nok(regn.get("sum_egenkapital")))
        rc2.metric("Eiendeler", _fmt_nok(regn.get("sum_eiendeler")))
        eq = regn.get("equity_ratio")
        rc3.metric("EK-andel", f"{eq*100:.1f} %" if eq is not None else "–")

    st.markdown("---")
    st.caption(f"Denne rapporten utløper {data.get('expires_at', '')[:10]}. "
               "Kontakt megleren din for oppdatert analyse.")
