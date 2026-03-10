import requests
import streamlit as st
import pandas as pd

API_BASE = "http://127.0.0.1:8000"

# ── Language toggle ──────────────────────────────────────────────────────────
if "lang" not in st.session_state:
    st.session_state["lang"] = "no"

_TRANSLATIONS = {
    "Organisation":                  {"no": "Organisasjon",               "en": "Organisation"},
    "Bankruptcy & liquidation":      {"no": "Konkurs- og avviklingsstatus","en": "Bankruptcy & liquidation status"},
    "Board members":                 {"no": "Styremedlemmer og roller",    "en": "Board members & roles"},
    "Active members":                {"no": "Aktive",                      "en": "Active"},
    "Resigned / deceased":           {"no": "Fratrådt / avdød",            "en": "Resigned / deceased"},
    "Key figures":                   {"no": "Nøkkeltall",                  "en": "Key figures"},
    "Turnover":                      {"no": "Omsetning",                   "en": "Turnover"},
    "Net result":                    {"no": "Nettoresultat",               "en": "Net result"},
    "Equity":                        {"no": "Egenkapital",                 "en": "Equity"},
    "Equity ratio":                  {"no": "Egenkapitalandel",            "en": "Equity ratio"},
    "Profit and loss":               {"no": "Resultatregnskap",            "en": "Profit and loss"},
    "Balance sheet":                 {"no": "Balanse",                     "en": "Balance sheet"},
    "Financial history":             {"no": "Finansiell historikk",        "en": "Financial history"},
    "Year-over-year overview":       {"no": "År-for-år oversikt",          "en": "Year-over-year overview"},
    "Revenue & net result (MNOK)":   {"no": "Omsetning og resultat (MNOK)","en": "Revenue & net result (MNOK)"},
    "Debt breakdown (MNOK)":         {"no": "Gjeldsstruktur (MNOK)",       "en": "Debt breakdown (MNOK)"},
    "Equity ratio trend (%)":        {"no": "Egenkapitalandel trend (%)",  "en": "Equity ratio trend (%)"},
    "Detailed view by year":         {"no": "Detaljert visning per år",    "en": "Detailed view by year"},
    "Select year":                   {"no": "Velg år",                     "en": "Select year"},
    "Profit & Loss":                 {"no": "Resultatregnskap",            "en": "Profit & Loss"},
    "Sales revenue":                 {"no": "Salgsinntekter",              "en": "Sales revenue"},
    "Total operating income":        {"no": "Sum driftsinntekter",         "en": "Total operating income"},
    "Wage costs":                    {"no": "Lønnskostnader",              "en": "Wage costs"},
    "Total operating costs":         {"no": "Sum driftskostnader",         "en": "Total operating costs"},
    "Operating result":              {"no": "Driftsresultat",              "en": "Operating result"},
    "Financial income":              {"no": "Finansinntekter",             "en": "Financial income"},
    "Financial costs":               {"no": "Finanskostnader",             "en": "Financial costs"},
    "Net financials":                {"no": "Netto finansposter",          "en": "Net financials"},
    "Result before tax":             {"no": "Resultat før skatt",          "en": "Result before tax"},
    "Tax cost":                      {"no": "Skattekostnad",               "en": "Tax cost"},
    "Annual result":                 {"no": "Årsresultat",                 "en": "Annual result"},
    "Total result":                  {"no": "Totalresultat",               "en": "Total result"},
    "Total assets":                  {"no": "Sum eiendeler",               "en": "Total assets"},
    "Current assets":                {"no": "Omløpsmidler",                "en": "Current assets"},
    "Fixed assets":                  {"no": "Anleggsmidler",               "en": "Fixed assets"},
    "Inventory":                     {"no": "Varebeholdning",              "en": "Inventory"},
    "Receivables":                   {"no": "Fordringer",                  "en": "Receivables"},
    "Investments":                   {"no": "Investeringer",               "en": "Investments"},
    "Cash & bank":                   {"no": "Bank og kontanter",           "en": "Cash & bank"},
    "Goodwill":                      {"no": "Goodwill",                    "en": "Goodwill"},
    "Paid-in equity":                {"no": "Innskutt egenkapital",        "en": "Paid-in equity"},
    "Retained earnings":             {"no": "Opptjent egenkapital",        "en": "Retained earnings"},
    "Total debt":                    {"no": "Sum gjeld",                   "en": "Total debt"},
    "Short-term debt":               {"no": "Kortsiktig gjeld",            "en": "Short-term debt"},
    "Long-term debt":                {"no": "Langsiktig gjeld",            "en": "Long-term debt"},
    "Employees":                     {"no": "Ansatte",                     "en": "Employees"},
    "Role":                          {"no": "Rolle",                       "en": "Role"},
    "Name":                          {"no": "Navn",                        "en": "Name"},
    "Born":                          {"no": "Fødselsår",                   "en": "Born"},
    "Founded":                       {"no": "Stiftet",                     "en": "Founded"},
    "Value":                         {"no": "Verdi",                       "en": "Value"},
    "Source":                        {"no": "Kilde",                       "en": "Source"},
    # ── Search & navigation ──────────────────────────────────────────────────
    "Search organisation":           {"no": "Søk organisasjon",             "en": "Search organisation"},
    "Name (or orgnr)":               {"no": "Navn (eller orgnr)",           "en": "Name (or orgnr)"},
    "Municipality (optional)":       {"no": "Kommunenummer (valgfritt)",    "en": "Municipality (optional)"},
    "Max results":                   {"no": "Maks resultater",              "en": "Max results"},
    "Search":                        {"no": "Søk",                          "en": "Search"},
    "View profile":                  {"no": "Vis profil",                   "en": "View profile"},
    "New search":                    {"no": "Ny søk",                       "en": "New search"},
    "Profile for":                   {"no": "Profil for",                   "en": "Profile for"},
    # ── Bankruptcy ───────────────────────────────────────────────────────────
    "Bankruptcy proceedings":        {"no": "⚠️ Dette selskapet er under konkursbehandling", "en": "⚠️ This company is currently under bankruptcy proceedings"},
    "Under liquidation":             {"no": "⚠️ Dette selskapet er under frivillig avvikling", "en": "⚠️ This company is currently under voluntary liquidation"},
    "No bankruptcy found":           {"no": "Ingen konkurs- eller avviklingsprosesser funnet", "en": "No bankruptcy or liquidation proceedings found"},
    "Bankruptcy unavailable":        {"no": "Konkursstatus utilgjengelig",  "en": "Bankruptcy status unavailable"},
    # ── Risk profile ─────────────────────────────────────────────────────────
    "Risk profile":                  {"no": "Risikoprofil",                 "en": "Risk profile"},
    "Turnover (m)":                  {"no": "Omsetning",                   "en": "Turnover"},
    "Employees (m)":                 {"no": "Ansatte",                     "en": "Employees"},
    "Equity ratio (m)":              {"no": "Egenkapitalandel",            "en": "Equity ratio"},
    "Risk score":                    {"no": "Risikoscore",                  "en": "Risk score"},
    "PEP hits":                      {"no": "PEP-treff",                   "en": "PEP hits"},
    "Checked vs OpenSanctions":      {"no": "Sjekket mot OpenSanctions",   "en": "Checked vs OpenSanctions"},
    "Data sources":                  {"no": "Kilde: BRREG Enhetsregisteret · BRREG Regnskapsregisteret · OpenSanctions",
                                      "en": "Source: BRREG Enhetsregisteret · BRREG Regnskapsregisteret · OpenSanctions"},
    "Low":                           {"no": "Lav",                         "en": "Low"},
    "Moderate":                      {"no": "Moderat",                     "en": "Moderate"},
    "High":                          {"no": "Høy",                         "en": "High"},
    "Very high":                     {"no": "Svært høy",                   "en": "Very high"},
    # ── Insurance recommendation ─────────────────────────────────────────────
    "Insurance recommendation":      {"no": "Forsikringsanbefaling",       "en": "Insurance recommendation"},
    "Generate recommendation":       {"no": "Generer forsikringstilbud",   "en": "Generate insurance recommendation"},
    "Analysing risk profile":        {"no": "Analyserer risikoprofil med AI...", "en": "Analysing risk profile with AI..."},
    "Analysing risk profile with AI...": {"no": "Analyserer risikoprofil med AI...", "en": "Analysing risk profile with AI..."},
    "Generating PDF...":             {"no": "Genererer PDF...",            "en": "Generating PDF..."},
    "Generating and saving...":      {"no": "Genererer og lagrer...",      "en": "Generating and saving..."},
    "Analysing with AI...":          {"no": "Analyserer med AI...",        "en": "Analysing with AI..."},
    "Generating PDF":                {"no": "Genererer PDF...",            "en": "Generating PDF..."},
    "Generating and saving":         {"no": "Genererer og lagrer...",      "en": "Generating and saving..."},
    "Analysing with AI":             {"no": "Analyserer med AI...",        "en": "Analysing with AI..."},
    "Download tilbud PDF":           {"no": "Last ned Forsikringstilbud (PDF)", "en": "Download Insurance Recommendation (PDF)"},
    "Generating PDF":                {"no": "Genererer PDF...",            "en": "Generating PDF..."},
    "Save to library":               {"no": "Lagre til dokumentbibliotek", "en": "Save to document library"},
    "Generating and saving":         {"no": "Genererer og lagrer...",      "en": "Generating and saving..."},
    "Saved to library":              {"no": "Lagret til Dokumenter-biblioteket!", "en": "Saved to document library!"},
    "Download generated PDF":        {"no": "Last ned generert PDF",       "en": "Download generated PDF"},
    "Clear recommendation":          {"no": "Nullstill anbefaling",        "en": "Clear recommendation"},
    # ── Benchmarks ───────────────────────────────────────────────────────────
    "Industry benchmarks":           {"no": "Bransjesammenligning",        "en": "Industry benchmarks"},
    "Section label":                 {"no": "Seksjon",                     "en": "Section"},
    "Profit margin":                 {"no": "Fortjenestemargin",           "en": "Profit margin"},
    "Equity ratio (bench)":          {"no": "Egenkapitalandel",            "en": "Equity ratio"},
    "vs industry mid":               {"no": "vs. bransjegjennomsnitt",     "en": "vs industry mid"},
    # ── AI narrative ─────────────────────────────────────────────────────────
    "AI risk narrative":             {"no": "AI risikoanalyse",            "en": "AI risk narrative"},
    "Regenerate narrative":          {"no": "Regenerer analyse",           "en": "Regenerate narrative"},
    "Generate risk narrative":       {"no": "Generer risikoanalyse",       "en": "Generate risk narrative"},
    "Analysing with AI":             {"no": "Analyserer med AI...",        "en": "Analysing with AI..."},
    # ── Insurance offers ─────────────────────────────────────────────────────
    "Insurance offers":              {"no": "Forsikringstilbud",           "en": "Insurance offers"},
    "Delete":                        {"no": "Slett",                       "en": "Delete"},
    "Analyse stored offers":         {"no": "Analyser lagrede tilbud med AI", "en": "Analyse stored offers with AI"},
    "Analysing offers":              {"no": "Analyserer tilbud med AI... (kan ta 30-60 sek)", "en": "Analysing offers with AI... (may take 30-60 sec)"},
    "Upload new offers":             {"no": "Last opp nye tilbud og lagre til database", "en": "Upload new offers and save to database"},
    "Select PDF offers":             {"no": "Velg PDF-tilbud fra forsikringsselskaper", "en": "Select PDF offers from insurers"},
    "Save to database":              {"no": "Lagre til database",          "en": "Save to database"},
    "Analyse without saving":        {"no": "Analyser uten å lagre",       "en": "Analyse without saving"},
    "Clear analysis":                {"no": "Nullstill analyse",           "en": "Clear analysis"},
    # ── Coverage gap ─────────────────────────────────────────────────────────
    "Coverage gap analysis":         {"no": "Dekningstomme analyse",       "en": "Coverage gap analysis"},
    "Coverage gap caption":          {"no": "Sammenligner risikoprofil mot opplastede tilbud og identifiserer manglende dekninger.",
                                      "en": "Compares risk profile against uploaded offers and identifies missing coverage."},
    "Analyse coverage gap":          {"no": "Analyser dekningstomme",      "en": "Analyse coverage gap"},
    "Covered by offers":             {"no": "Dekket av eksisterende tilbud:", "en": "Covered by existing offers:"},
    "Missing coverage":              {"no": "Mangler / dekningstomme:",    "en": "Missing / coverage gaps:"},
    "Clear":                         {"no": "Nullstill",                   "en": "Clear"},
    # ── Financial sources ────────────────────────────────────────────────────
    "Source BRREG":                  {"no": "Kilde: BRREG Regnskapsregisteret (offentlige regnskapsdata)",
                                      "en": "Source: BRREG Regnskapsregisteret (public financial data)"},
    "Source history":                {"no": "Kilde: BRREG Regnskapsregisteret · PDF-årsrapporter (AI-ekstraksjon via Gemini)",
                                      "en": "Source: BRREG Regnskapsregisteret · PDF annual reports (AI extraction via Gemini)"},
    "Source PDF":                    {"no": "PDF-årsrapport (Gemini AI-ekstraksjon)", "en": "PDF annual report (Gemini AI extraction)"},
    "Source BRREG short":            {"no": "BRREG Regnskapsregisteret",   "en": "BRREG Regnskapsregisteret"},
    "Source year":                   {"no": "År",                          "en": "Year"},
    # ── PDF re-extract ───────────────────────────────────────────────────────
    "Re-extract PDF history":        {"no": "Reekstraher all PDF-historikk", "en": "Re-extract all PDF history"},
    "Re-extract caption":            {"no": "Slett all lagret PDF-historikk og kjør ekstraksjon på nytt med siste AI-prompt. Bruk dette hvis dataen ser feil ut.",
                                      "en": "Delete all stored PDF history for this company and re-run extraction with the latest AI prompt. Use this if data looks wrong or incomplete."},
    "Reset and re-extract":          {"no": "Nullstill & Reekstraher",    "en": "Reset & Re-extract"},
    "Add Annual Report PDF":         {"no": "Legg til årsrapport (PDF)",   "en": "Add Annual Report PDF"},
    "Add PDF caption":               {"no": "Lim inn en offentlig PDF-URL for å hente ut finansiell historikk med AI.",
                                      "en": "Paste a public PDF URL to extract multi-year financial history using AI."},
    # ── PEP ──────────────────────────────────────────────────────────────────
    "PEP screening":                 {"no": "PEP / sanksjonsskjermling",   "en": "PEP / sanctions screening"},
    "No PEP matches":                {"no": "Ingen PEP/sanksjonstreff funnet i OpenSanctions.", "en": "No PEP/sanctions matches found in OpenSanctions."},
    "No PEP data":                   {"no": "Ingen PEP/sanksjonsdata tilgjengelig.", "en": "No PEP/sanctions data available."},
    # ── Analyst chat ─────────────────────────────────────────────────────────
    "Ask analyst":                   {"no": "Spør risikoanalytikeren",     "en": "Ask the risk analyst"},
    "Question label":                {"no": "Spørsmål",                    "en": "Question"},
    "Question placeholder":          {"no": "Hva er de viktigste tegningshensyn for dette selskapet?",
                                      "en": "What are the main underwriting concerns for this company?"},
    "Previous questions":            {"no": "Tidligere spørsmål",          "en": "Previous questions"},
    # ── Broker notes ─────────────────────────────────────────────────────────
    "Notes":                         {"no": "Notater",                     "en": "Notes"},
    "Save note":                     {"no": "Lagre notat",                 "en": "Save note"},
    "Note placeholder":              {"no": "Skriv et notat om dette selskapet...", "en": "Write a note about this company..."},
    # ── Spinners (no trailing ellipsis variants needed — T() returns the string) ─
    "Analysing risk profile with AI...": {"no": "Analyserer risikoprofil med AI...", "en": "Analysing risk profile with AI..."},
    "Generating PDF...":             {"no": "Genererer PDF...",            "en": "Generating PDF..."},
    "Generating and saving...":      {"no": "Genererer og lagrer...",      "en": "Generating and saving..."},
    "Analysing with AI...":          {"no": "Analyserer med AI...",        "en": "Analysing with AI..."},
}

