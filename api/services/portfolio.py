"""Portfolio service — named company lists with cross-portfolio risk analysis and chat."""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from api.db import Portfolio, PortfolioCompany, Company, CompanyHistory, CompanyChunk
from api.domain.exceptions import NotFoundError

logger = logging.getLogger(__name__)


class PortfolioService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def create(self, name: str, description: str = "") -> Portfolio:
        p = Portfolio(
            name=name.strip(),
            description=(description or "").strip(),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.db.add(p)
        self.db.commit()
        self.db.refresh(p)
        return p

    def list_portfolios(self) -> list[Portfolio]:
        return self.db.query(Portfolio).order_by(Portfolio.id.desc()).all()

    def get(self, portfolio_id: int) -> Portfolio:
        p = self.db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
        if not p:
            raise NotFoundError(f"Portfolio {portfolio_id} not found")
        return p

    def delete(self, portfolio_id: int) -> None:
        p = self.get(portfolio_id)
        self.db.delete(p)
        self.db.commit()

    def add_company(self, portfolio_id: int, orgnr: str) -> None:
        self.get(portfolio_id)  # raises if missing
        existing = (
            self.db.query(PortfolioCompany)
            .filter(PortfolioCompany.portfolio_id == portfolio_id, PortfolioCompany.orgnr == orgnr)
            .first()
        )
        if not existing:
            self.db.add(PortfolioCompany(
                portfolio_id=portfolio_id,
                orgnr=orgnr,
                added_at=datetime.now(timezone.utc).isoformat(),
            ))
            self.db.commit()

    def remove_company(self, portfolio_id: int, orgnr: str) -> None:
        row = (
            self.db.query(PortfolioCompany)
            .filter(PortfolioCompany.portfolio_id == portfolio_id, PortfolioCompany.orgnr == orgnr)
            .first()
        )
        if row:
            self.db.delete(row)
            self.db.commit()

    # ── Risk summary ──────────────────────────────────────────────────────────

    def get_risk_summary(self, portfolio_id: int) -> list[dict]:
        """Return one risk row per company in the portfolio, merging DB + latest history."""
        rows = (
            self.db.query(PortfolioCompany)
            .filter(PortfolioCompany.portfolio_id == portfolio_id)
            .all()
        )
        result = []
        for pc in rows:
            company = self.db.query(Company).filter(Company.orgnr == pc.orgnr).first()
            hist = (
                self.db.query(CompanyHistory)
                .filter(CompanyHistory.orgnr == pc.orgnr)
                .order_by(CompanyHistory.year.desc())
                .first()
            )
            if company:
                revenue = (hist.revenue if hist else None) or company.sum_driftsinntekter
                equity = (hist.equity if hist else None) or company.sum_egenkapital
                equity_ratio = (hist.equity_ratio if hist else None) or company.equity_ratio
                result.append({
                    "orgnr": pc.orgnr,
                    "navn": company.navn or pc.orgnr,
                    "kommune": company.kommune,
                    "naeringskode": company.naeringskode1_beskrivelse,
                    "regnskapsår": hist.year if hist else company.regnskapsår,
                    "revenue": revenue,
                    "equity": equity,
                    "equity_ratio": equity_ratio,
                    "risk_score": company.risk_score,
                    "added_at": pc.added_at,
                })
            else:
                result.append({"orgnr": pc.orgnr, "navn": pc.orgnr, "risk_score": None, "added_at": pc.added_at})
        return sorted(result, key=lambda x: (x.get("risk_score") or 0), reverse=True)

    # ── Batch ingest ──────────────────────────────────────────────────────────

    def ingest_companies(self, portfolio_id: int) -> dict:
        """Fetch + embed all companies in the portfolio that aren't already in DB."""
        from api.services.company import fetch_org_profile

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

    # ── Norway Top 100 seed ───────────────────────────────────────────────────

    def seed_norway_top100(self, portfolio_id: int) -> dict:
        """Look up each name in TOP_100_NO_NAMES via BRREG and add to portfolio.
        Returns counts of added, already_present, not_found."""
        from api.constants import TOP_100_NO_NAMES
        from api.services.external_apis import fetch_enhetsregisteret

        self.get(portfolio_id)  # raises NotFoundError if missing
        existing = {
            pc.orgnr for pc in
            self.db.query(PortfolioCompany)
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
                self.db.add(PortfolioCompany(
                    portfolio_id=portfolio_id,
                    orgnr=orgnr,
                    added_at=datetime.now(timezone.utc).isoformat(),
                ))
                existing.add(orgnr)
                added += 1
            except Exception as exc:
                logger.warning("Top100 seed: error for '%s' — %s", name, exc)
                not_found += 1
        self.db.commit()
        return {"added": added, "already_present": already_present, "not_found": not_found}

    # ── Background PDF enrichment (5-year annual reports) ──────────────────────

    def enrich_pdfs_background(self, portfolio_id: int) -> dict:
        """Trigger background PDF discovery + extraction for all companies in the portfolio.

        Each company gets its own thread so discovery runs in parallel (up to 3 at a time).
        Returns immediately — enrichment continues in background.
        """
        from concurrent.futures import ThreadPoolExecutor
        from api.db import SessionLocal
        from api.services.pdf_extract import _auto_extract_pdf_sources
        from api.services.external_apis import fetch_enhet_by_orgnr

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

    # ── Portfolio chat ─────────────────────────────────────────────────────────

    def chat(self, portfolio_id: int, question: str) -> dict:
        """Answer a question using financial data from all companies in the portfolio as context."""
        from api.services.llm import _llm_answer_raw, _embed

        rows = self.get_risk_summary(portfolio_id)
        if not rows:
            return {"answer": "Ingen selskaper i denne porteføljen.", "sources": []}

        # Build rich context: risk table + retrieved chunks per company
        table_lines = ["| Selskap | Orgnr | Risk | Omsetning (MNOK) | EK-andel % | År |",
                       "|---------|-------|------|-----------------|------------|-----|"]
        for r in rows:
            rev = f"{round(r['revenue'] / 1_000_000, 1)}" if r.get("revenue") else "–"
            eq = f"{round((r['equity_ratio'] or 0) * 100, 1)}" if r.get("equity_ratio") else "–"
            score = r.get("risk_score") or "–"
            year = r.get("regnskapsår") or "–"
            table_lines.append(f"| {r['navn']} | {r['orgnr']} | {score} | {rev} | {eq} | {year} |")
        portfolio_context = "\n".join(table_lines)

        # Retrieve relevant chunks across all portfolio companies
        q_emb = _embed(question)
        orgnrs = [r["orgnr"] for r in rows]
        chunk_texts = []
        if q_emb:
            chunks = (
                self.db.query(CompanyChunk)
                .filter(CompanyChunk.orgnr.in_(orgnrs), CompanyChunk.embedding.isnot(None))
                .order_by(CompanyChunk.embedding.cosine_distance(q_emb))
                .limit(10)
                .all()
            )
            chunk_texts = [f"[{c.orgnr}] {c.chunk_text[:600]}" for c in chunks]

        context_parts = [f"Porteføljesammendrag:\n{portfolio_context}"]
        if chunk_texts:
            context_parts.append("Relevante utdrag:\n" + "\n\n".join(chunk_texts))

        prompt = (
            "Du er en forsikringsmegler-assistent som analyserer en portefølje av norske bedrifter. "
            "Bruk tallene i konteksten til å svare presist. Svar på norsk.\n\n"
            f"Kontekst:\n{'---'.join(context_parts)}\n\n"
            f"Spørsmål: {question}"
        )
        answer = _llm_answer_raw(prompt) or "Beklager, fikk ikke svar fra AI-tjenesten."
        sources = [r["orgnr"] for r in rows]
        return {"answer": answer, "sources": sources}
