"""Guided onboarding tour — shown once on first visit, re-triggerable via ? icon."""
import streamlit as st


_STEPS = [
    {
        "icon": "🔍",
        "title": "1. Søk opp et selskap",
        "body": (
            "Gå til **Selskaper**-fanen og skriv inn et firmanavn eller organisasjonsnummer. "
            "Vi henter data fra BRREG, regnskapsregisteret og viser risikoscore automatisk."
        ),
    },
    {
        "icon": "📊",
        "title": "2. Se risikoprofilen",
        "body": (
            "Under **Oversikt** ser du risikoscore, nøkkeltall og styremedlemmer. "
            "Under **Økonomi** finner du historiske regnskapstall og equity ratio-trend."
        ),
    },
    {
        "icon": "📁",
        "title": "3. Bygg en portefølje",
        "body": (
            "Gå til **Portefølje**-fanen, opprett en ny portefølje og legg til selskaper. "
            "Du får konsentrasjonsanalyse, premiebok og fornyelsesvarsel på tvers av alle selskaper."
        ),
    },
    {
        "icon": "📋",
        "title": "4. Administrer forsikringsavtaler",
        "body": (
            "Under **Forsikring** kan du registrere poliser, skader og aktiviteter. "
            "**Fornyelser**-fanen gir deg en pipeline med alle avtaler som forfaller."
        ),
    },
    {
        "icon": "💬",
        "title": "5. Spør AI-assistenten",
        "body": (
            "Bruk **Analyser**-knappen på et selskap for å stille spørsmål om økonomi og risiko. "
            "**Kunnskapsbase**-fanen lar deg chatte med opplastede dokumenter og videoer."
        ),
    },
    {
        "icon": "⚙️",
        "title": "6. Konfigurer firmaet ditt",
        "body": (
            "Under **Innstillinger** legger du inn meglerfirmaets navn, kontaktinfo og e-post. "
            "Dette brukes i SLA-avtaler, PDF-rapporter og e-postvarsler."
        ),
    },
]


def render_onboarding_button() -> None:
    """Render a ? button in the sidebar that re-opens the onboarding tour."""
    if st.sidebar.button("❓ Veiledning", key="onboarding_trigger", width="stretch"):
        st.session_state["onboarding_open"] = True
        st.session_state["onboarding_step"] = 0
        st.rerun()


def render_onboarding_tour() -> None:
    """Show the onboarding tour modal if active. Call this early in main render."""
    # First-time auto-show
    if "onboarding_seen" not in st.session_state:
        st.session_state["onboarding_seen"] = False
        st.session_state["onboarding_open"] = True
        st.session_state["onboarding_step"] = 0

    if not st.session_state.get("onboarding_open"):
        return

    step = st.session_state.get("onboarding_step", 0)
    total = len(_STEPS)
    current = _STEPS[step]

    with st.container(border=True):
        progress_pct = int((step + 1) / total * 100)
        st.progress(progress_pct)
        st.markdown(
            f"<span style='color:#888;font-size:12px'>Steg {step + 1} av {total}</span>",
            unsafe_allow_html=True,
        )
        st.markdown(f"## {current['icon']} {current['title']}")
        st.markdown(current["body"])
        st.markdown("")

        col_prev, col_skip, col_next = st.columns([1, 2, 1])
        if step > 0:
            if col_prev.button("← Forrige", key="onb_prev"):
                st.session_state["onboarding_step"] = step - 1
                st.rerun()
        col_skip.button(
            "Hopp over",
            key="onb_skip",
            on_click=lambda: st.session_state.update(
                {"onboarding_open": False, "onboarding_seen": True}
            ),
        )
        if step < total - 1:
            if col_next.button("Neste →", key="onb_next", type="primary"):
                st.session_state["onboarding_step"] = step + 1
                st.rerun()
        else:
            if col_next.button("Fullfør ✓", key="onb_done", type="primary"):
                st.session_state["onboarding_open"] = False
                st.session_state["onboarding_seen"] = True
                st.rerun()
