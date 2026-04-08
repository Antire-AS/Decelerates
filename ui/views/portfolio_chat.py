"""Portfolio AI chat — financial analysis mode and knowledge base mode."""
import streamlit as st

from ui.views.portfolio_helpers import _post


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


def _render_nl_query() -> None:
    st.markdown("#### Spør om finansdata (English / Norsk)")
    st.caption("Still spørsmål på naturlig språk — systemet oversetter til SQL og kjører mot databasen.")

    examples = [
        "Top 10 companies by revenue in MNOK",
        "Companies with risk score above 8, sorted by risk",
        "Average equity ratio per industry",
        "Which companies have financial data for 2023?",
    ]
    with st.expander("Eksempler", expanded=False):
        for ex in examples:
            st.code(ex, language=None)

    question = st.text_input(
        "Spørsmål",
        placeholder="Top 10 companies by revenue in MNOK",
        key="nl_query_input",
    )
    if st.button("Kjør spørring", key="nl_query_btn", type="primary") and question.strip():
        with st.spinner("Genererer SQL og kjører..."):
            result = _post("/financials/query", {"question": question})

        if not result:
            st.error("Ingen respons fra serveren.")
            return

        if result.get("error"):
            st.error(result["error"])
            if result.get("sql"):
                st.code(result["sql"], language="sql")
            return

        with st.expander("Generert SQL", expanded=False):
            st.code(result.get("sql", ""), language="sql")

        rows = result.get("rows", [])
        if rows:
            st.dataframe(rows, width="stretch")
            st.caption(f"{len(rows)} rader")
        else:
            st.info("Ingen resultater.")
