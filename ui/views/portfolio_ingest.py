"""Portfolio ingestion — live BRREG lookup, company add, CSV import, seed Norway, PDF enrichment."""
import json

import requests
import streamlit as st

from ui.config import API_BASE
from ui.views.portfolio_helpers import _delete, _fetch, _post


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

    st.markdown("#### 📄 PDF-årsrapporter (5-årig historikk)")
    st.caption(
        f"{covered}/{len(rows)} selskaper har regnskapsdata. "
        "Klikk nedenfor for å starte automatisk søk etter årsrapport-PDF-er fra nettet for alle selskaper. "
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

        tab_search, tab_manual, tab_csv = st.tabs(
            ["Fra analyserte selskaper", "Orgnr manuelt", "CSV-import"]
        )

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

        with tab_csv:
            st.caption("Last opp en CSV-fil med én kolonne med header `orgnr` (eller én kolonne uten header). Maks 500 rader.")
            csv_file = st.file_uploader("Velg CSV-fil", type=["csv"], key=f"port_csv_{portfolio_id}")
            fetch_brreg = st.checkbox("Hent BRREG-data for hvert selskap", value=True, key=f"port_csv_fetch_{portfolio_id}")
            if st.button("Start import", key=f"port_csv_import_{portfolio_id}", disabled=csv_file is None):
                progress = st.empty()
                log = st.empty()
                lines = []
                try:
                    resp = requests.post(
                        f"{API_BASE}/batch/import",
                        files={"file": (csv_file.name, csv_file.getvalue(), "text/csv")},
                        params={"portfolio_id": portfolio_id, "fetch_brreg": str(fetch_brreg).lower()},
                        stream=True, timeout=300,
                    )
                    for raw in resp.iter_lines():
                        if not raw:
                            continue
                        evt = json.loads(raw)
                        if evt.get("type") == "start":
                            progress.info(f"Importerer {evt['total']} orgnr… ({evt.get('invalid', 0)} ugyldige ignorert)")
                        elif evt.get("type") == "done":
                            lines.append(f"✅ {evt['orgnr']} — {evt.get('navn', '')}")
                            log.markdown("\n".join(lines[-12:]))
                        elif evt.get("type") == "error":
                            lines.append(f"❌ {evt['orgnr']} — {evt.get('error', '')}")
                            log.markdown("\n".join(lines[-12:]))
                        elif evt.get("type") == "complete":
                            progress.success(
                                f"Import fullført — {evt['added']} lagt til, "
                                f"{evt['failed']} feilet, {evt.get('invalid', 0)} ugyldige."
                            )
                            st.rerun()
                except Exception as e:
                    st.error(str(e))


def _render_live_ingest(portfolio_id: int, rows: list) -> None:
    """Live-streaming company lookup with animated progress via st.status()."""
    needs_fetch = [r for r in rows if r.get("risk_score") is None or r.get("navn") == r.get("orgnr")]

    include_pdfs = st.checkbox(
        "Inkluder PDF-søk fra selskapets nettside (årsrapporter + kvartalsrapporter)",
        key=f"include_pdfs_{portfolio_id}",
        help=(
            "Når aktivert søker agenten (Claude/Gemini) opp investor relations-siden for hvert selskap, "
            "finner årsrapport- og kvartalsrapport-PDF-er, og starter ekstraksjon av 5-årig historikk i bakgrunnen. "
            "Tar 20–60 sek per selskap — anbefalt for ≤20 selskaper om gangen."
        ),
    )

    col_btn, col_del = st.columns([3, 1])
    with col_btn:
        btn_label = (
            f"🔍 Søk opp alle {len(rows)} selskaper live"
            if needs_fetch else
            f"♻️ Oppdater alle {len(rows)} selskaper"
        )
        if st.button(btn_label, key=f"live_ingest_{portfolio_id}", type="primary"):
            done, skipped, failed = 0, 0, 0
            stream_params = {"include_pdfs": "true"} if include_pdfs else {}
            with st.status(f"Søker opp {len(rows)} selskaper...", expanded=True) as status:
                try:
                    with requests.get(
                        f"{API_BASE}/portfolio/{portfolio_id}/ingest/stream",
                        params=stream_params, stream=True, timeout=600,
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
                            elif etype == "pdf_searching":
                                yrs = ", ".join(str(y) for y in event.get("missing_years", []))
                                status.write(f"🌐 `{idx}/{total}` &nbsp; Søker PDF-rapporter for **{navn}** (år: {yrs})...")
                            elif etype == "pdf_found":
                                if event.get("new"):
                                    yrs = ", ".join(str(y) for y in event.get("new_years", []))
                                    status.write(f"📄 `{idx}/{total}` &nbsp; **{navn}** — fant årsrapporter for {yrs}")
                                else:
                                    status.write(f"📋 `{idx}/{total}` &nbsp; **{navn}** — PDF-er allerede hentet")
                            elif etype == "pdf_none":
                                status.write(f"⚠️ `{idx}/{total}` &nbsp; **{navn}** — ingen årsrapport-PDF funnet på nett")
                            elif etype == "pdf_error":
                                status.write(f"❌ `{idx}/{total}` &nbsp; **{navn}** — PDF-søk feilet: {event.get('error', '')[:80]}")
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
