"""Cron/notification trigger endpoints — portfolio digest, renewal emails, activity reminders."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.container import resolve
from api.db import (
    Policy, PolicyStatus, Activity, BrokerFirm, BrokerSettings,
    Portfolio, NotificationKind,
)
from api.dependencies import get_db
from api.ports.driven.notification_port import NotificationPort
from api.services.notification_inbox_service import create_notification_for_users_safe
from api.services.portfolio import collect_alerts

router = APIRouter()


def _get_notification() -> NotificationPort:
    return resolve(NotificationPort)  # type: ignore[return-value]


def _resolve_single_firm_id(db: Session) -> int:
    firm_count = db.query(BrokerFirm).count()
    if firm_count == 0:
        raise HTTPException(status_code=503, detail="No BrokerFirm configured.")
    if firm_count > 1:
        raise HTTPException(status_code=409, detail="Multiple BrokerFirms — refactor to per-firm cron.")
    firm = db.query(BrokerFirm).order_by(BrokerFirm.id).first()
    return firm.id  # type: ignore[return-value]


def _activity_to_dict(a: Activity) -> dict:
    return {
        "orgnr": a.orgnr, "subject": a.subject,
        "activity_type": a.activity_type.value if a.activity_type else "",
        "due_date": a.due_date.isoformat() if a.due_date else None,
    }


def _build_coverage_gap_email(companies_with_gaps: list[dict]) -> str:
    gap_lines = "\n".join(
        f"- {c['navn']} ({c['orgnr']}): {c['gap_count']} gap(s) — " + ", ".join(g["type"] for g in c["gaps"])
        for c in companies_with_gaps
    )
    return f"<h2>Dekningsgap-rapport</h2><p>{len(companies_with_gaps)} kunder med manglende dekning:</p><pre>{gap_lines}</pre>"


def _check_recipient(db: Session) -> str:
    settings = db.query(BrokerSettings).first()
    recipient = settings.contact_email if settings else None
    if not recipient:
        raise HTTPException(status_code=422, detail="Ingen broker contact_email konfigurert.")
    return recipient


def _check_notification(notification: NotificationPort):
    if not notification.is_configured():
        raise HTTPException(status_code=503, detail="AZURE_COMMUNICATION_CONNECTION_STRING ikke konfigurert.")


@router.post("/admin/portfolio-digest")
def send_portfolio_digest(
    db: Session = Depends(get_db),
    notification: NotificationPort = Depends(_get_notification),
) -> dict:
    recipient = _check_recipient(db)
    _check_notification(notification)
    firm_id = _resolve_single_firm_id(db)

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
    renewals = db.query(Policy).filter(
        Policy.firm_id == firm_id, Policy.status == PolicyStatus.active,
        Policy.renewal_date >= today, Policy.renewal_date <= today + timedelta(days=90),
    ).order_by(Policy.renewal_date.asc()).all()
    renewal_dicts = [
        {"orgnr": p.orgnr, "insurer": p.insurer, "product_type": p.product_type,
         "annual_premium_nok": p.annual_premium_nok,
         "renewal_date": p.renewal_date.isoformat() if p.renewal_date else None,
         "days_to_renewal": (p.renewal_date - today).days if p.renewal_date else 0}
        for p in renewals
    ]
    renewal_sent = notification.send_renewal_digest(recipient, renewal_dicts)

    total_sent = sum(1 for r in results if r["sent"])
    if total_sent > 0 or renewal_sent:
        create_notification_for_users_safe(db, firm_id=firm_id, kind=NotificationKind.digest,
            title="Porteføljedigest sendt",
            message=f"{total_sent} portefølje(r) med varsler · {len(renewal_dicts)} fornyelse(r) innen 90 dager",
            link="/portfolio")
    return {"recipient": recipient, "portfolios_checked": len(portfolios), "emails_sent": total_sent,
            "details": results, "renewal_digest_sent": renewal_sent, "renewals_included": len(renewal_dicts)}


@router.post("/admin/renewal-threshold-emails")
def send_renewal_threshold_emails(
    db: Session = Depends(get_db),
    notification: NotificationPort = Depends(_get_notification),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    recipient = _check_recipient(db)
    _check_notification(notification)

    from api.services.policy_service import PolicyService
    from api.services.renewal_agent import RenewalAgentService

    svc = PolicyService(db)
    today = date.today()
    RenewalAgentService().process_renewals_batch(user.firm_id, db)

    results = []
    for threshold in [90, 60, 30]:
        policies_needing = svc.get_policies_needing_renewal_notification(firm_id=user.firm_id, threshold_days=threshold)
        if not policies_needing:
            results.append({"threshold_days": threshold, "policies_found": 0, "sent": False})
            continue
        policy_dicts = [
            {"orgnr": p.orgnr, "insurer": p.insurer, "product_type": p.product_type,
             "annual_premium_nok": p.annual_premium_nok,
             "renewal_date": p.renewal_date.isoformat() if p.renewal_date else None,
             "days_to_renewal": (p.renewal_date - today).days if p.renewal_date else threshold,
             "renewal_brief": p.renewal_brief, "renewal_email_draft": p.renewal_email_draft}
            for p in policies_needing
        ]
        sent = notification.send_renewal_threshold_emails(recipient, threshold, policy_dicts)
        if sent:
            for p in policies_needing:
                svc.mark_renewal_notified(p.id, threshold)
        results.append({"threshold_days": threshold, "policies_found": len(policies_needing), "sent": sent})

    total_sent = sum(r["policies_found"] for r in results if r["sent"])
    if total_sent > 0:
        create_notification_for_users_safe(db, firm_id=user.firm_id, kind=NotificationKind.renewal,
            title=f"{total_sent} fornyelser kommer opp",
            message=", ".join(f"{r['policies_found']} på {r['threshold_days']}d" for r in results if r["sent"]),
            link="/renewals")
    return {"recipient": recipient, "thresholds_checked": results, "total_notifications_sent": total_sent}


@router.post("/admin/activity-reminders")
def send_activity_reminders(
    db: Session = Depends(get_db),
    notification: NotificationPort = Depends(_get_notification),
) -> dict:
    recipient = _check_recipient(db)
    _check_notification(notification)
    firm_id = _resolve_single_firm_id(db)

    today = date.today()
    overdue = db.query(Activity).filter(
        Activity.firm_id == firm_id, Activity.completed == False, Activity.due_date < today,  # noqa: E712
    ).order_by(Activity.due_date.asc()).all()
    due_today_list = db.query(Activity).filter(
        Activity.firm_id == firm_id, Activity.completed == False, Activity.due_date == today,  # noqa: E712
    ).order_by(Activity.created_at.asc()).all()

    if not overdue and not due_today_list:
        return {"sent": False, "reason": "no due activities"}

    sent = notification.send_activity_reminders(
        recipient, [_activity_to_dict(a) for a in overdue], [_activity_to_dict(a) for a in due_today_list])
    if sent:
        create_notification_for_users_safe(db, firm_id=firm_id, kind=NotificationKind.activity_overdue,
            title=f"{len(overdue)} forfalt · {len(due_today_list)} i dag",
            message="Aktivitetspåminnelser sendt på e-post", link="/dashboard")
    return {"sent": sent, "overdue": len(overdue), "due_today": len(due_today_list), "recipient": recipient}


@router.post("/admin/trigger-coverage-gap-alerts")
def trigger_coverage_gap_alerts(
    db: Session = Depends(get_db),
    notification: NotificationPort = Depends(_get_notification),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    from api.services.coverage_gap import get_companies_with_gaps
    from api.services.audit import log_audit

    recipient = _check_recipient(db)
    companies_with_gaps = get_companies_with_gaps(user.firm_id, db)
    if not companies_with_gaps:
        return {"sent": False, "companies_with_gaps": 0, "reason": "no gaps found"}

    body_html = _build_coverage_gap_email(companies_with_gaps)
    sent = notification.send_email(recipient, "Dekningsgap oppdaget i porteføljen", body_html)
    log_audit(db, "coverage_gap_alert_sent", actor_email=user.email,
              detail={"companies": len(companies_with_gaps), "recipient": recipient})
    if sent:
        create_notification_for_users_safe(db, firm_id=user.firm_id, kind=NotificationKind.coverage_gap,
            title=f"{len(companies_with_gaps)} kunder med dekningsgap",
            message="Manglende forsikringsdekning oppdaget — sjekk porteføljen", link="/portfolio")
    return {"sent": sent, "companies_with_gaps": len(companies_with_gaps), "recipient": recipient}


@router.post("/admin/trigger-renewal-digest")
def trigger_renewal_digest(
    db: Session = Depends(get_db),
    notification: NotificationPort = Depends(_get_notification),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    recipient = _check_recipient(db)
    _check_notification(notification)

    today = date.today()
    policies = db.query(Policy).filter(
        Policy.firm_id == user.firm_id, Policy.status == PolicyStatus.active,
        Policy.renewal_date >= today, Policy.renewal_date <= today + timedelta(days=30),
    ).order_by(Policy.renewal_date.asc()).all()

    renewal_dicts = [
        {"orgnr": p.orgnr, "insurer": p.insurer, "product_type": p.product_type,
         "annual_premium_nok": p.annual_premium_nok,
         "renewal_date": p.renewal_date.isoformat() if p.renewal_date else None,
         "days_to_renewal": (p.renewal_date - today).days if p.renewal_date else 0}
        for p in policies
    ]
    sent = notification.send_renewal_digest(recipient, renewal_dicts)
    if sent and renewal_dicts:
        create_notification_for_users_safe(db, firm_id=user.firm_id, kind=NotificationKind.renewal,
            title=f"{len(renewal_dicts)} fornyelser innen 30 dager",
            message="Fornyelsesdigest sendt på e-post", link="/renewals")
    return {"recipient": recipient, "policies_included": len(renewal_dicts), "sent": sent}


@router.post("/admin/refresh-portfolio-risk")
def refresh_portfolio_risk(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    from api.services.risk_monitor import refresh_all_portfolios
    return refresh_all_portfolios(user.firm_id, db)
