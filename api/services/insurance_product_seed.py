"""Seed the canonical Norwegian broker product catalog.

Idempotent — every run upserts via natural-key (category, sub_category,
name). Safe to call from app startup.

Categories follow Norwegian broker convention:
- personell — employee/people-coverage products (15 entries)
- bygning   — property + plant coverage
- ansvar    — liability lines
- drift     — operational/business-interruption
- transport — goods/cargo/auto
- marine    — ships, hull, cargo (heavy industry)
- annet     — travel, art, valuables, kidnap & ransom

The list is curated; we are not trying to be exhaustive on first ship.
The user can extend via ADMIN UI later. Numbers in `sort_order` are
spaced by 10 so we can insert between entries without renumbering.

Coverage limits are typical Norwegian defaults — informational only,
not legally binding. JSON shape: {"min": x, "max": y, "unit": "NOK"}.
"""

from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from api.models.insurance_product import InsuranceProduct


_CATALOG: list[dict] = [
    # ── Personell (15 produkter) ────────────────────────────────────────────
    {
        "category": "personell",
        "name": "Yrkesskadeforsikring",
        "description": "Lovpålagt for arbeidsgivere — dekker yrkesskader og yrkessykdom",
        "sort_order": 10,
    },
    {
        "category": "personell",
        "name": "Gruppelivsforsikring",
        "description": "Engangsutbetaling ved død i tjeneste — vanlig 5G–20G",
        "typical_coverage_limits": {"min": 500_000, "max": 5_000_000, "unit": "NOK"},
        "sort_order": 20,
    },
    {
        "category": "personell",
        "name": "Helseforsikring (privat)",
        "description": "Rask tilgang til spesialist + privat behandling",
        "sort_order": 30,
    },
    {
        "category": "personell",
        "name": "Behandlingsforsikring",
        "description": "Dekker fysioterapi, kiropraktor, manuellterapi for ansatte",
        "sort_order": 40,
    },
    {
        "category": "personell",
        "name": "Sykelønnsforsikring",
        "description": "Dekker arbeidsgiverperiode + 16-dagers etter folketrygden",
        "sort_order": 50,
    },
    {
        "category": "personell",
        "name": "Uføreforsikring (kollektiv)",
        "description": "Månedlig utbetaling ved uførhet — typisk 60–80 % av lønn",
        "sort_order": 60,
    },
    {
        "category": "personell",
        "name": "Annen sykdomsforsikring",
        "description": "Engangsutbetaling ved alvorlig sykdom (kreft, hjerte, slag)",
        "sort_order": 70,
    },
    {
        "category": "personell",
        "name": "Reiseforsikring tjenestereiser",
        "description": "Forretningsreise + arbeidsulykke utenfor Norge",
        "sort_order": 80,
    },
    {
        "category": "personell",
        "name": "Tjenestepensjon (innskuddsbasert OTP)",
        "description": "Lovpålagt minimum 2 % — markedsvanlig 5–7 %",
        "sort_order": 90,
    },
    {
        "category": "personell",
        "name": "Tjenestepensjon (ytelsesbasert)",
        "description": "Garantert pensjonsnivå — under utfasing for nye ansatte",
        "sort_order": 100,
    },
    {
        "category": "personell",
        "name": "Innskuddspensjon med investeringsvalg",
        "description": "Egen profil per ansatt med valg av aksje-/rentefond",
        "sort_order": 110,
    },
    {
        "category": "personell",
        "name": "Personalfond/AFP-tilskudd",
        "description": "Tariff-AFP — for tariffbundne bedrifter",
        "sort_order": 120,
    },
    {
        "category": "personell",
        "name": "Lederpensjon (kompensasjonsavtale)",
        "description": "Tilleggsavtale over 12G for ledere",
        "sort_order": 130,
    },
    {
        "category": "personell",
        "name": "Nøkkelpersonforsikring",
        "description": "Bedriften er begunstiget — dekker tap ved nøkkelpersons fravær",
        "sort_order": 140,
    },
    {
        "category": "personell",
        "name": "Lisens-/utdanningsforsikring",
        "description": "Dekker ansattes pålagte sertifikater og kursutgifter",
        "sort_order": 150,
    },
    # ── Bygning ─────────────────────────────────────────────────────────────
    {
        "category": "bygning",
        "name": "Bygning (eiendom)",
        "description": "Brann, vann, naturskade på selve bygget",
        "sort_order": 10,
    },
    {
        "category": "bygning",
        "sub_category": "innhold",
        "name": "Inventar og løsøre",
        "description": "Møbler, IT, varer, maskiner inne i bygget",
        "sort_order": 20,
    },
    {
        "category": "bygning",
        "sub_category": "innhold",
        "name": "Maskiner og produksjonsutstyr",
        "description": "Spesialdekning for produksjonsmaskiner — havari + tap",
        "sort_order": 30,
    },
    {
        "category": "bygning",
        "name": "Glass og skilt",
        "description": "Knust glass, fasadeskilt, lysreklame",
        "sort_order": 40,
    },
    {
        "category": "bygning",
        "name": "Vedlikehold/teknisk skadestopp",
        "description": "Plutselig stans i tekniske anlegg (heis, ventilasjon, kjøl)",
        "sort_order": 50,
    },
    {
        "category": "bygning",
        "name": "Kontant- og verdisaksforsikring",
        "description": "Penger, gavekort, verdipapirer i lokalet og under transport",
        "sort_order": 60,
    },
    # ── Ansvar ──────────────────────────────────────────────────────────────
    {
        "category": "ansvar",
        "name": "Alminnelig ansvarsforsikring",
        "description": "Erstatningsansvar for skade på 3. person eller tredjeparts ting",
        "typical_coverage_limits": {
            "min": 5_000_000,
            "max": 100_000_000,
            "unit": "NOK",
        },
        "sort_order": 10,
    },
    {
        "category": "ansvar",
        "name": "Yrkesansvar (PI)",
        "description": "Profesjonell rådgivning — feil/forsømmelse i tjenesteleveranser",
        "sort_order": 20,
    },
    {
        "category": "ansvar",
        "name": "Styreansvar (D&O)",
        "description": "Personlig styreansvar — anlegg, søksmål, gransking",
        "sort_order": 30,
    },
    {
        "category": "ansvar",
        "name": "Produktansvar",
        "description": "Skader fra solgte produkter — tilbakekalling, personskade",
        "sort_order": 40,
    },
    {
        "category": "ansvar",
        "name": "Cyber- og datasikkerhetsforsikring",
        "description": "Hendelsesrespons, krav fra tredjeparter, GDPR-bøter",
        "sort_order": 50,
    },
    {
        "category": "ansvar",
        "name": "Cyber utvidet (extortion + BI)",
        "description": "Cyber + ransom + driftstap pga. cyberhendelse",
        "sort_order": 60,
    },
    {
        "category": "ansvar",
        "name": "Miljøansvarsforsikring",
        "description": "Forurensning, opprydning, tredjepartskrav",
        "sort_order": 70,
    },
    {
        "category": "ansvar",
        "name": "Krimforsikring (employee dishonesty)",
        "description": "Ansattes underslag, bedrageri, datatyveri internt",
        "sort_order": 80,
    },
    # ── Drift / driftsavbrudd ──────────────────────────────────────────────
    {
        "category": "drift",
        "name": "Driftstap (avbruddsforsikring)",
        "description": "Tap av dekningsbidrag etter brann, vannskade, etc.",
        "sort_order": 10,
    },
    {
        "category": "drift",
        "name": "Leveringssvikt-/avhengighetsforsikring",
        "description": "Driftstap fra navngitte leverandører eller kunders skade",
        "sort_order": 20,
    },
    {
        "category": "drift",
        "name": "Husleietap",
        "description": "For utleier — tap av leie under reparasjon etter skade",
        "sort_order": 30,
    },
    # ── Transport ───────────────────────────────────────────────────────────
    {
        "category": "transport",
        "name": "Vareforsikring (cargo)",
        "description": "Varer under transport — sjø, land, luft",
        "sort_order": 10,
    },
    {
        "category": "transport",
        "name": "Bilforsikring (firmabil)",
        "description": "Ansvar + kasko for enkeltkjøretøy",
        "sort_order": 20,
    },
    {
        "category": "transport",
        "name": "Flåteforsikring",
        "description": "Bilflåte — fellesvilkår, rabatt på volum",
        "sort_order": 30,
    },
    {
        "category": "transport",
        "name": "Tilhengerforsikring",
        "description": "Tilhengere brukt i næringsvirksomhet",
        "sort_order": 40,
    },
    {
        "category": "transport",
        "name": "Anleggsmaskiner/entreprenørmateriell",
        "description": "Gravemaskin, kran, forskaling — på byggeplass",
        "sort_order": 50,
    },
    # ── Marine (heavy industry) ─────────────────────────────────────────────
    {
        "category": "marine",
        "name": "Hull & Machinery (skip)",
        "description": "Skipsskader — kasko + maskinhavari",
        "sort_order": 10,
    },
    {
        "category": "marine",
        "name": "P&I (Protection & Indemnity)",
        "description": "Reder-ansvar — passasjerer, mannskap, last",
        "sort_order": 20,
    },
    {
        "category": "marine",
        "name": "Shipbuilding (byggerisiko)",
        "description": "Skipsverft — fra kjølstrekk til levering",
        "sort_order": 30,
    },
    {
        "category": "marine",
        "name": "Offshore equipment",
        "description": "Subsea + topside utstyr på rigg/plattform",
        "sort_order": 40,
    },
    # ── Annet ───────────────────────────────────────────────────────────────
    {
        "category": "annet",
        "name": "Reise og forretningsulykke",
        "description": "Tjenestereise + ulykke utenfor arbeidsplass",
        "sort_order": 10,
    },
    {
        "category": "annet",
        "name": "Kunst- og samlingsforsikring",
        "description": "Verdier i kontorer/utstillinger — All-Risk",
        "sort_order": 20,
    },
    {
        "category": "annet",
        "name": "Kidnap, Ransom & Extortion (K&R)",
        "description": "Eksponert ledelse — gjelder reise til risiko-områder",
        "sort_order": 30,
    },
    {
        "category": "annet",
        "name": "Event cancellation",
        "description": "Avlysning av store arrangementer",
        "sort_order": 40,
    },
    {
        "category": "annet",
        "name": "Politisk risiko / handelskreditt",
        "description": "Eksport-relatert — manglende betaling fra utenlandske kjøpere",
        "sort_order": 50,
    },
]


def seed_insurance_products(db: Session) -> int:
    """Idempotent upsert of the catalog. Returns number of rows inserted."""
    if not _CATALOG:
        return 0
    stmt = pg_insert(InsuranceProduct.__table__).values(_CATALOG)
    stmt = stmt.on_conflict_do_nothing(constraint="uq_product_triple")
    result = db.execute(stmt)
    db.commit()
    return result.rowcount or 0


def catalog_size() -> int:
    """Used by tests to assert seeding inserts the expected count."""
    return len(_CATALOG)
