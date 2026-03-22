"""
Broker Accelerator API — application entry point.

Run with:  uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
Or use:    bash scripts/run_api.sh

See CLAUDE.md for architecture reference; live API docs at /docs.
"""

import logging
import os

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api.db import init_db
from api.limiter import limiter
from api.container import configure, AppConfig
from api.adapters.blob_storage_adapter import BlobStorageConfig
from api.adapters.notification_adapter import NotificationConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
from api.services import _seed_pdf_sources
from api.services.search_service import SearchService
from api.dependencies import get_db

from api.routers import (
    company,
    financials,
    risk_router,
    offers,
    documents,
    videos,
    knowledge,
    broker,
    sla,
    utils,
    portfolio_router,
)

app = FastAPI(title="Broker Accelerator API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "HEAD", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"],
)


def _stamp_existing_db_if_needed(alembic_cfg) -> None:
    """If the DB has tables but Alembic hasn't tracked them, stamp the initial revision.

    Handles the case where data was migrated before Alembic was introduced:
    tables exist but alembic_version does not, causing CREATE TABLE to fail.
    After stamping, upgrade() will only apply new migrations (e.g. add_tags).
    """
    from sqlalchemy import text
    from api.db import engine  # reuse the already-configured psycopg3 engine

    with engine.connect() as conn:
        has_version_table = conn.execute(text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'alembic_version')"
        )).scalar()
        if not has_version_table:
            has_companies = conn.execute(text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'companies')"
            )).scalar()
            if has_companies:
                alembic_command.stamp(alembic_cfg, "4fa17f9b251a")


@app.on_event("startup")
def on_startup():
    alembic_cfg = AlembicConfig("alembic.ini")
    _stamp_existing_db_if_needed(alembic_cfg)
    alembic_command.upgrade(alembic_cfg, "head")
    init_db()
    SearchService().ensure_index()
    db = next(get_db())
    try:
        _seed_pdf_sources(db)
    finally:
        db.close()

    # ── DI container ──────────────────────────────────────────────────────────
    configure(AppConfig(
        blob=BlobStorageConfig(
            endpoint=os.getenv("AZURE_BLOB_ENDPOINT"),
        ),
        notification=NotificationConfig(
            conn_str=os.getenv("AZURE_COMMUNICATION_CONNECTION_STRING"),
            sender=os.getenv(
                "ACS_SENDER_ADDRESS",
                "donotreply@acs-broker-accelerator-prod.azurecomm.net",
            ),
        ),
    ))


# ── Routers ────────────────────────────────────────────────────────────────
app.include_router(company.router)
app.include_router(financials.router)
app.include_router(risk_router.router)
app.include_router(offers.router)
app.include_router(documents.router)
app.include_router(videos.router)
app.include_router(knowledge.router)
app.include_router(broker.router)
app.include_router(sla.router)
app.include_router(utils.router)
app.include_router(portfolio_router.router)

__all__ = ["app", "limiter"]
