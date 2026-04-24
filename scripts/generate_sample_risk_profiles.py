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
        "\nFerdig! 3 risikoprofiler klare i sample_risk_profiles/. "
        "Last opp som anbudspakke-vedlegg i UI, eller bruk som 'outgoing' "
        "demo-PDFer. Par med scripts/generate_sample_offers.py for hele e2e-flyten."
    )


if __name__ == "__main__":
    # Ensure we can import api.services when invoked from repo root
    os.environ.setdefault(
        "DATABASE_URL", "postgresql://tharusan@localhost:5432/brokerdb"
    )
    main()
