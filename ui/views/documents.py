"""Document library and comparison tab."""
import base64

import requests
import streamlit as st

from ui.config import API_BASE


def render_documents_tab() -> None:
    # ── Session state ──
    for key, default in [
        ("doc_chat_id", None),
        ("doc_chat_title", ""),
        ("doc_chat_history", []),
        ("doc_comparison", None),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    docs_sub_lib, docs_sub_cmp = st.tabs(["Dokumentbibliotek", "Sammenlign vilkår"])

    # ── Fetch document list (shared by both sub-tabs) ──
    try:
        docs_resp = requests.get(f"{API_BASE}/insurance-documents", timeout=10)
        all_docs = docs_resp.json() if docs_resp.ok else []
    except Exception:
        all_docs = []

    with docs_sub_lib:
        with st.expander("Last opp nytt forsikringsdokument", expanded=False):
            up_file = st.file_uploader("Velg PDF", type=["pdf"], key="doc_upload")
            col1, col2 = st.columns(2)
            with col1:
                up_title = st.text_input("Tittel", placeholder="Forsikringsavtale Næringsliv 2026")
                up_category = st.selectbox(
                    "Kategori",
                    ["næringslivsforsikring", "personalforsikring", "reise", "annet"],
                )
            with col2:
                up_insurer = st.text_input("Forsikringsselskap", placeholder="If, Gjensidige...")
                up_year = st.number_input("År", min_value=2000, max_value=2100, value=2026, step=1)
                up_period = st.radio("Periode", ["aktiv", "historisk"], horizontal=True)

            if st.button("Last opp", disabled=up_file is None or not up_title) and up_file is not None:
                try:
                    resp = requests.post(
                        f"{API_BASE}/insurance-documents",
                        files={"file": (up_file.name, up_file.getvalue(), "application/pdf")},
                        data={
                            "title": up_title,
                            "category": up_category,
                            "insurer": up_insurer,
                            "year": str(up_year),
                            "period": up_period,
                        },
                        timeout=30,
                    )
                    if resp.ok:
                        st.success(f"Lastet opp: {resp.json().get('title')}")
                        st.rerun()
                    else:
                        st.error(f"Feil: {resp.text}")
                except Exception as e:
                    st.error(str(e))

        st.markdown("### Dokumentbibliotek")

        if "doc_open_id" not in st.session_state:
            st.session_state["doc_open_id"] = None
        if "doc_keypoints_cache" not in st.session_state:
            st.session_state["doc_keypoints_cache"] = {}

        if not all_docs:
            st.info("Ingen dokumenter lastet opp ennå.")
        else:
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                filter_cat = st.selectbox("Kategori", ["Alle"] + list({d["category"] for d in all_docs if d.get("category")}), key="doc_filter_cat")
            with col_f2:
                filter_year = st.selectbox("År", ["Alle"] + sorted({str(d["year"]) for d in all_docs if d.get("year")}, reverse=True), key="doc_filter_year")
            with col_f3:
                filter_period = st.selectbox("Periode", ["Alle", "aktiv", "historisk"], key="doc_filter_period")

            filtered_docs = [
                d for d in all_docs
                if (filter_cat == "Alle" or d.get("category") == filter_cat)
                and (filter_year == "Alle" or str(d.get("year")) == filter_year)
                and (filter_period == "Alle" or d.get("period") == filter_period)
            ]

            for d in filtered_docs:
                is_open = st.session_state["doc_open_id"] == d["id"]
                period_badge = "🟢" if d.get("period") == "aktiv" else "⬜"
                c1, c2, c3, c4 = st.columns([5, 3, 1, 1])
                with c1:
                    st.markdown(f"**{d['title']}**")
                with c2:
                    st.caption(f"{d.get('insurer', '')} · {d.get('year', '')} · {period_badge} {d.get('period', '')}")
                with c3:
                    btn_label = "Lukk" if is_open else "Åpne"
                    if st.button(btn_label, key=f"open-{d['id']}"):
                        st.session_state["doc_open_id"] = None if is_open else d["id"]
                        st.session_state["doc_chat_id"] = None
                        st.session_state["doc_chat_history"] = []
                        st.rerun()
                with c4:
                    if st.button("🗑 Slett", key=f"del-doc-{d['id']}", type="secondary"):
                        requests.delete(f"{API_BASE}/insurance-documents/{d['id']}", timeout=10)
                        if st.session_state.get("doc_open_id") == d["id"]:
                            st.session_state["doc_open_id"] = None
                        if st.session_state.get("doc_chat_id") == d["id"]:
                            st.session_state["doc_chat_id"] = None
                        st.rerun()

                if is_open:
                    with st.container(border=True):
                        kp_col, pdf_col = st.columns([3, 2])

                        with kp_col:
                            st.markdown("#### Nøkkelpunkter")
                            cache_key = f"kp_{d['id']}"
                            if cache_key not in st.session_state["doc_keypoints_cache"]:
                                with st.spinner("Analyserer dokument med AI…"):
                                    try:
                                        kp_resp = requests.get(
                                            f"{API_BASE}/insurance-documents/{d['id']}/keypoints",
                                            timeout=90,
                                        )
                                        st.session_state["doc_keypoints_cache"][cache_key] = (
                                            kp_resp.json() if kp_resp.ok else {}
                                        )
                                    except Exception:
                                        st.session_state["doc_keypoints_cache"][cache_key] = {}

                            kp = st.session_state["doc_keypoints_cache"].get(cache_key, {})
                            has_any = any(kp.get(k) for k in ["om_dokumentet", "sammendrag", "hva_dekkes", "viktige_vilkaar", "unntak", "forsikringssum"])

                            if not has_any:
                                st.caption("Nøkkelpunkter ikke tilgjengelig — Gemini API-nøkkel kreves.")
                            else:
                                om_dok = kp.get("om_dokumentet") or kp.get("sammendrag", "")
                                if om_dok:
                                    st.markdown(
                                        f"<div style='font-size:14px;color:#3A4E60;line-height:1.65;"
                                        f"background:#F0EDE8;padding:12px 16px;border-radius:6px;"
                                        f"border-left:4px solid #4A6FA5;margin-bottom:14px'>"
                                        f"<span style='font-size:11px;text-transform:uppercase;letter-spacing:0.08em;"
                                        f"color:#8A7F74;display:block;margin-bottom:4px'>Om dokumentet</span>"
                                        f"{om_dok}</div>",
                                        unsafe_allow_html=True,
                                    )

                                kp_fields = [
                                    ("Forsikringssum", kp.get("forsikringssum")),
                                    ("Egenandel",      kp.get("egenandel")),
                                    ("Periode",        kp.get("forsikringsperiode")),
                                    ("Kontakt",        kp.get("kontaktinfo")),
                                ]
                                has_fields = any(v for _, v in kp_fields)
                                if has_fields:
                                    rows_html = ""
                                    for label, val in kp_fields:
                                        if val:
                                            rows_html += (
                                                f"<tr>"
                                                f"<td style='color:#8A7F74;font-size:11px;text-transform:uppercase;"
                                                f"letter-spacing:0.06em;padding:5px 12px 5px 0;white-space:nowrap;"
                                                f"vertical-align:top;font-weight:600'>{label}</td>"
                                                f"<td style='font-size:13px;color:#2C2C2C;padding:5px 0;"
                                                f"line-height:1.5'>{val}</td></tr>"
                                            )
                                    st.markdown(
                                        f"<table style='border-collapse:collapse;width:100%;margin-bottom:14px;"
                                        f"background:#FAFAF7;border-radius:6px;padding:4px'>{rows_html}</table>",
                                        unsafe_allow_html=True,
                                    )

                                hva_dekkes = [v for v in (kp.get("hva_dekkes") or []) if v]
                                if hva_dekkes:
                                    items_html = "".join(
                                        f"<li style='padding:4px 0;color:#2C3E50;font-size:13px;line-height:1.55'>{item}</li>"
                                        for item in hva_dekkes
                                    )
                                    st.markdown(
                                        f"<div style='margin-bottom:14px'>"
                                        f"<p style='font-size:11px;text-transform:uppercase;letter-spacing:0.08em;"
                                        f"color:#4A6FA5;font-weight:700;margin:0 0 6px 0'>Hva dekkes</p>"
                                        f"<ul style='margin:0;padding-left:18px;list-style:disc'>{items_html}</ul>"
                                        f"</div>",
                                        unsafe_allow_html=True,
                                    )

                                vilkaar = [v for v in (kp.get("viktige_vilkaar") or []) if v]
                                if vilkaar:
                                    items_html = "".join(
                                        f"<li style='padding:3px 0;color:#2C3E50;font-size:13px;line-height:1.5'>{v}</li>"
                                        for v in vilkaar
                                    )
                                    st.markdown(
                                        f"<div style='margin-bottom:14px'>"
                                        f"<p style='font-size:11px;text-transform:uppercase;letter-spacing:0.08em;"
                                        f"color:#5A7A40;font-weight:700;margin:0 0 6px 0'>Viktige vilkår</p>"
                                        f"<ul style='margin:0;padding-left:18px;list-style:disc;"
                                        f"border-left:3px solid #5A7A40;padding-left:20px;background:#F5FAF2;"
                                        f"border-radius:0 6px 6px 0;padding-top:8px;padding-bottom:8px'>"
                                        f"{items_html}</ul></div>",
                                        unsafe_allow_html=True,
                                    )

                                unntak = [u for u in (kp.get("unntak") or []) if u]
                                if unntak:
                                    items_html = "".join(
                                        f"<li style='padding:3px 0;color:#5A2020;font-size:13px;line-height:1.5'>{u}</li>"
                                        for u in unntak
                                    )
                                    st.markdown(
                                        f"<div style='margin-bottom:8px'>"
                                        f"<p style='font-size:11px;text-transform:uppercase;letter-spacing:0.08em;"
                                        f"color:#C0504D;font-weight:700;margin:0 0 6px 0'>Unntak og eksklusjoner</p>"
                                        f"<ul style='margin:0;padding-left:18px;list-style:disc;"
                                        f"border-left:3px solid #C0504D;padding-left:20px;background:#FDF5F5;"
                                        f"border-radius:0 6px 6px 0;padding-top:8px;padding-bottom:8px'>"
                                        f"{items_html}</ul></div>",
                                        unsafe_allow_html=True,
                                    )

                        with pdf_col:
                            st.markdown("#### Dokument")
                            pdf_url = f"{API_BASE}/insurance-documents/{d['id']}/pdf"
                            try:
                                pdf_bytes_resp = requests.get(pdf_url, timeout=15)
                                if pdf_bytes_resp.ok:
                                    b64 = base64.b64encode(pdf_bytes_resp.content).decode()
                                    st.markdown(
                                        f'<iframe src="data:application/pdf;base64,{b64}" '
                                        f'width="100%" height="640" style="border:1px solid #D0CBC3;border-radius:6px"></iframe>',
                                        unsafe_allow_html=True,
                                    )
                                    st.download_button(
                                        "Last ned PDF",
                                        data=pdf_bytes_resp.content,
                                        file_name=f"{d['title']}.pdf",
                                        mime="application/pdf",
                                        key=f"dl-doc-{d['id']}",
                                    )
                            except Exception as e:
                                st.error(str(e))

                        st.markdown("---")
                        st.markdown("#### Chat med dokumentet")

                        if st.session_state.get("doc_chat_id") != d["id"]:
                            st.session_state["doc_chat_id"] = d["id"]
                            st.session_state["doc_chat_title"] = d["title"]
                            st.session_state["doc_chat_history"] = []

                        if st.session_state["doc_chat_history"]:
                            for qa in st.session_state["doc_chat_history"][-6:]:
                                with st.chat_message("user"):
                                    st.write(qa["q"])
                                with st.chat_message("assistant"):
                                    st.write(qa["a"])

                        with st.form(f"doc_chat_{d['id']}", clear_on_submit=True):
                            question = st.text_input("Spør om vilkår, dekning, egenandel...", key=f"q_{d['id']}")
                            ask_btn = st.form_submit_button("Spør")

                        if ask_btn and question:
                            with st.spinner("Leser dokumentet..."):
                                try:
                                    chat_resp = requests.post(
                                        f"{API_BASE}/insurance-documents/{d['id']}/chat",
                                        json={"question": question},
                                        timeout=60,
                                    )
                                    if chat_resp.ok:
                                        st.session_state["doc_chat_history"].append(
                                            {"q": question, "a": chat_resp.json().get("answer", "")}
                                        )
                                        st.rerun()
                                    else:
                                        st.error(chat_resp.text)
                                except Exception as e:
                                    st.error(str(e))

    with docs_sub_cmp:
        st.subheader("Sammenlign vilkår")
        st.caption("Velg to forsikringsdokumenter for å sammenligne vilkår, dekning og egenandel side om side med AI.")

        if len(all_docs) < 2:
            st.info("Du trenger minst 2 dokumenter i biblioteket for å bruke sammenligning. Last opp flere dokumenter under Dokumentbibliotek.")
        else:
            doc_options = {d["title"]: d["id"] for d in all_docs}
            titles = list(doc_options.keys())
            cmp_c1, cmp_c2, cmp_c3 = st.columns([5, 5, 2])
            with cmp_c1:
                doc_a_title = st.selectbox("Dokument A", titles, key="compare_a")
            with cmp_c2:
                remaining = [t for t in titles if t != doc_a_title]
                doc_b_title = st.selectbox("Dokument B", remaining if remaining else titles, key="compare_b")
            with cmp_c3:
                st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
                do_cmp = st.button("Sammenlign", key="do_compare", type="primary")

            if do_cmp:
                with st.spinner("Analyserer dokumenter med AI… (kan ta opptil 3 minutter for store PDFer)"):
                    try:
                        cmp_resp = requests.post(
                            f"{API_BASE}/insurance-documents/compare",
                            json={"doc_ids": [doc_options[doc_a_title], doc_options[doc_b_title]]},
                            timeout=300,
                        )
                        if cmp_resp.ok:
                            cmp_data = cmp_resp.json()
                            st.session_state["doc_comparison"] = cmp_data.get("structured") or {}
                            st.session_state["doc_cmp_a"] = doc_a_title
                            st.session_state["doc_cmp_b"] = doc_b_title
                        else:
                            st.error(f"Feil: {cmp_resp.text}")
                    except Exception as e:
                        st.error(str(e))

            if st.session_state.get("doc_comparison"):
                cmp = st.session_state["doc_comparison"]
                cmp_a_name = st.session_state.get("doc_cmp_a", "Dokument A")
                cmp_b_name = st.session_state.get("doc_cmp_b", "Dokument B")

                if "raw_text" in cmp:
                    hdr_a, hdr_b = st.columns(2)
                    with hdr_a:
                        st.markdown(
                            f"<div style='background:#2C3E50;color:#D4C9B8;padding:10px 16px;"
                            f"border-radius:6px 6px 0 0;font-weight:700;font-size:0.92rem'>"
                            f"A — {cmp_a_name}</div>", unsafe_allow_html=True)
                    with hdr_b:
                        st.markdown(
                            f"<div style='background:#4A6FA5;color:#E8F0FB;padding:10px 16px;"
                            f"border-radius:6px 6px 0 0;font-weight:700;font-size:0.92rem'>"
                            f"B — {cmp_b_name}</div>", unsafe_allow_html=True)
                    with st.container(border=True):
                        st.markdown(cmp["raw_text"])
                else:
                    st.markdown("#### Dokumentoversikt")
                    sum_a, sum_b = st.columns(2)
                    with sum_a:
                        st.markdown(
                            f"<div style='background:#2C3E50;color:#D4C9B8;padding:10px 16px;"
                            f"border-radius:8px 8px 0 0;font-weight:700;font-size:0.9rem;letter-spacing:0.03em'>"
                            f"A — {cmp_a_name}</div>"
                            f"<div style='background:#F7F5F2;border:1px solid #D0CBC3;border-top:none;"
                            f"border-radius:0 0 8px 8px;padding:14px 16px;font-size:0.88rem;line-height:1.55'>"
                            f"{cmp.get('doc_a_summary', '–')}</div>",
                            unsafe_allow_html=True,
                        )
                    with sum_b:
                        st.markdown(
                            f"<div style='background:#4A6FA5;color:#E8F0FB;padding:10px 16px;"
                            f"border-radius:8px 8px 0 0;font-weight:700;font-size:0.9rem;letter-spacing:0.03em'>"
                            f"B — {cmp_b_name}</div>"
                            f"<div style='background:#F0F4FB;border:1px solid #C5D0E8;border-top:none;"
                            f"border-radius:0 0 8px 8px;padding:14px 16px;font-size:0.88rem;line-height:1.55'>"
                            f"{cmp.get('doc_b_summary', '–')}</div>",
                            unsafe_allow_html=True,
                        )

                    st.markdown("<div style='margin:1rem 0'></div>", unsafe_allow_html=True)

                    st.markdown("#### Fordeler og ulemper")
                    pc_a, pc_b = st.columns(2)
                    with pc_a:
                        pros_a = cmp.get("pros_a") or []
                        cons_a = cmp.get("cons_a") or []
                        pros_html = "".join(f"<li style='color:#2E7D32;margin-bottom:4px'>✅ {p}</li>" for p in pros_a)
                        cons_html = "".join(f"<li style='color:#C62828;margin-bottom:4px'>❌ {c}</li>" for c in cons_a)
                        st.markdown(
                            f"<div style='border:1px solid #D0CBC3;border-radius:8px;padding:14px 16px;"
                            f"background:#FAFAF8'>"
                            f"<div style='font-weight:700;font-size:0.82rem;letter-spacing:0.06em;"
                            f"text-transform:uppercase;color:#2C3E50;margin-bottom:8px'>A — {cmp_a_name}</div>"
                            f"<ul style='margin:0;padding-left:18px;font-size:0.86rem'>{pros_html}{cons_html}</ul>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                    with pc_b:
                        pros_b = cmp.get("pros_b") or []
                        cons_b = cmp.get("cons_b") or []
                        pros_html = "".join(f"<li style='color:#2E7D32;margin-bottom:4px'>✅ {p}</li>" for p in pros_b)
                        cons_html = "".join(f"<li style='color:#C62828;margin-bottom:4px'>❌ {c}</li>" for c in cons_b)
                        st.markdown(
                            f"<div style='border:1px solid #C5D0E8;border-radius:8px;padding:14px 16px;"
                            f"background:#F5F8FF'>"
                            f"<div style='font-weight:700;font-size:0.82rem;letter-spacing:0.06em;"
                            f"text-transform:uppercase;color:#4A6FA5;margin-bottom:8px'>B — {cmp_b_name}</div>"
                            f"<ul style='margin:0;padding-left:18px;font-size:0.86rem'>{pros_html}{cons_html}</ul>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

                    st.markdown("<div style='margin:1rem 0'></div>", unsafe_allow_html=True)

                    rows = cmp.get("comparison") or []
                    if rows:
                        st.markdown("#### Detaljert sammenligning")
                        _WINNER_STYLE = {
                            "A":   ("background:#E8F5E9;color:#2E7D32;font-weight:600", "A er bedre"),
                            "B":   ("background:#E3F2FD;color:#1565C0;font-weight:600", "B er bedre"),
                            "Lik": ("background:#F5F5F5;color:#616161",                 "Ingen vesentlig forskjell"),
                        }
                        table_html = (
                            "<table style='width:100%;border-collapse:collapse;font-size:0.84rem'>"
                            "<thead><tr>"
                            "<th style='background:#EDEAE6;padding:8px 12px;text-align:left;border-bottom:2px solid #D0CBC3;width:18%'>Område</th>"
                            "<th style='background:#2C3E50;color:#D4C9B8;padding:8px 12px;text-align:left;border-bottom:2px solid #1a2a38;width:35%'>A — " + cmp_a_name + "</th>"
                            "<th style='background:#4A6FA5;color:#E8F0FB;padding:8px 12px;text-align:left;border-bottom:2px solid #3A5F94;width:35%'>B — " + cmp_b_name + "</th>"
                            "<th style='background:#EDEAE6;padding:8px 12px;text-align:center;border-bottom:2px solid #D0CBC3;width:12%'>Vinner</th>"
                            "</tr></thead><tbody>"
                        )
                        for i, row in enumerate(rows):
                            bg = "#FFFFFF" if i % 2 == 0 else "#F7F5F2"
                            winner = row.get("winner", "Lik")
                            w_style, w_label = _WINNER_STYLE.get(winner, _WINNER_STYLE["Lik"])
                            table_html += (
                                f"<tr style='background:{bg}'>"
                                f"<td style='padding:8px 12px;border-bottom:1px solid #E5E0D8;font-weight:600;color:#3A4E60'>{row.get('area', '')}</td>"
                                f"<td style='padding:8px 12px;border-bottom:1px solid #E5E0D8'>{row.get('doc_a', '–')}</td>"
                                f"<td style='padding:8px 12px;border-bottom:1px solid #E5E0D8'>{row.get('doc_b', '–')}</td>"
                                f"<td style='padding:8px 12px;border-bottom:1px solid #E5E0D8;text-align:center'>"
                                f"<span style='padding:3px 8px;border-radius:4px;font-size:0.8rem;{w_style}'>{winner}</span></td>"
                                f"</tr>"
                            )
                        table_html += "</tbody></table>"
                        st.markdown(table_html, unsafe_allow_html=True)

                    st.markdown("<div style='margin:1rem 0'></div>", unsafe_allow_html=True)

                    if cmp.get("conclusion"):
                        st.markdown("#### Konklusjon")
                        st.info(cmp["conclusion"])

                st.markdown("---")
                if st.button("Nullstill sammenligning", key="clr_cmp", type="secondary"):
                    st.session_state["doc_comparison"] = None
                    st.rerun()
