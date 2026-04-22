"""
Broker Accelerator API — application entry point.

Run with:  uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
Or use:    bash scripts/run_api.sh

See CLAUDE.md for architecture reference; live API docs at /docs.
"""

import logging
import os

# ── Vertex AI service-account bootstrap ───────────────────────────────────────
# In Container Apps the SA key arrives base64-encoded
# (`GCP_VERTEX_AI_SA_JSON_B64`) — multi-line JSON with quotes/newlines breaks
# the bash --env-vars array used by `az containerapp create`, so deploy.yml
# encodes it before passing. Materialize it to a file so the google-auth ADC
# chain picks it up via GOOGLE_APPLICATION_CREDENTIALS. Locally the developer
# sets GOOGLE_APPLICATION_CREDENTIALS directly to the downloaded JSON path,
# so this block is a no-op in dev.
import base64 as _base64

_sa_json_b64 = os.getenv("GCP_VERTEX_AI_SA_JSON_B64")
_sa_json = os.getenv("GCP_VERTEX_AI_SA_JSON")
if _sa_json_b64 and not _sa_json:
    try:
        _sa_json = _base64.b64decode(_sa_json_b64).decode("utf-8")
    except Exception:  # noqa: BLE001 — bad input falls through to ADC default
        _sa_json = None
if _sa_json and not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
    _sa_path = "/tmp/gcp-vertex-ai-sa.json"
    with open(_sa_path, "w") as _fh:
        _fh.write(_sa_json)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = _sa_path

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
from api.adapters.serper_search_adapter import SerperSearchConfig
from api.adapters.foundry_llm_adapter import FoundryConfig
from api.adapters.msgraph_email_adapter import MsGraphConfig
from api.adapters.notification_adapter import NotificationConfig
from api.adapters.secret_adapter import SecretConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

# ── Auth-disabled startup warning ──────────────────────────────────────────────
# Mirrors the gate in api/auth.py::_is_auth_disabled — kept here so the warning
# fires once at boot, not on every request. Production cannot disable auth.
from api.auth import _is_auth_disabled  # noqa: E402

if _is_auth_disabled():
    logging.getLogger("api.auth").warning(
        "⚠ AUTH_DISABLED is active — ENVIRONMENT=%s. Anyone can hit any endpoint. "
        "This MUST NOT happen in production.",
        os.getenv("ENVIRONMENT", "development"),
    )

_ai_conn_str = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
if _ai_conn_str:
    from azure.monitor.opentelemetry import configure_azure_monitor

    configure_azure_monitor(connection_string=_ai_conn_str)

# Sentry — secondary error tracker (free tier 5K errors/month). DSN empty by
# default → SDK no-ops, no traffic sent. Set SENTRY_DSN env var to activate.
# Sentry is complementary to App Insights: App Insights = infra metrics +
# alerts, Sentry = error grouping + stack traces + release tracking.
_sentry_dsn = os.getenv("SENTRY_DSN")
if _sentry_dsn:
    import sentry_sdk

    sentry_sdk.init(
        dsn=_sentry_dsn,
        environment=os.getenv("ENVIRONMENT", "development"),
        release=os.getenv("GIT_SHA", "unknown"),
        # Capture 10% of transactions for performance monitoring; full sample
        # of errors. Tune up if you need more APM detail and have headroom in
        # your free-tier monthly event quota.
        traces_sample_rate=0.1,
        # Send default PII (req IPs, usernames) — fine for B2B, revisit if
        # we ever serve consumer end-users directly.
        send_default_pii=True,
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
    commission,
    deals,
    notifications,
    saved_searches,
    email_compose,
    webhooks,
    accounting,
    insurer_api,
    coverage_router,
    tender_router,
    chat_history,
    whiteboard,
)

app = FastAPI(title="Broker Accelerator API")

# OpenTelemetry FastAPI instrumentation — populates AppRequests + AppDependencies
# tables in Application Insights with per-endpoint method/status/duration data.
# Without this, only AppTraces / AppPerformanceCounters / AppExceptions get
# populated. configure_azure_monitor() above does NOT auto-instrument FastAPI
# in 1.8.x; explicit instrument_app() is required.
if _ai_conn_str:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
_cors_origins_env = os.getenv("CORS_ORIGINS", "")
_cors_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
if not _cors_origins:
    _env = os.getenv("ENVIRONMENT", "development")
    if _env in ("production", "staging"):
        logging.getLogger(__name__).warning(
            "CORS_ORIGINS not set in %s — defaulting to meglerai.no only", _env
        )
        _cors_origins = ["https://meglerai.no", "https://www.meglerai.no"]
    else:
        _cors_origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"],
)


def _run_migrations_with_lock(alembic_cfg) -> None:
    """Run Alembic migrations under a Postgres advisory lock.

    Uses pg_try_advisory_lock (non-blocking) instead of pg_advisory_lock.
    If the lock is already held (by another container that's mid-migration,
    or by a stale connection from a crashed container), we skip and let
    Alembic run without the lock. This is safe because:

    1. If another container is actively running migrations, Alembic's own
       DDL will either succeed (idempotent) or fail on conflict (DDL is
       transactional in Postgres — no partial state).
    2. If a stale connection holds the lock, the migration still runs — the
       lock_timeout in alembic/env.py will catch any DDL-level conflict.

    The old pg_advisory_lock (blocking) caused every deploy to hang
    indefinitely when a crashed container left an orphaned session-level
    lock in the connection pool.
    """
    from sqlalchemy import text
    from api.db import engine

    _LOCK_ID = 4_242_424_242  # arbitrary stable integer; unique to this app

    with engine.connect() as lock_conn:
        got_lock = lock_conn.execute(
            text(f"SELECT pg_try_advisory_lock({_LOCK_ID})")
        ).scalar()
        if not got_lock:
            logging.getLogger(__name__).warning(
                "Advisory lock %d held by another session — running migrations without lock",
                _LOCK_ID,
            )
        try:
            alembic_command.upgrade(alembic_cfg, "head")
        finally:
            if got_lock:
                lock_conn.execute(text(f"SELECT pg_advisory_unlock({_LOCK_ID})"))


