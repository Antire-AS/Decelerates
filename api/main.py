"""
Broker Accelerator API — application entry point.

Run with:  uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
Or use:    bash scripts/run_api.sh

See CLAUDE.md for architecture reference; live API docs at /docs.
"""

import logging

from fastapi import FastAPI

from api.db import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
from api.services import _seed_pdf_sources
from api.dependencies import get_db

from api.routers import (
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
