import os
from typing import Any, Dict, List

# ======================
# Model configuration
# ======================
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
VOYAGE_MODEL = os.getenv("VOYAGE_MODEL", "voyage-3-lite")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# ======================
# PDF Seed Data
# Annual report PDFs for listed companies with stable public URLs.
# ======================
PDF_SEED_DATA: Dict[str, List[Dict[str, Any]]] = {
    "984851006": [   # DNB Bank ASA
        {
            "year": 2024,
            "pdf_url": "https://www.ir.dnb.no/sites/default/files/pr/202503192798-2-1.pdf",
            "label": "DNB Annual Report 2024",
        },
        {
            "year": 2023,
            "pdf_url": "https://www.ir.dnb.no/sites/default/files/Annual%20Report%202023.pdf",
            "label": "DNB Annual Report 2023",
        },
        {
            "year": 2022,
            "pdf_url": "https://www.ir.dnb.no/sites/default/files/pr/202303097878-2.pdf",
            "label": "DNB Annual Report 2022",
        },
        {
            "year": 2021,
            "pdf_url": "https://www.ir.dnb.no/sites/default/files/Annual%20Report%202021.pdf",
            "label": "DNB Annual Report 2021",
        },
        {
            "year": 2020,
            "pdf_url": "https://www.ir.dnb.no/sites/default/files/results/DNB_Bank_annual_report_2020.pdf",
            "label": "DNB Annual Report 2020",
        },
        {
            "year": 2019,
            "pdf_url": "https://www.ir.dnb.no/sites/default/files/Annual%20Report%20DNB%20Bank%202019.pdf",
            "label": "DNB Annual Report 2019",
        },
    ],
    "995568217": [   # Gjensidige Forsikring ASA
        {
            "year": 2024,
            "pdf_url": "https://www.gjensidige.com/files/content-innhold/konsern-filer/annual-reports/Annual%20report%202024.pdf",
            "label": "Gjensidige Annual Report 2024",
        },
        {
            "year": 2023,
            "pdf_url": "https://www.gjensidige.com/files/content-innhold/konsern-filer/annual-reports/Annual%20report%202023%20Gjensidige.pdf",
            "label": "Gjensidige Annual Report 2023",
        },
        {
            "year": 2022,
            "pdf_url": "https://www.gjensidige.com/files/content-files/group-files/Gjensidige%20Forsikring%20Annual%20Report%202022.pdf",
            "label": "Gjensidige Annual Report 2022",
        },
        {
            "year": 2021,
            "pdf_url": "https://mb.cision.com/Public/1122/3508195/afe168b161d05b93.pdf",
            "label": "Gjensidige Annual Report 2021",
        },
        {
            "year": 2020,
            "pdf_url": "https://mb.cision.com/Public/1122/3285601/8353111a7aca0ddf.pdf",
            "label": "Gjensidige Annual Report 2020",
        },
        {
            "year": 2019,
            "pdf_url": "https://mb.cision.com/Main/1122/3035389/1193913.pdf",
            "label": "Gjensidige Annual Report 2019",
        },
    ],
    "979981344": [   # Søderberg & Partners Norge AS
        {
            "year": 2023,
            "pdf_url": "https://mb.cision.com/Main/6558/3945675/2668201.pdf",
            "label": "Söderberg & Partners Group Annual Report 2023 (SEK)",
        },
    ],
    "923609016": [   # Equinor ASA
        {
            "year": 2024,
            "pdf_url": "https://cdn.sanity.io/files/h61q9gi9/global/16ccbc5a098c3b971979118420c4f83ddee18fb4.pdf",
            "label": "Equinor Annual Report 2024",
        },
        {
            "year": 2023,
            "pdf_url": "https://cdn.equinor.com/files/h61q9gi9/global/76629806e2cc50eefdd89d5b8daabda39247db63.pdf",
            "label": "Equinor Annual Report 2023",
        },
        {
            "year": 2022,
            "pdf_url": "https://cdn.equinor.com/files/h61q9gi9/global/d3b41d2d0b98906de981ded0cd454636c1ba9088.pdf",
            "label": "Equinor Annual Report 2022",
        },
        {
            "year": 2021,
            "pdf_url": "https://cdn.equinor.com/files/h61q9gi9/global/83ce4c64e602e203100e1ce2c5de9b2d42ff8192.pdf",
            "label": "Equinor Annual Report 2021",
        },
        {
            "year": 2020,
            "pdf_url": "https://cdn.equinor.com/files/h61q9gi9/global/50088434118167232c3cd8dc335ca7d419eb272f.pdf",
            "label": "Equinor Annual Report 2020",
        },
        {
            "year": 2019,
            "pdf_url": "https://cdn.equinor.com/files/h61q9gi9/global/285c51a7491a6dd19f981ee256f34b08ec83bb85.pdf",
            "label": "Equinor Annual Report 2019",
        },
    ],
}

