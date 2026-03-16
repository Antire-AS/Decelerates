"""
Generate three realistic Norwegian insurance offer PDFs for demo purposes.
Run:  python generate_sample_offers.py
Output: sample_offers/tilbud_if.pdf, tilbud_gjensidige.pdf, tilbud_tryg.pdf
"""

from fpdf import FPDF
from datetime import date

def _s(t: str) -> str:
    """Sanitize for fpdf2 latin-1 Helvetica."""
    return (
        t.replace("\u2013", "-").replace("\u2014", "-")
         .replace("\u2018", "'").replace("\u2019", "'")
         .replace("\u201c", '"').replace("\u201d", '"')
         .encode("latin-1", errors="replace").decode("latin-1")
    )


TODAY = date.today().strftime("%d.%m.%Y")
CLIENT_NAVN = "Bergmann Industri AS"
CLIENT_ORGNR = "987 654 321"
CLIENT_ADRESSE = "Industriveien 12, 0484 Oslo"
GYLDIG_TIL = "30.04.2026"


class SafePDF(FPDF):
    """FPDF subclass that auto-sanitizes strings through latin-1 safe filter."""
    def cell(self, *args, **kwargs):
        if args:
            args = list(args)
            # text is 4th positional arg (w, h, text, ...)
            if len(args) > 2 and isinstance(args[2], str):
                args[2] = _s(args[2])
        if "text" in kwargs:
            kwargs["text"] = _s(kwargs["text"])
        super().cell(*args, **kwargs)

    def multi_cell(self, *args, **kwargs):
        if args:
            args = list(args)
            if len(args) > 2 and isinstance(args[2], str):
                args[2] = _s(args[2])
        if "text" in kwargs:
            kwargs["text"] = _s(kwargs["text"])
        super().multi_cell(*args, **kwargs)


def page_header(pdf: FPDF, insurer: str, quote_no: str, color: tuple):
    pdf.set_fill_color(*color)
    pdf.rect(0, 0, 210, 28, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_xy(10, 8)
    pdf.cell(0, 10, insurer, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_xy(10, 18)
    pdf.cell(0, 6, f"Forsikringstilbud  |  Tilbudsnr.: {quote_no}  |  Dato: {TODAY}  |  Gyldig til: {GYLDIG_TIL}")
    pdf.set_text_color(0, 0, 0)
    pdf.set_xy(10, 32)


def section(pdf: FPDF, title: str, color: tuple):
    pdf.set_fill_color(*color)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"  {title}", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 11)
    pdf.ln(2)


def kv(pdf: FPDF, label: str, value: str):
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(70, 6, label + ":", new_x="RIGHT", new_y="TOP")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, value, new_x="LMARGIN", new_y="NEXT")


def coverage_table(pdf: FPDF, rows: list, color: tuple):
    headers = ["Dekning", "Forsikringssum", "Egenandel", "Premie/ar (eks. mva)"]
    widths = [65, 45, 35, 45]
    pdf.set_fill_color(*color)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 9)
    for h, w in zip(headers, widths):
        pdf.cell(w, 8, h, border=1, fill=True)
    pdf.ln()
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 9)
    fill = False
    for row in rows:
        pdf.set_fill_color(240, 240, 240) if fill else pdf.set_fill_color(255, 255, 255)
        for val, w in zip(row, widths):
            pdf.cell(w, 7, str(val), border=1, fill=True)
        pdf.ln()
        fill = not fill
    pdf.ln(3)


