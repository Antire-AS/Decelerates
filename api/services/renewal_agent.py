"""Renewal recommendation agent — generates renewal briefs + client email drafts.

The proactive renewal agent enhances the daily cron (`/admin/renewal-threshold-emails`)
with AI-generated content:

1. **Renewal brief** (3 bullets) — for the broker's internal use: what to do next,
   market arguments, and client recommendation.
2. **Email draft** — a professional Norwegian email to the client summarising the
   upcoming renewal and next steps.

Both are cached on the Policy row so the LLM is only called once per renewal cycle.
The cron idempotency still comes from `last_renewal_notified_days`.
"""
import logging

from sqlalchemy.orm import Session

from api.db import Company, Policy, Submission

_log = logging.getLogger(__name__)


def _get_gap_summary(policy: Policy, db: Session) -> str:
    """Return a Norwegian coverage-gap sentence, or empty string if none."""
    from api.services.coverage_gap import analyze_coverage_gap
    try:
        gap = analyze_coverage_gap(policy.orgnr, policy.firm_id, db)
        if gap["gap_count"] > 0:
            gap_types = ", ".join(
                i["type"] for i in gap["items"] if i["status"] == "gap"
            )
            return f"Manglende dekning: {gap_types}."
    except Exception:
        pass
    return ""


def _get_submission_context(policy: Policy, db: Session) -> str:
    """Return a Norwegian summary of recent submissions for this policy/product."""
    subs = (
        db.query(Submission)
        .filter(
            Submission.orgnr == policy.orgnr,
            Submission.firm_id == policy.firm_id,
            Submission.product_type == policy.product_type,
        )
        .order_by(Submission.created_at.desc())
        .limit(5)
        .all()
    )
    if not subs:
        return ""
    lines = []
    for s in subs:
        status = s.status.value if s.status else "ukjent"
        premium = f"{int(s.premium_offered_nok):,} NOK" if s.premium_offered_nok else "ikke oppgitt"
        lines.append(f"  - {status}: premie {premium}")
    return "Tidligere markedstilnærminger:\n" + "\n".join(lines)


class RenewalAgentService:

    def generate_renewal_brief(self, policy: Policy, db: Session) -> str:
        """Draft a 3-bullet renewal brief for a policy using LLM."""
        from api.services.llm import _llm_answer_raw

        company = db.query(Company).filter(Company.orgnr == policy.orgnr).first()
        company_name = company.navn if company else policy.orgnr
        gap_summary = _get_gap_summary(policy, db)
        sub_lines = _get_submission_context(policy, db)
        renewal_date = policy.renewal_date.isoformat() if policy.renewal_date else "ukjent"
        premium = f"{int(policy.annual_premium_nok):,} NOK" if policy.annual_premium_nok else "ikke oppgitt"
        prompt = (
            f"Du er en norsk forsikringsmegler. Lag en kort fornyelsesbriefing (3 kulepunkter) "
            f"for følgende polise:\n\n"
            f"Kunde: {company_name} ({policy.orgnr})\n"
            f"Forsikringstype: {policy.product_type}\n"
            f"Forsikringsselskap: {policy.insurer}\n"
            f"Fornyelsesdato: {renewal_date}\n"
            f"Nåværende premie: {premium}\n"
            f"{gap_summary}\n"
            f"{sub_lines}\n\n"
            "Kulepunktene skal dekke: (1) aksjoner neste 30 dager, "
            "(2) markedsargumenter / forhandlingspunkter, "
            "(3) anbefaling til kunden. Svar kun med kulepunktene."
        )
        return _llm_answer_raw(prompt) or ""

    def generate_renewal_email_draft(self, policy: Policy, brief: str, db: Session) -> str:
        """Draft a professional Norwegian email to the client about the upcoming renewal."""
        from api.services.llm import _llm_answer_raw

        company = db.query(Company).filter(Company.orgnr == policy.orgnr).first()
        company_name = company.navn if company else policy.orgnr
        renewal_date = policy.renewal_date.isoformat() if policy.renewal_date else "ukjent"
        prompt = (
            f"Du er en norsk forsikringsmegler. Skriv en profesjonell e-post til kunden "
            f"om kommende fornyelse av forsikringspolisen.\n\n"
            f"Kunde: {company_name}\n"
            f"Forsikringstype: {policy.product_type}\n"
            f"Forsikringsselskap: {policy.insurer}\n"
            f"Fornyelsesdato: {renewal_date}\n\n"
            f"Din interne briefing (ikke vis til kunden, bruk som grunnlag):\n{brief}\n\n"
            "E-posten skal:\n"
            "- Informere om at fornyelsen nærmer seg\n"
            "- Kort nevne hva megleren vil gjøre (f.eks. innhente tilbud fra flere selskaper)\n"
            "- Be om et møte eller en samtale for å gjennomgå behovene\n"
            "- Være høflig, profesjonell og kort (maks 150 ord)\n"
            "- Bruk 'Med vennlig hilsen' som avslutning\n"
            "Svar kun med selve e-postteksten."
        )
        return _llm_answer_raw(prompt) or ""

    def process_renewals_batch(
        self, firm_id: int, db: Session
    ) -> list[dict]:
        """Generate AI briefs + email drafts for all policies approaching renewal.

        Called by the daily cron endpoint. Caches results on the Policy row so
        the LLM is only called once per renewal cycle. Returns a summary list.
        """
        from api.services.policy_service import PolicyService

        svc = PolicyService(db)
        results = []
        for threshold in [90, 60, 30]:
            policies = svc.get_policies_needing_renewal_notification(
                firm_id=firm_id, threshold_days=threshold,
            )
            for p in policies:
                try:
                    if not p.renewal_brief:
                        brief = self.generate_renewal_brief(p, db)
                        p.renewal_brief = brief
                    else:
                        brief = p.renewal_brief

                    if not p.renewal_email_draft:
                        p.renewal_email_draft = self.generate_renewal_email_draft(p, brief, db)

                    db.commit()
                    results.append({
                        "orgnr": p.orgnr, "policy_id": p.id,
                        "threshold": threshold, "brief_generated": True,
                    })
                except Exception as exc:
                    _log.warning("Renewal agent: failed for policy %d: %s", p.id, exc)
                    db.rollback()
                    results.append({
                        "orgnr": p.orgnr, "policy_id": p.id,
                        "threshold": threshold, "brief_generated": False, "error": str(exc),
                    })
        return results
