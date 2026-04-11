"""Admin, debug, and notification endpoints.

Covers:
  - Admin CRUD: reset, demo seed, Norway top-100, CRM demo, demo documents
  - Debug: /debug/status (blob, DB, video moov-atom check)
  - Dashboard summary endpoint
  - Portfolio-digest and activity-reminder email notifications
"""
import os
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from api.limiter import limiter

from api.auth import CurrentUser, get_current_user
from api.container import resolve
from api.db import Policy, PolicyStatus, Claim, ClaimStatus, Activity, BrokerFirm, NotificationKind
from api.dependencies import get_db
from api.ports.driven.notification_port import NotificationPort
from api.services.admin_service import AdminService
from api.services.notification_inbox_service import create_notification_for_users_safe
from api.services.portfolio import collect_alerts

router = APIRouter()



def _admin_svc(db: Session = Depends(get_db)) -> AdminService:
    return AdminService(db)


def _get_notification() -> NotificationPort:
    return resolve(NotificationPort)  # type: ignore[return-value]


def _fetch_due_activities(db: Session, firm_id: int) -> tuple[list, list]:
    """Return (overdue, due_today) activity lists for the firm. Extracted so
    `send_activity_reminders` stays under the 40-line limit."""
    today = date.today()
    overdue = db.query(Activity).filter(
        Activity.firm_id == firm_id,
        Activity.completed == False, Activity.due_date < today,  # noqa: E712
    ).order_by(Activity.due_date.asc()).all()
    due_today_list = db.query(Activity).filter(
        Activity.firm_id == firm_id,
        Activity.completed == False, Activity.due_date == today,  # noqa: E712
    ).order_by(Activity.created_at.asc()).all()
    return overdue, due_today_list


def _build_coverage_gap_email(companies_with_gaps: list[dict]) -> str:
    """Render the coverage-gap alert email body. Extracted so
    `trigger_coverage_gap_alerts` stays under the 40-line limit."""
    gap_lines = "\n".join(
        f"- {c['navn']} ({c['orgnr']}): {c['gap_count']} gap(s) — "
        + ", ".join(g["type"] for g in c["gaps"])
        for c in companies_with_gaps
    )
    return (
        "<h2>Dekningsgap-rapport</h2>"
        f"<p>{len(companies_with_gaps)} kunder har manglende forsikringsdekning:</p>"
        f"<pre>{gap_lines}</pre>"
    )


def _activity_to_dict(a: Activity) -> dict:
    """Serialize an Activity for the reminder email payload. Module-level so
    `send_activity_reminders` stays under the 40-line limit."""
    return {
        "orgnr": a.orgnr,
        "subject": a.subject,
        "activity_type": a.activity_type.value if a.activity_type else "",
        "due_date": a.due_date.isoformat() if a.due_date else None,
    }


def _resolve_single_firm_id(db: Session) -> int:
    """Resolve the single firm_id for cron endpoints driven by the singleton
    BrokerSettings row. Cron endpoints are single-firm by design — adding
    multi-tenant support requires per-firm BrokerSettings (not yet modelled).

    Fails loudly with a 409 if more than one firm exists, so the leak the
    cron used to cause (queries spanning all firms) becomes impossible.
    """
    firm_count = db.query(BrokerFirm).count()
    if firm_count == 0:
        raise HTTPException(
            status_code=503,
            detail="No BrokerFirm configured — cron jobs require at least one firm.",
        )
    if firm_count > 1:
        raise HTTPException(
            status_code=409,
            detail=(
                "Multiple BrokerFirms exist but cron endpoints are still single-firm. "
                "Refactor the cron architecture to per-firm BrokerSettings before "
                "running this on a multi-tenant deployment."
            ),
        )
    firm = db.query(BrokerFirm).order_by(BrokerFirm.id).first()
    return firm.id  # type: ignore[return-value]


# ── Admin: reset + demo seed ───────────────────────────────────────────────────

