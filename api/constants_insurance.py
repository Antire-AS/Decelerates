"""Insurance premium benchmark data for Norwegian business insurance.

Indicative annual premium ranges (NOK) by product type and company size.
Based on Norwegian market practice 2024-2026 (Finans Norge, If, Gjensidige,
Tryg SMB pricing tiers). NOT quotes — rough industry guides for brokers.
"""

REVENUE_BRACKETS = {
    "XS": {"label": "Under 10 MNOK", "min": 0, "max": 10_000_000},
    "S": {"label": "10–50 MNOK", "min": 10_000_000, "max": 50_000_000},
    "M": {"label": "50–200 MNOK", "min": 50_000_000, "max": 200_000_000},
    "L": {"label": "200 MNOK – 1 MRD", "min": 200_000_000, "max": 1_000_000_000},
    "XL": {"label": "Over 1 MRD", "min": 1_000_000_000, "max": None},
}

PREMIUM_BENCHMARKS = {
    "eiendom": {
        "label": "Eiendomsforsikring",
        "description": "Brann, vann, innbrudd, naturskade. Dekker bygg, inventar, maskiner, varer.",
        "premiums": {
            "XS": {"low": 5000, "mid": 10000, "high": 20000},
            "S": {"low": 12000, "mid": 25000, "high": 50000},
            "M": {"low": 30000, "mid": 70000, "high": 150000},
            "L": {"low": 80000, "mid": 200000, "high": 500000},
            "XL": {"low": 250000, "mid": 600000, "high": 2000000},
        },
    },
    "ansvar": {
        "label": "Ansvarsforsikring",
        "description": "Bedriftens erstatningsansvar overfor tredjeparter (alminnelig ansvar + produktansvar).",
        "premiums": {
            "XS": {"low": 5000, "mid": 8000, "high": 15000},
            "S": {"low": 8000, "mid": 18000, "high": 35000},
            "M": {"low": 20000, "mid": 45000, "high": 90000},
            "L": {"low": 50000, "mid": 120000, "high": 250000},
            "XL": {"low": 150000, "mid": 350000, "high": 800000},
        },
    },
    "yrkesskade": {
        "label": "Yrkesskadeforsikring",
        "description": "Lovpålagt dekning for yrkesskade og yrkessykdom (AML § 16-7). Premie basert på lønnskostnad og risiko.",
        "premiums": {
            "XS": {"low": 5000, "mid": 12000, "high": 25000},
            "S": {"low": 15000, "mid": 40000, "high": 80000},
            "M": {"low": 50000, "mid": 120000, "high": 250000},
            "L": {"low": 150000, "mid": 400000, "high": 800000},
            "XL": {"low": 500000, "mid": 1500000, "high": 4000000},
        },
    },
    "motor": {
        "label": "Næringsforsikring motor",
        "description": "Ansvar + kasko for firmabiler, varebiler, lastebiler.",
        "premiums": {
            "XS": {"low": 8000, "mid": 15000, "high": 30000},
            "S": {"low": 20000, "mid": 50000, "high": 120000},
            "M": {"low": 60000, "mid": 150000, "high": 400000},
            "L": {"low": 200000, "mid": 500000, "high": 1500000},
            "XL": {"low": 500000, "mid": 2000000, "high": 6000000},
        },
    },
    "cyber": {
        "label": "Cyberforsikring",
        "description": "Datainnbrudd, løsepengevirus, GDPR-brudd, driftsavbrudd IT.",
        "premiums": {
            "XS": {"low": 8000, "mid": 15000, "high": 30000},
            "S": {"low": 20000, "mid": 45000, "high": 90000},
            "M": {"low": 50000, "mid": 120000, "high": 250000},
            "L": {"low": 120000, "mid": 300000, "high": 700000},
            "XL": {"low": 300000, "mid": 800000, "high": 2500000},
        },
    },
    "dno": {
        "label": "Styreansvarsforsikring (D&O)",
        "description": "Personlig erstatningsansvar for styremedlemmer og daglig leder.",
        "premiums": {
            "XS": {"low": 8000, "mid": 15000, "high": 25000},
            "S": {"low": 15000, "mid": 30000, "high": 60000},
            "M": {"low": 30000, "mid": 70000, "high": 150000},
            "L": {"low": 70000, "mid": 180000, "high": 400000},
            "XL": {"low": 200000, "mid": 500000, "high": 1500000},
        },
    },
    "reise": {
        "label": "Reiseforsikring næring",
        "description": "Tjenestereiseforsikring for ansatte. Premie typisk per hode.",
        "premiums": {
            "XS": {"low": 2000, "mid": 5000, "high": 10000},
            "S": {"low": 5000, "mid": 15000, "high": 35000},
            "M": {"low": 15000, "mid": 40000, "high": 100000},
            "L": {"low": 40000, "mid": 120000, "high": 300000},
            "XL": {"low": 100000, "mid": 350000, "high": 1000000},
        },
    },
    "kriminalitet": {
        "label": "Kriminalitetsforsikring",
        "description": "Underslag, bedrageri, datakriminalitet utført av ansatte eller tredjeparter.",
        "premiums": {
            "XS": {"low": 5000, "mid": 10000, "high": 20000},
            "S": {"low": 10000, "mid": 25000, "high": 50000},
            "M": {"low": 25000, "mid": 60000, "high": 130000},
            "L": {"low": 60000, "mid": 150000, "high": 350000},
            "XL": {"low": 150000, "mid": 400000, "high": 1000000},
        },
    },
    "personalforsikring": {
        "label": "Personalforsikring",
        "description": "Gruppelivsforsikring, behandlingsforsikring, uføreforsikring for ansatte.",
        "premiums": {
            "XS": {"low": 5000, "mid": 12000, "high": 25000},
            "S": {"low": 15000, "mid": 40000, "high": 90000},
            "M": {"low": 50000, "mid": 130000, "high": 300000},
            "L": {"low": 150000, "mid": 450000, "high": 1000000},
            "XL": {"low": 500000, "mid": 1500000, "high": 5000000},
        },
    },
}

