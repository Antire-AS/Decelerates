"""
Broker Accelerator API — application entry point.

This file creates the FastAPI app and wires all routers.
Run with:  uvicorn app:app --host 0.0.0.0 --port 8000 --reload

Module map:
  constants.py    — URL strings, model names, seed data, SLA/NACE tables
  db.py           — SQLAlchemy ORM models and init_db()
  dependencies.py — get_db() FastAPI dependency
  prompts.py      — LLM prompt constants
  rag_chain.py    — LangChain RAG: chunk_text, embed_chunks, build_rag_chain
  risk.py         — pure risk scoring (derive_simple_risk, build_risk_summary)
  schemas.py      — Pydantic request/response models
  services.py     — all business logic helper functions
  routers/
    company.py      — /ping, /search, /org/{orgnr}, /org-by-name, /companies
    financials.py   — /org/{orgnr}/history, /pdf-history, /pdf-sources
    risk_router.py  — /org/{orgnr}/risk-offer, /risk-report/pdf, /coverage-gap, /narrative, /estimate
    offers.py       — /org/{orgnr}/offers (CRUD + compare + forsikringstilbud/pdf)
    documents.py    — /insurance-documents (CRUD + keypoints + chat + compare)
    knowledge.py    — /org/{orgnr}/chat, /knowledge, /ingest-knowledge
    broker.py       — /broker/settings, /org/{orgnr}/broker-notes
    sla.py          — /sla (CRUD + pdf)
    utils.py        — /org/{orgnr}/bankruptcy, /koordinater, /losore, /benchmark, /struktur
                      /norgesbank/rate/{ccy}, /org/{orgnr}/roles, /org/{orgnr}/estimate
"""

from fastapi import FastAPI

from db import init_db
from services import _seed_pdf_sources
from dependencies import get_db  # noqa: F401 — re-exported for backward compat

from routers import (
    company,
    financials,
    risk_router,
    offers,
    documents,
    knowledge,
    broker,
    sla,
    utils,
)

app = FastAPI(title="Broker Accelerator API")


@app.on_event("startup")
def on_startup():
    init_db()
    db = next(get_db())
    try:
        _seed_pdf_sources(db)
    finally:
        db.close()


# ── Routers ────────────────────────────────────────────────────────────────
app.include_router(company.router)
app.include_router(financials.router)
app.include_router(risk_router.router)
app.include_router(offers.router)
app.include_router(documents.router)
app.include_router(knowledge.router)
app.include_router(broker.router)
app.include_router(sla.router)
app.include_router(utils.router)
