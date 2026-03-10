# Broker Accelerator

A Norwegian insurance broker tool. Enter a company name or org number and get a full due-diligence report: financial history, risk score, PEP/sanctions screening, AI-generated narrative, and professional PDF outputs — all from public Norwegian registries.

---

## What it does

| Feature | Description |
|---------|-------------|
| **Company lookup** | Search by name or org number. Pulls data from BRREG, Regnskapsregisteret, Kartverket and Finanstilsynet automatically. |
| **Risk scoring** | Rule-based risk score (0–20+) with labelled factors: financial health, industry exposure, company age, PEP hits, and more. |
| **Financial history** | Multi-year P&L and balance sheet data. Pulls from BRREG for most companies; uses Gemini AI to extract figures from annual report PDFs for banks and others not in the registry. |
| **PEP / sanctions screening** | Name-based screening against OpenSanctions (covers UN, EU, OFAC and 100+ other lists). |
| **AI risk narrative** | One-click AI-written risk summary covering financials, industry, key persons and exposure — ready to paste into a client report. |
| **Insurance offers** | Upload competitor offer PDFs. The AI extracts key terms (premium, coverage, deductible, conditions) and produces a structured comparison. |
| **Forsikringstilbud PDF** | Generate a professional Norwegian insurance offer document with your broker branding, coverage recommendations and premium estimates. |
| **Risk report PDF** | Download a formatted risk assessment report for any company. |
| **SLA agreements** | Generate, store and download signed SLA (tjenesteavtale) PDFs for broker–client engagements. |
| **AI chat** | Ask free-text questions about any company. Answers are grounded in the company's financial data, annual reports and prior analysis. |
| **Industry benchmark** | SSB-informed equity ratio and profit margin ranges per NACE section, shown alongside the company's own figures. |

---

## Quickstart

### With Docker (recommended)

```bash
# 1. Clone and enter the project
git clone <repo-url>
cd Decelerates

# 2. Copy the environment file and fill in your API keys
cp .env.example .env
# Edit .env — at minimum add GEMINI_API_KEY

# 3. Start the API
docker compose up --build

# 4. Start the UI (separate terminal)
pip install streamlit
streamlit run ui.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

### Without Docker

```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Start the API
uvicorn app:app --reload

# Start the UI (separate terminal)
streamlit run ui.py
```

---

## API keys

| Key | Required | Used for |
|-----|----------|---------|
| `GEMINI_API_KEY` | **Recommended** | PDF extraction, AI narrative, embeddings, IR discovery |
| `ANTHROPIC_API_KEY` | Optional | Preferred LLM for text generation and agentic PDF discovery |
| `VOYAGE_API_KEY` | Optional | Higher-quality RAG embeddings (falls back to Gemini) |

Set these in your `.env` file:

```
GEMINI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
VOYAGE_API_KEY=your_key_here
DATABASE_URL=postgresql://user@localhost:5432/brokerdb
```

You can add up to three Gemini keys (`GEMINI_API_KEY`, `GEMINI_API_KEY_2`, `GEMINI_API_KEY_3`) for automatic key rotation when free-tier quota is exhausted.

---

## Typical workflow

```
1. Search company by name or org number
      └─► Profile loads: org info, financials, risk score, PEP, map

2. Review risk summary
      └─► Score, labelled risk factors, SSB industry benchmark

3. Generate AI narrative
      └─► One-click written risk analysis, saved for future chat context

4. Upload competitor offers (optional)
      └─► AI extracts and compares terms across up to 3 PDFs

5. Generate PDF outputs
      └─► Risk report PDF  or  Forsikringstilbud PDF (with your branding)
```

---

## PDF annual report extraction

For companies not in BRREG Regnskapsregisteret (banks, holding companies, foreign subsidiaries), the tool automatically:

1. Searches for investor relations pages using an AI agent (Claude → Gemini → DuckDuckGo fallback)
2. Validates and stores PDF URLs
3. Extracts financial figures using Gemini's native PDF understanding
4. Stores results in the financial history table

You can also paste any public PDF URL manually in the "Add Annual Report PDF" section on the company profile.

---

## Broker settings

Go to the **Settings** tab in the sidebar and fill in your firm details:

- Firm name, org number, address
- Contact name, email, phone

These are embedded in all generated PDFs (Forsikringstilbud, SLA agreements).

---

## Running tests

```bash
python -m pytest tests/ -v
```

78 tests covering risk scoring, PDF extraction, LLM helpers, company upsert and external API transforms. Tests run without API keys or installed external services.

---

## Tech stack

| Component | Technology |
|-----------|------------|
| Backend API | FastAPI + uvicorn |
| Frontend | Streamlit |
| Database | PostgreSQL + pgvector |
| ORM | SQLAlchemy |
| PDF generation | fpdf2 |
| PDF extraction | Gemini native PDF + pdfplumber fallback |
| AI / LLM | Claude (Anthropic) + Gemini (Google) |
| Embeddings | Voyage AI or Gemini text-embedding-004 |
| Web scraping | Playwright (headless Chromium) + requests fallback |
| Chunking | LangChain text splitters |

---

## What we want to achieve

The goal is a fully-automated first-pass due-diligence tool for Norwegian insurance brokers:

- **Cut research time** — a company profile that would take 30–60 minutes of manual registry lookups is ready in seconds
- **Better client conversations** — AI-written narratives and structured risk factors give brokers a clear starting point for client meetings
- **Offer comparison at scale** — upload any insurer's PDF and get a structured breakdown, not raw text
- **Professional outputs** — branded PDFs (risk reports, Forsikringstilbud, SLA agreements) ready to share with clients directly from the tool
- **Institutional knowledge** — every analysis, Q&A and narrative is saved and searchable via the AI chat, so insights accumulate over time

### Roadmap direction

- Live premium estimates from insurer APIs
- Multi-company portfolio view and aggregate risk reporting
- Automated renewal workflow with document versioning
- Role-based access for broker teams
