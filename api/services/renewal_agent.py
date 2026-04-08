"""Renewal recommendation agent — generates renewal briefs using LLM + coverage gap analysis."""
from sqlalchemy.orm import Session

from api.db import Company, Policy, Submission


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