def T(key: str) -> str:
    """Return translated label for current language."""
    lang = st.session_state.get("lang", "no")
    entry = _TRANSLATIONS.get(key)
    if entry:
        return entry.get(lang, entry.get("en", key))
    return key

st.set_page_config(
    page_title="Broker Accelerator",
    page_icon="⚖️",
    layout="wide",
)

st.markdown("""
<style>
/* ══════════════════════════════════════════
   PALETTE
   Slate   #2C3E50   (headings)
   Steel   #4A6FA5   (accents)
   Parch   #F7F5F2   (main bg)
   Linen   #EDEBE6   (cards)
   Stone   #D0CBC3   (borders)
   Ink     #2C2C2C
══════════════════════════════════════════ */

/* ── Global ── */
html, body, [class*="css"] {
    font-family: 'Georgia', 'Times New Roman', serif;
    color: #2C2C2C;
}
.main > div { background: #F7F5F2; }
[data-testid="stAppViewContainer"] { background: #F7F5F2; }

/* ── Top header — clean and restrained ── */
.broker-header {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1.1rem 2rem 1rem 2rem;
    background: #FFFFFF;
    border-bottom: 2px solid #D0CBC3;
    margin: -4rem -4rem 1.5rem -4rem;
    box-shadow: 0 1px 8px rgba(0,0,0,0.06);
}
.broker-header-icon {
    font-size: 2rem;
    line-height: 1;
    opacity: 0.85;
}
.broker-header h1 {
    color: #2C3E50;
    font-size: 1.65rem;
    font-weight: 700;
    letter-spacing: 0.03em;
    margin: 0;
}
.broker-header p {
    color: #8A7F74;
    font-size: 0.72rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    margin: 0.15rem 0 0 0;
}

/* ── Tab bar ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 0;
    background: #F0EDE8;
    border-bottom: 1px solid #D0CBC3;
    padding: 0 0.5rem;
}
.stTabs [data-baseweb="tab"] {
    font-family: Georgia, serif;
    font-size: 0.88rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    padding: 0.6rem 1.6rem;
    border-radius: 0;
    color: #5A5248;
    border-bottom: 2px solid transparent;
    background: transparent;
}
.stTabs [aria-selected="true"] {
    background: #FFFFFF !important;
    color: #2C3E50 !important;
    border-bottom: 2px solid #4A6FA5 !important;
}

/* ── Section headings ── */
h2 {
    color: #2C3E50;
    border-bottom: 1px solid #D0CBC3;
    padding-bottom: 0.3rem;
    margin-top: 1.5rem;
    font-size: 1.35rem;
    font-weight: 700;
}
h3 {
    color: #3A4E60;
    padding-bottom: 0.2rem;
    margin-top: 1rem;
    font-size: 1.08rem;
    font-weight: 600;
}
h4 { color: #4A6070; font-size: 0.95rem; font-weight: 600; }

/* ── Metric cards ── */
[data-testid="metric-container"] {
    background: #FFFFFF;
    border: 1px solid #D8D3CC;
    border-top: 3px solid #4A6FA5;
    border-radius: 6px;
    padding: 0.85rem 1rem;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}
[data-testid="stMetricValue"] {
    font-size: 1.4rem !important;
    font-weight: 700;
    color: #2C3E50;
}
[data-testid="stMetricLabel"] {
    font-size: 0.72rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #8A7F74;
}
[data-testid="stMetricDelta"] { font-size: 0.82rem !important; }

/* ── Buttons — primary (solid blue) ── */
[data-testid="baseButton-primary"],
[data-testid="baseButton-primaryFormSubmit"] {
    font-family: Georgia, serif !important;
    font-size: 0.88rem !important;
    letter-spacing: 0.03em !important;
    border-radius: 5px !important;
    border: 1px solid #4A6FA5 !important;
    background: #4A6FA5 !important;
    color: #FFFFFF !important;
    padding: 0.45rem 1.2rem !important;
    box-shadow: 0 1px 4px rgba(74,111,165,0.18) !important;
    transition: all 0.12s ease !important;
}
[data-testid="baseButton-primary"]:hover,
[data-testid="baseButton-primaryFormSubmit"]:hover {
    background: #3A5F94 !important;
    border-color: #3A5F94 !important;
}
/* ── Buttons — secondary (outlined) ── */
[data-testid="baseButton-secondary"] {
    font-family: Georgia, serif !important;
    font-size: 0.88rem !important;
    border-radius: 5px !important;
    border: 1px solid #B8B0A6 !important;
    background: #FFFFFF !important;
    color: #3A4E60 !important;
    padding: 0.45rem 1.2rem !important;
    box-shadow: none !important;
}
[data-testid="baseButton-secondary"]:hover {
    background: #F0EDE8 !important;
    border-color: #4A6FA5 !important;
    color: #2C3E50 !important;
}

/* ── Sidebar — light, readable ── */
[data-testid="stSidebar"] {
    background: #F0EDE8;
    border-right: 1px solid #D0CBC3;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] small { color: #5A5248 !important; }
[data-testid="stSidebar"] h3 {
    font-family: Georgia, serif;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    border-bottom: 1px solid #C8C0B6;
    padding-bottom: 0.45rem;
    color: #8A7F74 !important;
    margin-bottom: 0.7rem;
}
[data-testid="stSidebar"] .stProgress > div > div {
    background: #4A6FA5;
}
[data-testid="stSidebar"] .stProgress > div {
    background: #D8D3CC;
    border-radius: 4px;
}
[data-testid="stSidebar"] hr {
    border-top: 1px solid #D0CBC3;
    margin: 0.7rem 0;
}
[data-testid="stSidebar"] .stCheckbox label { color: #3A3530 !important; }

/* ── Expanders ── */
[data-testid="stExpander"] {
    background: #FFFFFF;
    border: 1px solid #D0CBC3;
    border-radius: 6px;
}

/* ── Dataframe / tables ── */
/* Only style the outer border — never override inner canvas/div
   as that breaks the glide-data-grid canvas rendering           */
[data-testid="stDataFrame"] {
    border: 1px solid #D0CBC3;
    border-radius: 6px;
    overflow: hidden;
}
/* st.table (static HTML tables) */
[data-testid="stTable"] table {
    border-radius: 6px;
    border-collapse: collapse;
    width: 100%;
}
/* Header row cells only */
[data-testid="stTable"] thead th {
    background: #EDEAE6;
    color: #3A3530;
    font-size: 12px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    padding: 7px 10px;
    border-bottom: 2px solid #D0CBC3;
}
/* Index column cells (row labels) — normal case, no bg */
[data-testid="stTable"] tbody th {
    background: transparent;
    font-size: 13px;
    font-weight: 500;
    color: #2C2C2C;
    text-transform: none;
    letter-spacing: 0;
    padding: 6px 10px;
    border-bottom: 1px solid #E5E0D8;
}
[data-testid="stTable"] td {
    padding: 6px 10px;
    border-bottom: 1px solid #E5E0D8;
    font-size: 13px;
    color: #2C2C2C;
}
[data-testid="stTable"] tr:nth-child(even) td { background: #F5F2EE; }

/* ── Input fields ── */
input, textarea, select {
    font-family: Georgia, serif !important;
    background: #FFFFFF !important;
}

/* ── Alert boxes ── */
[data-testid="stAlert"] {
    border-radius: 6px;
    border-left-width: 4px;
}

/* ── Divider ── */
hr {
    border: none;
    border-top: 1px solid #D0CBC3;
    margin: 1.4rem 0;
}
</style>

<div class="broker-header">
    <div class="broker-header-icon">⚖️</div>
    <div>
        <h1>Broker Accelerator</h1>
        <p>Forsikringsmegling &nbsp;&middot;&nbsp; Due Diligence &nbsp;&middot;&nbsp; Risikoprofil</p>
    </div>
</div>
""", unsafe_allow_html=True)

