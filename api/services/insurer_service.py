"""Insurer and Submission CRUD service."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from api.db import Insurer, Submission, SubmissionStatus
from api.domain.exceptions import NotFoundError
import logging

logger = logging.getLogger(__name__)


def _aggregate_submissions(submissions) -> tuple[dict, dict, dict]:
    """Count by status, by insurer_id, and by product_type for win/loss analysis."""
    by_status: dict[str, int] = {}
    by_insurer: dict[int, dict] = {}
    by_product: dict[str, dict] = {}
    for s in submissions:
        status_val = s.status.value if s.status else "pending"
        by_status[status_val] = by_status.get(status_val, 0) + 1
        iid = s.insurer_id
        if iid not in by_insurer:
            by_insurer[iid] = {"sent": 0, "quoted": 0, "declined": 0}
        by_insurer[iid]["sent"] += 1
        if status_val == "quoted":
            by_insurer[iid]["quoted"] += 1
        elif status_val == "declined":
            by_insurer[iid]["declined"] += 1
        pt = s.product_type
        if pt not in by_product:
            by_product[pt] = {"sent": 0, "quoted": 0, "declined": 0}
        by_product[pt]["sent"] += 1
        if status_val == "quoted":
            by_product[pt]["quoted"] += 1
        elif status_val == "declined":
            by_product[pt]["declined"] += 1
    return by_status, by_insurer, by_product


class InsurerService:
    def __init__(self, db: Session):
        self.db = db

    # ── Insurers ──────────────────────────────────────────────────────────────

    def list_insurers(self, firm_id: int) -> list[Insurer]:
        return (
            self.db.query(Insurer)
            .filter(Insurer.firm_id == firm_id)
            .order_by(Insurer.name)
            .all()
        )

    def create_insurer(self, firm_id: int, data: dict) -> Insurer:
        row = Insurer(
            firm_id=firm_id,
            created_at=datetime.now(timezone.utc),
            **data,
        )
        self.db.add(row)
        try:
            self.db.commit()
            self.db.refresh(row)
        except Exception:
            self.db.rollback()
            raise
        return row

    def update_insurer(self, firm_id: int, insurer_id: int, data: dict) -> Insurer:
        row = self._get_insurer_or_raise(firm_id, insurer_id)
        for key, val in data.items():
            if val is not None:
                setattr(row, key, val)
        try:
            self.db.commit()
            self.db.refresh(row)
        except Exception:
            self.db.rollback()
            raise
        return row

    def delete_insurer(self, firm_id: int, insurer_id: int) -> None:
        row = self._get_insurer_or_raise(firm_id, insurer_id)
        self.db.delete(row)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def _get_insurer_or_raise(self, firm_id: int, insurer_id: int) -> Insurer:
        row = (
            self.db.query(Insurer)
            .filter(Insurer.id == insurer_id, Insurer.firm_id == firm_id)
            .first()
        )
        if not row:
            raise NotFoundError(f"Insurer {insurer_id} not found")
        return row

    # ── Submissions ───────────────────────────────────────────────────────────

    def list_submissions(self, orgnr: str, firm_id: int) -> list[Submission]:
        return (
            self.db.query(Submission)
            .filter(Submission.orgnr == orgnr, Submission.firm_id == firm_id)
            .order_by(Submission.created_at.desc())
            .all()
        )

    def list_submissions_enriched(
        self, orgnr: str, firm_id: int
    ) -> list[tuple["Submission", str | None]]:
        """Return submissions paired with their insurer name for display."""
        rows = self.list_submissions(orgnr, firm_id)
        insurer_ids = [s.insurer_id for s in rows]
        insurer_map = (
            {
                i.id: i.name
                for i in self.db.query(Insurer)
                .filter(Insurer.id.in_(insurer_ids))
                .all()
            }
            if insurer_ids
            else {}
        )
        return [(r, insurer_map.get(r.insurer_id)) for r in rows]

    def create_submission(
        self, orgnr: str, firm_id: int, created_by_email: str, data: dict
    ) -> Submission:
        status_val = data.pop("status", "pending")
        try:
            status_enum = SubmissionStatus(status_val)
        except ValueError:
            status_enum = SubmissionStatus.pending

        row = Submission(
            orgnr=orgnr,
            firm_id=firm_id,
            created_by_email=created_by_email,
            created_at=datetime.now(timezone.utc),
            status=status_enum,
            **data,
        )
        self.db.add(row)
        try:
            self.db.commit()
            self.db.refresh(row)
        except Exception:
            self.db.rollback()
            raise
        return row

    def update_submission(
        self, firm_id: int, submission_id: int, data: dict
    ) -> Submission:
        row = self._get_submission_or_raise(firm_id, submission_id)
        if "status" in data and data["status"] is not None:
            try:
                data["status"] = SubmissionStatus(data["status"])
            except ValueError:
                pass
        for key, val in data.items():
            if val is not None:
                setattr(row, key, val)
        try:
            self.db.commit()
            self.db.refresh(row)
        except Exception:
            self.db.rollback()
            raise
        return row

    def delete_submission(self, firm_id: int, submission_id: int) -> None:
        row = self._get_submission_or_raise(firm_id, submission_id)
        self.db.delete(row)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def match_appetite(self, firm_id: int, product_type: str) -> list[Insurer]:
        """Return insurers whose appetite list includes the given product_type."""
        insurers = self.list_insurers(firm_id)
        exact, partial = [], []
        pt_lower = product_type.lower()
        for ins in insurers:
            appetite = ins.appetite or []
            appetite_lower = [a.lower() for a in appetite]
            if pt_lower in appetite_lower:
                exact.append(ins)
            elif any(pt_lower in a or a in pt_lower for a in appetite_lower):
                partial.append(ins)
        return exact + partial

    def get_win_loss_summary(self, firm_id: int) -> dict:
        """Win/loss analysis across all submissions for the firm."""
        submissions = (
            self.db.query(Submission).filter(Submission.firm_id == firm_id).all()
        )
        total = len(submissions)
        by_status, by_insurer, by_product = _aggregate_submissions(submissions)
        insurer_ids = list(by_insurer.keys())
        insurer_map = (
            {
                i.id: i.name
                for i in self.db.query(Insurer)
                .filter(Insurer.id.in_(insurer_ids))
                .all()
            }
            if insurer_ids
            else {}
        )
        quoted = by_status.get("quoted", 0)
        win_rate = round(quoted / total * 100, 1) if total else 0.0
        return {
            "total_submissions": total,
            "by_status": by_status,
            "win_rate_pct": win_rate,
            "by_insurer": {
                insurer_map.get(iid, str(iid)): stats
                for iid, stats in by_insurer.items()
            },
            "by_product_type": by_product,
        }

    def draft_submission_email(self, firm_id: int, submission_id: int) -> str:
        """Generate a professional Norwegian submission email draft via LLM."""
        from api.services.llm import _llm_answer_raw
        from api.db import Company

        sub = self._get_submission_or_raise(firm_id, submission_id)
        insurer = self._get_insurer_or_raise(firm_id, sub.insurer_id)
        company = self.db.query(Company).filter(Company.orgnr == sub.orgnr).first()

        company_info = ""
        if company:
            company_info = (
                f"Selskap: {company.navn} (orgnr {company.orgnr}), "
                f"NACE: {company.naeringskode1_beskrivelse or company.naeringskode1 or 'ukjent'}, "
                f"ansatte: {company.antall_ansatte or 'ukjent'}, "
                f"omsetning: {int(company.sum_driftsinntekter or 0):,} NOK"
            )
        else:
            company_info = f"Orgnr: {sub.orgnr}"

        prompt = (
            f"Skriv en profesjonell forsikringssøknad på norsk til {insurer.name}.\n"
            f"Produkttype: {sub.product_type}\n"
            f"{company_info}\n"
            f"Ønsket forsikringssum: "
            f"{'ukjent' if not sub.premium_offered_nok else f'{int(sub.premium_offered_nok):,} NOK'}\n\n"
            "Inkluder: hilsen, presentasjon av kunden, forsikringsbehovet, "
            "og en høflig forespørsel om tilbud. Bruk profesjonell forsikringsmegler-tone."
        )
        draft = _llm_answer_raw(prompt)
        return draft or ""

    def _get_submission_or_raise(self, firm_id: int, submission_id: int) -> Submission:
        row = (
            self.db.query(Submission)
            .filter(Submission.id == submission_id, Submission.firm_id == firm_id)
            .first()
        )
        if not row:
            raise NotFoundError(f"Submission {submission_id} not found")
        return row
