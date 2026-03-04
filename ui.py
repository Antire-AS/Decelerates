import requests
import streamlit as st
import pandas as pd

API_BASE = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="Broker Accelerator",
    page_icon="⚖",
    layout="wide",
)

st.markdown("""
<style>
/* ── Global typography ── */
html, body, [class*="css"] {
    font-family: 'Georgia', 'Times New Roman', serif;
}

/* ── Top banner ── */
.broker-header {
    background: #1B3A6B;
    padding: 1.6rem 2rem 1.2rem 2rem;
    border-bottom: 4px solid #C9A84C;
    margin: -4rem -4rem 1.8rem -4rem;
}
.broker-header h1 {
    color: #FFFFFF;
    font-size: 2rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    margin: 0;
}
.broker-header p {
    color: #C9A84C;
    font-size: 0.85rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    margin: 0.2rem 0 0 0;
}

/* ── Tab bar ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 0;
    border-bottom: 2px solid #1B3A6B;
}
.stTabs [data-baseweb="tab"] {
    font-family: Georgia, serif;
    font-size: 1rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    padding: 0.6rem 1.6rem;
    border-radius: 0;
    color: #1B3A6B;
}
.stTabs [aria-selected="true"] {
    background: #1B3A6B !important;
    color: #FFFFFF !important;
}

/* ── Section headings ── */
h2, h3 {
    color: #1B3A6B;
    border-bottom: 1px solid #C9A84C;
    padding-bottom: 0.3rem;
}

/* ── Metric cards ── */
[data-testid="metric-container"] {
    background: #F5F2EC;
    border: 1px solid #D6D0C4;
    border-left: 4px solid #1B3A6B;
    border-radius: 4px;
    padding: 0.8rem 1rem;
}
[data-testid="stMetricValue"] {
    font-size: 1.5rem !important;
    font-weight: 700;
    color: #1B3A6B;
}
[data-testid="stMetricLabel"] {
    font-size: 0.8rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #555;
}

/* ── Buttons ── */
.stButton > button {
    font-family: Georgia, serif;
    font-size: 0.95rem;
    letter-spacing: 0.04em;
    border-radius: 3px;
    border: 1px solid #1B3A6B;
    background: #1B3A6B;
    color: white;
    padding: 0.45rem 1.2rem;
}
.stButton > button:hover {
    background: #C9A84C;
    border-color: #C9A84C;
    color: white;
}
button[kind="secondary"] {
    background: white !important;
    color: #1B3A6B !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #F5F2EC;
    border-right: 1px solid #D6D0C4;
}
[data-testid="stSidebar"] h2 {
    font-size: 1.1rem;
    border-bottom: 2px solid #C9A84C;
}

/* ── Dataframes / tables ── */
[data-testid="stDataFrame"] {
    border: 1px solid #D6D0C4;
}

/* ── Input fields ── */
input, textarea, select {
    font-family: Georgia, serif !important;
    font-size: 1rem !important;
}

/* ── Divider ── */
hr {
    border: none;
    border-top: 1px solid #C9A84C;
    margin: 1.5rem 0;
}
</style>

<div class="broker-header">
    <h1>Broker Accelerator</h1>
    <p>Forsikringsmegling &nbsp;&bull;&nbsp; Due Diligence &nbsp;&bull;&nbsp; Risikoprofil</p>
</div>
""", unsafe_allow_html=True)

tab_search, tab_portfolio, tab_sla = st.tabs(["Selskapsok", "Portefolje", "Avtaler"])

