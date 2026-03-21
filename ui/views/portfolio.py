"""Portfolio tab — named company lists with risk analysis and AI chat."""
import json
from datetime import date as _date, timedelta as _td

import pandas as pd
import requests
import streamlit as st

from ui.config import API_BASE


# ── Helpers ───────────────────────────────────────────────────────────────────

def _risk_badge(score) -> str:
    if score is None:
        return "–"
    if score <= 3:
        return "🟢 Lav"
    if score <= 7:
        return "🟡 Moderat"
    if score <= 11:
        return "🔴 Høy"
    return "🚨 Svært høy"


def _fmt_mnok(val) -> str:
    if val is None:
        return "–"
    return f"{round(val / 1_000_000, 1)} MNOK"


def _fetch(path: str, params: dict | None = None):
    try:
        r = requests.get(f"{API_BASE}{path}", params=params, timeout=10)
        return r.json() if r.ok else []
    except Exception:
        return []


def _post(path: str, json: dict) -> dict | None:
    try:
        r = requests.post(f"{API_BASE}{path}", json=json, timeout=30)
        return r.json() if r.ok else None
    except Exception:
        return None


def _delete(path: str) -> bool:
    try:
        r = requests.delete(f"{API_BASE}{path}", timeout=10)
        return r.ok
    except Exception:
        return False


# ── Overview metrics (all previously analysed companies) ─────────────────────

def _render_overview(companies: list, all_slas: list) -> None:
    scores = [c["risk_score"] for c in companies if c.get("risk_score") is not None]
    high_risk = sum(1 for s in scores if s >= 8)
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0
    active_slas = sum(1 for s in all_slas if s.get("status") == "active")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Selskaper analysert", len(companies))
    m2.metric("Gj.snitt risikoscore", avg_score)
    m3.metric("Høyrisikoselskaper", high_risk)
    m4.metric("Aktive SLA-avtaler", active_slas)

    # Renewal alerts
    renewals = []
    for s in all_slas:
        sd = s.get("start_date")
        if not sd:
            continue
        try:
            renewal = _date.fromisoformat(sd[:10]) + _td(days=365)
            days_left = (renewal - _date.today()).days
            if 0 <= days_left <= 90:
                renewals.append((s, renewal, days_left))
        except Exception:
            pass
    if renewals:
        with st.expander(f"⚠️ Fornyelser innen 90 dager ({len(renewals)} avtale(r))", expanded=True):
            for s, renewal, days_left in sorted(renewals, key=lambda x: x[2]):
                st.warning(
                    f"**{s.get('client_navn', s.get('client_orgnr', '?'))}** "
                    f"— fornyelse {renewal.strftime('%d.%m.%Y')} ({days_left} dager)"
                )

    df = pd.DataFrame(companies)
    display_cols = {
        "orgnr": "Orgnr", "navn": "Selskap", "kommune": "Kommune",
        "naeringskode1_beskrivelse": "Bransje", "regnskapsår": "År",
        "risk_score": "Risikoscore",
    }
    df_disp = df[[c for c in display_cols if c in df.columns]].copy()
    df_disp.rename(columns=display_cols, inplace=True)
    if "Risikoscore" in df_disp.columns:
        df_disp.insert(0, "Risikonivå", df["risk_score"].apply(_risk_badge))
        df_disp = df_disp.sort_values("Risikoscore", ascending=False, na_position="last")
    st.dataframe(df_disp, use_container_width=True, hide_index=True)

    col_left, col_right = st.columns(2)
    with col_left:
        if "risk_score" in df.columns and df["risk_score"].notna().any():
            st.markdown("#### Risikoscore")
            st.bar_chart(
                df[df["risk_score"].notna()].set_index("navn")[["risk_score"]]
                .rename(columns={"risk_score": "Score"})
                .sort_values("Score", ascending=False).head(20)
            )
    with col_right:
        if "sum_driftsinntekter" in df.columns and df["sum_driftsinntekter"].notna().any():
            st.markdown("#### Omsetning (MNOK)")
            rev = df[df["sum_driftsinntekter"].notna()].copy()
            rev["MNOK"] = (rev["sum_driftsinntekter"] / 1_000_000).round(1)
            st.bar_chart(rev.set_index("navn")[["MNOK"]].sort_values("MNOK", ascending=False).head(20))


