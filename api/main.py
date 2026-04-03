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
    admin_router,
    portfolio_router,
    users,
    contacts,
    policies,
    claims,
    activities,
    client_token,
    analytics,
    audit,
    gdpr,
    idd,
    insurers,
    recommendations,
    coverage,
)

app = FastAPI(title="Broker Accelerator API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
_cors_origins_env = os.getenv("CORS_ORIGINS", "")
_cors_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
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

    # ── GDPR retention purge — hard-delete companies soft-deleted >90 days ago ─
    db_gdpr = next(get_db())
    try:
        from api.services.gdpr_service import GdprService
        purged = GdprService(db_gdpr).purge_old_deletions()
        if purged:
            logging.getLogger(__name__).info("GDPR purge: hard-deleted %d company records", purged)
    except Exception:
        db_gdpr.rollback()
    finally:
        db_gdpr.close()

    # ── Job queue — register handlers + start worker loop ─────────────────────
    from api.services.job_queue_service import register_handler, JobQueueService
    from api.services.pdf_background import _auto_extract_pdf_sources

    def _handle_pdf_extract(db, payload: dict):
        orgnr = payload.get("orgnr", "")
        org = payload.get("org", {})
        _auto_extract_pdf_sources(orgnr, org)

    register_handler("pdf_extract", _handle_pdf_extract)

    import asyncio

    _job_logger = logging.getLogger("api.job_worker")

    async def _job_worker():
        from api.db import SessionLocal as _SL
        while True:
            try:
                JobQueueService.process_pending(db_factory=_SL)
            except Exception as _exc:
                _job_logger.error("Job worker error: %s", _exc, exc_info=True)
            await asyncio.sleep(10)

    asyncio.get_event_loop().create_task(_job_worker())

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
app.include_router(admin_router.router)
app.include_router(portfolio_router.router)
app.include_router(users.router)
app.include_router(contacts.router)
app.include_router(policies.router)
app.include_router(claims.router)
app.include_router(activities.router)
app.include_router(client_token.router)
app.include_router(analytics.router)
app.include_router(idd.router)
app.include_router(insurers.router)
app.include_router(recommendations.router)
app.include_router(coverage.router)
app.include_router(audit.router)
app.include_router(gdpr.router)

__all__ = ["app", "limiter"]
