"""Generate three realistic Norwegian risk-profile PDFs for demo purposes.

These match what brokers send to insurance companies as the "anbudspakke"
(the outgoing side of the tender flow). Pairs with
``generate_sample_offers.py`` which generates the reply side.

Run:  uv run python scripts/generate_sample_risk_profiles.py
Output: sample_risk_profiles/risk_<company-slug>.pdf (3 files)
"""

from __future__ import annotations

import os
from pathlib import Path

from api.services.pdf_risk import generate_risk_report_pdf


def _s(t: str) -> str:
    """fpdf2's default Helvetica is latin-1 - strip unicode dashes/quotes
    before passing to the PDF generator."""
    return (
        t.replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .encode("latin-1", errors="replace")
        .decode("latin-1")
    )


def _sanitize(profile: dict) -> dict:
    """Deep-sanitize strings in a profile dict (handles nested reasons list)."""
    out: dict = {}
    for k, v in profile.items():
        if isinstance(v, str):
            out[k] = _s(v)
        elif isinstance(v, dict):
            out[k] = _sanitize(v)
        elif isinstance(v, list):
            out[k] = [_s(x) if isinstance(x, str) else x for x in v]
        else:
            out[k] = v
    return out


# Three fictional-but-plausible Norwegian SMBs spanning the risk spectrum:
# manufacturing (mid), hospitality (high), consulting (low). Each has a
# filled-out financial + risk profile realistic enough for an insurance
# underwriter to treat as a genuine anbudspakke.

