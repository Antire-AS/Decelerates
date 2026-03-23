"""Render key figures, financial history, PEP, chat, and notes sections."""
import requests
import streamlit as st
import pandas as pd

from ui.config import API_BASE, T, fmt_mnok


def render_profile_financials(
    selected_orgnr: str,
    org: dict,
    regn: dict,
    risk: dict,
    risk_summary: dict,
    pep: dict,
    history_data,
    prof: dict,
    lic,
) -> None:
    _lang = st.session_state.get("lang", "no")

    # ── 5) Key figures ─────────────────────────────────
    has_real_regn = bool(
        prof.get("regnskap") and prof["regnskap"].get("regnskapsår") is not None
    )
    has_estimated = bool(regn and regn.get("synthetic"))

    with st.expander(T("Key figures"), expanded=True):
        if has_real_regn or has_estimated:
            year_label = regn.get("regnskapsår") or "estimated"
            label_suffix = " *(AI estimated)*" if has_estimated else ""
            st.markdown(f"**{T('Key figures')} ({year_label}){label_suffix}**")

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
                st.markdown(f"#### {T('Profit and loss')}")
                _pl_rows = [
                    (T("Sales revenue"),          regn.get("salgsinntekter")),
                    (T("Total operating income"), regn.get("sum_driftsinntekter")),
                    (T("Wage costs"),             regn.get("loennskostnad")),
                    (T("Total operating costs"),  regn.get("sum_driftskostnad")),
                    (T("Operating result"),       regn.get("driftsresultat")),
                    (T("Financial income"),       regn.get("sum_finansinntekt")),
                    (T("Financial costs"),        regn.get("sum_finanskostnad")),
                    (T("Net financials"),         regn.get("netto_finans")),
                    (T("Result before tax"),      regn.get("ordinaert_resultat_foer_skattekostnad")),
                    (T("Tax cost"),               regn.get("ordinaert_resultat_skattekostnad")),
                    (T("Annual result"),          regn.get("aarsresultat")),
                    (T("Total result"),           regn.get("totalresultat")),
                ]
                _pl_rows = [(k, v) for k, v in _pl_rows if v is not None]
                st.table(pd.DataFrame({T("Value"): {k: fmt_mnok(v) for k, v in _pl_rows}}))
                st.caption(T("Source BRREG"))

                st.markdown(f"#### {T('Balance sheet')}")
                _bal_rows = [
                    (T("Total assets"),      regn.get("sum_eiendeler")),
                    (T("Current assets"),    regn.get("sum_omloepsmidler")),
                    (T("Fixed assets"),      regn.get("sum_anleggsmidler")),
                    (T("Inventory"),         regn.get("sum_varer")),
                    (T("Receivables"),       regn.get("sum_fordringer")),
                    (T("Investments"),       regn.get("sum_investeringer")),
                    (T("Cash & bank"),       regn.get("sum_bankinnskudd_og_kontanter")),
                    (T("Goodwill"),          regn.get("goodwill")),
                    (T("Equity"),            regn.get("sum_egenkapital")),
                    (T("Paid-in equity"),    regn.get("sum_innskutt_egenkapital")),
                    (T("Retained earnings"), regn.get("sum_opptjent_egenkapital")),
                    (T("Total debt"),        regn.get("sum_gjeld")),
                    (T("Short-term debt"),   regn.get("sum_kortsiktig_gjeld")),
                    (T("Long-term debt"),    regn.get("sum_langsiktig_gjeld")),
                ]
                _bal_rows = [(k, v) for k, v in _bal_rows if v is not None]
                st.table(pd.DataFrame({T("Value"): {k: fmt_mnok(v) for k, v in _bal_rows}}))
                st.caption(T("Source BRREG"))
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
    with st.expander(T("Financial history"), expanded=bool(years_data)):
        if years_data:
            sorted_years = sorted(years_data, key=lambda x: x["year"])

            _currencies_used = {r.get("currency", "NOK") for r in sorted_years if r.get("currency") and r.get("currency") != "NOK"}
            _nb_rates: dict = {}
            for _ccy in _currencies_used:
                try:
                    _rate_resp = requests.get(f"{API_BASE}/norgesbank/rate/{_ccy}", timeout=5)
                    if _rate_resp.ok:
                        _nb_rates[_ccy] = _rate_resp.json().get("nok_rate", 1.0)
                except Exception:
                    pass
            if _nb_rates:
                _rate_lines = ", ".join(f"1 {c} = {r:.4f} NOK" for c, r in _nb_rates.items())
                _nb_note = (
                    f"Beløp i fremmed valuta vises i opprinnelig valuta. Dagskurs (Norges Bank): {_rate_lines}"
                    if _lang == "no" else
                    f"Amounts in foreign currency shown in original currency. Current rate (Norges Bank): {_rate_lines}"
                )
                st.info(f"💱 {_nb_note}")

            st.markdown(f"#### {T('Year-over-year overview')}")
            summary_rows = []
            prev = None
            for row in sorted_years:
                rev = row.get("revenue")
                net = row.get("net_result")
                eq_ratio = row.get("equity_ratio")
                curr_margin = (net / rev) if (net is not None and rev and rev > 0) else None
                currency = row.get("currency", "NOK")
                ccy_label = currency if currency else "NOK"
                source_label = "PDF" if row.get("source") == "pdf" else "BRREG"
                r = {
                    "Year": str(row["year"]),
                    f"Revenue (M{ccy_label})": f"{rev/1e6:.1f}" if rev is not None else "–",
                    f"Net Result (M{ccy_label})": f"{net/1e6:.1f}" if net is not None else "–",
                    "Margin %": f"{curr_margin*100:.1f}%" if curr_margin is not None else "–",
                    "Equity Ratio": f"{eq_ratio*100:.1f}%" if eq_ratio is not None else "–",
                    "Employees": str(row.get("antall_ansatte")) if row.get("antall_ansatte") else "–",
                    "Source": source_label,
                }
                if prev:
                    prev_rev = prev.get("revenue")
                    r["Rev YoY"] = (
                        f"{(rev - prev_rev) / abs(prev_rev) * 100:+.1f}%"
                        if rev is not None and prev_rev is not None and prev_rev != 0 else "–"
                    )
                    prev_net = prev.get("net_result")
                    prev_rev2 = prev.get("revenue")
                    prev_margin = (prev_net / prev_rev2) if (prev_net is not None and prev_rev2 and prev_rev2 > 0) else None
                    r["Margin Δ"] = (
                        f"{(curr_margin - prev_margin)*100:+.1f}pp"
                        if curr_margin is not None and prev_margin is not None else "–"
                    )
                    prev_eq = prev.get("equity_ratio")
                    r["Eq. Ratio Δ"] = (
                        f"{(eq_ratio - prev_eq)*100:+.1f}pp"
                        if eq_ratio is not None and prev_eq is not None else "–"
                    )
                else:
                    r["Rev YoY"] = r["Margin Δ"] = r["Eq. Ratio Δ"] = "–"
                summary_rows.append(r)
                prev = row

            st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)
            st.caption(T("Source history"))

            df_hist = pd.DataFrame(sorted_years).set_index("year")
            rev_cols = [c for c in ["revenue", "net_result"] if c in df_hist.columns]
            if rev_cols:
                st.markdown(f"#### {T('Revenue & net result (MNOK)')}")
                chart_df = df_hist[rev_cols].copy()
                for col in rev_cols:
                    chart_df[col] = chart_df[col] / 1_000_000
                chart_df.columns = [c.replace("_", " ").title() for c in chart_df.columns]
                st.bar_chart(chart_df)

            debt_cols = [c for c in ["short_term_debt", "long_term_debt"] if c in df_hist.columns]
            if debt_cols:
                st.markdown(f"#### {T('Debt breakdown (MNOK)')}")
                debt_df = df_hist[debt_cols].copy()
                for col in debt_cols:
                    debt_df[col] = debt_df[col] / 1_000_000
                debt_df.columns = [c.replace("_", " ").title() for c in debt_df.columns]
                st.bar_chart(debt_df)

            if len(sorted_years) > 1 and "equity_ratio" in df_hist.columns:
                st.markdown(f"#### {T('Equity ratio trend (%)')}")
                eq_df = (df_hist[["equity_ratio"]].dropna() * 100).rename(
                    columns={"equity_ratio": "Equity ratio %"}
                )
                st.line_chart(eq_df)

            st.markdown(f"#### {T('Detailed view by year')}")
            available_years = [row["year"] for row in sorted_years]
            selected_year = st.selectbox(
                T("Select year"), available_years,
                index=len(available_years) - 1, key="hist_year_select",
            )
            year_row = next((r for r in sorted_years if r["year"] == selected_year), None)
            if year_row:
                if year_row.get("antall_ansatte"):
                    st.caption(f"{T('Employees')}: {year_row['antall_ansatte']}")
                col_pl, col_bal = st.columns(2)
                with col_pl:
                    st.markdown(f"**{T('Profit & Loss')}**")
                    pl_items = [
                        (T("Sales revenue"),         year_row.get("salgsinntekter")),
                        (T("Total operating income"),year_row.get("revenue")),
                        (T("Wage costs"),            year_row.get("loennskostnad")),
                        (T("Total operating costs"), year_row.get("sum_driftskostnad")),
                        (T("Operating result"),      year_row.get("driftsresultat")),
                        (T("Financial income"),      year_row.get("sum_finansinntekt")),
                        (T("Financial costs"),       year_row.get("sum_finanskostnad")),
                        (T("Net financials"),        year_row.get("netto_finans")),
                        (T("Result before tax"),     year_row.get("ordinaert_resultat_foer_skattekostnad")),
                        (T("Tax cost"),              year_row.get("ordinaert_resultat_skattekostnad")),
                        (T("Annual result"),         year_row.get("net_result")),
                        (T("Total result"),          year_row.get("totalresultat")),
                    ]
                    pl_items = [(k, v) for k, v in pl_items if v is not None]
                    st.table(pd.DataFrame({T("Value"): {k: fmt_mnok(v) for k, v in pl_items}}))
                with col_bal:
                    st.markdown(f"**{T('Balance sheet')}**")
                    bal_items = [
                        (T("Total assets"),      year_row.get("total_assets")),
                        (T("Current assets"),    year_row.get("sum_omloepsmidler")),
                        (T("Fixed assets"),      year_row.get("sum_anleggsmidler")),
                        (T("Inventory"),         year_row.get("sum_varer")),
                        (T("Receivables"),       year_row.get("sum_fordringer")),
                        (T("Investments"),       year_row.get("sum_investeringer")),
                        (T("Cash & bank"),       year_row.get("sum_bankinnskudd_og_kontanter")),
                        (T("Goodwill"),          year_row.get("goodwill")),
                        (T("Equity"),            year_row.get("equity")),
                        (T("Paid-in equity"),    year_row.get("sum_innskutt_egenkapital")),
                        (T("Retained earnings"), year_row.get("sum_opptjent_egenkapital")),
                        (T("Total debt"),        year_row.get("sum_gjeld")),
                        (T("Short-term debt"),   year_row.get("short_term_debt")),
                        (T("Long-term debt"),    year_row.get("long_term_debt")),
                    ]
                    bal_items = [(k, v) for k, v in bal_items if v is not None]
                    st.table(pd.DataFrame({T("Value"): {k: fmt_mnok(v) for k, v in bal_items}}))
                _src_label = T("Source PDF") if year_row.get("source") == "pdf" else T("Source BRREG short")
                _src_word = "Kilde" if _lang == "no" else "Source"
                _yr_word = "År" if _lang == "no" else "Year"
                st.caption(f"{_src_word}: {_src_label} · {_yr_word} {selected_year}")
        else:
            st.info("Ingen regnskapshistorikk tilgjengelig." if _lang == "no" else "No financial history available.")

        with st.expander(T("Re-extract PDF history")):
            st.caption(T("Re-extract caption"))
            if st.button(T("Reset and re-extract"), key="reset_history_btn", type="secondary"):
                try:
                    del_resp = requests.delete(f"{API_BASE}/org/{selected_orgnr}/history", timeout=10)
                    del_resp.raise_for_status()
                    n = del_resp.json().get("deleted_rows", 0)
                    st.success(f"Deleted {n} stored rows. Reload the company profile to trigger re-extraction.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Reset failed: {e}")

        with st.expander(T("Add Annual Report PDF")):
            st.caption(T("Add PDF caption"))
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
    _pep_hits = (pep or {}).get("hit_count", 0)
    with st.expander(T("PEP screening"), expanded=bool(_pep_hits)):
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
                st.write(T("No PEP matches"))
        else:
            st.write(T("No PEP data"))

    # ── 8) Analyst chat ────────────────────────────────
    with st.expander(T("Ask analyst"), expanded=False):
        question = st.text_input(
            T("Question label"),
            placeholder=T("Question placeholder"),
            key="chat_input",
        )
        if st.button("Ask"):
            if question:
                with st.spinner("Thinking..."):
                    try:
                        resp = requests.post(
                            f"{API_BASE}/org/{selected_orgnr}/chat",
                            json={"question": question}, timeout=30,
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
                f"{API_BASE}/org/{selected_orgnr}/chat", params={"limit": 10}, timeout=10,
            )
            chat_hist_resp.raise_for_status()
            chat_history = chat_hist_resp.json()
            if chat_history:
                st.markdown(f"#### {T('Previous questions')}")
                for item in chat_history:
                    date = item.get("created_at", "")[:10]
                    st.markdown(f"**[{date}] Q:** {item['question']}")
                    st.write(item["answer"])
                    st.divider()
        except Exception:
            pass

    # ── 9) Broker notes ────────────────────────────────
    with st.expander(T("Notes"), expanded=False):
        _notes_refresh = st.session_state.get("notes_refresh", 0)
        try:
            _notes_resp = requests.get(f"{API_BASE}/org/{selected_orgnr}/broker-notes", timeout=8)
            _existing_notes = _notes_resp.json() if _notes_resp.ok else []
        except Exception:
            _existing_notes = []

        _note_text = st.text_area(
            T("Notes"), height=80, placeholder=T("Note placeholder"),
            key=f"note_input_{_notes_refresh}", label_visibility="collapsed",
        )
        if st.button(T("Save note"), key=f"save_note_{_notes_refresh}"):
            if _note_text and _note_text.strip():
                try:
                    requests.post(
                        f"{API_BASE}/org/{selected_orgnr}/broker-notes",
                        json={"text": _note_text.strip()}, timeout=8,
                    )
                    st.session_state["notes_refresh"] = _notes_refresh + 1
                    st.rerun()
                except Exception as e:
                    st.error(f"Lagring feilet: {e}")
            else:
                st.warning("Skriv noe først.")

        if _existing_notes:
            for _note in _existing_notes:
                _nc1, _nc2 = st.columns([9, 1])
                with _nc1:
                    _date_str = (_note.get("created_at") or "")[:10]
                    st.markdown(f"**{_date_str}** — {_note['text']}")
                with _nc2:
                    if st.button("🗑", key=f"del_note_{_note['id']}"):
                        try:
                            requests.delete(
                                f"{API_BASE}/org/{selected_orgnr}/broker-notes/{_note['id']}", timeout=8,
                            )
                            st.session_state["notes_refresh"] = _notes_refresh + 1
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))

    # ── 10) Raw JSON debug ─────────────────────────────
    with st.expander("Raw API responses"):
        st.json(prof)
        st.json(lic or {"orgnr": selected_orgnr, "licenses": []})


# Alias used by sub-tab rendering in search.py
render_okonomi_section = render_profile_financials
