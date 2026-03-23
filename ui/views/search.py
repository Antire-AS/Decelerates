"""Search tab: session-state init, sidebar checklist, search form, profile orchestration."""
import requests
import streamlit as st

import requests as _requests

from ui.config import API_BASE, T, _fetch_company_data, get_auth_headers
from ui.views.profile_core import render_oversikt_section, render_forsikring_section
from ui.views.profile_financials import render_okonomi_section
from ui.views.contacts import render_contacts_section
from ui.views.policies import render_policies_section
from ui.views.claims import render_claims_section
from ui.views.activities import render_activity_feed


# ── Guided broker workflow helpers ────────────────────────────────────────────

_WORKFLOW_STEPS = [
    ("Datainnhenting",   "Selskapsdata fra BRREG",             "Oversikt"),
    ("Risikovurdering",  "Risikoscore og AI-narrativ",          "Oversikt"),
    ("Behovsanalyse",    "Forsikringsbehov estimert",           "Forsikring"),
    ("Tilbud innhentet", "Tilbud fra forsikringsselskaper",     "Forsikring"),
    ("Tilbudsanalyse",   "AI-sammenligning fullført",           "Forsikring"),
    ("Presentasjon",     "Forsikringstilbud PDF generert",      "Forsikring"),
    ("Kontrakt",         "Tjenesteavtale signert i Avtaler",    "Avtaler"),
]


def _compute_workflow_steps(orgnr: str, risk: dict) -> list[dict]:
    has_contract = False
    try:
        sla_list = requests.get(f"{API_BASE}/sla", timeout=3).json()
        has_contract = any(s.get("client_orgnr") == orgnr for s in (sla_list or []))
    except Exception:
        pass
    done_flags = [
        True,
        risk.get("score") is not None,
        bool(st.session_state.get("narrative")),
        len(st.session_state.get("offers_uploaded_names", [])) > 0,
        bool(st.session_state.get("offers_comparison")),
        bool(st.session_state.get("forsikringstilbud_pdf")),
        has_contract,
    ]
    return [
        {"done": done_flags[i], "label": label, "desc": desc, "tab_name": tab}
        for i, (label, desc, tab) in enumerate(_WORKFLOW_STEPS)
    ]


def _wf_circle(i: int, done: bool, active: bool) -> str:
    if done:
        style = "background:#2C3E50;color:#D4C9B8;"
        txt = "✓"
    elif active:
        style = "background:#4A6FA5;color:#fff;box-shadow:0 0 0 3px #C5D8F0;"
        txt = str(i + 1)
    else:
        style = "background:#EDEAE6;color:#A09890;border:1.5px solid #D0CBC3;"
        txt = str(i + 1)
    return (
        f"<div style='width:26px;height:26px;border-radius:50%;{style}"
        f"display:flex;align-items:center;justify-content:center;"
        f"font-size:11px;font-weight:700;flex-shrink:0'>{txt}</div>"
    )


