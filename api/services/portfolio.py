"""Portfolio service — named company lists with cross-portfolio risk analysis and chat."""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from api.db import Portfolio, PortfolioCompany, Company, CompanyHistory, CompanyChunk, Policy, PolicyStatus
from api.domain.exceptions import NotFoundError

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
        self.db.commit()
        self.db.refresh(p)
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

    # ── Policy premium analytics ──────────────────────────────────────────────

    @staticmethod
    def _insurer_concentration(policies: list, total_premium: float) -> list:
        insurer_map: dict[str, dict] = {}
        for p in policies:
            ins = p.insurer or "Ukjent"
            if ins not in insurer_map:
                insurer_map[ins] = {"insurer": ins, "policy_count": 0, "premium_nok": 0.0}
            insurer_map[ins]["policy_count"] += 1
            insurer_map[ins]["premium_nok"] += p.annual_premium_nok or 0
        rows = sorted(insurer_map.values(), key=lambda x: x["premium_nok"], reverse=True)
        for row in rows:
            row["share_pct"] = round(row["premium_nok"] / total_premium * 100, 1) if total_premium else 0
        return rows

    @staticmethod
    def _product_concentration(policies: list) -> list:
        product_map: dict[str, dict] = {}
        for p in policies:
            pt = p.product_type or "Ukjent"
            if pt not in product_map:
                product_map[pt] = {"product_type": pt, "count": 0, "premium_nok": 0.0}
            product_map[pt]["count"] += 1
            product_map[pt]["premium_nok"] += p.annual_premium_nok or 0
        return sorted(product_map.values(), key=lambda x: x["premium_nok"], reverse=True)

    def get_analytics(self, portfolio_id: int, firm_id: int) -> dict:
        """Aggregate policy premium data for all companies in the portfolio."""
        from datetime import date
        self.get(portfolio_id, firm_id)  # raises NotFoundError if missing or wrong firm
        orgnrs = [
            pc.orgnr for pc in
            self.db.query(PortfolioCompany)
            .filter(PortfolioCompany.portfolio_id == portfolio_id)
            .all()
        ]
        if not orgnrs:
            return {
                "total_annual_premium_nok": 0, "active_policy_count": 0,
                "insurer_concentration": [], "product_concentration": [],
                "upcoming_renewals_90d": 0, "upcoming_renewals_30d": 0,
            }
        policies = (
            self.db.query(Policy)
            .filter(Policy.orgnr.in_(orgnrs), Policy.firm_id == firm_id,
                    Policy.status == PolicyStatus.active)
            .all()
        )
        today = date.today()
        total_premium = sum(p.annual_premium_nok or 0 for p in policies)
        renewals_90 = sum(
            1 for p in policies
            if p.renewal_date and 0 <= (p.renewal_date - today).days <= 90
        )
        renewals_30 = sum(
            1 for p in policies
            if p.renewal_date and 0 <= (p.renewal_date - today).days <= 30
        )
        return {
            "total_annual_premium_nok": round(total_premium),
            "active_policy_count": len(policies),
            "insurer_concentration": self._insurer_concentration(policies, total_premium),
            "product_concentration": self._product_concentration(policies),
            "upcoming_renewals_90d": renewals_90,
            "upcoming_renewals_30d": renewals_30,
        }

    # ── Streaming ingest ──────────────────────────────────────────────────────

    def _stream_pdf_phase(self, pc, navn: str, i: int, total: int):
        """Phase 2: discover PDFs for one company and yield NDJSON events."""
        from datetime import datetime as _dt
        from threading import Thread
        from api.db import CompanyPdfSource, SessionLocal
        from api.services.external_apis import fetch_enhet_by_orgnr
        from api.services.pdf_extract import _run_phase2_discovery, _extract_pending_sources

        current_year = _dt.now().year
        covered = {s.year for s in self.db.query(CompanyPdfSource).filter(CompanyPdfSource.orgnr == pc.orgnr).all()}
        missing = [y for y in range(current_year - 4, current_year + 1) if y not in covered]
        if not missing:
            yield json.dumps({"type": "pdf_found", "orgnr": pc.orgnr, "navn": navn, "found_years": sorted(covered), "new": False, "index": i, "total": total}) + "\n"
            return
        yield json.dumps({"type": "pdf_searching", "orgnr": pc.orgnr, "navn": navn, "missing_years": missing, "index": i, "total": total}) + "\n"
        try:
            org = fetch_enhet_by_orgnr(pc.orgnr) or {"navn": navn, "organisasjonsnummer": pc.orgnr}
            sources = _run_phase2_discovery(pc.orgnr, org, self.db)
            found_years = sorted({s.year for s in sources})
            new_years = [y for y in found_years if y in missing]
            if new_years:
                yield json.dumps({"type": "pdf_found", "orgnr": pc.orgnr, "navn": navn, "found_years": found_years, "new_years": new_years, "new": True, "index": i, "total": total}) + "\n"
                Thread(target=_extract_pending_sources, args=(pc.orgnr, sources, SessionLocal()), daemon=True).start()
            else:
                yield json.dumps({"type": "pdf_none", "orgnr": pc.orgnr, "navn": navn, "index": i, "total": total}) + "\n"
        except Exception as exc:
            yield json.dumps({"type": "pdf_error", "orgnr": pc.orgnr, "navn": navn, "error": str(exc)[:120], "index": i, "total": total}) + "\n"

    def _stream_ingest_company(self, pc, i: int, total: int, include_pdfs: bool):
        """Stream BRREG + optional PDF events for one portfolio company."""
        from api.services.company import fetch_org_profile

        existing = self.db.query(Company).filter(Company.orgnr == pc.orgnr).first()
        navn = (existing.navn if existing else None) or pc.orgnr
        if existing and existing.navn and existing.risk_score is not None:
            yield json.dumps({"type": "skipped", "orgnr": pc.orgnr, "navn": navn, "risk_score": existing.risk_score, "index": i, "total": total}) + "\n"
            return
        yield json.dumps({"type": "searching", "orgnr": pc.orgnr, "navn": navn, "index": i, "total": total}) + "\n"
        try:
            fetch_org_profile(pc.orgnr, self.db)
            company = self.db.query(Company).filter(Company.orgnr == pc.orgnr).first()
            navn = company.navn if company else navn
            yield json.dumps({"type": "done", "orgnr": pc.orgnr, "navn": navn, "risk_score": company.risk_score if company else None, "index": i, "total": total}) + "\n"
        except Exception as exc:
            yield json.dumps({"type": "error", "orgnr": pc.orgnr, "navn": navn, "error": str(exc)[:120], "index": i, "total": total}) + "\n"
            return
        if include_pdfs:
            yield from self._stream_pdf_phase(pc, navn, i, total)

    def stream_ingest(self, portfolio_id: int, include_pdfs: bool = False):
        """Stream NDJSON progress events for portfolio ingest (BRREG + optional PDFs)."""
        rows = self.db.query(PortfolioCompany).filter(PortfolioCompany.portfolio_id == portfolio_id).all()
        total = len(rows)
        yield json.dumps({"type": "start", "total": total, "include_pdfs": include_pdfs}) + "\n"
        for i, pc in enumerate(rows):
            yield from self._stream_ingest_company(pc, i + 1, total, include_pdfs)
        yield json.dumps({"type": "complete", "total": total}) + "\n"

    def stream_seed_norway(self, portfolio_id: int):
        """Stream NDJSON events while adding Norway Top 100 companies to the portfolio."""
        from api.constants import TOP_100_NO_NAMES
        from api.services.external_apis import fetch_enhetsregisteret

        existing = {pc.orgnr for pc in self.db.query(PortfolioCompany).filter(PortfolioCompany.portfolio_id == portfolio_id).all()}
        total = len(TOP_100_NO_NAMES)
        yield json.dumps({"type": "start", "total": total}) + "\n"
        added, skipped, not_found = 0, 0, 0
        for i, name in enumerate(TOP_100_NO_NAMES):
            yield json.dumps({"type": "searching", "name": name, "index": i + 1, "total": total}) + "\n"
            try:
                results = fetch_enhetsregisteret(name, size=1)
                if not results:
                    yield json.dumps({"type": "not_found", "name": name, "index": i + 1, "total": total}) + "\n"
                    not_found += 1
                    continue
                orgnr, found_name = results[0]["orgnr"], results[0]["navn"]
                if orgnr in existing:
                    yield json.dumps({"type": "skipped", "name": found_name, "orgnr": orgnr, "index": i + 1, "total": total}) + "\n"
                    skipped += 1
                    continue
                self.db.add(PortfolioCompany(portfolio_id=portfolio_id, orgnr=orgnr, added_at=datetime.now(timezone.utc).isoformat()))
                self.db.commit()
                existing.add(orgnr)
                yield json.dumps({"type": "added", "name": found_name, "orgnr": orgnr, "index": i + 1, "total": total}) + "\n"
                added += 1
            except Exception as exc:
                yield json.dumps({"type": "error", "name": name, "error": str(exc)[:100], "index": i + 1, "total": total}) + "\n"
                not_found += 1
        yield json.dumps({"type": "complete", "added": added, "skipped": skipped, "not_found": not_found}) + "\n"

    def stream_batch_import(self, portfolio_id: int | None, orgnrs: list[str], invalid_count: int = 0):
        """Stream NDJSON progress while importing companies from a list of orgnrs."""
        from api.services import fetch_org_profile

        total = len(orgnrs)
        yield json.dumps({"type": "start", "total": total, "invalid": invalid_count}) + "\n"
        added, failed = 0, 0
        for i, orgnr in enumerate(orgnrs):
            yield json.dumps({"type": "searching", "orgnr": orgnr, "index": i + 1, "total": total}) + "\n"
            try:
                result = fetch_org_profile(orgnr, self.db)
                navn = (result or {}).get("org", {}).get("navn", orgnr) if result else orgnr
                if portfolio_id:
                    self.db.merge(PortfolioCompany(portfolio_id=portfolio_id, orgnr=orgnr, added_at=datetime.now(timezone.utc).isoformat()))
                    self.db.commit()
                yield json.dumps({"type": "done", "orgnr": orgnr, "navn": navn, "index": i + 1, "total": total}) + "\n"
                added += 1
            except Exception as exc:
                yield json.dumps({"type": "error", "orgnr": orgnr, "error": str(exc)[:120], "index": i + 1, "total": total}) + "\n"
                failed += 1
        yield json.dumps({"type": "complete", "added": added, "failed": failed, "invalid": invalid_count}) + "\n"

    # ── Portfolio concentration ────────────────────────────────────────────────

    @staticmethod
    def _nace_section(nace) -> str:
        from api.constants import _NACE_SECTION_MAP
        if not nace:
            return "?"
        try:
            code = int(str(nace).split(".")[0])
            for rng, s in _NACE_SECTION_MAP:
                if code in rng:
                    return s
        except (ValueError, AttributeError):
            pass
        return "?"

    @staticmethod
    def _rev_band(rev) -> str:
        if not rev:
            return "Ukjent"
        if rev < 10_000_000:
            return "<10 MNOK"
        if rev < 100_000_000:
            return "10–100 MNOK"
        if rev < 1_000_000_000:
            return "100 MNOK–1 BNOK"
        return ">1 BNOK"

    def get_concentration(self, portfolio_id: int) -> dict:
        """Return portfolio concentration breakdown by industry, geography, and revenue size."""
        from api.constants import NACE_BENCHMARKS
        self.get(portfolio_id)  # raises NotFoundError if missing
        orgnrs = [r.orgnr for r in self.db.query(PortfolioCompany).filter(PortfolioCompany.portfolio_id == portfolio_id).all()]
        companies = self.db.query(Company).filter(Company.orgnr.in_(orgnrs)).all()
        industry: dict[str, dict] = {}
        geography: dict[str, int] = {}
        size: dict[str, int] = {}
        total_revenue = 0.0
        for c in companies:
            sec = self._nace_section(c.naeringskode1)
            label = NACE_BENCHMARKS.get(sec, {}).get("industry", sec)
            industry.setdefault(sec, {"section": sec, "label": label, "count": 0, "revenue": 0})
            industry[sec]["count"] += 1
            industry[sec]["revenue"] += c.sum_driftsinntekter or 0
            geography[c.kommune or "Ukjent"] = geography.get(c.kommune or "Ukjent", 0) + 1
            band = self._rev_band(c.sum_driftsinntekter)
            size[band] = size.get(band, 0) + 1
            total_revenue += c.sum_driftsinntekter or 0
        geo_sorted = sorted(geography.items(), key=lambda x: x[1], reverse=True)[:10]
        return {
            "portfolio_id": portfolio_id, "total_companies": len(companies), "total_revenue": total_revenue,
            "by_industry": sorted(industry.values(), key=lambda x: x["count"], reverse=True),
            "by_geography": [{"kommune": k, "count": v} for k, v in geo_sorted],
            "by_size": [{"band": k, "count": v} for k, v in size.items()],
        }

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
    alerts: list[dict] = []
    for orgnr in orgnrs:
        history = (
            db.query(CompanyHistory)
            .filter(CompanyHistory.orgnr == orgnr)
            .order_by(CompanyHistory.year.desc())
            .limit(2)
            .all()
        )
        if len(history) < 2:
            continue
        curr, prev = history[0], history[1]
        navn = company_names.get(orgnr, orgnr)

        if curr.revenue and prev.revenue and prev.revenue > 0:
            yoy = (curr.revenue - prev.revenue) / prev.revenue
            if yoy > 0.25:
                alerts.append({"orgnr": orgnr, "navn": navn, "alert_type": "Sterk vekst",
                    "severity": "Moderat", "detail": f"Omsetning +{yoy*100:.0f}% YoY — gjennomgå dekning",
                    "year_from": prev.year, "year_to": curr.year})
            elif yoy < -0.20:
                alerts.append({"orgnr": orgnr, "navn": navn, "alert_type": "Omsetningsfall",
                    "severity": "Høy", "detail": f"Omsetning {yoy*100:.0f}% YoY — kan ha betalingsproblemer",
                    "year_from": prev.year, "year_to": curr.year})

        if curr.equity_ratio is not None and prev.equity_ratio is not None:
            eq_drop = prev.equity_ratio - curr.equity_ratio
            if curr.equity_ratio < 0 and prev.equity_ratio >= 0:
                alerts.append({"orgnr": orgnr, "navn": navn, "alert_type": "Negativ EK",
                    "severity": "Kritisk", "detail": "Negativ egenkapital dette år — vurder kansellering",
                    "year_from": prev.year, "year_to": curr.year})
            elif eq_drop > 0.08:
                alerts.append({"orgnr": orgnr, "navn": navn, "alert_type": "Egenkapital svekket",
                    "severity": "Høy", "detail": f"Egenkapitalandel falt {eq_drop*100:.1f}pp — øk risikopåslag",
                    "year_from": prev.year, "year_to": curr.year})

        if curr.antall_ansatte and prev.antall_ansatte and prev.antall_ansatte > 0:
            emp_growth = (curr.antall_ansatte - prev.antall_ansatte) / prev.antall_ansatte
            if emp_growth > 0.5:
                alerts.append({"orgnr": orgnr, "navn": navn, "alert_type": "Ny ansattvekst",
                    "severity": "Moderat", "detail": f"+{emp_growth*100:.0f}% ansatte — oppdater yrkesskadeforsikring",
                    "year_from": prev.year, "year_to": curr.year})

        for threshold in (100_000_000, 1_000_000_000):
            if curr.revenue and prev.revenue:
                if prev.revenue < threshold <= curr.revenue:
                    alerts.append({"orgnr": orgnr, "navn": navn, "alert_type": "Krysset terskel",
                        "severity": "Moderat",
                        "detail": f"Omsetning krysset {threshold/1e6:.0f} MNOK — ny premiesone",
                        "year_from": prev.year, "year_to": curr.year})

    _sev_order = {"Kritisk": 0, "Høy": 1, "Moderat": 2}
    alerts.sort(key=lambda a: _sev_order.get(a["severity"], 9))
    return alerts
