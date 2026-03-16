"""Search tab: session-state init, sidebar checklist, search form, profile orchestration."""
import requests
import streamlit as st

from ui.config import API_BASE, T, _fetch_company_data
from ui.views.profile_core import render_profile_core
from ui.views.profile_financials import render_profile_financials


def render_search_tab() -> None:
    _lang = st.session_state.get("lang", "no")
    st.subheader(T("Search organisation"))
    name = st.text_input(T("Name (or orgnr)"), value="DNB")
    kommune = st.text_input(T("Municipality (optional)"), value="")
    size = st.slider(T("Max results"), 5, 50, 20)

    # ── Session state defaults ────────────────────────
    for key, default in [
        ("search_results", []),
        ("selected_orgnr", None),
        ("chat_answer", None),
        ("narrative", None),
        ("estimated_financials", None),
        ("offers_uploaded_names", []),
        ("offers_comparison", None),
        ("show_results", True),
        ("coverage_gap", None),
        ("notes_refresh", 0),
        ("forsikringstilbud_pdf", None),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    # ── Sidebar: broker process checklist ────────────────────────────────────
    orgnr_ctx = st.session_state.get("selected_orgnr")
    if orgnr_ctx:
        with st.sidebar:
            st.markdown("### Salgsprosess")

            step1 = True
            step2 = bool(st.session_state.get("narrative")) or bool(st.session_state.get("risk_offer"))
            step3 = len(st.session_state.get("offers_uploaded_names", [])) > 0
            step4 = bool(st.session_state.get("offers_comparison"))
            step5 = st.session_state.get(f"step5_{orgnr_ctx}", False)
            step6 = st.session_state.get(f"step6_{orgnr_ctx}", False)
            step7 = False
            try:
                _sla_list = requests.get(f"{API_BASE}/sla", timeout=4).json()
                step7 = any(s.get("client_orgnr") == orgnr_ctx for s in _sla_list)
            except Exception:
                pass

            steps = [
                (step1, "Datainnhenting",    "Selskapsdata hentet fra BRREG"),
                (step2, "Behovsanalyse",     "Risikoscoring og AI-analyse"),
                (step3, "Tilbudsinnhenting", "Tilbud fra forsikringsselskaper"),
                (step4, "Analyse av tilbud", "Sammenstilling og AI-sammenligning"),
                (step5, "Presentasjon",      "Tilbud presentert for kunde"),
                (step6, "Forhandlinger",     "Vilkår og pris avklart"),
                (step7, "Kontrakt",          "Tjenesteavtale signert"),
            ]

            done_count = sum(1 for done, _, _ in steps if done)
            total = len(steps)

            st.progress(done_count / total)
            st.caption(f"{done_count} av {total} steg fullført")
            st.markdown("---")

            active_idx = next((i for i, (done, _, _) in enumerate(steps) if not done), total)

            for i, (done, title, desc) in enumerate(steps):
                is_active = i == active_idx
                if done:
                    st.markdown(
                        f"<div style='display:flex;align-items:center;padding:5px 0;gap:10px'>"
                        f"<span style='width:22px;height:22px;border-radius:50%;background:#4A6FA5;"
                        f"display:inline-flex;align-items:center;justify-content:center;"
                        f"font-size:12px;color:#fff;font-weight:700;flex-shrink:0'>✓</span>"
                        f"<span style='color:#7A9A5A;font-size:13px;font-weight:600'>{title}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                elif is_active:
                    st.markdown(
                        f"<div style='display:flex;align-items:center;padding:6px 8px;gap:10px;"
                        f"background:#FFFFFF;border-left:3px solid #4A6FA5;border-radius:4px;"
                        f"margin:3px 0;box-shadow:0 1px 3px rgba(0,0,0,0.06)'>"
                        f"<span style='width:22px;height:22px;border-radius:50%;background:#4A6FA5;"
                        f"display:inline-flex;align-items:center;justify-content:center;"
                        f"font-size:11px;color:#fff;font-weight:700;flex-shrink:0'>{i+1}</span>"
                        f"<div><div style='color:#2C3E50;font-size:13px;font-weight:700'>{title}</div>"
                        f"<div style='color:#8A7F74;font-size:10px;margin-top:1px'>{desc}</div></div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f"<div style='display:flex;align-items:center;padding:5px 0;gap:10px'>"
                        f"<span style='width:22px;height:22px;border-radius:50%;border:1.5px solid #C8C0B6;"
                        f"display:inline-flex;align-items:center;justify-content:center;"
                        f"font-size:11px;color:#B8B0A8;font-weight:600;flex-shrink:0'>{i+1}</span>"
                        f"<span style='color:#A09890;font-size:13px'>{title}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

            st.markdown("---")
            new5 = st.checkbox("Presentasjon fullført", value=step5, key=f"cb5_{orgnr_ctx}")
            new6 = st.checkbox("Forhandlinger fullført", value=step6, key=f"cb6_{orgnr_ctx}")
            st.session_state[f"step5_{orgnr_ctx}"] = new5
            st.session_state[f"step6_{orgnr_ctx}"] = new6

            if not step7:
                st.caption("Gå til **Avtaler**-fanen for å opprette tjenesteavtale (steg 7)")

    # ── Search button + results ───────────────────────
    if st.button(T("Search")):
        params = {"name": name, "size": size}
        if kommune:
            params["kommunenummer"] = kommune
        st.session_state["narrative"] = None
        st.session_state["estimated_financials"] = None
        st.session_state["show_results"] = True
        st.session_state["selected_orgnr"] = None
        try:
            resp = requests.get(f"{API_BASE}/search", params=params, timeout=10)
            resp.raise_for_status()
            st.session_state["search_results"] = resp.json()
        except Exception as e:
            st.error(f"Failed to call backend: {e}")

    results = st.session_state["search_results"]

    if st.session_state.get("show_results", True):
        st.write(f"Found {len(results)} results")
        for r in results:
            line = (
                f"{r.get('orgnr', '?')} - {r.get('navn', 'N/A')} "
                f"({r.get('organisasjonsform', 'N/A')}) "
                f"[{r.get('kommune', '')}, {r.get('postnummer', '')}] "
                f"– {r.get('naeringskode1', '')} {r.get('naeringskode1_beskrivelse', '')}"
            )
            st.write(line)
            if st.button(T("View profile"), key=f"view-{r['orgnr']}"):
                st.session_state["selected_orgnr"] = r["orgnr"]
                st.session_state["narrative"] = None
                st.session_state["estimated_financials"] = None
                st.session_state["show_results"] = False
                st.rerun()
    elif results:
        selected = st.session_state.get("selected_orgnr")
        selected_name = next(
            (r.get("navn", selected) for r in results if r.get("orgnr") == selected),
            selected,
        )
        col_info, col_btn = st.columns([5, 1])
        with col_info:
            _showing = "Viser profil" if _lang == "no" else "Showing profile"
            st.caption(f"{_showing}: **{selected_name}** ({selected}) — {len(results)} {'treff' if _lang == 'no' else 'results'}")
        with col_btn:
            if st.button(T("New search"), key="back_to_results"):
                st.session_state["show_results"] = True
                st.session_state["selected_orgnr"] = None
                st.rerun()

    # ── Profile section ───────────────────────────────
    selected_orgnr = st.session_state["selected_orgnr"]
    if selected_orgnr:
        st.markdown("---")
        st.subheader(f"{T('Profile for')} {selected_orgnr}")

        with st.spinner("Laster selskapsdata..."):
            _cd = _fetch_company_data(selected_orgnr)

        prof             = _cd.get("prof")
        lic              = _cd.get("lic")
        roles_data       = _cd.get("roles")
        history_data     = _cd.get("history")
        konkurs_data     = _cd.get("konkurs")
        struktur_data    = _cd.get("struktur")
        koordinater_data = _cd.get("koordinater")
        benchmark_data   = _cd.get("benchmark")

        if prof is None:
            st.error("Failed to fetch org profile — API may be offline or orgnr not found.")

        if prof:
            org          = prof.get("org") or {}
            regn         = prof.get("regnskap") or {}
            risk         = prof.get("risk") or {}
            pep          = prof.get("pep") or {}
            risk_summary = prof.get("risk_summary") or {}

            estimated = st.session_state.get("estimated_financials") or {}
            if not regn and estimated:
                regn = estimated
                risk = {
                    "equity_ratio": estimated.get("equity_ratio"),
                    "score": None,
                    "reasons": ["Based on AI estimates — no public financial data"],
                }

            render_profile_core(
                selected_orgnr, org, regn, risk, risk_summary, pep,
                lic, roles_data, konkurs_data, struktur_data,
                koordinater_data, benchmark_data, prof,
            )
            render_profile_financials(
                selected_orgnr, org, regn, risk, risk_summary, pep,
                history_data, prof, lic,
            )