@router.delete("/admin/reset")
@limiter.limit("5/hour")
def admin_reset(request: Request, svc: AdminService = Depends(_admin_svc)) -> dict:
    """Reset collected company data so it will be re-fetched fresh from the web."""
    return svc.reset()


@router.post("/admin/demo")
@limiter.limit("10/hour")
def admin_demo(request: Request, svc: AdminService = Depends(_admin_svc)) -> dict:
    """Seed demo portfolio with 8 major Norwegian companies and trigger PDF extraction."""
    return svc.seed_demo()


@router.post("/admin/seed-norway-top100")
@limiter.limit("10/hour")
def admin_seed_norway_top100(request: Request, svc: AdminService = Depends(_admin_svc)) -> dict:
    """Seed Norges Topp 100 portfolio, fetch BRREG profiles, queue PDF extraction."""
    return svc.seed_norway_top100()


@router.post("/admin/seed-crm-demo")
@limiter.limit("10/hour")
def seed_crm_demo(request: Request, svc: AdminService = Depends(_admin_svc)) -> dict:
    """Seed realistic demo policies, claims, and activities for the demo companies."""
    return svc.seed_crm_demo()


@router.post("/admin/seed-demo-documents")
def seed_demo_documents_endpoint(db: Session = Depends(get_db)) -> dict:
    """Generate anonymised demo insurance documents from existing real documents."""
    from api.services.demo_documents import seed_demo_documents
    return seed_demo_documents(db)


@router.post("/admin/seed-full-demo")
def seed_full_demo_endpoint(db: Session = Depends(get_db)) -> dict:
    """Seed 8 fictional Norwegian companies with 5-year financial history and renewal policies.

    Completely synthetic data (orgnr 999100101–108). Idempotent — skips existing records.
    Renewal dates spread 15–91 days out for a realistic pipeline demo.
    """
    from api.services.demo_seed import seed_full_demo
    return seed_full_demo(db)


# ── Debug ──────────────────────────────────────────────────────────────────────

def _has_mp4_faststart(data: bytes):
    """Return True if moov box precedes mdat in the first chunk, False if not, None if inconclusive."""
    pos = 0
    while pos + 8 <= len(data):
        size = int.from_bytes(data[pos:pos + 4], "big")
        box_type = data[pos + 4:pos + 8].decode("ascii", errors="replace")
        if box_type == "moov":
            return True
        if box_type == "mdat":
            return False
        if size < 8 or pos + size > len(data):
            break
        pos += size
    return None


def _debug_blob_status(svc) -> dict:
    """Probe the transksrt container — returns count, sample, and any error."""
    try:
        blobs = svc.list_blobs("transksrt")
        return {"count": len(blobs), "sample": blobs[:5], "error": None}
    except Exception as exc:
        return {"count": None, "sample": [], "error": str(exc)}


def _debug_db_status() -> dict:
    """Inspect Alembic version, public tables, and the insurance_documents.tags column."""
    from api.db import engine
    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            version = conn.execute(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            ).scalar()
            rows = conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='public' ORDER BY table_name"
                )
            ).fetchall()
            tags_col = conn.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                    "WHERE table_name='insurance_documents' AND column_name='tags')"
                )
            ).scalar()
        return {
            "alembic_version": version,
            "alembic_error": None,
            "public_tables": [r[0] for r in rows],
            "tags_column_exists": tags_col,
        }
    except Exception as exc:
        return {
            "alembic_version": None,
            "alembic_error": str(exc),
            "public_tables": [],
            "tags_column_exists": None,
        }


