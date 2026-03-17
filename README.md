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

# 3. Start everything (API + UI + Postgres)
docker compose up --build
```

Open [http://localhost:8501](http://localhost:8501) in your browser.
API is at [http://localhost:8000](http://localhost:8000).

### Without Docker

```bash
# One-time setup (installs uv + dependencies + Playwright)
bash scripts/setup.sh

# Start both API and UI
bash scripts/run_all.sh
```

Or run them separately in two terminals:

```bash
bash scripts/run_api.sh   # FastAPI on http://localhost:8000
bash scripts/run_ui.sh    # Streamlit on http://localhost:8501
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

82 tests covering risk scoring, PDF extraction, LLM helpers, company upsert and external API transforms. Tests run without API keys or installed external services.

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

## Deploying to Azure

### Services needed

| Component | Azure service |
|-----------|--------------|
| FastAPI backend | Azure Container Apps |
| Streamlit UI | Azure Container Apps (second app) |
| PostgreSQL + pgvector | Azure Database for PostgreSQL – Flexible Server |
| Docker images | Azure Container Registry |
| Secrets / API keys | Azure Container Apps environment secrets |

### Step-by-step

**1. Create a resource group**
```bash
az group create --name broker-rg --location norwayeast
```

**2. Create a container registry**
```bash
az acr create --resource-group broker-rg --name brokeracr --sku Basic
az acr login --name brokeracr
```

**3. Build and push images**
```bash
docker build -t brokeracr.azurecr.io/broker-api:latest .
docker build -f Dockerfile.ui -t brokeracr.azurecr.io/broker-ui:latest .
docker push brokeracr.azurecr.io/broker-api:latest
docker push brokeracr.azurecr.io/broker-ui:latest
```

**4. Create PostgreSQL Flexible Server**
```bash
az postgres flexible-server create \
  --resource-group broker-rg \
  --name broker-postgres \
  --location norwayeast \
  --admin-user brokeruser \
  --admin-password <your-password> \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --version 16

# Enable pgvector extension
az postgres flexible-server parameter set \
  --resource-group broker-rg \
  --server-name broker-postgres \
  --name azure.extensions \
  --value vector

# Create database
az postgres flexible-server db create \
  --resource-group broker-rg \
  --server-name broker-postgres \
  --database-name brokerdb
```

**5. Create a Container Apps environment**
```bash
az containerapp env create \
  --name broker-env \
  --resource-group broker-rg \
  --location norwayeast
```

**6. Deploy the API**
```bash
az containerapp create \
  --name broker-api \
  --resource-group broker-rg \
  --environment broker-env \
  --image brokeracr.azurecr.io/broker-api:latest \
  --registry-server brokeracr.azurecr.io \
  --target-port 8000 \
  --ingress external \
  --min-replicas 1 \
  --env-vars \
    DATABASE_URL="postgresql://brokeruser:<password>@broker-postgres.postgres.database.azure.com:5432/brokerdb?sslmode=require" \
    GEMINI_API_KEY=secretref:gemini-key \
    ANTHROPIC_API_KEY=secretref:anthropic-key
```

**7. Deploy the UI** (point it at the API container app URL)
```bash
az containerapp create \
  --name broker-ui \
  --resource-group broker-rg \
  --environment broker-env \
  --image brokeracr.azurecr.io/broker-ui:latest \
  --registry-server brokeracr.azurecr.io \
  --target-port 8501 \
  --ingress external \
  --min-replicas 1 \
  --env-vars \
    API_BASE_URL="https://<broker-api-fqdn>"
```

### Key gotchas

- **pgvector** — must run `CREATE EXTENSION IF NOT EXISTS vector;` once on the database after provisioning. The `azure.extensions=vector` parameter above enables it at the server level, but you still need to activate it per database.
- **Playwright cold starts** — set `--min-replicas 1` on the API container to avoid 30-second cold starts during agentic PDF discovery.
- **Firewall** — Azure Postgres Flexible Server blocks all IPs by default. Add a firewall rule to allow the Container Apps outbound IPs, or use VNet integration.
- **SSL** — Container Apps handles TLS termination. The `--server.headless=true` flag in Dockerfile.ui tells Streamlit not to open a browser.

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