NACE_RISK_MULTIPLIERS = {
    "A": {"label": "Jordbruk/skogbruk/fiske", "multiplier": 1.15},
    "B": {"label": "Bergverksdrift", "multiplier": 1.25},
    "C": {"label": "Industri", "multiplier": 1.20},
    "D": {"label": "Kraftforsyning", "multiplier": 1.10},
    "E": {"label": "Vann/avløp/renovasjon", "multiplier": 1.10},
    "F": {"label": "Bygge- og anleggsvirksomhet", "multiplier": 1.30},
    "G": {"label": "Varehandel", "multiplier": 1.00},
    "H": {"label": "Transport og lagring", "multiplier": 1.20},
    "I": {"label": "Overnatting og servering", "multiplier": 1.15},
    "J": {"label": "Informasjon og kommunikasjon", "multiplier": 1.00},
    "K": {"label": "Finansiering og forsikring", "multiplier": 1.05},
    "L": {"label": "Omsetning/drift av fast eiendom", "multiplier": 1.05},
    "M": {"label": "Faglig/vitenskapelig tjeneste", "multiplier": 1.00},
    "N": {"label": "Forretningsmessig tjeneste", "multiplier": 1.00},
    "O": {"label": "Offentlig forvaltning", "multiplier": 0.95},
    "P": {"label": "Undervisning", "multiplier": 0.95},
    "Q": {"label": "Helse- og sosialtjenester", "multiplier": 1.05},
    "R": {"label": "Kultur/underholdning/fritid", "multiplier": 1.05},
    "S": {"label": "Annen tjenesteyting", "multiplier": 1.00},
}


def get_bracket_for_revenue(revenue: float | None) -> str:
    """Return the bracket key (XS/S/M/L/XL) for a given revenue."""
    if revenue is None or revenue <= 0:
        return "S"  # default to small
    for key, b in REVENUE_BRACKETS.items():
        if b["max"] is None:
            return key
        if revenue < b["max"]:
            return key
    return "XL"


def estimate_premiums_for_company(
    revenue: float | None,
    nace_section: str | None = None,
) -> dict:
    """Return estimated premiums for all product types for a given company size."""
    bracket = get_bracket_for_revenue(revenue)
    multiplier = 1.0
    if nace_section and nace_section.upper() in NACE_RISK_MULTIPLIERS:
        multiplier = NACE_RISK_MULTIPLIERS[nace_section.upper()]["multiplier"]

    result = {}
    for key, product in PREMIUM_BENCHMARKS.items():
        base = product["premiums"][bracket]
        result[key] = {
            "label": product["label"],
            "description": product["description"],
            "bracket": bracket,
            "bracket_label": REVENUE_BRACKETS[bracket]["label"],
            "low": round(base["low"] * multiplier),
            "mid": round(base["mid"] * multiplier),
            "high": round(base["high"] * multiplier),
            "nace_adjustment": multiplier,
        }
    return result