def _debug_video_status(svc) -> tuple[dict, bool | None]:
    """Inspect every .mp4 in transksrt — moov-atom faststart + SAS URL generation.

    Returns ({mp4_name: info}, sas_url_works).
    """
    if not svc._client:
        return {}, None
    video_info: dict = {}
    sas_url_works: bool | None = None
    try:
        mp4_blobs = [b for b in svc.list_blobs("transksrt") if b.endswith(".mp4")]
    except Exception:
        return {}, None

    for mp4 in mp4_blobs:
        try:
            chunks = svc.stream_range("transksrt", mp4, offset=0, length=256)
            header = b"".join(chunks) if chunks else b""
            sas_url = svc.generate_sas_url("transksrt", mp4, hours=1)
            if sas_url_works is None:
                sas_url_works = sas_url is not None
            video_info[mp4] = {
                "size_mb": round((svc.get_blob_size("transksrt", mp4) or 0) / 1e6),
                "faststart": _has_mp4_faststart(header),
                "sas_url_generated": sas_url is not None,
            }
        except Exception as exc:
            video_info[mp4] = {"error": str(exc)}
    return video_info, sas_url_works


@router.get("/debug/status")
def debug_status() -> dict:
    """Diagnostic endpoint — returns blob storage health, DB state, and video moov-atom status."""
    from api.services.blob_storage import BlobStorageService

    azure_client_id = os.getenv("AZURE_CLIENT_ID", "")
    azure_blob_endpoint = os.getenv("AZURE_BLOB_ENDPOINT", "")
    svc = BlobStorageService()

    blob = _debug_blob_status(svc)
    db_info = _debug_db_status()
    video_info, sas_url_works = _debug_video_status(svc)

    return {
        "azure_client_id_set": bool(azure_client_id),
        "azure_client_id_prefix": azure_client_id[:8] + "..." if azure_client_id else None,
        "azure_blob_endpoint_set": bool(azure_blob_endpoint),
        "blob_client_init": svc._client is not None,
        "blob_count": blob["count"],
        "blob_sample": blob["sample"],
        "blob_error": blob["error"],
        "sas_url_works": sas_url_works,
        "video_info": video_info,
        "alembic_version": db_info["alembic_version"],
        "alembic_error": db_info["alembic_error"],
        "tags_column_exists": db_info["tags_column_exists"],
        "public_tables": db_info["public_tables"],
    }


# ── Dashboard ──────────────────────────────────────────────────────────────────

