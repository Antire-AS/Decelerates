"""Portfolio ingest — batch BRREG fetch and Norway Top-100 seed."""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from api.db import PortfolioCompany, Company, SessionLocal
from api.services.company import fetch_org_profile
from api.services.external_apis import fetch_enhetsregisteret, fetch_enhet_by_orgnr
from api.services.pdf_extract import _auto_extract_pdf_sources

logger = logging.getLogger(__name__)


class PortfolioIngestService:
    def __init__(self, db: Session):
        self.db = db

    def ingest_companies(self, portfolio_id: int) -> dict:
        """Fetch + embed all companies in the portfolio that aren't already in DB."""
        rows = (
            self.db.query(PortfolioCompany)
            .filter(PortfolioCompany.portfolio_id == portfolio_id)
            .all()
        )
        fetched, skipped, failed = 0, 0, 0
        for pc in rows:
            existing = self.db.query(Company).filter(Company.orgnr == pc.orgnr).first()
            if existing and existing.navn:
                skipped += 1
                continue
            try:
                fetch_org_profile(pc.orgnr, self.db)
                fetched += 1
            except Exception as exc:
                logger.warning("Portfolio ingest: failed for %s — %s", pc.orgnr, exc)
                failed += 1
        return {"fetched": fetched, "skipped": skipped, "failed": failed}

    def seed_norway_top100(self, portfolio_id: int) -> dict:
        """Look up each name in TOP_100_NO_NAMES via BRREG and add to portfolio.

        Returns counts of added, already_present, not_found.
        """
        from api.constants import TOP_100_NO_NAMES

        existing = {
            pc.orgnr
            for pc in self.db.query(PortfolioCompany)
            .filter(PortfolioCompany.portfolio_id == portfolio_id)
            .all()
        }
        added, already_present, not_found = 0, 0, 0
        for name in TOP_100_NO_NAMES:
            try:
                results = fetch_enhetsregisteret(name, size=1)
                if not results:
                    not_found += 1
                    logger.info("Top100 seed: no BRREG hit for '%s'", name)
                    continue
                orgnr = results[0]["orgnr"]
                if orgnr in existing:
                    already_present += 1
                    continue
                self.db.add(
                    PortfolioCompany(
                        portfolio_id=portfolio_id,
                        orgnr=orgnr,
                        added_at=datetime.now(timezone.utc).isoformat(),
                    )
                )
                existing.add(orgnr)
                added += 1
            except Exception as exc:
                logger.warning("Top100 seed: error for '%s' — %s", name, exc)
                not_found += 1
        self.db.commit()
        return {
            "added": added,
            "already_present": already_present,
            "not_found": not_found,
        }

    def enrich_pdfs_background(self, portfolio_id: int) -> dict:
        """Trigger background PDF discovery + extraction for all companies in the portfolio.

        Each company gets its own thread so discovery runs in parallel (up to 3 at a time).
        Returns immediately — enrichment continues in background.
        """
        rows = (
            self.db.query(PortfolioCompany)
            .filter(PortfolioCompany.portfolio_id == portfolio_id)
            .all()
        )
        orgnrs = [pc.orgnr for pc in rows]

        def _run(orgnr: str) -> None:
            try:
                org = fetch_enhet_by_orgnr(orgnr) or {}
                _auto_extract_pdf_sources(orgnr, org, db_factory=SessionLocal)
            except Exception as exc:
                logger.warning("PDF enrichment background: %s — %s", orgnr, exc)

        executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="pdf_enrich")
        for orgnr in orgnrs:
            executor.submit(_run, orgnr)
        executor.shutdown(wait=False)

        return {"queued": len(orgnrs), "message": "PDF-innhenting kjører i bakgrunnen"}


# Backward compat
def ingest_companies(portfolio_id: int, db: Session) -> dict:
    return PortfolioIngestService(db).ingest_companies(portfolio_id)


def seed_norway_top100(portfolio_id: int, db: Session) -> dict:
    return PortfolioIngestService(db).seed_norway_top100(portfolio_id)


def enrich_pdfs_background(portfolio_id: int, db: Session) -> dict:
    return PortfolioIngestService(db).enrich_pdfs_background(portfolio_id)