# ─────────────────────────────────────────────────────────────────
# TILBUD 1: If Skadeforsikring
# ─────────────────────────────────────────────────────────────────
def build_if():
    COLOR = (0, 100, 170)
    pdf = SafePDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(10, 10, 10)

    # Page 1 — Summary
    pdf.add_page()
    page_header(pdf, "If Skadeforsikring", "IF-2026-44821", COLOR)

    section(pdf, "Klientinformasjon", COLOR)
    kv(pdf, "Selskap", CLIENT_NAVN)
    kv(pdf, "Org.nr", CLIENT_ORGNR)
    kv(pdf, "Adresse", CLIENT_ADRESSE)
    kv(pdf, "Kontaktperson", "Lars Bergmann")
    kv(pdf, "Bransje", "Industriell produksjon (NACE 25.1)")
    pdf.ln(4)

    section(pdf, "Tilbudssammendrag", COLOR)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6,
        "If Skadeforsikring tilbyr herved et skreddersydd forsikringsprogram for Bergmann "
        "Industri AS. Tilbudet dekker selskapets kjernerisiko innen eiendom, ansvar og "
        "yrkesskade. If er Nordens ledende skadeforsikringsselskap og tilbyr avtaleperiode "
        "pa 12 maneder med start 01.05.2026."
    )
    pdf.ln(3)

    kv(pdf, "Avtaleperiode", "01.05.2026 - 30.04.2027")
    kv(pdf, "Total arspremie", "NOK 387 500 (eks. mva)")
    kv(pdf, "Betalingsvilkar", "Kvartalsvise terminpremier")
    kv(pdf, "Provisjon megler", "12 % av nettopremie")
    pdf.ln(4)

    # Page 2 — Coverage details
    pdf.add_page()
    page_header(pdf, "If Skadeforsikring", "IF-2026-44821", COLOR)

    section(pdf, "Vedlegg A - Dekningsoversikt", COLOR)
    coverage_table(pdf, [
        ["Tingskade / Bygning",       "NOK 85 000 000", "NOK 50 000",  "NOK 112 000"],
        ["Tingskade / Losore",        "NOK 40 000 000", "NOK 30 000",  "NOK  68 500"],
        ["Driftsavbrudd (12 mnd)",    "NOK 25 000 000", "5 dager",     "NOK  89 000"],
        ["Produktansvar",             "NOK 50 000 000", "NOK 100 000", "NOK  54 000"],
        ["Allmenn ansvarsforsikring", "NOK 20 000 000", "NOK  50 000", "NOK  32 000"],
        ["Yrkesskade (lovpliktig)",   "Ubegrenset",     "Lovpliktig",  "NOK  32 000"],
    ], COLOR)

    section(pdf, "Vasentlige vilkar og klausuler", COLOR)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6,
        "- Tingskade er basert pa If's bedriftsvilkar 2025, klausul BED-TG-01.\n"
        "- Driftsavbruddsforsikringen dekker tapt bruttofortjeneste i inntil 12 maneder "
        "etter en erstatningsberettiget skade pa forsikret eiendom.\n"
        "- Produktansvaret gjelder kun for produkter distribuert i EOS-omradet.\n"
        "- Yrkesskade er lovpliktig etter yrkesskadeforsikringsloven med full dekning.\n"
        "- Egenandeler indeksreguleres arlig med KPI.\n"
        "- Sikkerhetsforskrifter iht. If's standard bedriftsvilkar ma overholdes. "
        "Ved brudd reduseres erstatningen med inntil 30 %.\n"
        "- Forsikringen er underlagt norsk rett og Oslo tingrett er verneting."
    )
    pdf.ln(4)

    section(pdf, "Rabatter og betingelser", COLOR)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6,
        "- Skadefri bonus: 5 % rabatt etter 2 ar uten skader over egenandel.\n"
        "- Volum: 3 % samlerabatt ved tegning av alle linjer.\n"
        "- Skadefri bonus bortfaller ved skadeutbetalinger over NOK 500 000.\n"
        "- Premien er fast i 12 maneder og justeres kun ved vesentlig risikoendring."
    )
    pdf.ln(4)

    section(pdf, "Skadebehandling", COLOR)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6,
        "If tilbyr 24/7 skademelding via If Naeringsliv-portalen eller tlf. 02400. "
        "Saksbehandlingstid for tingskader: normalt 5-10 virkedager. "
        "Erstatningsoppgjor utbetales innen 30 dager etter endelig dokumentasjon. "
        "Dedikert skaderradgiver tildeles ved skader over NOK 1 000 000."
    )

    return bytes(pdf.output())