# Language toggle — top-right
_lang_col, _btn_col = st.columns([9, 1])
with _lang_col:
    _current_lang = st.session_state.get("lang", "no")
    _lang_label = "🇳🇴 Norsk" if _current_lang == "no" else "🇬🇧 English"
    st.caption(f"Språk: **{_lang_label}** — klikk for å bytte" if _current_lang == "no" else f"Language: **{_lang_label}** — click to switch")
with _btn_col:
    _toggle_label = "🇬🇧 EN" if _current_lang == "no" else "🇳🇴 NO"
    if st.button(_toggle_label, key="lang_toggle", type="secondary"):
        st.session_state["lang"] = "en" if _current_lang == "no" else "no"
        st.session_state["forsikringstilbud_pdf"] = None  # clear cached PDF on lang switch
        st.rerun()

tab_search, tab_portfolio, tab_docs, tab_sla, tab_knowledge = st.tabs(["Selskapsøk", "Portefølje", "Dokumenter", "Avtaler", "Kunnskapsbase"])

# ──────────────────────────────────────────────
# TAB 1 — Company Search
# ──────────────────────────────────────────────
with tab_search:
    _lang = st.session_state.get("lang", "no")
    st.subheader(T("Search organisation"))
    name = st.text_input(T("Name (or orgnr)"), value="DNB")
    kommune = st.text_input(T("Municipality (optional)"), value="")
    size = st.slider(T("Max results"), 5, 50, 20)

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
    if "show_results" not in st.session_state:
        st.session_state["show_results"] = True
    if "coverage_gap" not in st.session_state:
        st.session_state["coverage_gap"] = None
    if "notes_refresh" not in st.session_state:
        st.session_state["notes_refresh"] = 0
    if "forsikringstilbud_pdf" not in st.session_state:
        st.session_state["forsikringstilbud_pdf"] = None

    # ── Sidebar: broker process checklist ────────────────────────────────────
    orgnr_ctx = st.session_state.get("selected_orgnr")
    if orgnr_ctx:
        with st.sidebar:
            st.markdown("### Salgsprosess")

            step1 = True
            step2 = bool(st.session_state.get("narrative")) or bool(st.session_state.get("risk_offer"))
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
                (step1, "Datainnhenting",       "Selskapsdata hentet fra BRREG"),
                (step2, "Behovsanalyse",        "Risikoscoring og AI-analyse"),
                (step3, "Tilbudsinnhenting",    "Tilbud fra forsikringsselskaper"),
                (step4, "Analyse av tilbud",    "Sammenstilling og AI-sammenligning"),
                (step5, "Presentasjon",         "Tilbud presentert for kunde"),
                (step6, "Forhandlinger",        "Vilkår og pris avklart"),
                (step7, "Kontrakt",             "Tjenesteavtale signert"),
            ]

            done_count = sum(1 for done, _, _ in steps if done)
            total = len(steps)

            # Progress bar
            st.progress(done_count / total)
            st.caption(f"{done_count} av {total} steg fullført")
            st.markdown("---")

            # Determine active step (first incomplete)
            active_idx = next((i for i, (done, _, _) in enumerate(steps) if not done), total)

            for i, (done, title, desc) in enumerate(steps):
                is_active = i == active_idx
                if done:
                    st.markdown(
                        f"<div style='display:flex;align-items:center;padding:5px 0;gap:10px'>"
                        f"<span style='width:22px;height:22px;border-radius:50%;background:#4A6FA5;"
                        f"display:inline-flex;align-items:center;justify-content:center;"
                        f"font-size:12px;color:#fff;font-weight:700;flex-shrink:0'>✓</span>"
                        f"<span style='color:#7A9A5A;font-size:13px;font-weight:600'>{title}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                elif is_active:
                    st.markdown(
                        f"<div style='display:flex;align-items:center;padding:6px 8px;gap:10px;"
                        f"background:#FFFFFF;border-left:3px solid #4A6FA5;border-radius:4px;"
                        f"margin:3px 0;box-shadow:0 1px 3px rgba(0,0,0,0.06)'>"
                        f"<span style='width:22px;height:22px;border-radius:50%;background:#4A6FA5;"
                        f"display:inline-flex;align-items:center;justify-content:center;"
                        f"font-size:11px;color:#fff;font-weight:700;flex-shrink:0'>{i+1}</span>"
                        f"<div><div style='color:#2C3E50;font-size:13px;font-weight:700'>{title}</div>"
                        f"<div style='color:#8A7F74;font-size:10px;margin-top:1px'>{desc}</div></div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f"<div style='display:flex;align-items:center;padding:5px 0;gap:10px'>"
                        f"<span style='width:22px;height:22px;border-radius:50%;border:1.5px solid #C8C0B6;"
                        f"display:inline-flex;align-items:center;justify-content:center;"
                        f"font-size:11px;color:#B8B0A8;font-weight:600;flex-shrink:0'>{i+1}</span>"
                        f"<span style='color:#A09890;font-size:13px'>{title}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

            st.markdown("---")

            # Manual toggles for steps 5 & 6
            new5 = st.checkbox("Presentasjon fullført", value=step5, key=f"cb5_{orgnr_ctx}")
            new6 = st.checkbox("Forhandlinger fullført", value=step6, key=f"cb6_{orgnr_ctx}")
            st.session_state[f"step5_{orgnr_ctx}"] = new5
            st.session_state[f"step6_{orgnr_ctx}"] = new6

            if not step7:
                st.caption("Gå til **Avtaler**-fanen for å opprette tjenesteavtale (steg 7)")

    if st.button(T("Search")):
        params = {"name": name, "size": size}
        if kommune:
            params["kommunenummer"] = kommune
        st.session_state["narrative"] = None
        st.session_state["estimated_financials"] = None
        st.session_state["show_results"] = True
        st.session_state["selected_orgnr"] = None
        try:
            resp = requests.get(f"{API_BASE}/search", params=params, timeout=10)
            resp.raise_for_status()
            st.session_state["search_results"] = resp.json()
        except Exception as e:
            st.error(f"Failed to call backend: {e}")

    results = st.session_state["search_results"]

    if st.session_state.get("show_results", True):
        st.write(f"Found {len(results)} results")
        for r in results:
            line = (
                f"{r.get('orgnr', '?')} - {r.get('navn', 'N/A')} "
                f"({r.get('organisasjonsform', 'N/A')}) "
                f"[{r.get('kommune', '')}, {r.get('postnummer', '')}] "
                f"– {r.get('naeringskode1', '')} {r.get('naeringskode1_beskrivelse', '')}"
            )
            st.write(line)
            if st.button(T("View profile"), key=f"view-{r['orgnr']}"):
                st.session_state["selected_orgnr"] = r["orgnr"]
                st.session_state["narrative"] = None
                st.session_state["estimated_financials"] = None
                st.session_state["show_results"] = False
                st.rerun()
    elif results:
        selected = st.session_state.get("selected_orgnr")
        selected_name = next(
            (r.get("navn", selected) for r in results if r.get("orgnr") == selected),
            selected,
        )
        col_info, col_btn = st.columns([5, 1])
        with col_info:
            _showing = "Viser profil" if _lang == "no" else "Showing profile"
            st.caption(f"{_showing}: **{selected_name}** ({selected}) — {len(results)} {'treff' if _lang == 'no' else 'results'}")
        with col_btn:
            if st.button(T("New search"), key="back_to_results"):
                st.session_state["show_results"] = True
                st.session_state["selected_orgnr"] = None
                st.rerun()

    # ── Profile section ──────────────────────────────────────────
    selected_orgnr = st.session_state["selected_orgnr"]
    if selected_orgnr:
        st.markdown("---")
        st.subheader(f"{T('Profile for')} {selected_orgnr}")

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

        struktur_data = None
        try:
            str_resp = requests.get(f"{API_BASE}/org/{selected_orgnr}/struktur", timeout=8)
            if str_resp.ok:
                struktur_data = str_resp.json()
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
                    return f"{value/1_000_000:,.0f} MNOK".replace(",", " ")
                except Exception:
                    return str(value)

            # ── 1) Organisation info + map ─────────────────────
            st.markdown(f"### {T('Organisation')}")
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

            # ── 1c) Konsernstruktur ────────────────────────────
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
            st.markdown(f"### {T('Bankruptcy & liquidation')}")
            kd = konkurs_data or {}
            if kd.get("konkurs") or kd.get("under_konkursbehandling"):
                st.error(T("Bankruptcy proceedings"))
            elif kd.get("under_avvikling"):
                st.warning(T("Under liquidation"))
            elif konkurs_data is not None:
                st.success(T("No bankruptcy found"))
            else:
                st.info(T("Bankruptcy unavailable"))

            # ── 2) Board members ───────────────────────────────
            st.markdown(f"### {T('Board members')}")
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
            st.markdown(f"### {T('Risk profile')}")
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

            # Score gauge + premium note
            if raw_score is not None:
                pct = min(raw_score / MAX_SCORE, 1.0)
                gauge_color = band_color
                st.markdown(
                    f"<div style='margin:6px 0 2px 0;display:flex;align-items:center;gap:12px'>"
                    f"<div style='flex:1;height:7px;background:#E8E4E0;border-radius:4px;overflow:hidden'>"
                    f"<div style='width:{pct*100:.0f}%;height:100%;background:{gauge_color};border-radius:4px;transition:width 0.4s'></div>"
                    f"</div>"
                    f"<span style='font-size:12px;color:{gauge_color};font-weight:700;white-space:nowrap'>{band_label} — {raw_score}/{MAX_SCORE}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                # Premium indication note
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

            # ── Risikofaktorer-tabell ──
            factors = risk_summary.get("risk_factors") or []
            if factors:
                import pandas as pd
                CATEGORY_COLORS = {
                    "Selskapsstatus": "🔴",
                    "Økonomi": "🟠",
                    "Bransje": "🟡",
                    "Historikk": "🔵",
                    "Eksponering": "🟣",
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

            # ── Forsikringsanbefaling ──
            st.markdown(f"### {T('Insurance recommendation')}")
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
                    import pandas as pd
                    df_offer = pd.DataFrame(anbefalinger)
                    col_map = {"type": "Forsikringstype", "prioritet": "Prioritet",
                               "anbefalt_sum": "Anbefalt dekningssum", "begrunnelse": "Begrunnelse"}
                    df_offer = df_offer.rename(columns={k: v for k, v in col_map.items() if k in df_offer.columns})
                    st.dataframe(df_offer, use_container_width=True, hide_index=True)
                if offer.get("total_premieanslag"):
                    st.caption(f"Estimert premieanslag: **{offer['total_premieanslag']}**")

                # Download Forsikringstilbud PDF
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
                                    json=_pdf_payload,
                                    timeout=90,
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
                                    json=_pdf_payload,
                                    params={"save": "true"},
                                    timeout=90,
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

            # ── 3b) Industry benchmarks ────────────────────────
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
                    if eq_ratio_val is not None:
                        delta_eq = eq_ratio_val - (b_eq_min + b_eq_max) / 2
                        delta_label = f"{delta_eq*100:+.1f}% {T('vs industry mid')}"
                    else:
                        delta_label = None
                    st.metric(T("Equity ratio (bench)"), company_eq, delta=delta_label, help=f"Industry typical: {industry_eq}")

                with col_b2:
                    omsetning = risk_summary.get("omsetning")
                    aarsresultat = (prof.get("regnskap") or {}).get("aarsresultat")
                    if omsetning and aarsresultat is not None and omsetning > 0:
                        company_margin = aarsresultat / omsetning
                        company_mg_str = f"{company_margin*100:.1f}%"
                        industry_mg = f"{b_mg_min*100:.0f}–{b_mg_max*100:.0f}%"
                        delta_mg = company_margin - (b_mg_min + b_mg_max) / 2
                        st.metric(T("Profit margin"), company_mg_str, delta=f"{delta_mg*100:+.1f}% {T('vs industry mid')}", help=f"Industry typical: {industry_mg}")
                    else:
                        st.metric(T("Profit margin"), "N/A", help=f"Industry typical: {b_mg_min*100:.0f}–{b_mg_max*100:.0f}%")

            # ── 4) AI risk narrative ───────────────────────────
            st.markdown(f"### {T('AI risk narrative')}")
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
                                params={"lang": _lang},
                                timeout=60,
                            )
                            nav_resp.raise_for_status()
                            st.session_state["narrative"] = nav_resp.json().get("narrative")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Narrative generation failed: {e}")

            # ── Steg 3-4: Innhente og analysere tilbud ─────────
            st.markdown(f"### {T('Insurance offers')}")

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
                        if st.button(f"🗑 {T('Delete')}", key=f"del_offer_{offer['id']}", type="secondary"):
                            requests.delete(
                                f"{API_BASE}/org/{selected_orgnr}/offers/{offer['id']}",
                                timeout=6,
                            )
                            st.rerun()

                # Compare stored offers
                st.session_state["offers_uploaded_names"] = [o["filename"] for o in stored_offers]
                sel_ids = [o["id"] for o in stored_offers]
                _analyse_label = (
                    f"Analyser alle {len(stored_offers)} lagrede tilbud med AI"
                    if _lang == "no"
                    else f"Analyse all {len(stored_offers)} stored offers with AI"
                )
                if st.button(_analyse_label, key="compare_stored_btn", type="primary"):
                    with st.spinner(T("Analysing offers")):
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
            with st.expander(T("Upload new offers")):
                uploaded_files = st.file_uploader(
                    T("Select PDF offers"),
                    type=["pdf"],
                    accept_multiple_files=True,
                    key="offers_uploader",
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
                        if st.button(T("Analyse without saving"), key="compare_offers_btn"):
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
                if st.button(T("Clear analysis"), key="clear_comparison_btn"):
                    st.session_state["offers_comparison"] = None
                    st.session_state["offers_uploaded_names"] = []
                    st.rerun()

            # ── Coverage gap analysis ──────────────────────────
            st.markdown(f"#### {T('Coverage gap analysis')}")
            st.caption(T("Coverage gap caption"))
            if st.button(T("Analyse coverage gap"), key="coverage_gap_btn", type="secondary"):
                with st.spinner("Analyserer..."):
                    try:
                        gap_resp = requests.post(
                            f"{API_BASE}/org/{selected_orgnr}/coverage-gap",
                            params={"lang": st.session_state.get("lang", "no")},
                            timeout=60,
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

            # ── 5) Key figures ─────────────────────────────────
            has_real_regn = bool(
                prof.get("regnskap") and prof["regnskap"].get("regnskapsår") is not None
            )
            has_estimated = bool(regn and regn.get("synthetic"))

            if has_real_regn or has_estimated:
                year_label = regn.get("regnskapsår") or "estimated"
                label_suffix = " *(AI estimated)*" if has_estimated else ""
                st.markdown(f"### {T('Key figures')} ({year_label}){label_suffix}")

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
            if years_data:
                st.markdown(f"### {T('Financial history')}")
                sorted_years = sorted(years_data, key=lambda x: x["year"])

                # ── Currency conversion banner ─────────────────
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
                    _nb_note = f"Beløp i fremmed valuta vises i opprinnelig valuta. Dagskurs (Norges Bank): {_rate_lines}" if _lang == "no" else f"Amounts in foreign currency shown in original currency. Current rate (Norges Bank): {_rate_lines}"
                    st.info(f"💱 {_nb_note}")

                # ── Year-over-year summary table ──────────────
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
                st.caption(T("Source history"))

                # ── Charts (always shown, even for 1 year) ───────
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

                # ── Year drill-down ───────────────────────────
                st.markdown(f"#### {T('Detailed view by year')}")
                available_years = [row["year"] for row in sorted_years]
                selected_year = st.selectbox(
                    T("Select year"),
                    available_years,
                    index=len(available_years) - 1,
                    key="hist_year_select",
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

            # ── Re-extract history ──────────────────────────────
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

            # ── Add PDF report ─────────────────────────────────
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
            st.markdown(f"### {T('PEP screening')}")
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
            st.markdown("---")
            st.subheader(T("Ask analyst"))
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
                    st.markdown(f"#### {T('Previous questions')}")
                    for item in chat_history:
                        date = item.get("created_at", "")[:10]
                        st.markdown(f"**[{date}] Q:** {item['question']}")
                        st.write(item["answer"])
                        st.divider()
            except Exception:
                pass

            # ── 9) Broker notes ────────────────────────────────
            st.markdown("---")
            st.markdown(f"### {T('Notes')}")
            _notes_refresh = st.session_state.get("notes_refresh", 0)
            try:
                _notes_resp = requests.get(
                    f"{API_BASE}/org/{selected_orgnr}/broker-notes", timeout=8
                )
                _existing_notes = _notes_resp.json() if _notes_resp.ok else []
            except Exception:
                _existing_notes = []

            _note_text = st.text_area(
                T("Notes"),
                height=80,
                placeholder=T("Note placeholder"),
                key=f"note_input_{_notes_refresh}",
                label_visibility="collapsed",
            )
            if st.button(T("Save note"), key=f"save_note_{_notes_refresh}"):
                if _note_text and _note_text.strip():
                    try:
                        requests.post(
                            f"{API_BASE}/org/{selected_orgnr}/broker-notes",
                            json={"text": _note_text.strip()},
                            timeout=8,
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
                                    f"{API_BASE}/org/{selected_orgnr}/broker-notes/{_note['id']}",
                                    timeout=8,
                                )
                                st.session_state["notes_refresh"] = _notes_refresh + 1
                                st.rerun()
                            except Exception as e:
                                st.error(str(e))

            # ── 10) Raw JSON debug ─────────────────────────────
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

    try:
        _sla_resp = requests.get(f"{API_BASE}/sla", timeout=8)
        _all_slas = _sla_resp.json() if _sla_resp.ok else []
    except Exception:
        _all_slas = []

    if not companies:
        st.info("No companies in portfolio yet. Search and view a company profile to add it here.")
    else:
        df = pd.DataFrame(companies)

        # ── Summary metrics ────────────────────────────────────
        _scores = df["risk_score"].dropna() if "risk_score" in df.columns else pd.Series([], dtype=float)
        _high_risk = int((_scores >= 8).sum())
        _avg_score = round(float(_scores.mean()), 1) if len(_scores) else 0
        _active_slas = sum(1 for s in _all_slas if s.get("status") == "active")

        _m1, _m2, _m3, _m4 = st.columns(4)
        _m1.metric("Selskaper", len(companies))
        _m2.metric("Gj.snitt risikoscore", _avg_score)
        _m3.metric("Høyrisikoselskaper", _high_risk)
        _m4.metric("Aktive avtaler (SLA)", _active_slas)

        # ── Renewal alerts ─────────────────────────────────────
        from datetime import date as _date, timedelta as _td
        _renewals = []
        for _s in _all_slas:
            _sd = _s.get("start_date")
            if not _sd:
                continue
            try:
                _renewal = _date.fromisoformat(_sd[:10]) + _td(days=365)
                _days_left = (_renewal - _date.today()).days
                if 0 <= _days_left <= 90:
                    _renewals.append((_s, _renewal, _days_left))
            except Exception:
                pass

        if _renewals:
            with st.expander(f"⚠️ Fornyelser innen 90 dager ({len(_renewals)} avtale(r))", expanded=True):
                for _s, _renewal, _days_left in sorted(_renewals, key=lambda x: x[2]):
                    st.warning(
                        f"**{_s.get('client_navn', _s.get('client_orgnr', '?'))}** "
                        f"— fornyelse {_renewal.strftime('%d.%m.%Y')} "
                        f"({_days_left} dager)"
                    )

        # ── Risk level column ──────────────────────────────────
        def _risk_badge(score):
            if score is None:
                return "–"
            if score <= 3:
                return "🟢 Lav"
            if score <= 7:
                return "🟡 Moderat"
            if score <= 11:
                return "🔴 Høy"
            return "🚨 Svært høy"

        display_cols = {
            "orgnr": "Orgnr",
            "navn": "Company",
            "organisasjonsform_kode": "Form",
            "kommune": "Municipality",
            "naeringskode1_beskrivelse": "Industry",
            "regnskapsår": "Year",
            "omsetning": "Revenue (MNOK)",
            "egenkapitalandel": "Equity ratio %",
            "risk_score": "Risk score",
        }
        df_display = df[[c for c in display_cols if c in df.columns]].copy()
        df_display.rename(columns=display_cols, inplace=True)

        if "Revenue (MNOK)" in df_display.columns:
            df_display["Revenue (MNOK)"] = (df_display["Revenue (MNOK)"] / 1_000_000).round(1)
        if "Equity ratio %" in df_display.columns:
            df_display["Equity ratio %"] = (df_display["Equity ratio %"] * 100).round(1)

        if "Risk score" in df_display.columns:
            df_display.insert(0, "Risikonivå", df["risk_score"].apply(_risk_badge))
            df_display = df_display.sort_values("Risk score", ascending=False, na_position="last")

        st.dataframe(df_display, use_container_width=True, hide_index=True)

        # ── Quick-load ─────────────────────────────────────────
        with st.expander("Åpne selskapsprofil"):
            _company_names = [f"{c['navn']} ({c['orgnr']})" for c in companies]
            _selected_name = st.selectbox("Velg selskap", _company_names, key="portfolio_quickload")
            if st.button("Åpne profil", key="portfolio_load_btn"):
                _idx = _company_names.index(_selected_name)
                st.session_state["selected_orgnr"] = companies[_idx]["orgnr"]
                st.session_state["show_results"] = False
                st.info("Bytt til **Selskapsøk**-fanen for å se profilen.")

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

# ──────────────────────────────────────────────
# TAB 3 — Dokumentbibliotek
# ──────────────────────────────────────────────
with tab_docs:
    # Session state
    if "doc_chat_id" not in st.session_state:
        st.session_state["doc_chat_id"] = None
    if "doc_chat_title" not in st.session_state:
        st.session_state["doc_chat_title"] = ""
    if "doc_chat_history" not in st.session_state:
        st.session_state["doc_chat_history"] = []
    if "doc_comparison" not in st.session_state:
        st.session_state["doc_comparison"] = None

    docs_sub_lib, docs_sub_cmp = st.tabs(["Dokumentbibliotek", "Sammenlign vilkår"])

    # ── Hent dokumentliste (shared) ──
    try:
        docs_resp = requests.get(f"{API_BASE}/insurance-documents", timeout=10)
        all_docs = docs_resp.json() if docs_resp.ok else []
    except Exception:
        all_docs = []

with docs_sub_lib:
    # ── Last opp dokument ──
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

    # Session state for open document panel
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

            # ── Document panel (open) ──────────────────────────────────────
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
                            # ── Om dokumentet ──────────────────────────────
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

                            # ── Key figures row ────────────────────────────
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

                            # ── Hva dekkes ────────────────────────────────
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

                            # ── Viktige vilkår ────────────────────────────
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

                            # ── Unntak ────────────────────────────────────
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
                            import base64
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

                    # ── Chat ─────────────────────────────────────────────────
                    st.markdown("---")
                    st.markdown("#### Chat med dokumentet")

                    # Initialize chat for this doc if needed
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

            # ── Fallback: raw text ─────────────────────────────
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
                # ── Structured view ────────────────────────────

                # 1) Side-by-side document summaries
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

                # 2) Pros / Cons side by side
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

                # 3) Comparison table
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

                # 4) Conclusion
                if cmp.get("conclusion"):
                    st.markdown("#### Konklusjon")
                    st.info(cmp["conclusion"])

            st.markdown("---")
            if st.button("Nullstill sammenligning", key="clr_cmp", type="secondary"):
                st.session_state["doc_comparison"] = None
                st.rerun()


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

# ──────────────────────────────────────────────
# TAB 5 — Knowledge Base (LangChain RAG)
# ──────────────────────────────────────────────
with tab_knowledge:
    st.markdown("## Kunnskapsbase")
    st.caption("Søk på tvers av all lagret selskapskunnskap, eller legg til manuell tekst som en kilde for AI-chat.")

    kb_sub_search, kb_sub_ingest = st.tabs(["Søk i kunnskap", "Legg til kunnskap"])

    # ── Search ──────────────────────────────────────────
    with kb_sub_search:
        kb_query = st.text_input("Søk i kunnskapsbase", placeholder="f.eks. 'negativ egenkapital' eller 'cyber dekning'", key="kb_query")
        kb_limit = st.slider("Antall resultater", 5, 30, 10, key="kb_limit")

        if st.button("Søk", key="kb_search_btn") and kb_query.strip():
            with st.spinner("Søker..."):
                try:
                    resp = requests.get(
                        f"{API_BASE}/knowledge",
                        params={"query": kb_query, "limit": kb_limit},
                        timeout=10,
                    )
                    results = resp.json() if resp.ok else []
                except Exception:
                    results = []

            if not results:
                st.info("Ingen relevante treff. Prøv et annet søkeord, eller legg til mer kunnskap via 'Legg til kunnskap'.")
            else:
                st.markdown(f"**{len(results)} treff**")
                for r in results:
                    with st.container(border=True):
                        c1, c2 = st.columns([2, 5])
                        with c1:
                            st.markdown(f"**Orgnr:** `{r['orgnr']}`")
                            st.caption(f"Kilde: {r['source']}")
                            st.caption(f"{(r.get('created_at') or '')[:10]}")
                        with c2:
                            st.markdown(r["chunk_text"])

    # ── Manual ingest ────────────────────────────────────
    with kb_sub_ingest:
        st.markdown("### Legg til tekst i kunnskapsbasen")
        st.caption("Teksten vil bli delt opp i biter og embeddet for bruk i AI-chat.")

        ingest_orgnr = st.text_input("Orgnr (9 siffer)", max_chars=9, key="kb_ingest_orgnr")
        ingest_source = st.text_input("Kildelabel (f.eks. 'notat_2025' eller 'e-post_klient')", key="kb_ingest_source", value="custom_note")
        ingest_text = st.text_area("Tekst å legge inn", height=200, key="kb_ingest_text")

        if st.button("Lagre i kunnskapsbase", key="kb_ingest_btn"):
            if not ingest_orgnr.strip() or len(ingest_orgnr.strip()) != 9:
                st.error("Skriv inn et gyldig 9-sifret orgnr.")
            elif not ingest_text.strip():
                st.error("Teksten kan ikke være tom.")
            else:
                with st.spinner("Chunker og embedder..."):
                    try:
                        r = requests.post(
                            f"{API_BASE}/org/{ingest_orgnr.strip()}/ingest-knowledge",
                            json={"text": ingest_text.strip(), "source": ingest_source.strip() or "custom_note"},
                            timeout=30,
                        )
                        if r.ok:
                            data = r.json()
                            st.success(f"Lagret {data['chunks_stored']} biter for orgnr {data['orgnr']} (kilde: {data['source']}).")
                        else:
                            st.error(f"Feil: {r.status_code} — {r.text}")
                    except Exception as e:
                        st.error(f"Kunne ikke kontakte API: {e}")