# ======================
# External API URLs
# ======================

# --- BRREG ---
BRREG_ENHETER_URL = "https://data.brreg.no/enhetsregisteret/api/enheter"

# --- Finanstilsynet ---
FINANSTILSYNET_REGISTRY_URL = "https://api.finanstilsynet.no/registry/api/v2/entities"

# --- OpenSanctions (PEP/sanctions) ---
OPENSANCTIONS_SEARCH_URL = "https://api.opensanctions.org/search/peps"

# --- Kartverket – geocoding ---
KARTVERKET_ADRESSE_URL = "https://ws.geonorge.no/adresser/v1/sok"

# ======================
# PDF extraction models
# ======================
GEMINI_PDF_MODELS: List[str] = ["gemini-2.5-flash", "gemini-1.5-flash"]

# ======================
# SSB-informed industry benchmarks
# ======================
NACE_BENCHMARKS: Dict[str, Dict[str, Any]] = {
    "A": {"industry": "Agriculture / Forestry / Fishing",      "eq_ratio_min": 0.35, "eq_ratio_max": 0.55, "margin_min": 0.03, "margin_max": 0.10},
    "B": {"industry": "Mining / Quarrying",                     "eq_ratio_min": 0.30, "eq_ratio_max": 0.50, "margin_min": 0.10, "margin_max": 0.25},
    "C": {"industry": "Manufacturing",                          "eq_ratio_min": 0.30, "eq_ratio_max": 0.50, "margin_min": 0.03, "margin_max": 0.10},
    "D": {"industry": "Electricity / Gas / Steam",              "eq_ratio_min": 0.30, "eq_ratio_max": 0.50, "margin_min": 0.05, "margin_max": 0.15},
    "E": {"industry": "Water / Waste Management",               "eq_ratio_min": 0.30, "eq_ratio_max": 0.45, "margin_min": 0.05, "margin_max": 0.12},
    "F": {"industry": "Construction",                           "eq_ratio_min": 0.20, "eq_ratio_max": 0.38, "margin_min": 0.02, "margin_max": 0.07},
    "G": {"industry": "Wholesale / Retail Trade",               "eq_ratio_min": 0.25, "eq_ratio_max": 0.42, "margin_min": 0.01, "margin_max": 0.05},
    "H": {"industry": "Transport / Storage",                    "eq_ratio_min": 0.22, "eq_ratio_max": 0.38, "margin_min": 0.02, "margin_max": 0.07},
    "I": {"industry": "Accommodation / Food Service",           "eq_ratio_min": 0.15, "eq_ratio_max": 0.35, "margin_min": 0.01, "margin_max": 0.06},
    "J": {"industry": "Information / Communication / IT",       "eq_ratio_min": 0.40, "eq_ratio_max": 0.65, "margin_min": 0.08, "margin_max": 0.20},
    "K": {"industry": "Financial / Insurance Services",         "eq_ratio_min": 0.10, "eq_ratio_max": 0.25, "margin_min": 0.10, "margin_max": 0.30},
    "L": {"industry": "Real Estate",                            "eq_ratio_min": 0.30, "eq_ratio_max": 0.55, "margin_min": 0.15, "margin_max": 0.35},
    "M": {"industry": "Professional / Scientific / Technical",  "eq_ratio_min": 0.35, "eq_ratio_max": 0.60, "margin_min": 0.06, "margin_max": 0.15},
    "N": {"industry": "Administrative / Support Services",      "eq_ratio_min": 0.28, "eq_ratio_max": 0.45, "margin_min": 0.03, "margin_max": 0.10},
    "O": {"industry": "Public Administration",                  "eq_ratio_min": 0.30, "eq_ratio_max": 0.60, "margin_min": 0.00, "margin_max": 0.05},
    "P": {"industry": "Education",                              "eq_ratio_min": 0.30, "eq_ratio_max": 0.55, "margin_min": 0.02, "margin_max": 0.08},
    "Q": {"industry": "Health / Social Work",                   "eq_ratio_min": 0.28, "eq_ratio_max": 0.48, "margin_min": 0.02, "margin_max": 0.08},
    "R": {"industry": "Arts / Entertainment / Recreation",      "eq_ratio_min": 0.22, "eq_ratio_max": 0.45, "margin_min": 0.02, "margin_max": 0.08},
    "S": {"industry": "Other Service Activities",               "eq_ratio_min": 0.25, "eq_ratio_max": 0.45, "margin_min": 0.03, "margin_max": 0.09},
}

