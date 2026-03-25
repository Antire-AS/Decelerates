"""Guided onboarding tour — shown once on first visit, re-triggerable via ? button."""
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


@st.dialog("Veiledning", width="large")
def _onboarding_dialog() -> None:
    step  = st.session_state.get("onboarding_step", 0)
    total = len(_STEPS)
    current = _STEPS[step]

    st.progress(int((step + 1) / total * 100))
    st.caption(f"Steg {step + 1} av {total}")
    st.markdown(f"## {current['icon']} {current['title']}")
    st.markdown(current["body"])
    st.markdown("")

    col_prev, col_skip, col_next = st.columns([1, 2, 1])
    if step > 0:
        if col_prev.button("← Forrige", key="onb_prev"):
            st.session_state["onboarding_step"] = step - 1
            st.rerun()
    if col_skip.button("Hopp over", key="onb_skip"):
        st.session_state["onboarding_open"] = False
        st.session_state["onboarding_seen"] = True
        st.rerun()
    label = "Neste →" if step < total - 1 else "Fullfør ✓"
    if col_next.button(label, key="onb_next", type="primary"):
        if step < total - 1:
            st.session_state["onboarding_step"] = step + 1
            st.rerun()
        else:
            st.session_state["onboarding_open"] = False
            st.session_state["onboarding_seen"] = True
            st.rerun()


def render_onboarding_tour() -> None:
    """Open the dialog if onboarding is active. Call this early in main render."""
    if "onboarding_seen" not in st.session_state:
        st.session_state["onboarding_seen"] = False
        st.session_state["onboarding_open"] = True
        st.session_state["onboarding_step"] = 0

    if st.session_state.get("onboarding_open"):
        _onboarding_dialog()


def render_onboarding_button() -> None:
    """No-op — button is now rendered inline in main.py next to the language toggle."""