# ─────────────────────────────────────────────────────────────────
# TILBUD 2: Gjensidige Forsikring
# ─────────────────────────────────────────────────────────────────
def build_gjensidige():
    COLOR = (180, 0, 0)
    pdf = SafePDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(10, 10, 10)

    pdf.add_page()
    page_header(pdf, "Gjensidige Forsikring", "GJ-NB-2026-9921", COLOR)

    section(pdf, "Klientinformasjon", COLOR)
    kv(pdf, "Selskap", CLIENT_NAVN)
    kv(pdf, "Org.nr", CLIENT_ORGNR)
    kv(pdf, "Adresse", CLIENT_ADRESSE)
    kv(pdf, "Kontaktperson", "Lars Bergmann")
    kv(pdf, "Bransje", "Industriell produksjon")
    pdf.ln(4)

    section(pdf, "Tilbudssammendrag", COLOR)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6,
        "Gjensidige Forsikring tilbyr et komplett forsikringsprogram for Bergmann Industri AS. "
        "Gjensidige har over 200 ars erfaring og er Norges stoerste skadeforsikringsselskap malt "
        "i antall kunder. Tilbudet inkluderer utvidet produktansvar med eksportdekning og "
        "en styrket cyberforsikring. Gjensidige tilbyr 3-ars fastprisavtale."
    )
    pdf.ln(3)

    kv(pdf, "Avtaleperiode", "01.05.2026 - 30.04.2029 (3-ar fastpris)")
    kv(pdf, "Total arspremie", "NOK 412 000 (eks. mva)")
    kv(pdf, "Betalingsvilkar", "Halvars- eller arlig betaling (2 % rabatt ved arlig)")
    kv(pdf, "Provisjon megler", "11 % av nettopremie")
    pdf.ln(4)

    pdf.add_page()
    page_header(pdf, "Gjensidige Forsikring", "GJ-NB-2026-9921", COLOR)

    section(pdf, "Vedlegg A - Dekningsoversikt", COLOR)
    coverage_table(pdf, [
        ["Tingskade / Bygning",       "NOK 90 000 000", "NOK 75 000",  "NOK 118 000"],
        ["Tingskade / Losore",        "NOK 45 000 000", "NOK 50 000",  "NOK  72 000"],
        ["Driftsavbrudd (18 mnd)",    "NOK 30 000 000", "3 dager",     "NOK  98 000"],
        ["Produktansvar (global)",    "NOK 75 000 000", "NOK 100 000", "NOK  62 000"],
        ["Allmenn ansvarsforsikring", "NOK 20 000 000", "NOK  50 000", "NOK  30 000"],
        ["Yrkesskade (lovpliktig)",   "Ubegrenset",     "Lovpliktig",  "NOK  32 000"],
    ], COLOR)

    section(pdf, "Tilleggsdekning inkludert i tilbudet", COLOR)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6,
        "- Cyberforsikring (basispakke): NOK 5 000 000 dekning, egenandel NOK 50 000, "
        "arspremie NOK 28 000. Dekker datatap, gjenoppretting og ansvarskrav fra tredjeparter.\n"
        "- Transportforsikring: NOK 2 000 000 per sending, egenandel NOK 10 000, "
        "arspremie NOK 12 000.\n"
        "- Total tilbudspremie inkl. tilleggsdekning: NOK 452 000 eks. mva."
    )
    pdf.ln(4)

    section(pdf, "Vasentlige vilkar og klausuler", COLOR)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6,
        "- Tingskade regulert av Gjensidiges bedriftsvilkar GB-2024, basert pa CICG-vilkar.\n"
        "- Driftsavbrudd: 18 maneders maksimal erstatningsperiode — 6 maneder mer enn "
        "markedsstandard. Karenstid 3 dager.\n"
        "- Produktansvar: Global dekning inkludert USA/Canada med sublimit USD 10 000 000.\n"
        "- Egenandeler er faste i avtaleperioden (3 ar) og indeksreguleres ikke.\n"
        "- Sikkerhetsforskrifter: Brudd gir 20 % reduksjon (lavere enn bransjesnitt pa 30 %).\n"
        "- Gjensidige tilbyr arlig risikokartlegging hos kunden uten tilleggskostnad."
    )
    pdf.ln(4)

    section(pdf, "Skadebehandling og tilleggsfordeler", COLOR)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6,
        "- Skademelding via Gjensidige Bedrift-appen, nett eller tlf. 03100 (24/7).\n"
        "- Garantert tilbakemelding innen 24 timer pa alle skademeldinger.\n"
        "- Erstatningsoppgjor innen 21 dager etter fullstendig dokumentasjon.\n"
        "- Fast naeringskunderadgiver og arlig avtalemote inkludert.\n"
        "- Gratis HMS-kurs via Gjensidige Akademiet (inntil 3 ansatte/ar)."
    )

    return bytes(pdf.output())