def _stamp_existing_db_if_needed(alembic_cfg) -> None:
    """If the DB has tables but Alembic hasn't tracked them, stamp the initial revision.

    Handles the case where data was migrated before Alembic was introduced:
    tables exist but alembic_version does not, causing CREATE TABLE to fail.
    After stamping, upgrade() will only apply new migrations (e.g. add_tags).
    """
    from sqlalchemy import text
    from api.db import engine  # reuse the already-configured psycopg3 engine

    with engine.connect() as conn:
        has_version_table = conn.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'alembic_version')"
            )
        ).scalar()
        if not has_version_table:
            has_companies = conn.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = 'companies')"
                )
            ).scalar()
            if has_companies:
                alembic_command.stamp(alembic_cfg, "4fa17f9b251a")


@app.on_event("startup")
def on_startup():
    alembic_cfg = AlembicConfig("alembic.ini")
    _stamp_existing_db_if_needed(alembic_cfg)
    _run_migrations_with_lock(alembic_cfg)
    init_db()
    SearchService().ensure_index()
    db = next(get_db())
    try:
        _seed_pdf_sources(db)
    finally:
        db.close()

    # ── Auto-seed demo data on first boot (non-blocking) ────────────────────
    # Runs in a background thread so the health probe (/ping) responds
    # immediately and the Container App doesn't time out during activation.
    # seed_full_demo is idempotent (skips existing orgnrs).
    # Opt out with AUTO_SEED_DEMO=0 for real broker data.
    if os.getenv("AUTO_SEED_DEMO", "1") != "0":
        import threading

        def _auto_seed_background():
            from api.db import Company

            db_seed = next(get_db())
            try:
                if (
                    not db_seed.query(Company)
                    .filter(Company.orgnr == "999100101")
                    .first()
                ):
                    from api.services.demo_seed import seed_full_demo

                    result = seed_full_demo(db_seed)
                    logging.getLogger(__name__).info(
                        "Auto-seeded demo data: %s", result.get("message", "")
                    )
            except Exception as exc:
                logging.getLogger(__name__).warning(
                    "Auto-seed demo data failed: %s", exc
                )
                db_seed.rollback()
            finally:
                db_seed.close()

        threading.Thread(target=_auto_seed_background, daemon=True).start()

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
            logging.getLogger(__name__).info(
                "GDPR purge: hard-deleted %d company records", purged
            )
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

    def _handle_coverage_analysis(db, payload: dict):
        from api.services.coverage_service import CoverageService

        analysis_id = payload.get("analysis_id")
        if analysis_id:
            CoverageService(db).run_analysis(analysis_id)

    register_handler("coverage_analysis", _handle_coverage_analysis)

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
    configure(
        AppConfig(
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
            # Plan §🟢 #10 — MS Graph outbound. Empty strings until the broker
            # firm completes the Azure AD app registration; is_configured() then
            # returns False and POST /email/compose returns 503.
            msgraph=MsGraphConfig(
                tenant_id=os.getenv("AZURE_AD_TENANT_ID", ""),
                client_id=os.getenv("AZURE_AD_CLIENT_ID", ""),
                client_secret=os.getenv("AZURE_AD_CLIENT_SECRET", ""),
                service_mailbox=os.getenv("MS_GRAPH_SERVICE_MAILBOX", ""),
            ),
            # Antire Azure AI Foundry — primary LLM provider. OpenAI-compatible
            # endpoint fronting gpt-5.4 / gpt-5.4-mini / kimi / glm. Phase 1 of
            # the LLM-stack consolidation; consumers migrate one at a time.
            foundry=FoundryConfig(
                base_url=os.getenv("AZURE_FOUNDRY_BASE_URL"),
                api_key=os.getenv("AZURE_FOUNDRY_API_KEY"),
                default_text_model=os.getenv("AZURE_FOUNDRY_MODEL", "gpt-5.4-mini"),
            ),
            secret=SecretConfig(
                vault_url=os.getenv("AZURE_KEYVAULT_URL"),
            ),
            # Serper.dev Web Search — replaces both the broken DDG scrape
            # and the aborted Bing v7 attempt (Microsoft retired the
            # Bing.Search.v7 Cognitive Service in 2024). Google-backed
            # results via Serper's REST API; $5/mo flat covers 50K queries.
            # No key set = adapter is_configured() returns False and
            # pdf_web falls back to the (still broken) DDG scraper.
            serper_search=SerperSearchConfig(
                endpoint=os.getenv(
                    "SERPER_API_ENDPOINT", "https://google.serper.dev/search"
                ),
                api_key=os.getenv("SERPER_API_KEY"),
            ),
        )
    )


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
app.include_router(commission.router)
app.include_router(deals.router)
app.include_router(notifications.router)
app.include_router(saved_searches.router)
app.include_router(email_compose.router)
app.include_router(webhooks.router)
app.include_router(accounting.router)
app.include_router(insurer_api.router)
app.include_router(coverage_router.router)
app.include_router(tender_router.router)
app.include_router(chat_history.router)
app.include_router(whiteboard.router)

__all__ = ["app", "limiter"]