# ── LLM / analysis limits ─────────────────────────────────────────────────────
LLM_DOCUMENT_CHAR_LIMIT = 12_000   # max chars sent to LLM for document analysis
LLM_TEXT_CHAR_LIMIT = 8_000        # max chars for text-based LLM fallback
TEXT_EMBED_CHAR_LIMIT = 2_000      # max chars sent to the embedding model
GEMINI_FILES_API_THRESHOLD = 18 * 1024 * 1024  # 18 MB — use Files API above this
PDF_PAGE_LIMIT_EXTRACT = 60        # max pages for pdfplumber extraction
PDF_PAGE_LIMIT_LAYOUT = 40         # max pages for layout analysis
PDF_URL_LIMIT = 8                  # max PDF URLs to validate per discovery run

_NACE_SECTION_MAP: List[tuple] = [
    (range(1, 4),   "A"),
    (range(5, 10),  "B"),
    (range(10, 34), "C"),
    (range(35, 36), "D"),
    (range(36, 40), "E"),
    (range(41, 44), "F"),
    (range(45, 48), "G"),
    (range(49, 54), "H"),
    (range(55, 57), "I"),
    (range(58, 64), "J"),
    (range(64, 67), "K"),
    (range(68, 69), "L"),
    (range(69, 76), "M"),
    (range(77, 83), "N"),
    (range(84, 85), "O"),
    (range(85, 86), "P"),
    (range(86, 89), "Q"),
    (range(90, 94), "R"),
    (range(94, 97), "S"),
]

