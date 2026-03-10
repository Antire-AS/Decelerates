# ============================================================
# LLM Prompt Constants
# Centralised here so prompts can be reviewed / improved in one place.
# ============================================================

# ---------------------------------------------------------------------------
# Financial extraction from annual report PDFs / text
# ---------------------------------------------------------------------------
FINANCIALS_PROMPT = """You are extracting financial data from a corporate annual report PDF.
Company orgnr: {orgnr}, Report year: {year}

CRITICAL RULES:
1. Always extract from the CONSOLIDATED (GROUP) financial statements — never from the parent company standalone statements. If both are present, use the consolidated figures.
2. Return ALL monetary values as ABSOLUTE numbers in the base currency unit (not millions).
   Example: "66,115" with note "amounts in NOK millions" → return 66115000000
   Example: "32,861 TNOK" (thousands) → return 32861000. Plain NOK/USD → return as-is.
3. Return null for any field genuinely not found — do NOT guess or leave as 0.
4. This may be a BANK, insurance company, or standard company — adapt accordingly.
   - BANK income statements start with "Net interest income" + "Net fee and commission income".
     Sum these to get "revenue". Operating profit is often called "profit before loan impairment charges".
   - INSURANCE income statements start with "Net premiums earned" / "Gross written premiums".
   - STANDARD companies have "operating revenues" / "total revenues".

Extract ALL of these fields and return a single valid JSON object.
Each field shows the standard name AND common insurance/bank alternatives to look for:

{{
  "revenue": <FOR BANKS: net interest income + net fee and commission income + net other income (sum the top-line items) / FOR INSURANCE: net premiums earned / gross written premiums / FOR STANDARD: total operating revenues — ABSOLUTE>,
  "salgsinntekter": <product/sales revenue / gross premiums written / gross interest income — ABSOLUTE or null>,
  "loennskostnad": <wage costs / salaries / personnel expenses / staff costs / salary and administration expenses — ABSOLUTE or null>,
  "sum_driftskostnad": <total operating costs / total expenses / claims incurred + expenses / operating expenses excl. loan losses — ABSOLUTE or null>,
  "driftsresultat": <operating result / EBIT / technical result / underwriting result / profit before loan impairment charges / net profit before impairment — ABSOLUTE or null>,
  "sum_finansinntekt": <financial income / investment income / interest received / net interest income (banks) — ABSOLUTE or null>,
  "sum_finanskostnad": <financial costs / interest expense / finance costs / loan impairment charges / net losses on loans (banks) — ABSOLUTE or null>,
  "netto_finans": <net financial items / net investment result / net interest and fee income — ABSOLUTE or null>,
  "ordinaert_resultat_foer_skattekostnad": <profit before tax / result before tax / pre-tax profit — ABSOLUTE or null>,
  "ordinaert_resultat_skattekostnad": <income tax expense / tax charge — ABSOLUTE or null>,
  "aarsresultat": <net profit or loss for the year / profit after tax / annual result / profit for the year — ABSOLUTE>,
  "totalresultat": <total comprehensive income — ABSOLUTE or null>,
  "net_result": <same as aarsresultat — ABSOLUTE>,
  "equity": <total equity / total shareholders equity / equity attributable to shareholders — ABSOLUTE>,
  "sum_innskutt_egenkapital": <share capital + premium / paid-in capital — ABSOLUTE or null>,
  "sum_opptjent_egenkapital": <retained earnings / other equity / other reserves — ABSOLUTE or null>,
  "total_assets": <total assets — ABSOLUTE>,
  "sum_omloepsmidler": <current assets / short-term assets — null for banks (not applicable)>,
  "sum_anleggsmidler": <non-current assets / fixed assets — null for banks (not applicable)>,
  "sum_varer": <inventories — ABSOLUTE or null>,
  "sum_fordringer": <receivables / accounts receivable / premiums receivable / net loans to customers / loans and advances to customers (banks) — ABSOLUTE or null>,
  "sum_investeringer": <investments / financial assets / investment portfolio / financial instruments at fair value / securities / bonds (banks) — ABSOLUTE or null>,
  "sum_bankinnskudd_og_kontanter": <cash and bank / cash and equivalents / cash and balances with central banks — ABSOLUTE or null>,
  "goodwill": <goodwill / intangible assets — ABSOLUTE or null>,
  "sum_gjeld": <total liabilities / total debt — ABSOLUTE>,
  "short_term_debt": <current liabilities / short-term debt / technical provisions (insurance) / deposits from customers / customer deposits (banks) — ABSOLUTE or null>,
  "long_term_debt": <non-current liabilities / long-term debt / debt securities issued / covered bonds issued / subordinated loans (banks) — ABSOLUTE or null>,
  "antall_ansatte": <number of employees / headcount / FTEs as integer — or null>,
  "currency": <"NOK", "USD", "SEK", or "EUR">,
  "reporting_unit": <e.g. "NOK millions", "TNOK", "NOK" — as stated in the report>
}}

Return ONLY the JSON object. No explanation, no markdown, no code fences."""


