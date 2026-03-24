"""SLA agreements tab: new agreement wizard, list, and broker settings."""
import datetime as _dt

import requests
import streamlit as st
import pandas as pd

from ui.config import API_BASE

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


def render_sla_tab() -> None:
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
                st.dataframe(pd.DataFrame(fee_data), width="stretch", hide_index=True)

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
                    c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
                    with c1:
                        st.markdown(f"**{sla.get('client_navn', '—')}**  `{sla.get('client_orgnr', '')}`")
                        st.caption(f"Start: {sla.get('start_date', '—')}  |  Lines: {lines_str}")
                    with c2:
                        st.markdown(f":{color}[{sla.get('status', 'draft').upper()}]")
                        signed_at = sla.get("signed_at")
                        if signed_at:
                            st.caption(f"Signert: {signed_at[:10]} av {sla.get('signed_by') or '–'}")
                        else:
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
                    with c4:
                        if not sla.get("signed_at"):
                            if st.button("Signer", key=f"sign_sla_{sla['id']}", type="primary"):
                                try:
                                    r = requests.patch(
                                        f"{API_BASE}/sla/{sla['id']}/sign",
                                        json={"signed_by": "broker"},
                                        timeout=8,
                                    )
                                    if r.ok:
                                        st.toast("Avtale signert!")
                                        st.rerun()
                                    else:
                                        st.error(f"Feil: {r.text}")
                                except Exception as e:
                                    st.error(str(e))