# ======================
# SLA standard terms and broker tasks
# ======================
STANDARD_VILKAAR = [
    (
        "Avtalens varighet",
        "Avtalen gjelder for ett ar med automatisk fornyelse, med mindre den sies opp "
        "skriftlig av en av partene med fire maneders varsel for utlopsdato.",
    ),
    (
        "Kommunikasjon",
        "All skriftlig kommunikasjon mellom partene skjer elektronisk, som utgangspunkt pa norsk.",
    ),
    (
        "Kundens informasjonsplikt",
        "Kunden plikter a gi megler korrekt og fullstendig informasjon om forsikringsgjenstandene "
        "og risikoen, samt opplyse om tidligere forsikringsforhold og anmeldte skader. "
        "Kunden plikter a gjore lopende rede for endringer i risiko av betydning for forsikringsforholdene.",
    ),
    (
        "Premiebetaling",
        "Forsikringsselskapets premiefaktura sendes, etter kontroll av megler, til Kunden for "
        "betaling direkte til forsikringsselskapet. Kunden er selv ansvarlig for renter og "
        "purregebyr ved for sen betaling, med mindre forsinkelsen skyldes forhold megler har kontroll over.",
    ),
    (
        "Taushetsplikt",
        "Begge parter er forpliktet til a behandle konfidensiell informasjon med forsvarlig "
        "aktsomhet og ikke videreformidle denne til tredjeparter uten skriftlig samtykke.",
    ),
    (
        "Oppsigelse",
        "Avtalen kan sies opp av begge parter med fire maneders skriftlig varsel. "
        "Ved manglende betaling av utestaaende honorar kan megler varsle oppsigelse. "
        "Ved vesentlig mislighold kan avtalen heves med umiddelbar virkning.",
    ),
    (
        "Arlig avtalegjennomgang",
        "Partene skal gjennomga avtaleomfang og foreta nodvendige oppdateringer minimum en gang per ar.",
    ),
    (
        "Ansvarsbegrensning",
        "Meglers ansvar for radgivningsfeil er begrenset til NOK 25 000 000 per oppdrag og "
        "NOK 50 000 000 per kalenderaar. Det svares ikke erstatning for indirekte tap. "
        "Ansvarsbegrensningen omfatter ikke grov uaktsomhet og forsett.",
    ),
    (
        "Klageadgang og verneting",
        "Klager pa meglers tjenester rettes skriftlig til megler. Uloste tvister sokes lost "
        "i minnelighet, og kan bringes inn for Klagenemnda for forsikrings- og "
        "gjenforsikringsmeglingsvirksomhet. Oslo tingrett er verneting.",
    ),
    (
        "Konsesjon og eierskap",
        "Megler har konsesjon til a drive forsikringsmeglingsvirksomhet fra Finanstilsynet. "
        "Megler har verken direkte eller indirekte eierandel som utgjor mer enn 10 % av "
        "stemmeretten eller kapitalen i et forsikringsselskap, og tilsvarende gjelder motsatt vei.",
    ),
    (
        "Forholdet til forsikringsavtaleloven",
        "Med mindre forholdet er omtalt i denne avtalen, fravikes de bestemmelser i "
        "forsikringsavtaleloven som det er adgang til ved forsikringsmegling med andre enn "
        "forbrukere og ved avtale om store risikoer.",
    ),
]

BROKER_TASKS = [
    (
        "Forsikringsmegling av kundens forsikringsprogram",
        "Megler gir kunden rad pa basis av en objektiv analyse av tilgjengelige forsikringslosninger. "
        "Megler innhenter tilbud fra relevante forsikringsgivere, foretar sammenligning og anbefaler "
        "losning i samsvar med kundens behov og risikoeksponering.",
    ),
    (
        "Dokumentasjon og kontroll",
        "Megler kontrollerer at utstedte forsikringsdokumenter er i samsvar med avtalt dekning. "
        "Megler arkiverer og gjor forsikringsdokumentasjon tilgjengelig for kunden. "
        "Megler varsler kunden i god tid for forfall og ved vesentlige endringer i vilkar.",
    ),
    (
        "Skadebehandling",
        "Megler bistar kunden ved anmeldelse av skader til forsikringsselskapet. "
        "Megler folger opp skadebehandlingen og bistar ved uenighet om oppgjor. "
        "Megler dokumenterer alle skader pa vegne av kunden.",
    ),
    (
        "Tilleggstjenester",
        "Etter avtale kan megler yte tilleggstjenester som risikoanalyse, internasjonale "
        "forsikringsprogrammer, pensjonsradgivning og andre spesialtjenester. "
        "Slikt arbeid prises separat med mindre annet er avtalt.",
    ),
]