# ─────────────────────────────────────────────────────────────────
# TILBUD 3: Tryg Forsikring
# ─────────────────────────────────────────────────────────────────
def build_tryg():
    COLOR = (0, 130, 80)
    pdf = SafePDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(10, 10, 10)

    pdf.add_page()
    page_header(pdf, "Tryg Forsikring", "TRYG-NO-2026-5530", COLOR)

    section(pdf, "Klientinformasjon", COLOR)
    kv(pdf, "Selskap", CLIENT_NAVN)
    kv(pdf, "Org.nr", CLIENT_ORGNR)
    kv(pdf, "Adresse", CLIENT_ADRESSE)
    kv(pdf, "Kontaktperson", "Lars Bergmann")
    kv(pdf, "Bransje", "Industriell produksjon / metallvarer")
    pdf.ln(4)

    section(pdf, "Tilbudssammendrag", COLOR)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6,
        "Tryg Forsikring presenterer et konkurransedyktig tilbud med fokus pa laveste "
        "totalkostnad. Tryg er det nest stoerste skadeforsikringsselskapet i Norden. "
        "Tilbudet baseres pa et forenklende konsept der samletegning av alle linjer gir "
        "en rabatt pa 8 %. Betalbar premie er den laveste av de tre innhentede tilbudene, "
        "men med noe hoeyere egenandeler."
    )
    pdf.ln(3)

    kv(pdf, "Avtaleperiode", "01.05.2026 - 30.04.2027")
    kv(pdf, "Total arspremie", "NOK 351 000 (eks. mva)")
    kv(pdf, "Betalingsvilkar", "Arlig forskuddsbetaling")
    kv(pdf, "Provisjon megler", "13 % av nettopremie")
    pdf.ln(4)

    pdf.add_page()
    page_header(pdf, "Tryg Forsikring", "TRYG-NO-2026-5530", COLOR)

    section(pdf, "Vedlegg A - Dekningsoversikt", COLOR)
    coverage_table(pdf, [
        ["Tingskade / Bygning",       "NOK 80 000 000", "NOK 100 000", "NOK  98 000"],
        ["Tingskade / Losore",        "NOK 35 000 000", "NOK  75 000", "NOK  61 000"],
        ["Driftsavbrudd (12 mnd)",    "NOK 20 000 000", "7 dager",     "NOK  82 000"],
        ["Produktansvar",             "NOK 40 000 000", "NOK 150 000", "NOK  48 000"],
        ["Allmenn ansvarsforsikring", "NOK 15 000 000", "NOK  75 000", "NOK  30 000"],
        ["Yrkesskade (lovpliktig)",   "Ubegrenset",     "Lovpliktig",  "NOK  32 000"],
    ], COLOR)

    section(pdf, "Vasentlige vilkar og klausuler", COLOR)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6,
        "- Tingskade regulert av Tryg's Standard Bedriftsvilkar TB-2023.\n"
        "- Driftsavbrudd: 12 maneders erstatningsperiode, karenstid 7 dager "
        "(lengre enn konkurrentene pa 3-5 dager).\n"
        "- Produktansvar: Geografisk begrensning til EOS-omradet. USA/Canada er "
        "IKKE inkludert — krever separat utvidelse (+NOK 18 000/ar).\n"
        "- Egenandeler er vesentlig hoeyere enn konkurrentene, men premien er tilsvarende "
        "lavere. Anbefales for selskaper med god likviditet og lavt skadehistorikk.\n"
        "- Sikkerhetsforskrifter: Brudd gir 25 % erstatningsreduksjon.\n"
        "- Premie indeksreguleres med KPI + 2 % ved fornyelse."
    )
    pdf.ln(4)

    section(pdf, "Klausuler som avviker fra standard", COLOR)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6,
        "- VIKTIG: Tingskade-dekningen inkluderer IKKE maskinhavari. Dette ma tegnes "
        "separat (estimert tilleggspremie NOK 22 000/ar).\n"
        "- Naturskadedekning er inkludert via Norsk Naturskadepool (lovpliktig).\n"
        "- Terrordekning inntil NOK 20 000 000 inkludert via POL-ordningen.\n"
        "- Erstatning beregnes pa grunnlag av gjenanskaffelsesverdi for bygning og "
        "dagsverdibasis for losore eldre enn 5 ar."
    )
    pdf.ln(4)

    section(pdf, "Skadebehandling", COLOR)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6,
        "- Skademelding: tryg.no/skade, e-post eller tlf. 04040 (hverdager 08-20).\n"
        "- Saksbehandlingstid: 7-14 virkedager for tingskader.\n"
        "- Erstatningsoppgjor innen 45 dager etter fullstendig dokumentasjon.\n"
        "- Ingen dedikert skaderradgiver — saksbehandling via generell pool.\n"
        "- Merk: Tryg har ikke 24/7 naeringslivs-skadetelefon."
    )

    return bytes(pdf.output())


# ─────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os
    os.makedirs("sample_offers", exist_ok=True)

    specs = [
        ("sample_offers/tilbud_if_skadeforsikring.pdf", build_if),
        ("sample_offers/tilbud_gjensidige.pdf", build_gjensidige),
        ("sample_offers/tilbud_tryg.pdf", build_tryg),
    ]
    for path, builder in specs:
        with open(path, "wb") as fh:
            fh.write(builder())
        print(f"Wrote {path}")

    print("\nFerdig! Last opp filene fra sample_offers/ i UI-et for a teste tilbudsanalysen.")