def _render_workflow_stepper(steps: list[dict]) -> None:
    """Horizontal 7-step progress stepper shown above company profile tabs."""
    active_i = next((i for i, s in enumerate(steps) if not s["done"]), len(steps))
    parts = [
        "<div style='display:flex;align-items:flex-start;padding:14px 16px;"
        "background:#fff;border-radius:10px;border:1px solid #E0DBD5;"
        "box-shadow:0 1px 3px rgba(0,0,0,0.04);margin-bottom:8px'>"
    ]
    for i, step in enumerate(steps):
        is_active = i == active_i
        lbl_color = "#5A8A5A" if step["done"] else ("#1A2E40" if is_active else "#A09890")
        lbl_weight = "600" if step["done"] else ("700" if is_active else "400")
        lbl = step["label"].replace(" ", "<br>")
        parts += [
            "<div style='display:flex;flex-direction:column;align-items:center;gap:5px;flex:0 0 auto'>",
            _wf_circle(i, step["done"], is_active),
            f"<div style='font-size:9px;text-align:center;color:{lbl_color};"
            f"font-weight:{lbl_weight};line-height:1.3;max-width:58px'>{lbl}</div>",
            "</div>",
        ]
        if i < len(steps) - 1:
            conn_bg = "#2C3E50" if step["done"] else "#D0CBC3"
            parts.append(f"<div style='flex:1;height:2px;background:{conn_bg};margin-top:12px;min-width:8px'></div>")
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)

    if active_i < len(steps):
        s = steps[active_i]
        st.markdown(
            f"<div style='background:#EEF4FC;border-left:3px solid #4A6FA5;border-radius:5px;"
            f"padding:8px 14px;font-size:12px;margin-bottom:12px'>"
            f"<span style='color:#2C3E50;font-weight:700'>Neste: Steg {active_i+1} — {s['label']}</span>"
            f"<span style='color:#5A6A7A;margin-left:8px'>{s['desc']}. Gå til <b>{s['tab_name']}</b>-fanen.</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div style='background:#F0F7F0;border-left:3px solid #5A8A5A;border-radius:5px;"
            "padding:8px 14px;font-size:12px;margin-bottom:12px'>"
            "<span style='color:#2C3E50;font-weight:700'>✓ Alle 7 steg fullført</span>"
            "<span style='color:#5A6A7A;margin-left:8px'>Klientprosessen er komplett.</span>"
            "</div>",
            unsafe_allow_html=True,
        )


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

    # ── Sidebar: compact progress summary ────────────────────────────────────
    orgnr_ctx = st.session_state.get("selected_orgnr")
    if orgnr_ctx:
        with st.sidebar:
            st.markdown("### Salgsprosess")
            _sidebar_risk = {}
            try:
                _pr = requests.get(f"{API_BASE}/org/{orgnr_ctx}", timeout=5).json()
                _sidebar_risk = (_pr.get("risk") or {})
            except Exception:
                pass
            _sw = _compute_workflow_steps(orgnr_ctx, _sidebar_risk)
            _done = sum(1 for s in _sw if s["done"])
            st.progress(_done / len(_sw))
            st.caption(f"{_done} av {len(_sw)} steg fullført")
            st.markdown("---")
            _active_sb = next((i for i, s in enumerate(_sw) if not s["done"]), len(_sw))
            for i, s in enumerate(_sw):
                if s["done"]:
                    st.markdown(
                        f"<div style='display:flex;align-items:center;gap:8px;padding:4px 0'>"
                        f"<span style='width:20px;height:20px;border-radius:50%;background:#2C3E50;"
                        f"display:inline-flex;align-items:center;justify-content:center;"
                        f"font-size:10px;color:#D4C9B8;font-weight:700;flex-shrink:0'>✓</span>"
                        f"<span style='color:#5A8A5A;font-size:12px;font-weight:600'>{s['label']}</span></div>",
                        unsafe_allow_html=True,
                    )
                elif i == _active_sb:
                    st.markdown(
                        f"<div style='display:flex;align-items:center;gap:8px;padding:5px 8px;"
                        f"background:#fff;border-left:3px solid #4A6FA5;border-radius:4px;margin:2px 0'>"
                        f"<span style='width:20px;height:20px;border-radius:50%;background:#4A6FA5;"
                        f"display:inline-flex;align-items:center;justify-content:center;"
                        f"font-size:10px;color:#fff;font-weight:700;flex-shrink:0'>{i+1}</span>"
                        f"<div><div style='color:#2C3E50;font-size:12px;font-weight:700'>{s['label']}</div>"
                        f"<div style='color:#8A7F74;font-size:9px'>{s['desc']}</div></div></div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f"<div style='display:flex;align-items:center;gap:8px;padding:4px 0'>"
                        f"<span style='width:20px;height:20px;border-radius:50%;border:1px solid #C8C0B6;"
                        f"display:inline-flex;align-items:center;justify-content:center;"
                        f"font-size:10px;color:#C8C0B6;font-weight:600;flex-shrink:0'>{i+1}</span>"
                        f"<span style='color:#B0A898;font-size:12px'>{s['label']}</span></div>",
                        unsafe_allow_html=True,
                    )

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

            _wf_steps = _compute_workflow_steps(selected_orgnr, risk)
            _render_workflow_stepper(_wf_steps)

            tab_oversikt, tab_okonomi, tab_forsikring, tab_crm = st.tabs(
                ["Oversikt", "Økonomi", "Forsikring", "CRM"]
            )

            with tab_oversikt:
                render_oversikt_section(
                    selected_orgnr, org, regn, risk, risk_summary, pep,
                    lic, roles_data, konkurs_data, struktur_data,
                    koordinater_data, benchmark_data, prof,
                )

            with tab_okonomi:
                render_okonomi_section(
                    selected_orgnr, org, regn, risk, risk_summary, pep,
                    history_data, prof, lic,
                )

            with tab_forsikring:
                render_forsikring_section(
                    selected_orgnr, org, regn, risk, risk_summary, pep,
                    lic, roles_data, konkurs_data, struktur_data,
                    koordinater_data, benchmark_data, prof,
                )

            with tab_crm:
                render_contacts_section(selected_orgnr)

                try:
                    _policies_resp = _requests.get(
                        f"{API_BASE}/org/{selected_orgnr}/policies",
                        headers=get_auth_headers(), timeout=8,
                    )
                    _policies = _policies_resp.json() if _policies_resp.ok else []
                except Exception:
                    _policies = []

                render_policies_section(selected_orgnr)
                render_claims_section(selected_orgnr, _policies)
                render_activity_feed(selected_orgnr)