@router.get("/dashboard")
def get_dashboard(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Broker dashboard summary — renewals, claims, activities, premium book."""
    today = date.today()
    firm_id = user.firm_id

    renewals_30 = db.query(Policy).filter(
        Policy.firm_id == firm_id,
        Policy.status == PolicyStatus.active,
        Policy.renewal_date >= today,
        Policy.renewal_date <= today + timedelta(days=30),
    ).all()
    renewals_90 = db.query(Policy).filter(
        Policy.firm_id == firm_id,
        Policy.status == PolicyStatus.active,
        Policy.renewal_date >= today,
        Policy.renewal_date <= today + timedelta(days=90),
    ).all()

    active_policies = db.query(Policy).filter(
        Policy.firm_id == firm_id,
        Policy.status == PolicyStatus.active,
    ).all()
    total_premium = sum(p.annual_premium_nok or 0 for p in active_policies)

    open_claims = db.query(Claim).filter(
        Claim.firm_id == firm_id,
        Claim.status == ClaimStatus.open,
    ).count()

    due_today = db.query(Activity).filter(
        Activity.firm_id == firm_id,
        Activity.completed == False,  # noqa: E712
        Activity.due_date <= today,
    ).count()

    recent = db.query(Activity).filter(
        Activity.firm_id == firm_id,
    ).order_by(Activity.created_at.desc()).limit(5).all()

    return {
        "renewals_30d":          len(renewals_30),
        "renewals_90d":          len(renewals_90),
        "premium_at_risk_30d":   sum(p.annual_premium_nok or 0 for p in renewals_30),
        "open_claims":           open_claims,
        "activities_due":        due_today,
        "total_active_policies": len(active_policies),
        "total_premium_book":    total_premium,
        "recent_activities": [
            {
                "subject":    a.subject,
                "type":       a.activity_type.value,
                "orgnr":      a.orgnr,
                "created_by": a.created_by_email,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "completed":  a.completed,
            }
            for a in recent
        ],
    }


# ── Email notifications ────────────────────────────────────────────────────────

@router.post("/admin/portfolio-digest")
def send_portfolio_digest(
    db: Session = Depends(get_db),
    notification: NotificationPort = Depends(_get_notification),
) -> dict:
    """Send a portfolio health digest email to the broker's contact_email.

    Iterates all portfolios, collects alerts for each, and sends a single
    combined email. Idempotent — safe to call from a scheduled cron job.
    """
    from api.db import Portfolio, BrokerSettings

    settings = db.query(BrokerSettings).first()
    recipient = settings.contact_email if settings else None
    if not recipient:
        raise HTTPException(
            status_code=422,
            detail="Ingen broker contact_email konfigurert — sett det i Innstillinger.",
        )
    if not notification.is_configured():
        raise HTTPException(
            status_code=503,
            detail="AZURE_COMMUNICATION_CONNECTION_STRING ikke konfigurert.",
        )

    firm_id = _resolve_single_firm_id(db)

    # Portfolios can be firm-scoped (firm_id NOT NULL) or shared (firm_id IS NULL).
    # Include shared portfolios so the digest still emails about them.
    portfolios = db.query(Portfolio).filter(
        (Portfolio.firm_id == firm_id) | (Portfolio.firm_id.is_(None))
    ).all()
    results = []
    for portfolio in portfolios:
        alerts = collect_alerts(portfolio.id, db)
        if not alerts:
            results.append({"portfolio": portfolio.name, "alerts": 0, "sent": False})
            continue
        sent = notification.send_portfolio_digest(recipient, portfolio.name, alerts)
        results.append({"portfolio": portfolio.name, "alerts": len(alerts), "sent": sent})

    today = date.today()
    cutoff = today + timedelta(days=90)
    renewals = db.query(Policy).filter(
        Policy.firm_id == firm_id,
        Policy.status == PolicyStatus.active,
        Policy.renewal_date >= today,
        Policy.renewal_date <= cutoff,
    ).order_by(Policy.renewal_date.asc()).all()
    renewal_dicts = [
        {
            "orgnr": p.orgnr,
            "insurer": p.insurer,
            "product_type": p.product_type,
            "annual_premium_nok": p.annual_premium_nok,
            "renewal_date": p.renewal_date.isoformat() if p.renewal_date else None,
            "days_to_renewal": (p.renewal_date - today).days if p.renewal_date else 0,
        }
        for p in renewals
    ]
    renewal_sent = notification.send_renewal_digest(recipient, renewal_dicts)

    total_sent = sum(1 for r in results if r["sent"])
    # Plan §🟢 #17 — fan out to the bell-icon panel for every user in the firm.
    # Best-effort: failure here MUST NOT roll back the email-send success.
    if total_sent > 0 or renewal_sent:
        create_notification_for_users_safe(
            db,
            firm_id=firm_id,
            kind=NotificationKind.digest,
            title="Porteføljedigest sendt",
            message=f"{total_sent} portefølje(r) med varsler · {len(renewal_dicts)} fornyelse(r) innen 90 dager",
            link="/portfolio",
        )
    return {
        "recipient": recipient,
        "portfolios_checked": len(portfolios),
        "emails_sent": total_sent,
        "details": results,
        "renewal_digest_sent": renewal_sent,
        "renewals_included": len(renewal_dicts),
    }


@router.post("/admin/renewal-threshold-emails")
def send_renewal_threshold_emails(
    db: Session = Depends(get_db),
    notification: NotificationPort = Depends(_get_notification),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Send targeted renewal reminders at 90/60/30-day thresholds. Idempotent — safe for cron.

    Each policy is notified at most once per threshold: once a 30-day email is sent,
    it won't be re-sent until the next renewal cycle (last_renewal_notified_days reset on new policy).
    """
    from api.db import BrokerSettings
    from api.services.policy_service import PolicyService

    settings = db.query(BrokerSettings).first()
    recipient = settings.contact_email if settings else None
    if not recipient:
        raise HTTPException(status_code=422, detail="Ingen broker contact_email konfigurert.")
    if not notification.is_configured():
        raise HTTPException(status_code=503, detail="AZURE_COMMUNICATION_CONNECTION_STRING ikke konfigurert.")

    svc = PolicyService(db)
    today = date.today()
    results = []

    # Pre-generate AI briefs + email drafts for all approaching renewals.
    # Cached on the Policy row so subsequent cron runs skip the LLM calls.
    from api.services.renewal_agent import RenewalAgentService
    RenewalAgentService().process_renewals_batch(user.firm_id, db)

    for threshold in [90, 60, 30]:
        policies_needing = svc.get_policies_needing_renewal_notification(
            firm_id=user.firm_id, threshold_days=threshold
        )
        if not policies_needing:
            results.append({"threshold_days": threshold, "policies_found": 0, "sent": False})
            continue

        policy_dicts = [
            {
                "orgnr": p.orgnr,
                "insurer": p.insurer,
                "product_type": p.product_type,
                "annual_premium_nok": p.annual_premium_nok,
                "renewal_date": p.renewal_date.isoformat() if p.renewal_date else None,
                "days_to_renewal": (p.renewal_date - today).days if p.renewal_date else threshold,
                "renewal_brief": p.renewal_brief,
                "renewal_email_draft": p.renewal_email_draft,
            }
            for p in policies_needing
        ]
        sent = notification.send_renewal_threshold_emails(recipient, threshold, policy_dicts)
        if sent:
            for p in policies_needing:
                svc.mark_renewal_notified(p.id, threshold)
        results.append({"threshold_days": threshold, "policies_found": len(policies_needing), "sent": sent})

    total_sent = sum(r["policies_found"] for r in results if r["sent"])
    # Fan out to bell-icon panel — one notification summarizing all thresholds.
    if total_sent > 0:
        create_notification_for_users_safe(
            db,
            firm_id=user.firm_id,
            kind=NotificationKind.renewal,
            title=f"{total_sent} fornyelser kommer opp",
            message=", ".join(
                f"{r['policies_found']} på {r['threshold_days']}d"
                for r in results if r["sent"]
            ),
            link="/renewals",
        )
    return {"recipient": recipient, "thresholds_checked": results, "total_notifications_sent": total_sent}


@router.post("/admin/activity-reminders")
def send_activity_reminders(
    db: Session = Depends(get_db),
    notification: NotificationPort = Depends(_get_notification),
) -> dict:
    """Email the broker about overdue and due-today activities. Safe to call from cron."""
    from api.db import BrokerSettings

    settings = db.query(BrokerSettings).first()
    recipient = settings.contact_email if settings else None
    if not recipient:
        raise HTTPException(status_code=422, detail="Ingen broker contact_email konfigurert.")
    if not notification.is_configured():
        raise HTTPException(status_code=503, detail="AZURE_COMMUNICATION_CONNECTION_STRING ikke konfigurert.")

    firm_id = _resolve_single_firm_id(db)
    overdue, due_today_list = _fetch_due_activities(db, firm_id)

    if not overdue and not due_today_list:
        return {"sent": False, "reason": "no due activities"}

    sent = notification.send_activity_reminders(
        recipient,
        [_activity_to_dict(a) for a in overdue],
        [_activity_to_dict(a) for a in due_today_list],
    )
    if sent:
        create_notification_for_users_safe(
            db,
            firm_id=firm_id,
            kind=NotificationKind.activity_overdue,
            title=f"{len(overdue)} forfalt · {len(due_today_list)} i dag",
            message="Aktivitetspåminnelser sendt på e-post",
            link="/dashboard",
        )
    return {"sent": sent, "overdue": len(overdue), "due_today": len(due_today_list), "recipient": recipient}


@router.post("/admin/trigger-coverage-gap-alerts")
def trigger_coverage_gap_alerts(
    db: Session = Depends(get_db),
    notification: NotificationPort = Depends(_get_notification),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Scan all active clients for coverage gaps and email the broker. Safe for cron."""
    from api.db import BrokerSettings
    from api.services.coverage_gap import get_companies_with_gaps
    from api.services.audit import log_audit

    settings = db.query(BrokerSettings).first()
    recipient = settings.contact_email if settings else None
    if not recipient:
        raise HTTPException(status_code=422, detail="Ingen broker contact_email konfigurert.")

    companies_with_gaps = get_companies_with_gaps(user.firm_id, db)
    if not companies_with_gaps:
        return {"sent": False, "companies_with_gaps": 0, "reason": "no gaps found"}

    body_html = _build_coverage_gap_email(companies_with_gaps)
    sent = notification.send_email(recipient, "Dekningsgap oppdaget i porteføljen", body_html)
    log_audit(db, "coverage_gap_alert_sent", actor_email=user.email,
              detail={"companies": len(companies_with_gaps), "recipient": recipient})
    if sent:
        create_notification_for_users_safe(
            db,
            firm_id=user.firm_id,
            kind=NotificationKind.coverage_gap,
            title=f"{len(companies_with_gaps)} kunder med dekningsgap",
            message="Manglende forsikringsdekning oppdaget — sjekk porteføljen",
            link="/portfolio",
        )
    return {"sent": sent, "companies_with_gaps": len(companies_with_gaps), "recipient": recipient}


@router.post("/admin/trigger-renewal-digest")
def trigger_renewal_digest(
    db: Session = Depends(get_db),
    notification: NotificationPort = Depends(_get_notification),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Send a renewal digest for policies expiring within 30 days. Safe for cron."""
    from api.db import BrokerSettings

    settings = db.query(BrokerSettings).first()
    recipient = settings.contact_email if settings else None
    if not recipient:
        raise HTTPException(status_code=422, detail="Ingen broker contact_email konfigurert.")
    if not notification.is_configured():
        raise HTTPException(status_code=503, detail="AZURE_COMMUNICATION_CONNECTION_STRING ikke konfigurert.")

    today = date.today()
    cutoff = today + timedelta(days=30)
    policies = db.query(Policy).filter(
        Policy.firm_id == user.firm_id,
        Policy.status == PolicyStatus.active,
        Policy.renewal_date >= today,
        Policy.renewal_date <= cutoff,
    ).order_by(Policy.renewal_date.asc()).all()

    renewal_dicts = [
        {
            "orgnr": p.orgnr,
            "insurer": p.insurer,
            "product_type": p.product_type,
            "annual_premium_nok": p.annual_premium_nok,
            "renewal_date": p.renewal_date.isoformat() if p.renewal_date else None,
            "days_to_renewal": (p.renewal_date - today).days if p.renewal_date else 0,
        }
        for p in policies
    ]
    sent = notification.send_renewal_digest(recipient, renewal_dicts)
    if sent and renewal_dicts:
        create_notification_for_users_safe(
            db,
            firm_id=user.firm_id,
            kind=NotificationKind.renewal,
            title=f"{len(renewal_dicts)} fornyelser innen 30 dager",
            message="Fornyelsesdigest sendt på e-post",
            link="/renewals",
        )
    return {"recipient": recipient, "policies_included": len(renewal_dicts), "sent": sent}


@router.post("/admin/refresh-portfolio-risk")
def refresh_portfolio_risk(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Re-fetch BRREG data for all portfolio companies, re-score risk, notify on changes.

    Designed for weekly cron (Monday 05:00 UTC). Rate-limited to 500ms
    between BRREG requests to avoid hammering the government API.
    """
    from api.services.risk_monitor import refresh_all_portfolios
    return refresh_all_portfolios(user.firm_id, db)