# ──────────────────────────────────────────────
# TAB 1 — Company Search
# ──────────────────────────────────────────────
with tab_search:
    st.subheader("Search organisation")
    name = st.text_input("Name (or orgnr)", value="DNB")
    kommune = st.text_input("Kommunenummer (optional)", value="")
    size = st.slider("Max results", 5, 50, 20)

    if "search_results" not in st.session_state:
        st.session_state["search_results"] = []
    if "selected_orgnr" not in st.session_state:
        st.session_state["selected_orgnr"] = None
    if "chat_answer" not in st.session_state:
        st.session_state["chat_answer"] = None
    if "narrative" not in st.session_state:
        st.session_state["narrative"] = None
    if "estimated_financials" not in st.session_state:
        st.session_state["estimated_financials"] = None
    if "offers_uploaded_names" not in st.session_state:
        st.session_state["offers_uploaded_names"] = []
    if "offers_comparison" not in st.session_state:
        st.session_state["offers_comparison"] = None

    # ── Sidebar: broker process checklist ────────────────────────────────────
    orgnr_ctx = st.session_state.get("selected_orgnr")
    if orgnr_ctx:
        with st.sidebar:
            st.markdown("## Kundeprosess")
            st.caption(f"Orgnr: {orgnr_ctx}")

            step1 = True  # always done once a company is selected
            step2 = bool(st.session_state.get("narrative"))
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
                (step1, "Innhente data om ny kunde"),
                (step2, "Analysere kundens reelle behov"),
                (step3, "Innhente tilbud fra forsikringsselskaper"),
                (step4, "Sammenstille / analysere tilbud"),
                (step5, "Presentere tilbud til kunde"),
                (step6, "Forhandlinger"),
                (step7, "Kontrakt"),
            ]
            all_done = sum(1 for done, _ in steps if done)
            st.progress(all_done / 7, text=f"{all_done} av 7 steg fullført")
            st.markdown("")

            for i, (done, label) in enumerate(steps, 1):
                icon = "✅" if done else "⬜"
                # Bold = the next step the user should act on
                is_next = not done and (i == 1 or steps[i - 2][0])
                if is_next:
                    st.markdown(f"{icon} **{i}. {label}** ◀")
                else:
                    st.markdown(f"{icon} {i}. {label}")

            st.divider()
            st.caption("Marker som fullført manuelt:")
            new5 = st.checkbox("Presentert til kunde", value=step5, key=f"cb5_{orgnr_ctx}")
            new6 = st.checkbox("Forhandlinger fullført", value=step6, key=f"cb6_{orgnr_ctx}")
            st.session_state[f"step5_{orgnr_ctx}"] = new5
            st.session_state[f"step6_{orgnr_ctx}"] = new6

            if step7:
                st.success("Kontrakt opprettet ✅")
            else:
                st.info("Gå til **Agreements**-fanen for å opprette kontrakt (steg 7)")

    if st.button("Search"):
        params = {"name": name, "size": size}
        if kommune:
            params["kommunenummer"] = kommune
        st.session_state["narrative"] = None
        st.session_state["estimated_financials"] = None
        try:
            resp = requests.get(f"{API_BASE}/search", params=params, timeout=10)
            resp.raise_for_status()
            st.session_state["search_results"] = resp.json()
        except Exception as e:
            st.error(f"Failed to call backend: {e}")

    results = st.session_state["search_results"]
    st.write(f"Found {len(results)} results")

    for r in results:
        line = (
            f"{r.get('orgnr', '?')} - {r.get('navn', 'N/A')} "
            f"({r.get('organisasjonsform', 'N/A')}) "
            f"[{r.get('kommune', '')}, {r.get('postnummer', '')}] "
            f"– {r.get('naeringskode1', '')} {r.get('naeringskode1_beskrivelse', '')}"
        )
        st.write(line)
        if st.button("View profile", key=f"view-{r['orgnr']}"):
            st.session_state["selected_orgnr"] = r["orgnr"]
            st.session_state["narrative"] = None
            st.session_state["estimated_financials"] = None

    # ── Profile section ──────────────────────────────────────────
    selected_orgnr = st.session_state["selected_orgnr"]
    if selected_orgnr:
        st.markdown("---")
        st.subheader(f"Profile for {selected_orgnr}")

        prof = None
        try:
            prof_resp = requests.get(f"{API_BASE}/org/{selected_orgnr}", timeout=10)
            prof_resp.raise_for_status()
            prof = prof_resp.json()
        except Exception as e:
            st.error(f"Failed to fetch org profile: {e}")

        lic = None
        try:
            lic_resp = requests.get(f"{API_BASE}/org/{selected_orgnr}/licenses", timeout=10)
            lic_resp.raise_for_status()
            lic = lic_resp.json()
        except Exception:
            pass

        roles_data = None
        try:
            roles_resp = requests.get(f"{API_BASE}/org/{selected_orgnr}/roles", timeout=10)
            roles_resp.raise_for_status()
            roles_data = roles_resp.json()
        except Exception:
            pass

        history_data = None
        try:
            hist_resp = requests.get(f"{API_BASE}/org/{selected_orgnr}/history", timeout=10)
            hist_resp.raise_for_status()
            history_data = hist_resp.json()
        except Exception:
            pass

        konkurs_data = None
        try:
            konkurs_resp = requests.get(f"{API_BASE}/org/{selected_orgnr}/bankruptcy", timeout=10)
            konkurs_resp.raise_for_status()
            konkurs_data = konkurs_resp.json()
        except Exception:
            pass

        koordinater_data = None
        try:
            koor_resp = requests.get(f"{API_BASE}/org/{selected_orgnr}/koordinater", timeout=10)
            koor_resp.raise_for_status()
            koordinater_data = koor_resp.json()
        except Exception:
            pass

        benchmark_data = None
        try:
            bench_resp = requests.get(f"{API_BASE}/org/{selected_orgnr}/benchmark", timeout=10)
            bench_resp.raise_for_status()
            benchmark_data = bench_resp.json()
        except Exception:
            pass

        if prof:
            org = prof.get("org") or {}
            regn = prof.get("regnskap") or {}
            risk = prof.get("risk") or {}
            pep = prof.get("pep") or {}
            risk_summary = prof.get("risk_summary") or {}

            # Overlay estimated financials when no real data
            estimated = st.session_state.get("estimated_financials") or {}
            if not regn and estimated:
                regn = estimated
                risk = {
                    "equity_ratio": estimated.get("equity_ratio"),
                    "score": None,
                    "reasons": ["Based on AI estimates — no public financial data"],
                }

            def fmt_mnok(value):
                if value is None:
                    return "–"
                try:
                    return f"{value/1_000_000:,.1f} MNOK".replace(",", " ")
                except Exception:
                    return str(value)

            # ── 1) Organisation info + map ─────────────────────
            st.markdown("### Organisation")
            col_info, col_map = st.columns([1, 1])
            with col_info:
                st.write(
                    f"**{org.get('navn', 'N/A')}** "
                    f"({org.get('organisasjonsform', 'N/A')}) – "
                    f"orgnr {org.get('orgnr', 'N/A')}"
                )
                st.write(
                    f"{org.get('kommune', 'N/A')} {org.get('postnummer', '')}, "
                    f"{org.get('land', 'N/A')}"
                )
                st.write(
                    f"Næringskode: {org.get('naeringskode1', 'N/A')} "
                    f"{org.get('naeringskode1_beskrivelse', '')}"
                )
                if org.get("stiftelsesdato"):
                    st.write(f"Founded: {org.get('stiftelsesdato')}")
            with col_map:
                coords = (koordinater_data or {}).get("coordinates")
                if coords and coords.get("lat") and coords.get("lon"):
                    map_df = pd.DataFrame({"lat": [coords["lat"]], "lon": [coords["lon"]]})
                    st.map(map_df, zoom=13)
                    if coords.get("adressetekst"):
                        st.caption(f"📍 {coords['adressetekst']}")
                else:
                    st.info("Location not available")

            # ── 1b) Bankruptcy & liquidation status ────────────
            st.markdown("### Bankruptcy & liquidation status")
            kd = konkurs_data or {}
            if kd.get("konkurs") or kd.get("under_konkursbehandling"):
                st.error("⚠️ This company is currently under bankruptcy proceedings (konkursbehandling)")
            elif kd.get("under_avvikling"):
                st.warning("⚠️ This company is currently under voluntary liquidation (avvikling)")
            elif konkurs_data is not None:
                st.success("No bankruptcy or liquidation proceedings found")
            else:
                st.info("Bankruptcy status unavailable")

            # ── 2) Board members ───────────────────────────────
            st.markdown("### Board members & roles")
            members = (roles_data or {}).get("members") or []
            if members:
                active = [m for m in members if not m.get("resigned") and not m.get("deceased")]
                resigned = [m for m in members if m.get("resigned") or m.get("deceased")]
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Role": m["role"],
                                "Group": m["group"],
                                "Name": m["name"],
                                "Born": m.get("birth_year") or "–",
                            }
                            for m in active
                        ]
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
                if resigned:
                    with st.expander(f"Resigned / deceased ({len(resigned)})"):
                        st.dataframe(
                            pd.DataFrame(
                                [
                                    {
                                        "Role": m["role"],
                                        "Name": m["name"],
                                        "Status": "Deceased" if m.get("deceased") else "Resigned",
                                    }
                                    for m in resigned
                                ]
                            ),
                            use_container_width=True,
                            hide_index=True,
                        )
            else:
                st.info("No role data available for this organisation.")

            # ── 3) Risk summary ────────────────────────────────
            st.markdown("### Risk summary")
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric(label="Turnover", value=fmt_mnok(risk_summary.get("omsetning")))
            with col2:
                st.metric(label="Employees", value=risk_summary.get("antall_ansatte", "–"))
            with col3:
                eq_ratio = risk_summary.get("egenkapitalandel")
                eq_val = "–" if eq_ratio is None else f"{eq_ratio*100:,.1f} %".replace(",", " ")
                st.metric(label="Equity ratio", value=eq_val)
            with col4:
                st.metric(label="Risk score", value=risk_summary.get("risk_score", "–"))
            with col5:
                st.metric(label="PEP hits", value=risk_summary.get("pep_hits", 0))

            flags = risk_summary.get("risk_flags") or []
            if flags:
                st.write("Risk flags:")
                for f in flags:
                    st.write(f"- {f}")
            else:
                st.write("No specific risk flags identified.")

            # ── 3b) Industry benchmarks ────────────────────────
            bench = (benchmark_data or {}).get("benchmark")
            if bench:
                st.markdown("#### Industry benchmarks")
                st.caption(f"Section {bench.get('section')} — {bench.get('industry')} · {bench.get('source')}")
                eq_ratio_val = risk_summary.get("egenkapitalandel")
                b_eq_min = bench.get("typical_equity_ratio_min", 0)
                b_eq_max = bench.get("typical_equity_ratio_max", 0)
                b_mg_min = bench.get("typical_profit_margin_min", 0)
                b_mg_max = bench.get("typical_profit_margin_max", 0)

                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    company_eq = f"{eq_ratio_val*100:.1f}%" if eq_ratio_val is not None else "N/A"
                    industry_eq = f"{b_eq_min*100:.0f}–{b_eq_max*100:.0f}%"
                    if eq_ratio_val is not None:
                        delta_eq = eq_ratio_val - (b_eq_min + b_eq_max) / 2
                        delta_label = f"{delta_eq*100:+.1f}% vs industry mid"
                    else:
                        delta_label = None
                    st.metric("Equity ratio", company_eq, delta=delta_label, help=f"Industry typical: {industry_eq}")

                with col_b2:
                    omsetning = risk_summary.get("omsetning")
                    aarsresultat = (prof.get("regnskap") or {}).get("aarsresultat")
                    if omsetning and aarsresultat is not None and omsetning > 0:
                        company_margin = aarsresultat / omsetning
                        company_mg_str = f"{company_margin*100:.1f}%"
                        industry_mg = f"{b_mg_min*100:.0f}–{b_mg_max*100:.0f}%"
                        delta_mg = company_margin - (b_mg_min + b_mg_max) / 2
                        st.metric("Profit margin", company_mg_str, delta=f"{delta_mg*100:+.1f}% vs industry mid", help=f"Industry typical: {industry_mg}")
                    else:
                        st.metric("Profit margin", "N/A", help=f"Industry typical: {b_mg_min*100:.0f}–{b_mg_max*100:.0f}%")

            # ── 4) AI risk narrative ───────────────────────────
            st.markdown("### AI risk narrative")
            if st.session_state["narrative"]:
                st.info(st.session_state["narrative"])
                if st.button("Regenerate narrative"):
                    st.session_state["narrative"] = None
                    st.rerun()
            else:
                if st.button("Generate risk narrative"):
                    with st.spinner("Analysing with AI..."):
                        try:
                            nav_resp = requests.post(
                                f"{API_BASE}/org/{selected_orgnr}/narrative",
                                timeout=30,
                            )
                            nav_resp.raise_for_status()
                            st.session_state["narrative"] = nav_resp.json().get("narrative")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Narrative generation failed: {e}")

            # ── Steg 3-4: Innhente og analysere tilbud ─────────
            st.markdown("### Forsikringstilbud")

            # Load stored offers from DB
            stored_offers = []
            try:
                stored_offers = requests.get(
                    f"{API_BASE}/org/{selected_orgnr}/offers", timeout=6
                ).json()
            except Exception:
                pass

            # ── Stored offers table ────────────────────────────
            if stored_offers:
                st.caption(f"{len(stored_offers)} tilbud lagret i databasen")
                for offer in stored_offers:
                    col_name, col_date, col_dl, col_del = st.columns([3, 2, 1, 1])
                    with col_name:
                        st.write(f"**{offer['insurer_name']}**  `{offer['filename']}`")
                    with col_date:
                        st.caption(offer.get("uploaded_at", "")[:10])
                    with col_dl:
                        try:
                            pdf_bytes = requests.get(
                                f"{API_BASE}/org/{selected_orgnr}/offers/{offer['id']}/pdf",
                                timeout=10,
                            ).content
                            st.download_button(
                                "Last ned",
                                data=pdf_bytes,
                                file_name=offer["filename"],
                                mime="application/pdf",
                                key=f"dl_offer_{offer['id']}",
                            )
                        except Exception:
                            st.write("–")
                    with col_del:
                        if st.button("Slett", key=f"del_offer_{offer['id']}"):
                            requests.delete(
                                f"{API_BASE}/org/{selected_orgnr}/offers/{offer['id']}",
                                timeout=6,
                            )
                            st.rerun()

                # Compare stored offers
                st.session_state["offers_uploaded_names"] = [o["filename"] for o in stored_offers]
                sel_ids = [o["id"] for o in stored_offers]
                if st.button(
                    f"Analyser alle {len(stored_offers)} lagrede tilbud med AI",
                    key="compare_stored_btn",
                    type="primary",
                ):
                    with st.spinner("Analyserer tilbud med AI... (kan ta 30-60 sek)"):
                        try:
                            comp_resp = requests.post(
                                f"{API_BASE}/org/{selected_orgnr}/offers/compare-stored",
                                json=sel_ids,
                                timeout=120,
                            )
                            comp_resp.raise_for_status()
                            st.session_state["offers_comparison"] = comp_resp.json()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Analyse feilet: {e}")

            # ── Upload new offers ──────────────────────────────
            with st.expander("Last opp nye tilbud og lagre til database"):
                uploaded_files = st.file_uploader(
                    "Velg PDF-tilbud fra forsikringsselskaper",
                    type=["pdf"],
                    accept_multiple_files=True,
                    key="offers_uploader",
                )
                if uploaded_files:
                    st.caption(f"{len(uploaded_files)} fil(er) valgt: {', '.join(f.name for f in uploaded_files)}")
                    col_save, col_analyze = st.columns(2)
                    with col_save:
                        if st.button("Lagre til database", key="save_offers_btn"):
                            with st.spinner("Lagrer..."):
                                try:
                                    files_payload = [
                                        ("files", (f.name, f.getvalue(), "application/pdf"))
                                        for f in uploaded_files
                                    ]
                                    save_resp = requests.post(
                                        f"{API_BASE}/org/{selected_orgnr}/offers",
                                        files=files_payload,
                                        timeout=60,
                                    )
                                    save_resp.raise_for_status()
                                    n = len(save_resp.json().get("saved", []))
                                    st.success(f"{n} tilbud lagret!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Lagring feilet: {e}")
                    with col_analyze:
                        if st.button("Analyser uten å lagre", key="compare_offers_btn"):
                            with st.spinner("Analyserer..."):
                                try:
                                    files_payload = [
                                        ("files", (f.name, f.getvalue(), "application/pdf"))
                                        for f in uploaded_files
                                    ]
                                    comp_resp = requests.post(
                                        f"{API_BASE}/org/{selected_orgnr}/offers/compare",
                                        files=files_payload,
                                        timeout=120,
                                    )
                                    comp_resp.raise_for_status()
                                    st.session_state["offers_comparison"] = comp_resp.json()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Analyse feilet: {e}")

            # ── AI comparison result ───────────────────────────
            if st.session_state.get("offers_comparison"):
                comp = st.session_state["offers_comparison"]
                st.markdown("#### AI-analyse av tilbud")
                offer_names = comp.get("offers", [])
                st.caption(f"Basert på {len(offer_names)} tilbud: {', '.join(offer_names)}")
                st.markdown(comp.get("comparison", ""))
                if st.button("Nullstill analyse", key="clear_comparison_btn"):
                    st.session_state["offers_comparison"] = None
                    st.session_state["offers_uploaded_names"] = []
                    st.rerun()

            # ── 5) Key figures ─────────────────────────────────
            has_real_regn = bool(
                prof.get("regnskap") and prof["regnskap"].get("regnskapsår") is not None
            )
            has_estimated = bool(regn and regn.get("synthetic"))

            if has_real_regn or has_estimated:
                year_label = regn.get("regnskapsår") or "estimated"
                label_suffix = " *(AI estimated)*" if has_estimated else ""
                st.markdown(f"### Key figures ({year_label}){label_suffix}")

                if has_estimated:
                    st.warning(
                        "No public financial statements found in Regnskapsregisteret. "
                        "These figures are AI-generated estimates based on industry and company type. "
                        "Treat as indicative only."
                    )

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric(label="Turnover", value=fmt_mnok(regn.get("sum_driftsinntekter")))
                with col2:
                    st.metric(label="Net result", value=fmt_mnok(regn.get("aarsresultat")))
                with col3:
                    st.metric(label="Equity", value=fmt_mnok(regn.get("sum_egenkapital")))
                with col4:
                    eq_ratio = risk.get("equity_ratio")
                    eq_val = "–" if eq_ratio is None else f"{eq_ratio*100:,.1f} %".replace(",", " ")
                    st.metric(label="Equity ratio", value=eq_val)

                if has_real_regn:
                    st.markdown("#### Profit and loss")
                    pl_data = {
                        "Metric": [
                            "Sales revenue", "Total operating income", "Wage costs",
                            "Total operating costs", "Operating result", "Financial income",
                            "Financial costs", "Net financials", "Ordinary result before tax",
                            "Tax cost (ordinary)", "Extraordinary items",
                            "Tax on extraordinary result", "Annual result", "Total result",
                        ],
                        "Value": [
                            fmt_mnok(regn.get("salgsinntekter")),
                            fmt_mnok(regn.get("sum_driftsinntekter")),
                            fmt_mnok(regn.get("loennskostnad")),
                            fmt_mnok(regn.get("sum_driftskostnad")),
                            fmt_mnok(regn.get("driftsresultat")),
                            fmt_mnok(regn.get("sum_finansinntekt")),
                            fmt_mnok(regn.get("sum_finanskostnad")),
                            fmt_mnok(regn.get("netto_finans")),
                            fmt_mnok(regn.get("ordinaert_resultat_foer_skattekostnad")),
                            fmt_mnok(regn.get("ordinaert_resultat_skattekostnad")),
                            fmt_mnok(regn.get("ekstraordinaere_poster")),
                            fmt_mnok(regn.get("skattekostnad_ekstraord_resultat")),
                            fmt_mnok(regn.get("aarsresultat")),
                            fmt_mnok(regn.get("totalresultat")),
                        ],
                    }
                    st.table(pd.DataFrame(pl_data))

                    st.markdown("#### Balance sheet")
                    bal_data = {
                        "Metric": [
                            "Total assets", "Current assets", "Fixed assets", "Inventory",
                            "Receivables", "Investments", "Cash and bank", "Goodwill",
                            "Equity", "Paid-in equity", "Retained earnings",
                            "Total debt", "Short-term debt", "Long-term debt",
                        ],
                        "Value": [
                            fmt_mnok(regn.get("sum_eiendeler")),
                            fmt_mnok(regn.get("sum_omloepsmidler")),
                            fmt_mnok(regn.get("sum_anleggsmidler")),
                            fmt_mnok(regn.get("sum_varer")),
                            fmt_mnok(regn.get("sum_fordringer")),
                            fmt_mnok(regn.get("sum_investeringer")),
                            fmt_mnok(regn.get("sum_bankinnskudd_og_kontanter")),
                            fmt_mnok(regn.get("goodwill")),
                            fmt_mnok(regn.get("sum_egenkapital")),
                            fmt_mnok(regn.get("sum_innskutt_egenkapital")),
                            fmt_mnok(regn.get("sum_opptjent_egenkapital")),
                            fmt_mnok(regn.get("sum_gjeld")),
                            fmt_mnok(regn.get("sum_kortsiktig_gjeld")),
                            fmt_mnok(regn.get("sum_langsiktig_gjeld")),
                        ],
                    }
                    st.table(pd.DataFrame(bal_data))

            else:
                st.info("No public financial statements available for this organisation.")
                if st.button("Generate AI financial estimates"):
                    with st.spinner("Estimating financials with AI..."):
                        try:
                            est_resp = requests.get(
                                f"{API_BASE}/org/{selected_orgnr}/estimate", timeout=20
                            )
                            est_resp.raise_for_status()
                            st.session_state["estimated_financials"] = est_resp.json().get("estimated")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Estimate generation failed: {e}")

            # ── 6) Financial history ───────────────────────────
            years_data = (history_data or {}).get("years") or []
            if years_data:
                st.markdown("### Financial history")
                sorted_years = sorted(years_data, key=lambda x: x["year"])

                # ── Year-over-year summary table ──────────────
                st.markdown("#### Year-over-year overview")
                summary_rows = []
                prev = None
                for row in sorted_years:
                    rev = row.get("revenue")
                    net = row.get("net_result")
                    eq_ratio = row.get("equity_ratio")
                    curr_margin = (net / rev) if (net is not None and rev and rev > 0) else None

                    currency = row.get("currency", "NOK")
                    ccy_suffix = f" ({currency})" if currency and currency != "NOK" else ""
                    source_label = "PDF" if row.get("source") == "pdf" else "BRREG"
                    r = {
                        "Year": str(row["year"]),
                        f"Revenue (MNOK){ccy_suffix}": f"{rev/1e6:.1f}" if rev is not None else "–",
                        f"Net Result (MNOK){ccy_suffix}": f"{net/1e6:.1f}" if net is not None else "–",
                        "Margin %": f"{curr_margin*100:.1f}%" if curr_margin is not None else "–",
                        "Equity Ratio": f"{eq_ratio*100:.1f}%" if eq_ratio is not None else "–",
                        "Employees": str(row.get("antall_ansatte")) if row.get("antall_ansatte") else "–",
                        "Source": source_label,
                    }

                    if prev:
                        prev_rev = prev.get("revenue")
                        if rev is not None and prev_rev is not None and prev_rev != 0:
                            yoy = (rev - prev_rev) / abs(prev_rev) * 100
                            r["Rev YoY"] = f"{yoy:+.1f}%"
                        else:
                            r["Rev YoY"] = "–"

                        prev_net = prev.get("net_result")
                        prev_rev2 = prev.get("revenue")
                        prev_margin = (prev_net / prev_rev2) if (prev_net is not None and prev_rev2 and prev_rev2 > 0) else None
                        if curr_margin is not None and prev_margin is not None:
                            r["Margin Δ"] = f"{(curr_margin - prev_margin)*100:+.1f}pp"
                        else:
                            r["Margin Δ"] = "–"

                        prev_eq = prev.get("equity_ratio")
                        if eq_ratio is not None and prev_eq is not None:
                            r["Eq. Ratio Δ"] = f"{(eq_ratio - prev_eq)*100:+.1f}pp"
                        else:
                            r["Eq. Ratio Δ"] = "–"
                    else:
                        r["Rev YoY"] = "–"
                        r["Margin Δ"] = "–"
                        r["Eq. Ratio Δ"] = "–"

                    summary_rows.append(r)
                    prev = row

                st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

                # ── Charts (always shown, even for 1 year) ───────
                df_hist = pd.DataFrame(sorted_years).set_index("year")

                rev_cols = [c for c in ["revenue", "net_result"] if c in df_hist.columns]
                if rev_cols:
                    st.markdown("#### Revenue & net result (MNOK)")
                    chart_df = df_hist[rev_cols].copy()
                    for col in rev_cols:
                        chart_df[col] = chart_df[col] / 1_000_000
                    chart_df.columns = [c.replace("_", " ").title() for c in chart_df.columns]
                    st.bar_chart(chart_df)

                debt_cols = [c for c in ["short_term_debt", "long_term_debt"] if c in df_hist.columns]
                if debt_cols:
                    st.markdown("#### Debt breakdown (MNOK)")
                    debt_df = df_hist[debt_cols].copy()
                    for col in debt_cols:
                        debt_df[col] = debt_df[col] / 1_000_000
                    debt_df.columns = [c.replace("_", " ").title() for c in debt_df.columns]
                    st.bar_chart(debt_df)

                if len(sorted_years) > 1 and "equity_ratio" in df_hist.columns:
                    st.markdown("#### Equity ratio trend (%)")
                    eq_df = (df_hist[["equity_ratio"]].dropna() * 100).rename(
                        columns={"equity_ratio": "Equity ratio %"}
                    )
                    st.line_chart(eq_df)

                # ── Year drill-down ───────────────────────────
                st.markdown("#### Detailed view by year")
                available_years = [row["year"] for row in sorted_years]
                selected_year = st.selectbox(
                    "Select year",
                    available_years,
                    index=len(available_years) - 1,
                    key="hist_year_select",
                )
                year_row = next((r for r in sorted_years if r["year"] == selected_year), None)
                if year_row:
                    if year_row.get("antall_ansatte"):
                        st.caption(f"Employees: {year_row['antall_ansatte']}")
                    col_pl, col_bal = st.columns(2)
                    with col_pl:
                        st.markdown("**Profit & Loss**")
                        pl_items = [
                            ("Sales revenue",         year_row.get("salgsinntekter")),
                            ("Total operating income",year_row.get("revenue")),
                            ("Wage costs",            year_row.get("loennskostnad")),
                            ("Total operating costs", year_row.get("sum_driftskostnad")),
                            ("Operating result",      year_row.get("driftsresultat")),
                            ("Financial income",      year_row.get("sum_finansinntekt")),
                            ("Financial costs",       year_row.get("sum_finanskostnad")),
                            ("Net financials",        year_row.get("netto_finans")),
                            ("Result before tax",     year_row.get("ordinaert_resultat_foer_skattekostnad")),
                            ("Tax cost",              year_row.get("ordinaert_resultat_skattekostnad")),
                            ("Annual result",         year_row.get("net_result")),
                            ("Total result",          year_row.get("totalresultat")),
                        ]
                        st.table(pd.DataFrame({
                            "Metric": [x[0] for x in pl_items],
                            "Value":  [fmt_mnok(x[1]) for x in pl_items],
                        }))
                    with col_bal:
                        st.markdown("**Balance Sheet**")
                        bal_items = [
                            ("Total assets",      year_row.get("total_assets")),
                            ("Current assets",    year_row.get("sum_omloepsmidler")),
                            ("Fixed assets",      year_row.get("sum_anleggsmidler")),
                            ("Inventory",         year_row.get("sum_varer")),
                            ("Receivables",       year_row.get("sum_fordringer")),
                            ("Investments",       year_row.get("sum_investeringer")),
                            ("Cash & bank",       year_row.get("sum_bankinnskudd_og_kontanter")),
                            ("Goodwill",          year_row.get("goodwill")),
                            ("Equity",            year_row.get("equity")),
                            ("Paid-in equity",    year_row.get("sum_innskutt_egenkapital")),
                            ("Retained earnings", year_row.get("sum_opptjent_egenkapital")),
                            ("Total debt",        year_row.get("sum_gjeld")),
                            ("Short-term debt",   year_row.get("short_term_debt")),
                            ("Long-term debt",    year_row.get("long_term_debt")),
                        ]
                        st.table(pd.DataFrame({
                            "Metric": [x[0] for x in bal_items],
                            "Value":  [fmt_mnok(x[1]) for x in bal_items],
                        }))

            # ── Re-extract history ──────────────────────────────
            with st.expander("Re-extract all PDF history"):
                st.caption("Delete all stored PDF history for this company and re-run extraction with the latest AI prompt. Use this if data looks wrong or incomplete.")
                if st.button("Reset & Re-extract", key="reset_history_btn", type="secondary"):
                    try:
                        del_resp = requests.delete(f"{API_BASE}/org/{selected_orgnr}/history", timeout=10)
                        del_resp.raise_for_status()
                        n = del_resp.json().get("deleted_rows", 0)
                        st.success(f"Deleted {n} stored rows. Reload the company profile to trigger re-extraction.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Reset failed: {e}")

            # ── Add PDF report ─────────────────────────────────
            with st.expander("Add Annual Report PDF"):
                st.caption("Paste a public PDF URL to extract multi-year financial history using AI.")
                pdf_col1, pdf_col2 = st.columns([3, 1])
                with pdf_col1:
                    pdf_url_input = st.text_input("PDF URL", key="pdf_url_input", placeholder="https://...")
                with pdf_col2:
                    pdf_year_input = st.number_input("Year", min_value=2000, max_value=2030, value=2022, key="pdf_year_input")
                pdf_label_input = st.text_input("Label (optional)", key="pdf_label_input", placeholder="e.g. DNB Annual Report 2022")
                if st.button("Extract & Save", key="pdf_extract_btn"):
                    if pdf_url_input and pdf_year_input:
                        with st.spinner("Downloading PDF and extracting financials with AI... (may take 30s)"):
                            try:
                                pdf_resp = requests.post(
                                    f"{API_BASE}/org/{selected_orgnr}/pdf-history",
                                    json={"pdf_url": pdf_url_input, "year": int(pdf_year_input), "label": pdf_label_input},
                                    timeout=120,
                                )
                                pdf_resp.raise_for_status()
                                extracted = pdf_resp.json().get("extracted", {})
                                st.success(f"Extracted {pdf_year_input} data: Revenue {extracted.get('revenue', 'N/A')}, Currency {extracted.get('currency', 'NOK')}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"PDF extraction failed: {e}")
                    else:
                        st.warning("Please enter both a PDF URL and a year.")

            # ── 7) PEP / sanctions ─────────────────────────────
            st.markdown("### PEP / sanctions screening")
            if pep:
                st.write(f"Query name: {pep.get('query', org.get('navn', 'N/A'))}")
                st.write(f"Matches: {pep.get('hit_count', 0)}")
                hits = pep.get("hits") or []
                if hits:
                    for h in hits:
                        datasets = h.get("datasets") or []
                        topics = h.get("topics") or []
                        st.write(
                            f"- {h.get('name', 'N/A')} "
                            f"(schema: {h.get('schema', 'N/A')}, "
                            f"datasets: {', '.join(datasets) or 'n/a'}, "
                            f"topics: {', '.join(topics) or 'n/a'})"
                        )
                else:
                    st.write("No PEP/sanctions matches found in OpenSanctions.")
            else:
                st.write("No PEP/sanctions data available.")

            # ── 8) Analyst chat ────────────────────────────────
            st.markdown("---")
            st.subheader("Ask the risk analyst")
            question = st.text_input(
                "Question",
                placeholder="What are the main underwriting concerns for this company?",
                key="chat_input",
            )
            if st.button("Ask"):
                if question:
                    with st.spinner("Thinking..."):
                        try:
                            resp = requests.post(
                                f"{API_BASE}/org/{selected_orgnr}/chat",
                                json={"question": question},
                                timeout=30,
                            )
                            resp.raise_for_status()
                            st.session_state["chat_answer"] = resp.json()
                        except Exception as e:
                            st.error(f"Chat failed: {e}")
                else:
                    st.warning("Please enter a question.")

            if st.session_state["chat_answer"]:
                data = st.session_state["chat_answer"]
                st.markdown(f"**Q:** {data['question']}")
                st.info(data["answer"])

            try:
                chat_hist_resp = requests.get(
                    f"{API_BASE}/org/{selected_orgnr}/chat",
                    params={"limit": 10},
                    timeout=10,
                )
                chat_hist_resp.raise_for_status()
                chat_history = chat_hist_resp.json()
                if chat_history:
                    st.markdown("#### Previous questions")
                    for item in chat_history:
                        date = item.get("created_at", "")[:10]
                        st.markdown(f"**[{date}] Q:** {item['question']}")
                        st.write(item["answer"])
                        st.divider()
            except Exception:
                pass

            # ── 9) Raw JSON debug ──────────────────────────────
            with st.expander("Raw API responses"):
                st.json(prof)
                st.json(lic or {"orgnr": selected_orgnr, "licenses": []})


# ──────────────────────────────────────────────
# TAB 2 — Portfolio
# ──────────────────────────────────────────────
with tab_portfolio:
    st.subheader("Previously analysed companies")

    try:
        port_resp = requests.get(f"{API_BASE}/companies", params={"limit": 200}, timeout=10)
        port_resp.raise_for_status()
        companies = port_resp.json()
    except Exception as e:
        st.error(f"Failed to load portfolio: {e}")
        companies = []

    if not companies:
        st.info("No companies in portfolio yet. Search and view a company profile to add it here.")
    else:
        df = pd.DataFrame(companies)

        display_cols = {
            "orgnr": "Orgnr",
            "navn": "Company",
            "organisasjonsform_kode": "Form",
            "kommune": "Municipality",
            "naeringskode1_beskrivelse": "Industry",
            "regnskapsår": "Year",
            "omsetning": "Revenue (MNOK)",
            "sum_egenkapital": "Equity (MNOK)",
            "egenkapitalandel": "Equity ratio %",
            "risk_score": "Risk score",
        }
        df_display = df[[c for c in display_cols if c in df.columns]].copy()
        df_display.rename(columns=display_cols, inplace=True)

        for col in ["Revenue (MNOK)", "Equity (MNOK)"]:
            if col in df_display.columns:
                df_display[col] = (df_display[col] / 1_000_000).round(1)

        if "Equity ratio %" in df_display.columns:
            df_display["Equity ratio %"] = (df_display["Equity ratio %"] * 100).round(1)

        st.dataframe(df_display, use_container_width=True, hide_index=True)

        col_left, col_right = st.columns(2)

        with col_left:
            if "risk_score" in df.columns and df["risk_score"].notna().any():
                st.markdown("#### Risk score by company")
                risk_df = (
                    df[df["risk_score"].notna()]
                    .set_index("navn")[["risk_score"]]
                    .rename(columns={"risk_score": "Risk score"})
                    .sort_values("Risk score", ascending=False)
                    .head(20)
                )
                st.bar_chart(risk_df)

        with col_right:
            if "omsetning" in df.columns and df["omsetning"].notna().any():
                st.markdown("#### Revenue comparison (MNOK)")
                rev_df = (
                    df[df["omsetning"].notna()]
                    .set_index("navn")[["omsetning"]]
                    .rename(columns={"omsetning": "Revenue (MNOK)"})
                )
                rev_df["Revenue (MNOK)"] = (rev_df["Revenue (MNOK)"] / 1_000_000).round(1)
                rev_df = rev_df.sort_values("Revenue (MNOK)", ascending=False).head(20)
                st.bar_chart(rev_df)

        st.caption(f"{len(companies)} companies analysed. Data from BRREG public registry.")

# ── Agreements tab ────────────────────────────────────────────────────────────
INSURANCE_LINES = {
    "Skadeforsikringer": ["Ting / Avbrudd", "Bedrift-/Produktansvar", "Transport", "Motorvogn", "Prosjektforsikring"],
    "Financial Lines": ["Styreansvar (D&O)", "Kriminalitetsforsikring", "Profesjonsansvar", "Cyber", "Spesialforsikring"],
    "Personforsikringer": ["Yrkesskade", "Ulykke", "Gruppeliv", "Sykdom", "Reise", "Helseforsikring"],
    "Pensjonsforsikringer": ["Ytelsespensjon", "Innskuddspensjon", "Lederpensjon"],
    "Spesialdekning": ["Reassuranse", "Marine", "Energi", "Garanti"],
}

STANDARD_VILKAAR_TEXT = """
**Avtalens varighet**
Avtalen gjelder for ett år med automatisk fornyelse, med mindre den sies opp skriftlig av en av partene med fire måneders varsel før utløpsdato.

**Kommunikasjon**
All skriftlig kommunikasjon mellom partene skjer elektronisk, som utgangspunkt på norsk.

**Kundens informasjonsplikt**
Kunden plikter å gi megler korrekt og fullstendig informasjon om forsikringsgjenstandene og risikoen, samt opplyse om tidligere forsikringsforhold og anmeldte skader. Kunden plikter å gjøre løpende rede for endringer i risiko av betydning for forsikringsforholdene.

**Premiebetaling**
Forsikringsselskapets premiefaktura sendes, etter kontroll av megler, til Kunden for betaling direkte til forsikringsselskapet. Kunden er selv ansvarlig for renter og purregebyr ved for sen betaling, med mindre forsinkelsen skyldes forhold megler har kontroll over.

**Taushetsplikt**
Begge parter er forpliktet til å behandle konfidensiell informasjon med forsvarlig aktsomhet og ikke videreformidle denne til tredjeparter uten skriftlig samtykke.

**Oppsigelse**
Avtalen kan sies opp av begge parter med fire måneders skriftlig varsel. Ved manglende betaling av utestående honorar kan megler varsle oppsigelse. Ved vesentlig mislighold kan avtalen heves med umiddelbar virkning.

**Årlig avtalegjennomgang**
Partene skal gjennomgå avtaleomfang og foreta nødvendige oppdateringer minimum én gang per år.

**Ansvarsbegrensning**
Meglers ansvar for rådgivningsfeil er begrenset til NOK 25 000 000 per oppdrag og NOK 50 000 000 per kalenderår. Det svares ikke erstatning for indirekte tap. Ansvarsbegrensningen omfatter ikke grov uaktsomhet og forsett.

**Klageadgang og verneting**
Klager på meglers tjenester rettes skriftlig til megler. Uløste tvister søkes løst i minnelighet, og kan bringes inn for Klagenemnda for forsikrings- og gjenforsikringsmeglingsvirksomhet. Oslo tingrett er verneting.

**Konsesjon og eierskap**
Megler har konsesjon til å drive forsikringsmeglingsvirksomhet fra Finanstilsynet. Megler har verken direkte eller indirekte eierandel som utgjør mer enn 10 % av stemmeretten eller kapitalen i et forsikringsselskap, og tilsvarende gjelder motsatt vei.

**Forholdet til forsikringsavtaleloven**
Med mindre forholdet er omtalt i denne avtalen, fravikes de bestemmelser i forsikringsavtaleloven som det er adgang til ved forsikringsmegling med andre enn forbrukere og ved avtale om store risikoer.
""".strip()

with tab_sla:
    sla_sub_new, sla_sub_list, sla_sub_settings = st.tabs(
        ["New Agreement", "My Agreements", "Broker Settings"]
    )

    # ── Broker Settings ───────────────────────────────────────────────────────
    with sla_sub_settings:
        st.markdown("### Broker Settings")
        st.caption("These details are stamped on every agreement you create.")
        try:
            saved = requests.get(f"{API_BASE}/broker/settings", timeout=5).json()
        except Exception:
            saved = {}

        with st.form("broker_settings_form"):
            bs_firm   = st.text_input("Firm name *", value=saved.get("firm_name", ""))
            bs_orgnr  = st.text_input("Org.nr", value=saved.get("orgnr", "") or "")
            bs_addr   = st.text_area("Address", value=saved.get("address", "") or "", height=80)
            bs_col1, bs_col2 = st.columns(2)
            with bs_col1:
                bs_contact = st.text_input("Contact name", value=saved.get("contact_name", "") or "")
                bs_phone   = st.text_input("Phone", value=saved.get("contact_phone", "") or "")
            with bs_col2:
                bs_email   = st.text_input("Email", value=saved.get("contact_email", "") or "")
            save_btn = st.form_submit_button("Save settings", type="primary")

        if save_btn:
            if not bs_firm.strip():
                st.error("Firm name is required.")
            else:
                try:
                    r = requests.post(
                        f"{API_BASE}/broker/settings",
                        json={
                            "firm_name": bs_firm,
                            "orgnr": bs_orgnr or None,
                            "address": bs_addr or None,
                            "contact_name": bs_contact or None,
                            "contact_email": bs_email or None,
                            "contact_phone": bs_phone or None,
                        },
                        timeout=5,
                    )
                    r.raise_for_status()
                    st.success("Settings saved.")
                except Exception as e:
                    st.error(f"Failed to save: {e}")

    # ── New Agreement wizard ──────────────────────────────────────────────────
    with sla_sub_new:
        if "sla_step" not in st.session_state:
            st.session_state["sla_step"] = 1
        if "sla_data" not in st.session_state:
            st.session_state["sla_data"] = {}

        sla_d = st.session_state["sla_data"]
        step  = st.session_state["sla_step"]

        st.markdown(f"**Step {step} of 5** — " + [
            "", "Client details", "Services (Vedlegg A)",
            "Honorar (Vedlegg B)", "Standard terms", "Review & Generate",
        ][step])
        st.progress(step / 5)
        st.divider()

        def _next(): st.session_state["sla_step"] += 1
        def _back(): st.session_state["sla_step"] -= 1

        # Step 1 ── Client details
        if step == 1:
            st.markdown("#### Client details")
            orgnr_lookup = st.text_input(
                "Client org.nr",
                value=sla_d.get("client_orgnr", ""),
                placeholder="9 digits",
                key="sla_orgnr_input",
            )
            if st.button("Look up", key="sla_lookup"):
                if orgnr_lookup:
                    with st.spinner("Looking up..."):
                        try:
                            org_resp = requests.get(
                                f"{API_BASE}/org/{orgnr_lookup}", timeout=15
                            ).json()
                            org_info = org_resp.get("org", {})
                            sla_d["client_orgnr"] = orgnr_lookup
                            sla_d["client_navn"]  = org_info.get("navn", "")
                            addr_parts = [
                                org_info.get("adresse", ""),
                                org_info.get("poststed", ""),
                            ]
                            sla_d["client_adresse"] = ", ".join(p for p in addr_parts if p)
                            st.success(f"Found: {sla_d['client_navn']}")
                        except Exception as e:
                            st.error(f"Lookup failed: {e}")

            sla_d["client_navn"]    = st.text_input("Client name", value=sla_d.get("client_navn", ""))
            sla_d["client_adresse"] = st.text_area("Client address", value=sla_d.get("client_adresse", ""), height=80)
            sla_d["client_kontakt"] = st.text_input("Client contact person (name + email)", value=sla_d.get("client_kontakt", ""))

            if st.button("Next →", key="step1_next", type="primary"):
                if not sla_d.get("client_navn"):
                    st.error("Client name is required.")
                else:
                    _next()
                    st.rerun()

        # Step 2 ── Services
        elif step == 2:
            st.markdown("#### Services (Vedlegg A)")

            try:
                broker_cfg = requests.get(f"{API_BASE}/broker/settings", timeout=5).json()
            except Exception:
                broker_cfg = {}

            import datetime as _dt
            sla_d["start_date"] = str(
                st.date_input(
                    "Agreement start date",
                    value=_dt.date.fromisoformat(sla_d["start_date"]) if sla_d.get("start_date") else _dt.date.today(),
                )
            )
            sla_d["account_manager"] = st.text_input(
                "Account manager",
                value=sla_d.get("account_manager", broker_cfg.get("contact_name", "")),
            )

            st.markdown("**Insurance lines to be brokered:**")
            selected = set(sla_d.get("insurance_lines", []))
            for category, lines_list in INSURANCE_LINES.items():
                st.markdown(f"*{category}*")
                cols = st.columns(len(lines_list))
                for col, line in zip(cols, lines_list):
                    checked = col.checkbox(line, value=line in selected, key=f"line_{line}")
                    if checked:
                        selected.add(line)
                    else:
                        selected.discard(line)

            sla_d["insurance_lines"] = sorted(selected)
            sla_d["other_lines"] = st.text_input(
                "Other (specify)", value=sla_d.get("other_lines", "")
            )

            col_back, col_next = st.columns([1, 4])
            with col_back:
                if st.button("← Back", key="step2_back"):
                    _back(); st.rerun()
            with col_next:
                if st.button("Next →", key="step2_next", type="primary"):
                    if not sla_d.get("insurance_lines") and not sla_d.get("other_lines"):
                        st.error("Select at least one insurance line.")
                    else:
                        _next(); st.rerun()

        # Step 3 ── Honorar
        elif step == 3:
            st.markdown("#### Honorar (Vedlegg B)")
            st.caption("Set the fee arrangement for each selected insurance line.")

            all_lines = list(sla_d.get("insurance_lines", []))
            if sla_d.get("other_lines"):
                all_lines.append(sla_d["other_lines"])

            existing_fees = {f["line"]: f for f in sla_d.get("fee_structure", {}).get("lines", [])}
            fee_rows = []

            for line in all_lines:
                ef = existing_fees.get(line, {})
                st.markdown(f"**{line}**")
                col_type, col_rate = st.columns([2, 2])
                with col_type:
                    fee_type = st.selectbox(
                        "Fee type",
                        options=["provisjon", "fast", "ikke_avklart"],
                        format_func=lambda x: {"provisjon": "Provisjon (%)", "fast": "Fast honorar (NOK/år)", "ikke_avklart": "Ikke avklart"}[x],
                        index=["provisjon", "fast", "ikke_avklart"].index(ef.get("type", "provisjon")),
                        key=f"fee_type_{line}",
                    )
                with col_rate:
                    if fee_type != "ikke_avklart":
                        rate_label = "Rate (%)" if fee_type == "provisjon" else "Amount (NOK/år)"
                        rate = st.number_input(
                            rate_label,
                            min_value=0.0,
                            value=float(ef.get("rate", 0)),
                            key=f"fee_rate_{line}",
                        )
                    else:
                        rate = None
                fee_rows.append({"line": line, "type": fee_type, "rate": rate})

            sla_d["fee_structure"] = {"lines": fee_rows}

            col_back, col_next = st.columns([1, 4])
            with col_back:
                if st.button("← Back", key="step3_back"):
                    _back(); st.rerun()
            with col_next:
                if st.button("Next →", key="step3_next", type="primary"):
                    _next(); st.rerun()

        # Step 4 ── Standard terms + KYC
        elif step == 4:
            st.markdown("#### Standard terms")
            st.markdown(STANDARD_VILKAAR_TEXT)
            st.divider()

            st.markdown("#### Kundekontroll (KYC / AML)")
            st.caption("Norwegian law requires identity verification at agreement establishment. Please complete all fields below.")
            kyc_col1, kyc_col2 = st.columns(2)
            with kyc_col1:
                sla_d["kyc_id_type"] = st.selectbox(
                    "Type legitimasjon",
                    options=["Pass", "Nasjonalt ID-kort", "Bankkort med bilde", "Annet"],
                    index=["Pass", "Nasjonalt ID-kort", "Bankkort med bilde", "Annet"].index(
                        sla_d.get("kyc_id_type", "Pass")
                    ),
                    key="kyc_id_type_sel",
                )
                sla_d["kyc_id_ref"] = st.text_input(
                    "Dokumentreferanse / ID-nummer",
                    value=sla_d.get("kyc_id_ref", ""),
                    placeholder="e.g. N12345678",
                    key="kyc_id_ref_input",
                )
            with kyc_col2:
                sla_d["kyc_signatory"] = st.text_input(
                    "Navn på signatarens (den som signerer)",
                    value=sla_d.get("kyc_signatory", ""),
                    key="kyc_signatory_input",
                )
                sla_d["kyc_firmadato"] = st.text_input(
                    "Firmaattest dato (må være nyere enn 3 måneder)",
                    value=sla_d.get("kyc_firmadato", ""),
                    placeholder="DD.MM.ÅÅÅÅ",
                    key="kyc_firma_input",
                )

            st.divider()
            check1 = st.checkbox("Kunden bekrefter å ha lest og forstått vilkårene.")
            check2 = st.checkbox("Kunden bekrefter at kundekontroll (KYC/AML) er gjennomført og legitimasjon er fremlagt.")

            kyc_complete = bool(
                sla_d.get("kyc_id_type") and sla_d.get("kyc_id_ref") and
                sla_d.get("kyc_signatory") and sla_d.get("kyc_firmadato")
            )

            col_back, col_next = st.columns([1, 4])
            with col_back:
                if st.button("← Back", key="step4_back"):
                    _back(); st.rerun()
            with col_next:
                can_proceed = check1 and check2 and kyc_complete
                if not can_proceed and (check1 or check2):
                    if not kyc_complete:
                        st.caption("Fill in all KYC fields to continue.")
                if st.button("Next →", key="step4_next", type="primary", disabled=not can_proceed):
                    _next(); st.rerun()

        # Step 5 ── Review & Generate
        elif step == 5:
            st.markdown("#### Review")
            st.markdown(f"**Client:** {sla_d.get('client_navn')}  |  Org.nr: {sla_d.get('client_orgnr', '—')}")
            st.markdown(f"**Start date:** {sla_d.get('start_date')}  |  **Account manager:** {sla_d.get('account_manager')}")
            st.markdown(f"**Insurance lines:** {', '.join(sla_d.get('insurance_lines', []))}")
            if sla_d.get("other_lines"):
                st.markdown(f"**Other:** {sla_d['other_lines']}")
            if sla_d.get("kyc_signatory"):
                st.markdown(
                    f"**KYC:** {sla_d.get('kyc_signatory')} — "
                    f"{sla_d.get('kyc_id_type')} {sla_d.get('kyc_id_ref')} — "
                    f"Firmaattest: {sla_d.get('kyc_firmadato')}"
                )

            if sla_d.get("fee_structure", {}).get("lines"):
                fee_data = []
                for f in sla_d["fee_structure"]["lines"]:
                    type_label = {"provisjon": "Provisjon", "fast": "Fast honorar", "ikke_avklart": "Ikke avklart"}.get(f["type"], f["type"])
                    rate_str = f"{f['rate']} %" if f["type"] == "provisjon" and f.get("rate") else \
                               f"NOK {int(f['rate']):,}".replace(",", " ") if f["type"] == "fast" and f.get("rate") else "—"
                    fee_data.append({"Line": f["line"], "Fee type": type_label, "Rate / Amount": rate_str})
                st.dataframe(pd.DataFrame(fee_data), use_container_width=True, hide_index=True)

            st.divider()
            col_back, col_gen = st.columns([1, 4])
            with col_back:
                if st.button("← Back", key="step5_back"):
                    _back(); st.rerun()
            with col_gen:
                if st.button("Create Agreement & Download PDF", key="step5_generate", type="primary"):
                    with st.spinner("Creating agreement and generating PDF..."):
                        try:
                            create_resp = requests.post(
                                f"{API_BASE}/sla",
                                json={"form_data": sla_d},
                                timeout=15,
                            )
                            create_resp.raise_for_status()
                            sla_id = create_resp.json()["id"]

                            pdf_resp = requests.get(
                                f"{API_BASE}/sla/{sla_id}/pdf", timeout=15
                            )
                            pdf_resp.raise_for_status()

                            st.success(f"Agreement #{sla_id} created.")
                            st.download_button(
                                label="Download PDF",
                                data=pdf_resp.content,
                                file_name=f"tjenesteavtale_{sla_d.get('client_orgnr', sla_id)}.pdf",
                                mime="application/pdf",
                            )
                            # Reset wizard
                            st.session_state["sla_step"] = 1
                            st.session_state["sla_data"] = {}
                        except Exception as e:
                            st.error(f"Failed to create agreement: {e}")

    # ── My Agreements ─────────────────────────────────────────────────────────
    with sla_sub_list:
        st.markdown("### My Agreements")
        try:
            slas = requests.get(f"{API_BASE}/sla", timeout=5).json()
        except Exception:
            slas = []

        if not slas:
            st.info("No agreements yet. Create one in the 'New Agreement' tab.")
        else:
            status_color = {"active": "green", "draft": "grey", "terminated": "red"}
            for sla in slas:
                lines_str = ", ".join(sla.get("insurance_lines") or []) or "—"
                color = status_color.get(sla.get("status", "draft"), "grey")
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 1])
                    with c1:
                        st.markdown(f"**{sla.get('client_navn', '—')}**  `{sla.get('client_orgnr', '')}`")
                        st.caption(f"Start: {sla.get('start_date', '—')}  |  Lines: {lines_str}")
                    with c2:
                        st.markdown(f":{color}[{sla.get('status', 'draft').upper()}]")
                        st.caption(f"Created: {(sla.get('created_at') or '')[:10]}")
                    with c3:
                        try:
                            pdf_bytes = requests.get(
                                f"{API_BASE}/sla/{sla['id']}/pdf", timeout=15
                            ).content
                            st.download_button(
                                "PDF",
                                data=pdf_bytes,
                                file_name=f"tjenesteavtale_{sla.get('client_orgnr', sla['id'])}.pdf",
                                mime="application/pdf",
                                key=f"dl_sla_{sla['id']}",
                            )
                        except Exception:
                            st.button("PDF", disabled=True, key=f"dl_sla_err_{sla['id']}")
