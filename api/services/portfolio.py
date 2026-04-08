"""Portfolio service — named company lists with cross-portfolio risk analysis and chat."""
import logging
from datetime import datetime, timezone
from typing import Iterator, Optional

from sqlalchemy.orm import Session

from api.db import Portfolio, PortfolioCompany, Company, CompanyHistory, CompanyChunk
from api.domain.exceptions import NotFoundError
import api.services.portfolio_analytics as _analytics
import api.services.portfolio_ingest as _ingest
import api.services.portfolio_streaming as _streaming

logger = logging.getLogger(__name__)


class PortfolioService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def create(self, name: str, firm_id: int, description: str = "") -> Portfolio:
        p = Portfolio(
            name=name.strip(),
            firm_id=firm_id,
            description=(description or "").strip(),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.db.add(p)
        try:
            self.db.commit()
            self.db.refresh(p)
        except Exception:
            self.db.rollback()
            raise
        return p

    def list_portfolios(self, firm_id: int) -> list[Portfolio]:
        return (
            self.db.query(Portfolio)
            .filter((Portfolio.firm_id == firm_id) | (Portfolio.firm_id.is_(None)))
            .order_by(Portfolio.id.desc())
            .all()
        )

    def get(self, portfolio_id: int, firm_id: Optional[int] = None) -> Portfolio:
        q = self.db.query(Portfolio).filter(Portfolio.id == portfolio_id)
        if firm_id is not None:
            q = q.filter((Portfolio.firm_id == firm_id) | (Portfolio.firm_id.is_(None)))
        p = q.first()
        if not p:
            raise NotFoundError(f"Portfolio {portfolio_id} not found")
        return p

    def delete(self, portfolio_id: int, firm_id: int) -> None:
        p = self.get(portfolio_id, firm_id)
        self.db.delete(p)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

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
            try:
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise

    def remove_company(self, portfolio_id: int, orgnr: str) -> None:
        row = (
            self.db.query(PortfolioCompany)
            .filter(PortfolioCompany.portfolio_id == portfolio_id, PortfolioCompany.orgnr == orgnr)
            .first()
        )
        if row:
            self.db.delete(row)
            try:
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise

    # ── Risk summary ──────────────────────────────────────────────────────────

    def _fetch_latest_hist_map(self, orgnrs: list) -> dict:
        """Batch-load the most recent CompanyHistory row for each orgnr. Returns {orgnr: hist}."""
        from sqlalchemy import func
        sq = (
            self.db.query(
                CompanyHistory.orgnr,
                func.max(CompanyHistory.year).label("max_year"),
            )
            .filter(CompanyHistory.orgnr.in_(orgnrs))
            .group_by(CompanyHistory.orgnr)
            .subquery()
        )
        return {
            h.orgnr: h
            for h in self.db.query(CompanyHistory).join(
                sq,
                (CompanyHistory.orgnr == sq.c.orgnr) & (CompanyHistory.year == sq.c.max_year),
            ).all()
        }

    def get_risk_summary(self, portfolio_id: int) -> list[dict]:
        """Return one risk row per company in the portfolio, merging DB + latest history."""
        rows = (
            self.db.query(PortfolioCompany)
            .filter(PortfolioCompany.portfolio_id == portfolio_id)
            .all()
        )
        if not rows:
            return []
        orgnrs = [pc.orgnr for pc in rows]
        company_map = {
            c.orgnr: c
            for c in self.db.query(Company).filter(Company.orgnr.in_(orgnrs)).all()
        }
        hist_map = self._fetch_latest_hist_map(orgnrs)
        result = []
        for pc in rows:
            company = company_map.get(pc.orgnr)
            hist = hist_map.get(pc.orgnr)
            if company:
                result.append({
                    "orgnr": pc.orgnr,
                    "navn": company.navn or pc.orgnr,
                    "kommune": company.kommune,
                    "naeringskode": company.naeringskode1_beskrivelse,
                    "regnskapsår": hist.year if hist else company.regnskapsår,
                    "revenue": (hist.revenue if hist else None) or company.sum_driftsinntekter,
                    "equity": (hist.equity if hist else None) or company.sum_egenkapital,
                    "equity_ratio": (hist.equity_ratio if hist else None) or company.equity_ratio,
                    "risk_score": company.risk_score,
                    "added_at": pc.added_at,
                })
            else:
                result.append({"orgnr": pc.orgnr, "navn": pc.orgnr, "risk_score": None, "added_at": pc.added_at})
        return sorted(result, key=lambda x: (x.get("risk_score") or 0), reverse=True)

    # ── Batch ingest ──────────────────────────────────────────────────────────

    def ingest_companies(self, portfolio_id: int) -> dict:
        """Fetch + embed all companies in the portfolio that aren't already in DB."""
        return _ingest.ingest_companies(portfolio_id, self.db)

    # ── Norway Top 100 seed ───────────────────────────────────────────────────

    def seed_norway_top100(self, portfolio_id: int) -> dict:
        """Look up each name in TOP_100_NO_NAMES via BRREG and add to portfolio."""
        self.get(portfolio_id)  # raises NotFoundError if missing
        return _ingest.seed_norway_top100(portfolio_id, self.db)

    # ── Background PDF enrichment ──────────────────────────────────────────────

    def enrich_pdfs_background(self, portfolio_id: int) -> dict:
        """Trigger background PDF discovery + extraction for all companies in the portfolio."""
        return _ingest.enrich_pdfs_background(portfolio_id, self.db)

    # ── Policy premium analytics ──────────────────────────────────────────────

    @staticmethod
    def _insurer_concentration(policies: list, total_premium: float) -> list:
        return _analytics._insurer_concentration(policies, total_premium)

    @staticmethod
    def _product_concentration(policies: list) -> list:
        return _analytics._product_concentration(policies)

    def get_analytics(self, portfolio_id: int, firm_id: int) -> dict:
        """Aggregate policy premium data for all companies in the portfolio."""
        return _analytics.get_analytics(portfolio_id, firm_id, self.db, self.get)

    # ── Portfolio concentration ────────────────────────────────────────────────

    @staticmethod
    def _nace_section(nace) -> str:
        return _analytics._nace_section(nace)

    @staticmethod
    def _rev_band(rev) -> str:
        return _analytics._rev_band(rev)

    def get_concentration(self, portfolio_id: int) -> dict:
        """Return portfolio concentration breakdown by industry, geography, and revenue size."""
        return _analytics.get_concentration(portfolio_id, self.db, self.get)

    # ── Streaming ingest ──────────────────────────────────────────────────────

    def _stream_pdf_phase(self, pc, navn: str, i: int, total: int) -> Iterator[str]:
        """Phase 2: discover PDFs for one company and yield NDJSON events."""
        yield from _streaming._stream_pdf_phase(pc, navn, i, total, self.db)

    def _stream_ingest_company(self, pc, i: int, total: int, include_pdfs: bool) -> Iterator[str]:
        """Stream BRREG + optional PDF events for one portfolio company."""
        yield from _streaming._stream_ingest_company(pc, i, total, include_pdfs, self.db)

    def stream_ingest(self, portfolio_id: int, include_pdfs: bool = False) -> Iterator[str]:
        """Stream NDJSON progress events for portfolio ingest (BRREG + optional PDFs)."""
        yield from _streaming.stream_ingest(portfolio_id, include_pdfs, self.db)

    def stream_seed_norway(self, portfolio_id: int) -> Iterator[str]:
        """Stream NDJSON events while adding Norway Top 100 companies to the portfolio."""
        yield from _streaming.stream_seed_norway(portfolio_id, self.db)

    def stream_batch_import(self, portfolio_id: int | None, orgnrs: list[str], invalid_count: int = 0) -> Iterator[str]:
        """Stream NDJSON progress while importing companies from a list of orgnrs."""
        yield from _streaming.stream_batch_import(portfolio_id, orgnrs, invalid_count, self.db)

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


# ── Shared alert logic (used by both portfolio_router and utils) ───────────────

def _alert(orgnr: str, navn: str, alert_type: str, severity: str, detail: str,
           prev_year: int, curr_year: int) -> dict:
    return {
        "orgnr": orgnr, "navn": navn, "alert_type": alert_type,
        "severity": severity, "detail": detail,
        "year_from": prev_year, "year_to": curr_year,
    }


def _check_revenue_yoy(curr, prev, orgnr: str, navn: str) -> list[dict]:
    if not (curr.revenue and prev.revenue and prev.revenue > 0):
        return []
    yoy = (curr.revenue - prev.revenue) / prev.revenue
    if yoy > 0.25:
        return [_alert(orgnr, navn, "Sterk vekst", "Moderat",
            f"Omsetning +{yoy*100:.0f}% YoY — gjennomgå dekning", prev.year, curr.year)]
    if yoy < -0.20:
        return [_alert(orgnr, navn, "Omsetningsfall", "Høy",
            f"Omsetning {yoy*100:.0f}% YoY — kan ha betalingsproblemer", prev.year, curr.year)]
    return []


def _check_equity(curr, prev, orgnr: str, navn: str) -> list[dict]:
    if curr.equity_ratio is None or prev.equity_ratio is None:
        return []
    if curr.equity_ratio < 0 and prev.equity_ratio >= 0:
        return [_alert(orgnr, navn, "Negativ EK", "Kritisk",
            "Negativ egenkapital dette år — vurder kansellering", prev.year, curr.year)]
    eq_drop = prev.equity_ratio - curr.equity_ratio
    if eq_drop > 0.08:
        return [_alert(orgnr, navn, "Egenkapital svekket", "Høy",
            f"Egenkapitalandel falt {eq_drop*100:.1f}pp — øk risikopåslag", prev.year, curr.year)]
    return []


def _check_employees(curr, prev, orgnr: str, navn: str) -> list[dict]:
    if not (curr.antall_ansatte and prev.antall_ansatte and prev.antall_ansatte > 0):
        return []
    emp_growth = (curr.antall_ansatte - prev.antall_ansatte) / prev.antall_ansatte
    if emp_growth > 0.5:
        return [_alert(orgnr, navn, "Ny ansattvekst", "Moderat",
            f"+{emp_growth*100:.0f}% ansatte — oppdater yrkesskadeforsikring", prev.year, curr.year)]
    return []


def _check_revenue_thresholds(curr, prev, orgnr: str, navn: str) -> list[dict]:
    if not (curr.revenue and prev.revenue):
        return []
    out = []
    for threshold in (100_000_000, 1_000_000_000):
        if prev.revenue < threshold <= curr.revenue:
            out.append(_alert(orgnr, navn, "Krysset terskel", "Moderat",
                f"Omsetning krysset {threshold/1e6:.0f} MNOK — ny premiesone", prev.year, curr.year))
    return out


def _load_history_pairs(orgnrs: list[str], db: Session) -> dict[str, list]:
    """Batch-load (curr, prev) history rows per orgnr to avoid N+1 queries."""
    rows = (
        db.query(CompanyHistory)
        .filter(CompanyHistory.orgnr.in_(orgnrs))
        .order_by(CompanyHistory.orgnr, CompanyHistory.year.desc())
        .all()
    )
    hist_map: dict[str, list] = {}
    for h in rows:
        bucket = hist_map.setdefault(h.orgnr, [])
        if len(bucket) < 2:
            bucket.append(h)
    return hist_map


def collect_alerts(portfolio_id: int, db: Session) -> list[dict]:
    """Collect YoY financial change alerts for all companies in a portfolio.

    Returns alerts sorted by severity: Kritisk → Høy → Moderat.
    """
    orgnrs = [
        r.orgnr for r in
        db.query(PortfolioCompany).filter(PortfolioCompany.portfolio_id == portfolio_id).all()
    ]
    company_names = {
        c.orgnr: c.navn
        for c in db.query(Company).filter(Company.orgnr.in_(orgnrs)).all()
    }
    hist_map = _load_history_pairs(orgnrs, db)

    alerts: list[dict] = []
    for orgnr in orgnrs:
        history = hist_map.get(orgnr, [])
        if len(history) < 2:
            continue
        curr, prev = history[0], history[1]
        navn = company_names.get(orgnr, orgnr)
        alerts += _check_revenue_yoy(curr, prev, orgnr, navn)
        alerts += _check_equity(curr, prev, orgnr, navn)
        alerts += _check_employees(curr, prev, orgnr, navn)
        alerts += _check_revenue_thresholds(curr, prev, orgnr, navn)

    _sev_order = {"Kritisk": 0, "Høy": 1, "Moderat": 2}
    alerts.sort(key=lambda a: _sev_order.get(a["severity"], 9))
    return alerts
