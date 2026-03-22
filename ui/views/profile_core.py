"""Render organisation info, risk summary, narrative, and offers sections."""
import requests
import streamlit as st
import pandas as pd

from ui.config import API_BASE, T, fmt_mnok


def render_profile_core(
    selected_orgnr: str,
    org: dict,
    regn: dict,
    risk: dict,
    risk_summary: dict,
    pep: dict,
    lic,
    roles_data,
    konkurs_data,
    struktur_data,
    koordinater_data,
    benchmark_data,
    prof: dict,
) -> None:
    _lang = st.session_state.get("lang", "no")

    # ── 1) Organisation info + map ─────────────────────
    with st.expander(T("Organisation"), expanded=True):
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
                st.write(f"{T('Founded')}: {org.get('stiftelsesdato')}")
        with col_map:
            coords = (koordinater_data or {}).get("coordinates")
            if coords and coords.get("lat") and coords.get("lon"):
                map_df = pd.DataFrame({"lat": [coords["lat"]], "lon": [coords["lon"]]})
                st.map(map_df, zoom=13)
                if coords.get("adressetekst"):
                    st.caption(f"📍 {coords['adressetekst']}")
            else:
                st.info("Location not available")

        # Konsernstruktur (inside Organisation expander)
        _str = struktur_data or {}
        _parent = _str.get("parent")
        _subs = _str.get("sub_units") or []
        _total_subs = _str.get("total_sub_units", 0)
        if _parent or _subs:
            _ks_cols = st.columns(2)
            with _ks_cols[0]:
                if _parent:
                    st.markdown(
                        f"<div style='background:#F0F4FB;border:1px solid #C5D0E8;border-radius:8px;"
                        f"padding:10px 14px;font-size:0.86rem'>"
                        f"<div style='font-size:0.75rem;font-weight:700;letter-spacing:0.08em;"
                        f"text-transform:uppercase;color:#4A6FA5;margin-bottom:4px'>"
                        f"{'Morselskap' if _lang == 'no' else 'Parent company'}</div>"
                        f"<div style='font-weight:600;color:#2C3E50'>{_parent['navn']}</div>"
                        f"<div style='color:#6A6A6A;font-size:0.82rem'>"
                        f"{_parent.get('orgnr','')} · {_parent.get('kommune','')} · {_parent.get('organisasjonsform','')}"
                        f"</div></div>",
                        unsafe_allow_html=True,
                    )
            with _ks_cols[1]:
                if _subs:
                    _sub_label = "Underenheter" if _lang == "no" else "Sub-units"
                    _showing = "Viser" if _lang == "no" else "Showing"
                    st.markdown(
                        f"<div style='background:#F7F5F2;border:1px solid #D0CBC3;border-radius:8px;"
                        f"padding:10px 14px;font-size:0.86rem'>"
                        f"<div style='font-size:0.75rem;font-weight:700;letter-spacing:0.08em;"
                        f"text-transform:uppercase;color:#6A7F5A;margin-bottom:6px'>"
                        f"{_sub_label} ({_total_subs})</div>"
                        + "".join(
                            f"<div style='margin-bottom:3px'>🏢 <b>{s['navn']}</b>"
                            f"<span style='color:#888;font-size:0.8rem'> · {s.get('kommune','')}"
                            f"{(' · ' + str(s['antall_ansatte']) + ' ans.') if s.get('antall_ansatte') else ''}</span></div>"
                            for s in _subs[:6]
                        )
                        + (f"<div style='color:#999;font-size:0.8rem;margin-top:4px'>"
                           f"{_showing} 6 av {_total_subs}</div>" if _total_subs > 6 else "")
                        + "</div>",
                        unsafe_allow_html=True,
                    )

    # ── 1b) Bankruptcy & liquidation status ────────────
    kd = konkurs_data or {}
    _has_bankruptcy_flag = kd.get("konkurs") or kd.get("under_konkursbehandling") or kd.get("under_avvikling")
    with st.expander(T("Bankruptcy & liquidation"), expanded=bool(_has_bankruptcy_flag)):
        if kd.get("konkurs") or kd.get("under_konkursbehandling"):
            st.error(T("Bankruptcy proceedings"))
        elif kd.get("under_avvikling"):
            st.warning(T("Under liquidation"))
        elif konkurs_data is not None:
            st.success(T("No bankruptcy found"))
        else:
            st.info(T("Bankruptcy unavailable"))

    # ── 2) Board members ───────────────────────────────
    with st.expander(T("Board members"), expanded=True):
        members = (roles_data or {}).get("members") or []
        if members:
            active = [m for m in members if not m.get("resigned") and not m.get("deceased")]
            resigned = [m for m in members if m.get("resigned") or m.get("deceased")]
            if active:
                row_h = min(35 * len(active) + 38, 280)
                st.dataframe(
                    pd.DataFrame([
                        {
                            T("Role"): m["role"],
                            T("Name"): m["name"],
                            T("Born"): str(m["birth_year"]) if m.get("birth_year") else "–",
                        }
                        for m in active
                    ]),
                    use_container_width=True,
                    hide_index=True,
                    height=row_h,
                )
            if resigned:
                with st.expander(f"{T('Resigned / deceased')} ({len(resigned)})"):
                    st.dataframe(
                        pd.DataFrame([
                            {
                                T("Role"): m["role"],
                                T("Name"): m["name"],
                                "Status": ("Avdød" if st.session_state.get("lang") == "no" else "Deceased")
                                          if m.get("deceased")
                                          else ("Fratrådt" if st.session_state.get("lang") == "no" else "Resigned"),
                            }
                            for m in resigned
                        ]),
                        use_container_width=True,
                        hide_index=True,
                    )
        else:
            st.info("Ingen rolledata tilgjengelig." if st.session_state.get("lang") == "no" else "No role data available.")

    # ── 3) Risk summary ────────────────────────────────
    with st.expander(T("Risk profile"), expanded=True):
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric(label=T("Turnover (m)"), value=fmt_mnok(risk_summary.get("omsetning")))
        with col2:
            st.metric(label=T("Employees (m)"), value=risk_summary.get("antall_ansatte", "–"))
        with col3:
            eq_ratio = risk_summary.get("egenkapitalandel")
            eq_val = "–" if eq_ratio is None else f"{eq_ratio*100:,.1f} %".replace(",", " ")
            st.metric(label=T("Equity ratio (m)"), value=eq_val)
        with col4:
            raw_score = risk_summary.get("risk_score")
            MAX_SCORE = 20
            _BANDS = [
                (3,  T("Low"),       "🟢", "#2E7D32"),
                (7,  T("Moderate"),  "🟡", "#F57F17"),
                (12, T("High"),      "🟠", "#E65100"),
            ]
            def _score_band(s):
                if s is None: return ("–", "⬜", "#888")
                for cap, lbl, icon, col in _BANDS:
                    if s <= cap: return (lbl, icon, col)
                return (T("Very high"), "🔴", "#B71C1C")
            band_label, band_icon, band_color = _score_band(raw_score)
            score_display = f"{raw_score} / {MAX_SCORE}" if raw_score is not None else "–"
            st.metric(label=T("Risk score"), value=score_display,
                      delta=f"{band_icon} {band_label}", delta_color="off")
        with col5:
            pep_hits = risk_summary.get("pep_hits", 0)
            _pep_delta = T("Checked vs OpenSanctions") if pep_hits == 0 else f"⚠️ {pep_hits} {'treff' if _lang == 'no' else 'hits'}"
            st.metric(label=T("PEP hits"), value=pep_hits,
                      delta=_pep_delta, delta_color="off")

        st.caption(T("Data sources"))

        if raw_score is not None:
            pct = min(raw_score / MAX_SCORE, 1.0)
            st.markdown(
                f"<div style='margin:6px 0 2px 0;display:flex;align-items:center;gap:12px'>"
                f"<div style='flex:1;height:7px;background:#E8E4E0;border-radius:4px;overflow:hidden'>"
                f"<div style='width:{pct*100:.0f}%;height:100%;background:{band_color};border-radius:4px;transition:width 0.4s'></div>"
                f"</div>"
                f"<span style='font-size:12px;color:{band_color};font-weight:700;white-space:nowrap'>{band_label} — {raw_score}/{MAX_SCORE}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
            _price_notes_no = {
                T("Low"):       "Normalpremie forventes. Godt grunnlag for tegning.",
                T("Moderate"):  "Noe forhøyet premie mulig. Be om detaljer ved tegning.",
                T("High"):      "Forhøyet premie sannsynlig. Forsikringsselskaper kan kreve tilleggsopplysninger.",
                T("Very high"): "Betydelig risikopåslag ventet. Noen selskaper kan avslå tegning.",
            }
            _price_notes_en = {
                T("Low"):       "Standard premium expected. Good basis for underwriting.",
                T("Moderate"):  "Slightly elevated premium possible. Request additional details at underwriting.",
                T("High"):      "Elevated premium likely. Insurers may require additional information.",
                T("Very high"): "Significant risk loading expected. Some insurers may decline coverage.",
            }
            _price_notes = _price_notes_no if _lang == "no" else _price_notes_en
            st.caption(f"💡 {_price_notes.get(band_label, '')}")

        factors = risk_summary.get("risk_factors") or []
        if factors:
            CATEGORY_COLORS = {
                "Selskapsstatus": "🔴", "Økonomi": "🟠",
                "Bransje": "🟡", "Historikk": "🔵", "Eksponering": "🟣",
            }
            rows = [
                {
                    "Kategori": f"{CATEGORY_COLORS.get(f['category'], '⚪')} {f['category']}",
                    "Faktor": f["label"],
                    "Detalj": f.get("detail", ""),
                    "Poeng": f"+{f['points']}",
                }
                for f in factors
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            st.caption(f"Maks mulig score: {MAX_SCORE} poeng · Scoreskala: 0–3 Lav · 4–7 Moderat · 8–12 Høy · 13+ Svært høy")
        else:
            st.success("Ingen risikofaktorer identifisert.")

        # Industry benchmarks (inside risk expander)
        bench = (benchmark_data or {}).get("benchmark")
        if bench:
            st.markdown(f"#### {T('Industry benchmarks')}")
            st.caption(f"{T('Section label')} {bench.get('section')} — {bench.get('industry')} · {bench.get('source')}")
            eq_ratio_val = risk_summary.get("egenkapitalandel")
            b_eq_min = bench.get("typical_equity_ratio_min", 0)
            b_eq_max = bench.get("typical_equity_ratio_max", 0)
            b_mg_min = bench.get("typical_profit_margin_min", 0)
            b_mg_max = bench.get("typical_profit_margin_max", 0)
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                company_eq = f"{eq_ratio_val*100:.1f}%" if eq_ratio_val is not None else "N/A"
                industry_eq = f"{b_eq_min*100:.0f}–{b_eq_max*100:.0f}%"
                delta_eq = (
                    f"{(eq_ratio_val - (b_eq_min + b_eq_max) / 2)*100:+.1f}% {T('vs industry mid')}"
                    if eq_ratio_val is not None else None
                )
                st.metric(T("Equity ratio (bench)"), company_eq, delta=delta_eq, help=f"Industry typical: {industry_eq}")
            with col_b2:
                omsetning = risk_summary.get("omsetning")
                aarsresultat = (prof.get("regnskap") or {}).get("aarsresultat")
                if omsetning and aarsresultat is not None and omsetning > 0:
                    company_margin = aarsresultat / omsetning
                    industry_mg = f"{b_mg_min*100:.0f}–{b_mg_max*100:.0f}%"
                    delta_mg = company_margin - (b_mg_min + b_mg_max) / 2
                    st.metric(T("Profit margin"), f"{company_margin*100:.1f}%",
                              delta=f"{delta_mg*100:+.1f}% {T('vs industry mid')}", help=f"Industry typical: {industry_mg}")
                else:
                    st.metric(T("Profit margin"), "N/A", help=f"Industry typical: {b_mg_min*100:.0f}–{b_mg_max*100:.0f}%")

    # ── 4) Peer benchmark ──────────────────────────────
    with st.expander("📊 Bransje-benchmark (peer-sammenligning)", expanded=False):
        _pb_key = f"peer_benchmark_{selected_orgnr}"
        if _pb_key not in st.session_state:
            st.session_state[_pb_key] = None

        if st.button("Hent peer-benchmark", key="btn_peer_bench"):
            with st.spinner("Henter sammenligningsdata…"):
                try:
                    _r = requests.get(f"{API_BASE}/org/{selected_orgnr}/peer-benchmark", timeout=15)
                    st.session_state[_pb_key] = _r.json() if _r.ok else None
                    if not _r.ok:
                        st.error(f"Feil: {_r.status_code}")
                except Exception as _e:
                    st.error(str(_e))

        _pb = st.session_state.get(_pb_key)
        if _pb:
            peer_count = _pb.get("peer_count", 0)
            source = _pb.get("source", "")
            _src_lbl = f"Basert på {peer_count} selskaper i samme bransje" if source == "db_peers" else "SSB-bransjegjennomsnitt (få peers)"
            st.caption(f"NACE-seksjon **{_pb.get('nace_section', '?')}** · {_src_lbl}")
            metrics = _pb.get("metrics", {})
            pb_c1, pb_c2, pb_c3 = st.columns(3)
            _m = metrics.get("equity_ratio", {})
            _company_eq = _m.get("company")
            _peer_eq = _m.get("peer_avg")
            _delta_eq = f"{(_company_eq - _peer_eq)*100:+.1f}pp vs bransje" if _company_eq is not None and _peer_eq is not None else None
            pb_c1.metric("Egenkapitalandel",
                f"{_company_eq*100:.1f}%" if _company_eq is not None else "–",
                delta=_delta_eq)
            _m = metrics.get("revenue", {})
            _company_rev = _m.get("company")
            _peer_rev = _m.get("peer_avg")
            _delta_rev = f"{(_company_rev - _peer_rev)/1e6:+.0f} MNOK vs bransje" if _company_rev is not None and _peer_rev is not None else None
            pb_c2.metric("Omsetning",
                fmt_mnok(_company_rev) if _company_rev is not None else "–",
                delta=_delta_rev)
            _m = metrics.get("risk_score", {})
            _company_rs = _m.get("company")
            _peer_rs = _m.get("peer_avg")
            _delta_rs = f"{(_company_rs - _peer_rs):+.1f} vs bransje" if _company_rs is not None and _peer_rs is not None else None
            pb_c3.metric("Risikoscore",
                str(_company_rs) if _company_rs is not None else "–",
                delta=_delta_rs)

    # ── 5) Insurance needs estimator ───────────────────
    with st.expander("📋 Forsikringsbehovsestimator", expanded=False):
        _needs_key = f"insurance_needs_{selected_orgnr}"
        if _needs_key not in st.session_state:
            st.session_state[_needs_key] = None

        if st.button("Analyser forsikringsbehov", key="btn_ins_needs"):
            with st.spinner("Beregner forsikringsbehov…"):
                try:
                    _r = requests.get(f"{API_BASE}/org/{selected_orgnr}/insurance-needs", timeout=30)
                    st.session_state[_needs_key] = _r.json() if _r.ok else None
                    if not _r.ok:
                        st.error(f"Feil: {_r.status_code}")
                except Exception as _e:
                    st.error(str(_e))

        _ins_data = st.session_state.get(_needs_key)
        if _ins_data:
            narrative = _ins_data.get("narrative", "")
            if narrative:
                st.info(narrative)
            needs_list = _ins_data.get("needs", [])
            if needs_list:
                _PRIORITY_ICON = {"Kritisk": "🔴", "Anbefalt": "🟡", "Vurder": "⚪"}
                rows = [
                    {
                        "Prioritet": f"{_PRIORITY_ICON.get(n['priority'], '')} {n['priority']}",
                        "Forsikringstype": n["type"],
                        "Estimert dekningsbehov": fmt_mnok(n["estimated_coverage_nok"]),
                        "Begrunnelse": n["reason"],
                    }
                    for n in needs_list
                ]
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.info("Ingen forsikringsbehov identifisert.")

    # ── 5) Insurance recommendation ────────────────────
    with st.expander(T("Insurance recommendation"), expanded=False):
        if "risk_offer" not in st.session_state:
            st.session_state["risk_offer"] = None

        col_offer, col_pdf = st.columns([3, 1])
        with col_offer:
            if st.button(T("Generate recommendation"), key="gen_risk_offer"):
                with st.spinner(T("Analysing risk profile")):
                    try:
                        r = requests.post(
                            f"{API_BASE}/org/{selected_orgnr}/risk-offer",
                            params={"lang": st.session_state.get("lang", "no")},
                            timeout=90,
                        )
                        if r.ok:
                            st.session_state["risk_offer"] = r.json()
                        else:
                            st.error(f"Feil: {r.text}")
                    except Exception as e:
                        st.error(str(e))
        with col_pdf:
            pdf_url = f"{API_BASE}/org/{selected_orgnr}/risk-report/pdf"
            st.markdown(f"[Last ned risikorapport (PDF)]({pdf_url})", unsafe_allow_html=False)

        offer = st.session_state.get("risk_offer")
        if offer:
            if offer.get("sammendrag"):
                st.info(offer["sammendrag"])
            anbefalinger = offer.get("anbefalinger", [])
            if anbefalinger:
                df_offer = pd.DataFrame(anbefalinger)
                col_map2 = {"type": "Forsikringstype", "prioritet": "Prioritet",
                            "anbefalt_sum": "Anbefalt dekningssum", "begrunnelse": "Begrunnelse"}
                df_offer = df_offer.rename(columns={k: v for k, v in col_map2.items() if k in df_offer.columns})
                st.dataframe(df_offer, use_container_width=True, hide_index=True)
            if offer.get("total_premieanslag"):
                st.caption(f"Estimert premieanslag: **{offer['total_premieanslag']}**")

            _pdf_payload = {
                "anbefalinger": offer.get("anbefalinger", []),
                "total_premieanslag": offer.get("total_premieanslag", ""),
                "sammendrag": offer.get("sammendrag", ""),
            }
            _dl_col, _save_col = st.columns(2)
            with _dl_col:
                if st.button(T("Download tilbud PDF"), key="dl_tilbud"):
                    with st.spinner(T("Generating PDF")):
                        try:
                            r = requests.post(
                                f"{API_BASE}/org/{selected_orgnr}/forsikringstilbud/pdf",
                                json=_pdf_payload, timeout=90,
                            )
                            if r.ok:
                                st.session_state["forsikringstilbud_pdf"] = r.content
                                st.rerun()
                            else:
                                st.error(f"Feil: {r.text}")
                        except Exception as e:
                            st.error(str(e))
            with _save_col:
                if st.button(T("Save to library"), key="save_tilbud"):
                    with st.spinner(T("Generating and saving")):
                        try:
                            r = requests.post(
                                f"{API_BASE}/org/{selected_orgnr}/forsikringstilbud/pdf",
                                json=_pdf_payload, params={"save": "true"}, timeout=90,
                            )
                            if r.ok:
                                st.session_state["forsikringstilbud_pdf"] = r.content
                                st.success(T("Saved to library"))
                                st.rerun()
                            else:
                                st.error(f"Feil: {r.text}")
                        except Exception as e:
                            st.error(str(e))

            if st.session_state.get("forsikringstilbud_pdf"):
                st.download_button(
                    label=T("Download generated PDF"),
                    data=st.session_state["forsikringstilbud_pdf"],
                    file_name=f"forsikringstilbud_{selected_orgnr}.pdf",
                    mime="application/pdf",
                    key="dl_tilbud_btn",
                )
            if st.button(T("Clear recommendation"), key="clear_offer"):
                st.session_state["risk_offer"] = None
                st.rerun()

    # ── 5) AI risk narrative ───────────────────────────
    with st.expander(T("AI risk narrative"), expanded=False):
        if st.session_state["narrative"]:
            st.info(st.session_state["narrative"])
            if st.button(T("Regenerate narrative")):
                st.session_state["narrative"] = None
                st.rerun()
        else:
            if st.button(T("Generate risk narrative")):
                with st.spinner(T("Analysing with AI")):
                    try:
                        nav_resp = requests.post(
                            f"{API_BASE}/org/{selected_orgnr}/narrative",
                            params={"lang": _lang}, timeout=60,
                        )
                        nav_resp.raise_for_status()
                        st.session_state["narrative"] = nav_resp.json().get("narrative")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Narrative generation failed: {e}")

    # ── 6) Insurance offers ────────────────────────────
    with st.expander(T("Insurance offers"), expanded=True):
        stored_offers = []
        try:
            stored_offers = requests.get(
                f"{API_BASE}/org/{selected_orgnr}/offers", timeout=6
            ).json()
        except Exception:
            pass

        if stored_offers:
            _n_offers = len(stored_offers)
            st.caption(f"{_n_offers} {'tilbud lagret i databasen' if _lang == 'no' else 'offers stored in database'}")
            for offer in stored_offers:
                col_name, col_date, col_dl, col_del = st.columns([3, 2, 1, 1])
                with col_name:
                    st.write(f"**{offer['insurer_name']}**  `{offer['filename']}`")
                with col_date:
                    st.caption(offer.get("uploaded_at", "")[:10])
                with col_dl:
                    try:
                        pdf_bytes = requests.get(
                            f"{API_BASE}/org/{selected_orgnr}/offers/{offer['id']}/pdf", timeout=10,
                        ).content
                        st.download_button(
                            "Last ned", data=pdf_bytes, file_name=offer["filename"],
                            mime="application/pdf", key=f"dl_offer_{offer['id']}",
                        )
                    except Exception:
                        st.write("–")
                with col_del:
                    if st.button(f"🗑 {T('Delete')}", key=f"del_offer_{offer['id']}", type="secondary"):
                        requests.delete(f"{API_BASE}/org/{selected_orgnr}/offers/{offer['id']}", timeout=6)
                        st.rerun()

            st.session_state["offers_uploaded_names"] = [o["filename"] for o in stored_offers]
            sel_ids = [o["id"] for o in stored_offers]
            _analyse_label = (
                f"Analyser alle {len(stored_offers)} lagrede tilbud med AI"
                if _lang == "no" else f"Analyse all {len(stored_offers)} stored offers with AI"
            )
            if st.button(_analyse_label, key="compare_stored_btn", type="primary"):
                with st.spinner(T("Analysing offers")):
                    try:
                        comp_resp = requests.post(
                            f"{API_BASE}/org/{selected_orgnr}/offers/compare-stored",
                            json=sel_ids, timeout=120,
                        )
                        comp_resp.raise_for_status()
                        st.session_state["offers_comparison"] = comp_resp.json()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Analyse feilet: {e}")

        with st.expander(T("Upload new offers")):
            uploaded_files = st.file_uploader(
                T("Select PDF offers"), type=["pdf"],
                accept_multiple_files=True, key="offers_uploader",
            )
            if uploaded_files:
                st.caption(f"{len(uploaded_files)} fil(er) valgt: {', '.join(f.name for f in uploaded_files)}")
                col_save, col_analyze = st.columns(2)
                with col_save:
                    if st.button(T("Save to database"), key="save_offers_btn"):
                        with st.spinner("Lagrer..."):
                            try:
                                files_payload = [
                                    ("files", (f.name, f.getvalue(), "application/pdf"))
                                    for f in uploaded_files
                                ]
                                save_resp = requests.post(
                                    f"{API_BASE}/org/{selected_orgnr}/offers",
                                    files=files_payload, timeout=60,
                                )
                                save_resp.raise_for_status()
                                n = len(save_resp.json().get("saved", []))
                                st.success(f"{n} tilbud lagret!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Lagring feilet: {e}")
                with col_analyze:
                    if st.button(T("Analyse without saving"), key="compare_offers_btn"):
                        with st.spinner("Analyserer..."):
                            try:
                                files_payload = [
                                    ("files", (f.name, f.getvalue(), "application/pdf"))
                                    for f in uploaded_files
                                ]
                                comp_resp = requests.post(
                                    f"{API_BASE}/org/{selected_orgnr}/offers/compare",
                                    files=files_payload, timeout=120,
                                )
                                comp_resp.raise_for_status()
                                st.session_state["offers_comparison"] = comp_resp.json()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Analyse feilet: {e}")

        if st.session_state.get("offers_comparison"):
            comp = st.session_state["offers_comparison"]
            st.markdown("#### AI-analyse av tilbud")
            offer_names = comp.get("offers", [])
            st.caption(f"Basert på {len(offer_names)} tilbud: {', '.join(offer_names)}")
            st.markdown(comp.get("comparison", ""))
            if st.button(T("Clear analysis"), key="clear_comparison_btn"):
                st.session_state["offers_comparison"] = None
                st.session_state["offers_uploaded_names"] = []
                st.rerun()

        # Coverage gap analysis
        st.markdown(f"#### {T('Coverage gap analysis')}")
        st.caption(T("Coverage gap caption"))
        if st.button(T("Analyse coverage gap"), key="coverage_gap_btn", type="secondary"):
            with st.spinner("Analyserer..."):
                try:
                    gap_resp = requests.post(
                        f"{API_BASE}/org/{selected_orgnr}/coverage-gap",
                        params={"lang": st.session_state.get("lang", "no")}, timeout=60,
                    )
                    gap_resp.raise_for_status()
                    st.session_state["coverage_gap"] = gap_resp.json()
                    st.rerun()
                except Exception as e:
                    st.error(f"Feil: {e}")

        gap = st.session_state.get("coverage_gap")
        if gap:
            if gap.get("status") == "no_offers":
                st.warning(gap.get("message", "Ingen tilbud lastet opp."))
            else:
                dekket = gap.get("dekket") or []
                mangler = gap.get("mangler") or []
                if dekket:
                    st.markdown(f"**{T('Covered by offers')}**")
                    for item in dekket:
                        st.success(item)
                if mangler:
                    st.markdown(f"**{T('Missing coverage')}**")
                    for item in mangler:
                        st.error(item)
                if gap.get("anbefaling"):
                    st.info(gap["anbefaling"])
                if st.button(T("Clear"), key="clear_gap_btn"):
                    st.session_state["coverage_gap"] = None
                    st.rerun()
