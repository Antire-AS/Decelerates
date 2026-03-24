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

_ai_conn_str = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
if _ai_conn_str:
    from azure.monitor.opentelemetry import configure_azure_monitor
    configure_azure_monitor(connection_string=_ai_conn_str)
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
    users,
    contacts,
    policies,
    claims,
    activities,
    client_token,
    analytics,
    audit,
)

app = FastAPI(title="Broker Accelerator API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
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
    import logging as _log
    _startup = _log.getLogger("startup")
    _startup.setLevel(_log.INFO)
    alembic_cfg = AlembicConfig("alembic.ini")
    _startup.info("startup: stamping")
    _stamp_existing_db_if_needed(alembic_cfg)
    _startup.info("startup: running migrations")
    alembic_command.upgrade(alembic_cfg, "head")
    _startup.info("startup: init_db")
    init_db()
    _startup.info("startup: ensure_index")
    SearchService().ensure_index()
    _startup.info("startup: seed_pdf_sources")
    db = next(get_db())
    try:
        _seed_pdf_sources(db)
    finally:
        db.close()

    # ── Default firm name (set via BROKER_FIRM_NAME env var) ──────────────────
    firm_name = os.getenv("BROKER_FIRM_NAME")
    if firm_name:
        from api.db import BrokerFirm
        db_firm = next(get_db())
        try:
            firm = db_firm.query(BrokerFirm).filter(BrokerFirm.id == 1).first()
            if firm and firm.name != firm_name:
                firm.name = firm_name
                db_firm.commit()
        finally:
            db_firm.close()

    # ── Expired client token cleanup ──────────────────────────────────────────
    from datetime import datetime, timezone as _tz
    from api.db import ClientToken
    db_tok = next(get_db())
    try:
        db_tok.query(ClientToken).filter(
            ClientToken.expires_at < datetime.now(_tz.utc)
        ).delete(synchronize_session=False)
        db_tok.commit()
    except Exception:
        db_tok.rollback()
    finally:
        db_tok.close()

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
app.include_router(users.router)
app.include_router(contacts.router)
app.include_router(policies.router)
app.include_router(claims.router)
app.include_router(activities.router)
app.include_router(client_token.router)
app.include_router(analytics.router)
app.include_router(audit.router)

__all__ = ["app", "limiter"]