# ---------------------------------------------------------------------------
# Chat / RAG system prompt
# ---------------------------------------------------------------------------
CHAT_SYSTEM_PROMPT = (
    "You are a risk analyst assistant for an insurance broker in Norway. "
    "Help underwriters assess company risk based on Norwegian public registry data. "
    "Be concise and factual. Flag concerns relevant to insurance underwriting "
    "such as negative equity, high leverage, PEP exposure, or unusual financial patterns. "
    "Answer only based on the provided company data. If data is missing, say so."
)


# ---------------------------------------------------------------------------
# Insurance recommendation prompts (risk-offer)
# ---------------------------------------------------------------------------
RISK_OFFER_PROMPT_EN = """You are an experienced Norwegian insurance broker. Based on the company's risk profile, recommend which insurance coverages the company should have and at what coverage amounts.

Company information:
{company_info}

Risk factors (score: {score}):
{factors}

Industry benchmark:
{benchmark}

Return ONLY valid JSON in this format (no markdown, no text outside JSON):
{{
  "anbefalinger": [
    {{
      "type": "Liability Insurance",
      "prioritet": "Must have",
      "anbefalt_sum": "5,000,000 NOK",
      "begrunnelse": "Justification based on company profile"
    }}
  ],
  "total_premieanslag": "80,000\u2013120,000 NOK/year",
  "sammendrag": "Brief summary of the risk profile and recommendations"
}}

Priority must be one of: "Must have", "Recommended", "Optional"
Common insurance types for Norwegian companies: Liability Insurance, Workers Compensation, Group Life, Commercial Insurance, Crime/Fidelity, Cyber/Data Security, Directors & Officers (D&O), Travel Insurance, Property Insurance, Business Interruption
"""


RISK_OFFER_PROMPT = """Du er en erfaren norsk forsikringsmegler. Basert på selskapets risikoprofil skal du anbefale hvilke forsikringsdekninger selskapet bør ha og til hvilke forsikringssummer.

Selskapsinformasjon:
{company_info}

Risikofaktorer (score: {score}):
{factors}

Bransjenorm:
{benchmark}

Returner KUN gyldig JSON i dette formatet (ingen markdown, ingen forklaring utenfor JSON):
{{
  "anbefalinger": [
    {{
      "type": "Ansvarsforsikring",
      "prioritet": "Må ha",
      "anbefalt_sum": "5 000 000 NOK",
      "begrunnelse": "Begrunnelse basert på selskapets profil"
    }}
  ],
  "total_premieanslag": "80 000\u2013120 000 NOK/år",
  "sammendrag": "Kort sammendrag av risikoprofilen og anbefalingene"
}}

Prioritet skal være én av: "Må ha", "Anbefalt", "Valgfri"
Vanlige forsikringstyper for norske bedrifter: Ansvarsforsikring, Yrkesskade/yrkessykdom, Gruppeliv, Næringslivsforsikring, Kriminalitetsforsikring, Cyber/datasikkerhet, Styreansvar, Reiseforsikring, Eiendomsforsikring, Driftsavbrudd
"""


# ---------------------------------------------------------------------------
# IR (annual report) discovery validation prompt
# ---------------------------------------------------------------------------
IR_DISCOVERY_PROMPT_TEMPLATE = """You are helping identify official annual report PDFs for a company.
Company: {navn}
Organisation number: {orgnr}

Below are candidate PDF URLs found via search. Identify which are official annual reports
and extract the reporting year from the URL path or filename.
Exclude duplicates, marketing materials, sustainability reports, press releases, interim/quarterly reports.

Return a JSON array — one object per confirmed annual report, with the year inferred from the URL:
[{{"year": 2023, "pdf_url": "https://...", "label": "{navn} Annual Report 2023"}}]
Return ONLY the JSON array (no markdown, no commentary). Return [] if none are valid.

Candidate URLs:
{candidates_text}
"""