DEMO_PROFILES = [
    {
        "slug": "bergmann_industri",
        "orgnr": "987 654 321",
        "navn": "Bergmann Industri AS",
        "organisasjonsform_kode": "AS",
        "kommune": "Oslo",
        "naeringskode1": "25.110",
        "naeringskode1_beskrivelse": "Produksjon av metallkonstruksjoner og deler",
        "stiftelsesdato": "2011-03-14",
        "sum_driftsinntekter": 78_500_000.0,
        "sum_egenkapital": 21_400_000.0,
        "sum_eiendeler": 62_800_000.0,
        "regn": {
            "driftsresultat": 6_200_000.0,
            "aarsresultat": 4_350_000.0,
            "sum_omsetning": 78_500_000.0,
            "sum_gjeld": 41_400_000.0,
            "likviditetsgrad_1": 1.42,
            "egenkapitalandel": 0.34,
            "antall_ansatte": 54,
        },
        "risk": {
            "score": 6,
            "equity_ratio": 0.34,
            "factors": [
                {
                    "label": "Stabil omsetning +5% YoY siste 3 år",
                    "category": "Finans",
                    "points": 1,
                },
                {
                    "label": "Metallindustri - råvarepriseksponering",
                    "category": "Bransje",
                    "points": 2,
                },
                {
                    "label": "Moderat gearing (EK-andel 34%)",
                    "category": "Finans",
                    "points": 1,
                },
                {
                    "label": "Ingen historiske branner/storskader",
                    "category": "Historikk",
                    "points": 0,
                },
                {
                    "label": "Oslo - ingen naturfareeksponering",
                    "category": "Geografi",
                    "points": 2,
                },
            ],
        },
    },
    {
        "slug": "nordlys_restaurant",
        "orgnr": "912 345 678",
        "navn": "Nordlys Restaurantgruppe AS",
        "organisasjonsform_kode": "AS",
        "kommune": "Tromsø",
        "naeringskode1": "56.101",
        "naeringskode1_beskrivelse": "Drift av restauranter og kafeer",
        "stiftelsesdato": "2017-08-22",
        "sum_driftsinntekter": 42_300_000.0,
        "sum_egenkapital": 5_800_000.0,
        "sum_eiendeler": 28_600_000.0,
        "regn": {
            "driftsresultat": 1_850_000.0,
            "aarsresultat": 1_120_000.0,
            "sum_omsetning": 42_300_000.0,
            "sum_gjeld": 22_800_000.0,
            "likviditetsgrad_1": 0.91,
            "egenkapitalandel": 0.20,
            "antall_ansatte": 38,
        },
        "risk": {
            "score": 11,
            "equity_ratio": 0.20,
            "factors": [
                {
                    "label": "3 lokasjoner - øker brannpåvirkning",
                    "category": "Geografi",
                    "points": 2,
                },
                {
                    "label": "Åpen flamme/kjøkken - høy brannrisiko",
                    "category": "Bransje",
                    "points": 3,
                },
                {"label": "Lav EK-andel (20%)", "category": "Finans", "points": 2},
                {"label": "Likviditet under 1.0", "category": "Finans", "points": 2},
                {
                    "label": "Sesongbasert omsetning (60% sommer)",
                    "category": "Bransje",
                    "points": 2,
                },
                {
                    "label": "Ingen historiske storskader",
                    "category": "Historikk",
                    "points": 0,
                },
            ],
        },
    },
    {
        "slug": "arcticom_consulting",
        "orgnr": "925 888 111",
        "navn": "Arcticom Consulting AS",
        "organisasjonsform_kode": "AS",
        "kommune": "Trondheim",
        "naeringskode1": "70.220",
        "naeringskode1_beskrivelse": "Bedriftsrådgivning og annen administrativ rådgivning",
        "stiftelsesdato": "2019-01-10",
        "sum_driftsinntekter": 23_400_000.0,
        "sum_egenkapital": 14_200_000.0,
        "sum_eiendeler": 19_800_000.0,
        "regn": {
            "driftsresultat": 4_800_000.0,
            "aarsresultat": 3_620_000.0,
            "sum_omsetning": 23_400_000.0,
            "sum_gjeld": 5_600_000.0,
            "likviditetsgrad_1": 2.84,
            "egenkapitalandel": 0.72,
            "antall_ansatte": 17,
        },
        "risk": {
            "score": 3,
            "equity_ratio": 0.72,
            "factors": [
                {
                    "label": "Rådgivning - lav brann-/ulykkesrisiko",
                    "category": "Bransje",
                    "points": 0,
                },
                {"label": "Solid EK-andel (72%)", "category": "Finans", "points": 0},
                {"label": "Likviditet 2.84 - sterk", "category": "Finans", "points": 0},
                {
                    "label": "45% omsetning fra 2 kunder",
                    "category": "Strategi",
                    "points": 2,
                },
                {
                    "label": "Profesjonsansvar-eksponering",
                    "category": "Bransje",
                    "points": 1,
                },
            ],
        },
    },
    # ── Real-world Norwegian large caps (fictional numbers; for demo only) ─────
    {
        "slug": "dnb",
        "orgnr": "984 851 006",
        "navn": "DNB Bank ASA",
        "organisasjonsform_kode": "ASA",
        "kommune": "Oslo",
        "naeringskode1": "64.190",
        "naeringskode1_beskrivelse": "Annen bankvirksomhet",
        "stiftelsesdato": "2003-11-10",
        "sum_driftsinntekter": 68_500_000_000.0,
        "sum_egenkapital": 275_000_000_000.0,
        "sum_eiendeler": 3_450_000_000_000.0,
        "regn": {
            "driftsresultat": 40_800_000_000.0,
            "aarsresultat": 32_400_000_000.0,
            "sum_omsetning": 68_500_000_000.0,
            "sum_gjeld": 3_175_000_000_000.0,
            "likviditetsgrad_1": 1.45,
            "egenkapitalandel": 0.08,
            "antall_ansatte": 10_400,
        },
        "risk": {
            "score": 4,
            "equity_ratio": 0.08,
            "factors": [
                {
                    "label": "Systemviktig bank - tilsynsregulert",
                    "category": "Regulatorisk",
                    "points": 1,
                },
                {
                    "label": "Solid kapitaldekning (18.7% CET1)",
                    "category": "Finans",
                    "points": 0,
                },
                {
                    "label": "Cyber-risiko - hovedmål for angrep",
                    "category": "Operasjonell",
                    "points": 2,
                },
                {
                    "label": "Pengevasking/sanksjoner compliance",
                    "category": "Regulatorisk",
                    "points": 1,
                },
                {"label": "Kontorer i 16 land", "category": "Geografi", "points": 0},
            ],
        },
    },
    {
        "slug": "telenor",
        "orgnr": "982 463 718",
        "navn": "Telenor ASA",
        "organisasjonsform_kode": "ASA",
        "kommune": "Bærum",
        "naeringskode1": "61.200",
        "naeringskode1_beskrivelse": "Trådløs telekommunikasjon",
        "stiftelsesdato": "2000-05-18",
        "sum_driftsinntekter": 72_300_000_000.0,
        "sum_egenkapital": 58_200_000_000.0,
        "sum_eiendeler": 215_000_000_000.0,
        "regn": {
            "driftsresultat": 16_500_000_000.0,
            "aarsresultat": 11_200_000_000.0,
            "sum_omsetning": 72_300_000_000.0,
            "sum_gjeld": 156_800_000_000.0,
            "likviditetsgrad_1": 1.08,
            "egenkapitalandel": 0.27,
            "antall_ansatte": 16_000,
        },
        "risk": {
            "score": 5,
            "equity_ratio": 0.27,
            "factors": [
                {
                    "label": "Kritisk infrastruktur - terrormål",
                    "category": "Operasjonell",
                    "points": 2,
                },
                {
                    "label": "Cyber/nettangrep eksponering",
                    "category": "Operasjonell",
                    "points": 1,
                },
                {
                    "label": "Geopolitisk (Asia-eksponering)",
                    "category": "Geografi",
                    "points": 1,
                },
                {
                    "label": "Stabil kontantstrøm fra abonnenter",
                    "category": "Finans",
                    "points": 0,
                },
                {
                    "label": "Frekvenslisenser fornyelsesrisiko",
                    "category": "Regulatorisk",
                    "points": 1,
                },
            ],
        },
    },
    {
        "slug": "norgesgruppen",
        "orgnr": "926 227 819",
        "navn": "NorgesGruppen ASA",
        "organisasjonsform_kode": "ASA",
        "kommune": "Oslo",
        "naeringskode1": "46.390",
        "naeringskode1_beskrivelse": "Uspesifisert engroshandel med nærings- og nytelsesmidler",
        "stiftelsesdato": "2000-06-15",
        "sum_driftsinntekter": 125_400_000_000.0,
        "sum_egenkapital": 28_900_000_000.0,
        "sum_eiendeler": 82_500_000_000.0,
        "regn": {
            "driftsresultat": 5_100_000_000.0,
            "aarsresultat": 3_650_000_000.0,
            "sum_omsetning": 125_400_000_000.0,
            "sum_gjeld": 53_600_000_000.0,
            "likviditetsgrad_1": 0.98,
            "egenkapitalandel": 0.35,
            "antall_ansatte": 45_000,
        },
        "risk": {
            "score": 5,
            "equity_ratio": 0.35,
            "factors": [
                {
                    "label": "1800+ butikker - aggregert brannrisiko",
                    "category": "Geografi",
                    "points": 2,
                },
                {
                    "label": "Kaldelageranlegg - ammoniakk-lekkasje",
                    "category": "Operasjonell",
                    "points": 1,
                },
                {
                    "label": "Lav margin - sensitiv for driftsavbrudd",
                    "category": "Finans",
                    "points": 1,
                },
                {
                    "label": "Solid markedsposisjon (43% dagligvare)",
                    "category": "Strategi",
                    "points": 0,
                },
                {
                    "label": "Matvaresikkerhet/produktansvar",
                    "category": "Regulatorisk",
                    "points": 1,
                },
            ],
        },
    },
    {
        "slug": "kongsberg",
        "orgnr": "943 753 709",
        "navn": "Kongsberg Gruppen ASA",
        "organisasjonsform_kode": "ASA",
        "kommune": "Kongsberg",
        "naeringskode1": "30.300",
        "naeringskode1_beskrivelse": "Produksjon av luft- og romfartøyer",
        "stiftelsesdato": "1987-12-18",
        "sum_driftsinntekter": 33_400_000_000.0,
        "sum_egenkapital": 11_200_000_000.0,
        "sum_eiendeler": 48_600_000_000.0,
        "regn": {
            "driftsresultat": 4_200_000_000.0,
            "aarsresultat": 3_100_000_000.0,
            "sum_omsetning": 33_400_000_000.0,
            "sum_gjeld": 37_400_000_000.0,
            "likviditetsgrad_1": 1.32,
            "egenkapitalandel": 0.23,
            "antall_ansatte": 13_500,
        },
        "risk": {
            "score": 7,
            "equity_ratio": 0.23,
            "factors": [
                {
                    "label": "Forsvarsteknologi - eksportkontroll",
                    "category": "Regulatorisk",
                    "points": 3,
                },
                {
                    "label": "Høyt IP-verdi - industrispionasje",
                    "category": "Operasjonell",
                    "points": 2,
                },
                {
                    "label": "NATO-kontrakter (ordrereserve 100+ BNOK)",
                    "category": "Strategi",
                    "points": 0,
                },
                {
                    "label": "Maritime systemer - produktansvar",
                    "category": "Bransje",
                    "points": 1,
                },
                {
                    "label": "Geopolitisk - sensitiv for sanksjoner",
                    "category": "Regulatorisk",
                    "points": 1,
                },
            ],
        },
    },
    {
        "slug": "strawberry",
        "orgnr": "991 550 513",
        "navn": "Strawberry Hospitality Group AS",
        "organisasjonsform_kode": "AS",
        "kommune": "Oslo",
        "naeringskode1": "55.101",
        "naeringskode1_beskrivelse": "Drift av hoteller, pensjonater og moteller med restaurant",
        "stiftelsesdato": "2008-04-02",
        "sum_driftsinntekter": 12_800_000_000.0,
        "sum_egenkapital": 1_200_000_000.0,
        "sum_eiendeler": 9_800_000_000.0,
        "regn": {
            "driftsresultat": 980_000_000.0,
            "aarsresultat": 420_000_000.0,
            "sum_omsetning": 12_800_000_000.0,
            "sum_gjeld": 8_600_000_000.0,
            "likviditetsgrad_1": 0.87,
            "egenkapitalandel": 0.12,
            "antall_ansatte": 17_000,
        },
        "risk": {
            "score": 10,
            "equity_ratio": 0.12,
            "factors": [
                {
                    "label": "230+ hoteller i Norden",
                    "category": "Geografi",
                    "points": 2,
                },
                {
                    "label": "Brannrisiko - åpen flamme i restauranter",
                    "category": "Bransje",
                    "points": 2,
                },
                {
                    "label": "Covid-sårbar (2020-21 demonstrerte)",
                    "category": "Finans",
                    "points": 2,
                },
                {"label": "Lav EK-andel (12%)", "category": "Finans", "points": 2},
                {
                    "label": "Turistsesong - Q3 overvekt",
                    "category": "Strategi",
                    "points": 1,
                },
                {
                    "label": "Ansvarskrav gjester (fall, matforgiftning)",
                    "category": "Bransje",
                    "points": 1,
                },
            ],
        },
    },
    {
        "slug": "sats",
        "orgnr": "915 011 492",
        "navn": "SATS Group AS",
        "organisasjonsform_kode": "AS",
        "kommune": "Oslo",
        "naeringskode1": "93.130",
        "naeringskode1_beskrivelse": "Drift av treningssentre",
        "stiftelsesdato": "2016-09-30",
        "sum_driftsinntekter": 4_200_000_000.0,
        "sum_egenkapital": 850_000_000.0,
        "sum_eiendeler": 3_100_000_000.0,
        "regn": {
            "driftsresultat": 285_000_000.0,
            "aarsresultat": 145_000_000.0,
            "sum_omsetning": 4_200_000_000.0,
            "sum_gjeld": 2_250_000_000.0,
            "likviditetsgrad_1": 0.72,
            "egenkapitalandel": 0.27,
            "antall_ansatte": 6_400,
        },
        "risk": {
            "score": 8,
            "equity_ratio": 0.27,
            "factors": [
                {
                    "label": "250+ sentre (NO/SE/DK/FI) - brannrisiko",
                    "category": "Geografi",
                    "points": 2,
                },
                {
                    "label": "Medlemsskader - ansvarskrav",
                    "category": "Bransje",
                    "points": 2,
                },
                {
                    "label": "Covid viste sårbarhet (lockdown)",
                    "category": "Finans",
                    "points": 2,
                },
                {
                    "label": "Boblebad/badstu - Legionella-risiko",
                    "category": "Operasjonell",
                    "points": 1,
                },
                {
                    "label": "Lavere likviditet (0.72)",
                    "category": "Finans",
                    "points": 1,
                },
            ],
        },
    },
    {
        "slug": "thon_hotels",
        "orgnr": "982 504 590",
        "navn": "Thon Hotels AS",
        "organisasjonsform_kode": "AS",
        "kommune": "Oslo",
        "naeringskode1": "55.101",
        "naeringskode1_beskrivelse": "Drift av hoteller, pensjonater og moteller med restaurant",
        "stiftelsesdato": "2000-03-01",
        "sum_driftsinntekter": 4_900_000_000.0,
        "sum_egenkapital": 2_800_000_000.0,
        "sum_eiendeler": 8_600_000_000.0,
        "regn": {
            "driftsresultat": 780_000_000.0,
            "aarsresultat": 520_000_000.0,
            "sum_omsetning": 4_900_000_000.0,
            "sum_gjeld": 5_800_000_000.0,
            "likviditetsgrad_1": 1.48,
            "egenkapitalandel": 0.33,
            "antall_ansatte": 3_800,
        },
        "risk": {
            "score": 6,
            "equity_ratio": 0.33,
            "factors": [
                {
                    "label": "85+ hoteller - spredt portefølje",
                    "category": "Geografi",
                    "points": 1,
                },
                {
                    "label": "Solid eier (Olav Thon Stiftelse)",
                    "category": "Finans",
                    "points": 0,
                },
                {
                    "label": "Brannrisiko åpen flamme",
                    "category": "Bransje",
                    "points": 2,
                },
                {
                    "label": "Eier egne eiendommer - bygningsrisiko",
                    "category": "Bransje",
                    "points": 2,
                },
                {
                    "label": "Norskdominant - sesongavhengig",
                    "category": "Strategi",
                    "points": 1,
                },
            ],
        },
    },
    {
        "slug": "xxl",
        "orgnr": "983 320 768",
        "navn": "XXL ASA",
        "organisasjonsform_kode": "ASA",
        "kommune": "Oslo",
        "naeringskode1": "47.641",
        "naeringskode1_beskrivelse": "Butikkhandel med sportsutstyr",
        "stiftelsesdato": "2000-11-07",
        "sum_driftsinntekter": 8_900_000_000.0,
        "sum_egenkapital": 380_000_000.0,
        "sum_eiendeler": 4_200_000_000.0,
        "regn": {
            "driftsresultat": -240_000_000.0,
            "aarsresultat": -480_000_000.0,
            "sum_omsetning": 8_900_000_000.0,
            "sum_gjeld": 3_820_000_000.0,
            "likviditetsgrad_1": 0.68,
            "egenkapitalandel": 0.09,
            "antall_ansatte": 2_900,
        },
        "risk": {
            "score": 13,
            "equity_ratio": 0.09,
            "factors": [
                {
                    "label": "Negativt driftsresultat 2 år på rad",
                    "category": "Finans",
                    "points": 3,
                },
                {
                    "label": "Warehouse-brann Gardermoen 2023",
                    "category": "Historikk",
                    "points": 2,
                },
                {
                    "label": "EK-andel 9% - svært gearet",
                    "category": "Finans",
                    "points": 3,
                },
                {
                    "label": "Likviditet 0.68 - kortsiktig press",
                    "category": "Finans",
                    "points": 2,
                },
                {
                    "label": "Netthandel-disrupsjon fra Kina",
                    "category": "Strategi",
                    "points": 2,
                },
                {
                    "label": "100+ fysiske butikker - kostnadsbase",
                    "category": "Strategi",
                    "points": 1,
                },
            ],
        },
    },
    {
        "slug": "norwegian_air",
        "orgnr": "965 920 358",
        "navn": "Norwegian Air Shuttle ASA",
        "organisasjonsform_kode": "ASA",
        "kommune": "Bærum",
        "naeringskode1": "51.100",
        "naeringskode1_beskrivelse": "Passasjertransport med luftfartøy",
        "stiftelsesdato": "1993-01-28",
        "sum_driftsinntekter": 24_600_000_000.0,
        "sum_egenkapital": 4_800_000_000.0,
        "sum_eiendeler": 21_400_000_000.0,
        "regn": {
            "driftsresultat": 1_800_000_000.0,
            "aarsresultat": 780_000_000.0,
            "sum_omsetning": 24_600_000_000.0,
            "sum_gjeld": 16_600_000_000.0,
            "likviditetsgrad_1": 0.84,
            "egenkapitalandel": 0.22,
            "antall_ansatte": 4_500,
        },
        "risk": {
            "score": 14,
            "equity_ratio": 0.22,
            "factors": [
                {
                    "label": "Flyulykke - katastrofalt skadepotensial",
                    "category": "Bransje",
                    "points": 4,
                },
                {
                    "label": "Post-restrukturering (2020 konkurs)",
                    "category": "Historikk",
                    "points": 3,
                },
                {
                    "label": "Oljepris 80% korrelasjon m/driftskost",
                    "category": "Finans",
                    "points": 2,
                },
                {
                    "label": "Ekstremvær - askesky/vulkansky risiko",
                    "category": "Geografi",
                    "points": 2,
                },
                {
                    "label": "Pilotstreik historisk - driftsstans",
                    "category": "Operasjonell",
                    "points": 2,
                },
                {
                    "label": "EU261 kompensasjonskrav",
                    "category": "Regulatorisk",
                    "points": 1,
                },
            ],
        },
    },
    {
        "slug": "orkla",
        "orgnr": "910 747 711",
        "navn": "Orkla ASA",
        "organisasjonsform_kode": "ASA",
        "kommune": "Oslo",
        "naeringskode1": "10.890",
        "naeringskode1_beskrivelse": "Annen produksjon av næringsmidler ikke nevnt annet sted",
        "stiftelsesdato": "1929-04-15",
        "sum_driftsinntekter": 61_200_000_000.0,
        "sum_egenkapital": 32_400_000_000.0,
        "sum_eiendeler": 82_600_000_000.0,
        "regn": {
            "driftsresultat": 7_800_000_000.0,
            "aarsresultat": 5_400_000_000.0,
            "sum_omsetning": 61_200_000_000.0,
            "sum_gjeld": 50_200_000_000.0,
            "likviditetsgrad_1": 1.52,
            "egenkapitalandel": 0.39,
            "antall_ansatte": 21_000,
        },
        "risk": {
            "score": 4,
            "equity_ratio": 0.39,
            "factors": [
                {
                    "label": "Diversifisert portefølje (Stabburet, Grandiosa, Nidar)",
                    "category": "Strategi",
                    "points": 0,
                },
                {"label": "Solid EK-andel (39%)", "category": "Finans", "points": 0},
                {
                    "label": "Produksjonsanlegg - produktansvar",
                    "category": "Bransje",
                    "points": 1,
                },
                {
                    "label": "Råvarepriseksponering (korn, kakao)",
                    "category": "Finans",
                    "points": 1,
                },
                {
                    "label": "Stabil etterspørsel dagligvare",
                    "category": "Strategi",
                    "points": 0,
                },
                {
                    "label": "Brannrisiko matproduksjon",
                    "category": "Bransje",
                    "points": 2,
                },
            ],
        },
    },
    {
        "slug": "vinmonopolet",
        "orgnr": "817 200 722",
        "navn": "AS Vinmonopolet",
        "organisasjonsform_kode": "AS",
        "kommune": "Oslo",
        "naeringskode1": "47.250",
        "naeringskode1_beskrivelse": "Butikkhandel med drikkevarer",
        "stiftelsesdato": "1922-11-30",
        "sum_driftsinntekter": 18_400_000_000.0,
        "sum_egenkapital": 520_000_000.0,
        "sum_eiendeler": 3_100_000_000.0,
        "regn": {
            "driftsresultat": 186_000_000.0,
            "aarsresultat": 152_000_000.0,
            "sum_omsetning": 18_400_000_000.0,
            "sum_gjeld": 2_580_000_000.0,
            "likviditetsgrad_1": 1.18,
            "egenkapitalandel": 0.17,
            "antall_ansatte": 1_980,
        },
        "risk": {
            "score": 3,
            "equity_ratio": 0.17,
            "factors": [
                {
                    "label": "Statlig monopol - null konkurranse",
                    "category": "Strategi",
                    "points": 0,
                },
                {
                    "label": "350+ butikker - aggregert risiko",
                    "category": "Geografi",
                    "points": 1,
                },
                {
                    "label": "Tyveri/ran - høyverdivarer",
                    "category": "Operasjonell",
                    "points": 1,
                },
                {
                    "label": "Strengt regulert - alkoholloven",
                    "category": "Regulatorisk",
                    "points": 1,
                },
                {
                    "label": "Statsgaranti - lav kredittrisiko",
                    "category": "Finans",
                    "points": 0,
                },
            ],
        },
    },
]


def main() -> None:
    out_dir = Path("sample_risk_profiles")
    out_dir.mkdir(exist_ok=True)

    for raw in DEMO_PROFILES:
        slug = raw["slug"]
        profile = _sanitize({k: v for k, v in raw.items() if k != "slug"})
        pdf_bytes = generate_risk_report_pdf(**profile)  # type: ignore[arg-type]
        path = out_dir / f"risk_{slug}.pdf"
        path.write_bytes(pdf_bytes)
        print(f"Wrote {path} ({len(pdf_bytes) / 1024:.1f} KB)")

    print(
        f"\nFerdig! {len(DEMO_PROFILES)} risikoprofiler klare i "
        "sample_risk_profiles/. Last opp som anbudspakke-vedlegg i UI, eller "
        "bruk som 'outgoing' demo-PDFer. Par med "
        "scripts/generate_sample_offers.py for hele e2e-flyten."
    )


if __name__ == "__main__":
    # Ensure we can import api.services when invoked from repo root
    os.environ.setdefault(
        "DATABASE_URL", "postgresql://tharusan@localhost:5432/brokerdb"
    )
    main()