# ── Named portfolio management ────────────────────────────────────────────────

def _render_portfolio_selector() -> int | None:
    portfolios = _fetch("/portfolio")

    col_sel, col_new = st.columns([3, 1])
    with col_new:
        if st.button("+ Ny portefølje", use_container_width=True):
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

    # Show description
    selected_meta = next((p for p in portfolios if p["id"] == selected_id), None)
    if selected_meta and selected_meta.get("description"):
        st.caption(selected_meta["description"])

    return selected_id


def _render_seed_norway(portfolio_id: int) -> None:
    """One-click: stream BRREG lookups for Norway's Top 100 companies live."""
    with st.expander("🇳🇴 Seed med Norges topp 100 selskaper", expanded=False):
        st.caption(
            "Søker opp ~100 av Norges største selskaper (Equinor, DNB, Mowi, Telenor, Yara, osv.) "
            "direkte fra BRREG og legger dem til porteføljen — live."
        )
        if st.button("▶ Start live seeding", key=f"seed_norway_{portfolio_id}", type="primary"):
            added, skipped, not_found = 0, 0, 0
            with st.status("Søker opp Norges topp 100 selskaper...", expanded=True) as status:
                try:
                    with requests.get(
                        f"{API_BASE}/portfolio/{portfolio_id}/seed-norway/stream",
                        stream=True, timeout=300,
                    ) as resp:
                        for raw_line in resp.iter_lines():
                            if not raw_line:
                                continue
                            try:
                                ev = json.loads(raw_line)
                            except Exception:
                                continue
                            etype = ev.get("type")
                            name = ev.get("name", "")
                            idx, total = ev.get("index", ""), ev.get("total", "")
                            if etype == "start":
                                status.write(f"Starter oppslag av **{total}** selskaper i BRREG...")
                            elif etype == "searching":
                                status.write(f"🔍 `{idx}/{total}` &nbsp; Søker: **{name}**...")
                            elif etype == "added":
                                status.write(f"✅ `{idx}/{total}` &nbsp; **{ev.get('name')}** ({ev.get('orgnr')})")
                                added += 1
                            elif etype == "skipped":
                                status.write(f"⏭ `{idx}/{total}` &nbsp; {name} — allerede i portefølje")
                                skipped += 1
                            elif etype == "not_found":
                                status.write(f"⚠️ `{idx}/{total}` &nbsp; {name} — ikke funnet i BRREG")
                                not_found += 1
                            elif etype == "error":
                                status.write(f"❌ `{idx}/{total}` &nbsp; {name} — {ev.get('error', 'feil')}")
                                not_found += 1
                            elif etype == "complete":
                                status.update(
                                    label=f"✅ Ferdig — {added} lagt til, {skipped} allerede i portefølje, {not_found} ikke funnet",
                                    state="complete",
                                )
                except Exception as exc:
                    status.update(label=f"Feil: {exc}", state="error")
            st.rerun()


