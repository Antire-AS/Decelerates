"""Admin, debug, and notification endpoints.

Covers:
  - Admin CRUD: reset, demo seed, Norway top-100, CRM demo, demo documents
  - Debug: /debug/status (blob, DB, video moov-atom check)
  - Dashboard summary endpoint
  - Portfolio-digest and activity-reminder email notifications
"""
import os
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user, get_optional_user
from api.container import resolve
from api.db import Policy, PolicyStatus, Claim, ClaimStatus, Activity
from api.dependencies import get_db
from api.ports.driven.notification_port import NotificationPort
from api.services.admin_service import AdminService
from api.services.portfolio import collect_alerts

router = APIRouter()


def _admin_svc(db: Session = Depends(get_db)) -> AdminService:
    return AdminService(db)


def _get_notification() -> NotificationPort:
    return resolve(NotificationPort)  # type: ignore[return-value]


# ── Admin: reset + demo seed ───────────────────────────────────────────────────

@router.delete("/admin/reset")
def admin_reset(svc: AdminService = Depends(_admin_svc)) -> dict:
    """Reset collected company data so it will be re-fetched fresh from the web."""
    return svc.reset()


@router.post("/admin/demo")
def admin_demo(svc: AdminService = Depends(_admin_svc)) -> dict:
    """Seed demo portfolio with 8 major Norwegian companies and trigger PDF extraction."""
    return svc.seed_demo()


@router.post("/admin/seed-norway-top100")
def admin_seed_norway_top100(svc: AdminService = Depends(_admin_svc)) -> dict:
    """Seed Norges Topp 100 portfolio, fetch BRREG profiles, queue PDF extraction."""
    return svc.seed_norway_top100()


@router.post("/admin/seed-crm-demo")
def seed_crm_demo(svc: AdminService = Depends(_admin_svc)) -> dict:
    """Seed realistic demo policies, claims, and activities for the demo companies."""
    return svc.seed_crm_demo()


@router.post("/admin/seed-demo-documents")
def seed_demo_documents_endpoint(db: Session = Depends(get_db)) -> dict:
    """Generate anonymised demo insurance documents from existing real documents."""
    from api.services.demo_documents import seed_demo_documents
    return seed_demo_documents(db)


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


@router.get("/debug/status")
def debug_status() -> dict:
    """Diagnostic endpoint — returns blob storage health, DB state, and video moov-atom status."""
    from api.services.blob_storage import BlobStorageService
    from api.db import engine
    from sqlalchemy import text

    azure_client_id = os.getenv("AZURE_CLIENT_ID", "")
    azure_blob_endpoint = os.getenv("AZURE_BLOB_ENDPOINT", "")
    svc = BlobStorageService()
    blob_error = None
    blob_count = None
    blob_sample = []
    try:
        blobs = svc.list_blobs("transksrt")
        blob_count = len(blobs)
        blob_sample = blobs[:5]
    except Exception as exc:
        blob_error = str(exc)

    alembic_version = None
    alembic_error = None
    tables = []
    tags_col = None
    try:
        with engine.connect() as conn:
            alembic_version = conn.execute(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            ).scalar()
            rows = conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='public' ORDER BY table_name"
                )
            ).fetchall()
            tables = [r[0] for r in rows]
            tags_col = conn.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                    "WHERE table_name='insurance_documents' AND column_name='tags')"
                )
            ).scalar()
    except Exception as exc:
        alembic_error = str(exc)

    video_info = {}
    sas_url_works = None
    if svc._client:
        try:
            mp4_blobs = [b for b in svc.list_blobs("transksrt") if b.endswith(".mp4")]
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
        except Exception:
            pass

    return {
        "azure_client_id_set": bool(azure_client_id),
        "azure_client_id_prefix": azure_client_id[:8] + "..." if azure_client_id else None,
        "azure_blob_endpoint_set": bool(azure_blob_endpoint),
        "blob_client_init": svc._client is not None,
        "blob_count": blob_count,
        "blob_sample": blob_sample,
        "blob_error": blob_error,
        "sas_url_works": sas_url_works,
        "video_info": video_info,
        "alembic_version": alembic_version,
        "alembic_error": alembic_error,
        "tags_column_exists": tags_col,
        "public_tables": tables,
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

    portfolios = db.query(Portfolio).all()
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
            }
            for p in policies_needing
        ]
        sent = notification.send_renewal_threshold_emails(recipient, threshold, policy_dicts)
        if sent:
            for p in policies_needing:
                svc.mark_renewal_notified(p.id, threshold)
        results.append({"threshold_days": threshold, "policies_found": len(policies_needing), "sent": sent})

    total_sent = sum(r["policies_found"] for r in results if r["sent"])
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

    today = date.today()
    overdue = db.query(Activity).filter(
        Activity.completed == False, Activity.due_date < today,  # noqa: E712
    ).order_by(Activity.due_date.asc()).all()
    due_today_list = db.query(Activity).filter(
        Activity.completed == False, Activity.due_date == today,  # noqa: E712
    ).order_by(Activity.created_at.asc()).all()

    if not overdue and not due_today_list:
        return {"sent": False, "reason": "no due activities"}

    def _to_dict(a) -> dict:
        return {
            "orgnr": a.orgnr, "subject": a.subject,
            "activity_type": a.activity_type.value if a.activity_type else "",
            "due_date": a.due_date.isoformat() if a.due_date else None,
        }

    sent = notification.send_activity_reminders(
        recipient,
        [_to_dict(a) for a in overdue],
        [_to_dict(a) for a in due_today_list],
    )
    return {"sent": sent, "overdue": len(overdue), "due_today": len(due_today_list), "recipient": recipient}