def _render_pdf_enrichment(portfolio_id: int, rows: list) -> None:
    """Trigger background 5-year PDF annual report discovery for the whole portfolio."""
    covered = sum(1 for r in rows if r.get("revenue") is not None)
    missing_pdf = len(rows) - covered

    st.markdown("#### 📄 PDF-årsrapporter (5-årig historikk)")
    st.caption(
        f"{covered}/{len(rows)} selskaper har regnskapsdata. "
        f"Klikk nedenfor for å starte automatisk søk etter årsrapport-PDF-er fra nettet for alle selskaper. "
        "Dette kjører i bakgrunnen og kan ta 30–90 minutter for en full portefølje."
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        if st.button(
            f"🗂 Start PDF-innhenting for 5-årig historikk ({len(rows)} selskaper)",
            key=f"enrich_pdfs_{portfolio_id}",
        ):
            result = _post(f"/portfolio/{portfolio_id}/enrich-pdfs", {})
            if result:
                st.success(
                    f"✅ PDF-innhenting startet for **{result.get('queued', 0)}** selskaper i bakgrunnen. "
                    "Kom tilbake om 30–90 min for oppdaterte tall."
                )
            else:
                st.error("Kunne ikke starte PDF-innhenting.")
    with col2:
        st.caption("Bruker Claude + Gemini til å finne og lese PDF-er fra selskapenes investor relations-sider.")


def _render_add_company(portfolio_id: int, existing_orgnrs: set) -> None:
    with st.expander("Legg til selskap", expanded=False):
        all_companies = _fetch("/companies", params={"limit": 500})
        available = [c for c in all_companies if c["orgnr"] not in existing_orgnrs]

        tab_search, tab_manual = st.tabs(["Fra analyserte selskaper", "Orgnr manuelt"])

        with tab_search:
            if available:
                options = {f"{c['navn']} ({c['orgnr']})": c["orgnr"] for c in available}
                chosen = st.selectbox("Velg selskap", list(options.keys()), key=f"port_add_sel_{portfolio_id}")
                if st.button("Legg til", key=f"port_add_btn_{portfolio_id}"):
                    _post(f"/portfolio/{portfolio_id}/companies", {"orgnr": options[chosen]})
                    st.rerun()
            else:
                st.caption("Alle analyserte selskaper er allerede i denne porteføljen.")

        with tab_manual:
            manual_orgnr = st.text_input(
                "Organisasjonsnummer (9 siffer)",
                key=f"port_manual_{portfolio_id}",
                placeholder="923609016",
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Legg til", key=f"port_manual_add_{portfolio_id}") and manual_orgnr.strip():
                    _post(f"/portfolio/{portfolio_id}/companies", {"orgnr": manual_orgnr.strip()})
                    st.rerun()
            with c2:
                if st.button("Hent & legg til", key=f"port_manual_fetch_{portfolio_id}") and manual_orgnr.strip():
                    with st.spinner("Henter data fra BRREG..."):
                        requests.get(f"{API_BASE}/org/{manual_orgnr.strip()}", timeout=30)
                        _post(f"/portfolio/{portfolio_id}/companies", {"orgnr": manual_orgnr.strip()})
                    st.rerun()


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
    st.dataframe(df_display.sort_values("Score", ascending=False), use_container_width=True, hide_index=True)

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


# ── Portfolio chat (Financial mode + Knowledge mode) ──────────────────────────

def _render_portfolio_chat(portfolio_id: int) -> None:
    st.markdown("---")
    st.markdown("#### AI-analyse")

    mode = st.radio(
        "Modus",
        ["Finansiell analyse", "Forsikringskunnskap"],
        horizontal=True,
        key=f"chat_mode_{portfolio_id}",
        help=(
            "**Finansiell analyse** — spørsmål besvart basert på selskapenes regnskapstall og risikoscore.  \n"
            "**Forsikringskunnskap** — spørsmål besvart basert på kursvideoer og forsikringsdokumenter."
        ),
    )

    placeholders = {
        "Finansiell analyse": "Hvilke selskaper har høyest risiko? Hvem har svakest egenkapitalandel?",
        "Forsikringskunnskap": "Hva sier kurset om meglerens ansvar? Hva er god forretningsskikk?",
    }

    question = st.text_input(
        "Spørsmål til AI",
        placeholder=placeholders[mode],
        key=f"portfolio_chat_q_{portfolio_id}",
    )

    if st.button("Spør", key=f"portfolio_chat_btn_{portfolio_id}") and question.strip():
        with st.spinner("Analyserer..."):
            if mode == "Finansiell analyse":
                result = _post(f"/portfolio/{portfolio_id}/chat", {"question": question})
            else:
                result = _post("/knowledge/chat", {"question": question})

        if result and result.get("answer"):
            st.markdown(result["answer"])
            sources = result.get("sources") or []
            if sources:
                if mode == "Finansiell analyse":
                    st.caption(f"Basert på data fra: {', '.join(str(s) for s in sources[:8])}")
                else:
                    readable = []
                    for s in sources[:4]:
                        parts = s.split("::")
                        readable.append(f"{parts[1]} — {parts[3]}" if len(parts) >= 4 else s)
                    st.caption("Kilder: " + " · ".join(readable))
        else:
            st.warning("Ingen svar fra AI-tjenesten.")


# ── Live ingest ───────────────────────────────────────────────────────────────

def _render_live_ingest(portfolio_id: int, rows: list) -> None:
    """Live-streaming company lookup with animated progress via st.status()."""
    needs_fetch = [r for r in rows if r.get("risk_score") is None or r.get("navn") == r.get("orgnr")]
    already_done = len(rows) - len(needs_fetch)

    col_btn, col_del = st.columns([3, 1])
    with col_btn:
        btn_label = (
            f"🔍 Søk opp alle {len(rows)} selskaper live"
            if needs_fetch else
            f"♻️ Oppdater alle {len(rows)} selskaper"
        )
        if st.button(btn_label, key=f"live_ingest_{portfolio_id}", type="primary"):
            done, skipped, failed = 0, 0, 0
            with st.status(f"Søker opp {len(rows)} selskaper...", expanded=True) as status:
                try:
                    with requests.get(
                        f"{API_BASE}/portfolio/{portfolio_id}/ingest/stream",
                        stream=True,
                        timeout=300,
                    ) as resp:
                        for raw_line in resp.iter_lines():
                            if not raw_line:
                                continue
                            try:
                                event = json.loads(raw_line)
                            except Exception:
                                continue

                            etype = event.get("type")
                            navn = event.get("navn") or event.get("orgnr", "")
                            idx = event.get("index", "")
                            total = event.get("total", "")
                            score = event.get("risk_score")
                            score_str = f"  —  risikoscore **{score}**" if score is not None else ""

                            if etype == "start":
                                status.write(f"Starter innhenting av **{total}** selskaper...")
                            elif etype == "searching":
                                status.write(f"🔍 `{idx}/{total}` &nbsp; Søker opp **{navn}**...")
                            elif etype == "done":
                                status.write(f"✅ `{idx}/{total}` &nbsp; **{navn}**{score_str}")
                                done += 1
                            elif etype == "skipped":
                                status.write(f"⏭ `{idx}/{total}` &nbsp; {navn} — allerede hentet")
                                skipped += 1
                            elif etype == "error":
                                status.write(f"❌ `{idx}/{total}` &nbsp; {navn} — {event.get('error', 'feil')}")
                                failed += 1
                            elif etype == "complete":
                                status.update(
                                    label=f"✅ Ferdig — {done} hentet, {skipped} hoppet over, {failed} feilet",
                                    state="complete",
                                )
                except Exception as exc:
                    status.update(label=f"Feil under innhenting: {exc}", state="error")
            st.rerun()

    with col_del:
        if st.button("🗑 Slett portefølje", key=f"del_port_{portfolio_id}", type="secondary"):
            st.session_state[f"confirm_del_{portfolio_id}"] = True

    if st.session_state.get(f"confirm_del_{portfolio_id}"):
        st.warning("Er du sikker? Dette sletter porteføljen permanent.")
        c1, c2 = st.columns(2)
        if c1.button("Ja, slett", key=f"confirm_del_yes_{portfolio_id}"):
            _delete(f"/portfolio/{portfolio_id}")
            st.session_state.pop("selected_portfolio_id", None)
            st.session_state.pop(f"confirm_del_{portfolio_id}", None)
            st.rerun()
        if c2.button("Avbryt", key=f"confirm_del_no_{portfolio_id}"):
            st.session_state.pop(f"confirm_del_{portfolio_id}", None)
            st.rerun()


# ── Main ──────────────────────────────────────────────────────────────────────

def render_portfolio_tab() -> None:
    overview_tab, named_tab = st.tabs(["Oversikt", "Mine porteføljer"])

    with overview_tab:
        companies = _fetch("/companies", params={"limit": 200})
        all_slas = _fetch("/sla")
        if not companies:
            st.info("Ingen selskaper analysert ennå. Søk opp et selskap i Selskapsøk-fanen.")
        else:
            _render_overview(companies, all_slas)

    with named_tab:
        portfolio_id = _render_portfolio_selector()
        if not portfolio_id:
            return

        rows = _render_risk_table(portfolio_id)
        existing_orgnrs = {r["orgnr"] for r in rows}

        # Seed + add companies
        _render_seed_norway(portfolio_id)
        _render_add_company(portfolio_id, existing_orgnrs)

        if rows:
            _render_charts(rows)
            st.markdown("---")
            _render_pdf_enrichment(portfolio_id, rows)
            _render_portfolio_chat(portfolio_id)

        st.markdown("---")
        _render_live_ingest(portfolio_id, rows)
