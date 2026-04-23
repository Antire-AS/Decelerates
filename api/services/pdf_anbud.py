"""Anbudspakke PDF — aggregate risk & context report sent to insurers.

Problem this solves
-------------------
Today a broker who wants to solicit offers from Gjensidige/Tryg/If has to
open a dozen tabs (Oversikt, Økonomi, Forsikring, CRM, Notater, Nyheter)
and copy-paste the relevant pieces into an email. Every broker does it
slightly differently; insurers get uneven packages and ask follow-up
questions the broker already has the answers to.

One button, one PDF. The broker downloads the anbudspakke and attaches
it to their outgoing email — insurers receive a consistent underwriting
underlay with:

  1. Cover — client name, orgnr, broker firm, date
  2. Selskapsinformasjon — org form, industry, location, board
  3. Økonomisk utvikling — up to 5 years of key figures + YoY deltas
  4. Risikoprofil — rule-based score, Altman Z'' (if applicable), peer delta
  5. Forsikringsbehov — prioritised IDD needs
  6. Meglers kommentarer — saved broker notes (Notater tab content)
  7. Materielle hendelser (siste 30 dager) — filtered news
  8. Eksisterende poliser — active Policy rows

Design notes
------------
- fpdf2 not reportlab — the rest of the app standardised on fpdf for
  pdf_risk / pdf_sla / pdf_offer; stay consistent.
- Assembler returns a flat dict; renderer consumes it. Keeps the
  "what to show" decision separate from the "how to draw it" layout.
- Missing sections degrade gracefully — if a company has no policies
  the Eksisterende-poliser section just says "Ingen aktive poliser" and
  the PDF skips no pages (predictable output for the broker's email
  preview).
- No auth coupling — anyone who can hit GET /org/{orgnr} can download
  this. The payload is the same data the UI already shows; no new
  privacy surface.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from api.db import (
    Company,
    CompanyHistory,
    CompanyNews,
    CompanyNote,
    Policy,
    PolicyStatus,
)
from api.domain.exceptions import NotFoundError
from api.risk import compute_altman_z_score, derive_simple_risk
from api.services.company import compute_peer_benchmark
from api.services.external_apis import fetch_board_members
from api.use_cases.insurance_needs import estimate_insurance_needs

logger = logging.getLogger(__name__)


# ── Data assembly — pure orchestration, no PDF bytes yet ─────────────────────


def _load_company(orgnr: str, db: Session) -> Company:
    company = db.query(Company).filter(Company.orgnr == orgnr).first()
    if not company:
        raise NotFoundError(f"Company {orgnr} not found")
    return company


def _selskap_section(company: Company) -> Dict[str, Any]:
    try:
        members = fetch_board_members(company.orgnr)
    except Exception:
        members = []
    return {
        "navn": company.navn,
        "orgnr": company.orgnr,
        "organisasjonsform_kode": company.organisasjonsform_kode,
        "naeringskode1": company.naeringskode1,
        "naeringskode1_beskrivelse": company.naeringskode1_beskrivelse,
        "kommune": company.kommune,
        "land": company.land,
        "antall_ansatte": company.antall_ansatte,
        "stiftelsesdato": (company.regnskap_raw or {}).get("stiftelsesdato"),
        "board_members": members[:10],
    }


def _financials_section(orgnr: str, db: Session) -> List[Dict[str, Any]]:
    """Up to 5 most recent years from company_history, newest first."""
    rows = (
        db.query(CompanyHistory)
        .filter(CompanyHistory.orgnr == orgnr)
        .order_by(CompanyHistory.year.desc())
        .limit(5)
        .all()
    )
    return [
        {
            "year": r.year,
            "revenue": r.revenue,
            "net_result": r.net_result,
            "equity": r.equity,
            "total_assets": r.total_assets,
            "equity_ratio": r.equity_ratio,
            "antall_ansatte": r.antall_ansatte,
        }
        for r in rows
    ]


def _risk_section(company: Company, orgnr: str, db: Session) -> Dict[str, Any]:
    org = {
        "orgnr": company.orgnr,
        "navn": company.navn,
        "organisasjonsform_kode": company.organisasjonsform_kode,
        "naeringskode1": company.naeringskode1,
        "naeringskode1_beskrivelse": company.naeringskode1_beskrivelse,
        "kommune": company.kommune,
    }
    regn = dict(company.regnskap_raw) if company.regnskap_raw else {}
    pep = dict(company.pep_raw) if company.pep_raw else {}
    rule = derive_simple_risk(org, regn, pep) if regn else None
    altman = compute_altman_z_score(regn) if regn else None
    peer = compute_peer_benchmark(orgnr, db)
    return {
        "rule_score": rule.get("score") if rule else None,
        "rule_factors": (rule or {}).get("factors") or [],
        "equity_ratio": (rule or {}).get("equity_ratio"),
        "altman_z": altman,
        "peer": peer,
        "pep_hits": int(pep.get("hit_count") or 0),
    }


def _needs_section(company: Company, orgnr: str, db: Session) -> List[Dict[str, Any]]:
    org = {
        "orgnr": company.orgnr,
        "navn": company.navn,
        "naeringskode1": company.naeringskode1,
        "organisasjonsform_kode": company.organisasjonsform_kode,
        "antall_ansatte": company.antall_ansatte,
        "sum_driftsinntekter": company.sum_driftsinntekter,
        "sum_eiendeler": company.sum_eiendeler,
        "sum_egenkapital": company.sum_egenkapital,
    }
    latest = (
        db.query(CompanyHistory)
        .filter(CompanyHistory.orgnr == orgnr)
        .order_by(CompanyHistory.year.desc())
        .first()
    )
    regn = {}
    if latest:
        regn = {
            "sum_driftsinntekter": latest.revenue,
            "sum_eiendeler": latest.total_assets,
            "antall_ansatte": latest.antall_ansatte,
        }
    try:
        return list(estimate_insurance_needs(org, regn) or [])
    except Exception as exc:
        logger.warning("[anbud] estimate_insurance_needs failed for %s: %s", orgnr, exc)
        return []


def _notes_section(orgnr: str, db: Session) -> List[Dict[str, Any]]:
    rows = (
        db.query(CompanyNote)
        .filter(CompanyNote.orgnr == orgnr)
        .order_by(CompanyNote.created_at.desc())
        .limit(10)
        .all()
    )
    return [
        {"question": n.question, "answer": n.answer, "created_at": n.created_at}
        for n in rows
    ]


def _material_news_section(orgnr: str, db: Session) -> List[Dict[str, Any]]:
    """Material news from the last 30 days, newest first. Falls back to any
    material news if published_at is null (Serper gave a non-relative date
    we couldn't parse)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    rows = (
        db.query(CompanyNews)
        .filter(
            CompanyNews.orgnr == orgnr,
            CompanyNews.material.is_(True),
        )
        .order_by(
            CompanyNews.published_at.desc().nullslast(),
            CompanyNews.fetched_at.desc(),
        )
        .limit(10)
        .all()
    )
    out: List[Dict[str, Any]] = []
    for r in rows:
        if r.published_at and r.published_at < cutoff:
            continue
        out.append(
            {
                "headline": r.headline,
                "url": r.url,
                "source": r.source,
                "summary": r.summary,
                "event_type": r.event_type,
                "published_at": r.published_at.isoformat() if r.published_at else None,
            }
        )
    return out


def _policies_section(orgnr: str, db: Session) -> List[Dict[str, Any]]:
    # FIRM_ID_AUDIT: scoped by orgnr, which the caller resolved through
    # the firm-scoped /org/{orgnr} flow. The anbudspakke endpoint cannot
    # expose a different firm's policies because the orgnr comes from the
    # URL and policies are joined to it, not to firms.
    rows = (
        db.query(Policy)
        .filter(Policy.orgnr == orgnr, Policy.status == PolicyStatus.active)
        .all()
    )
    return [
        {
            "id": p.id,
            "product": getattr(p, "product_type", None) or getattr(p, "product", None),
            "insurer": getattr(p, "insurer_name", None),
            "annual_premium_nok": p.annual_premium_nok,
            "end_date": (
                p.end_date.isoformat() if getattr(p, "end_date", None) else None
            ),
        }
        for p in rows
    ]


def build_anbudspakke_data(orgnr: str, db: Session) -> Dict[str, Any]:
    """Assemble every section's data into one flat dict. Called by the
    PDF renderer and (indirectly) by unit tests — keeps rendering
    concerns separate from data collection."""
    company = _load_company(orgnr, db)
    return {
        "orgnr": orgnr,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "selskap": _selskap_section(company),
        "financials": _financials_section(orgnr, db),
        "risk": _risk_section(company, orgnr, db),
        "needs": _needs_section(company, orgnr, db),
        "notes": _notes_section(orgnr, db),
        "material_news": _material_news_section(orgnr, db),
        "policies": _policies_section(orgnr, db),
    }


# ── PDF rendering — fpdf2, matches pdf_risk / pdf_sla look & feel ────────────


def _safe(s: Any) -> str:
    """Sanitize text for fpdf2's latin-1 default Helvetica font."""
    if s is None:
        return ""
    return (
        str(s)
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2026", "...")
        .replace("\u2032", "'")
        .replace("\u2033", '"')
        .replace("\u00b0", " ")
        .encode("latin-1", errors="replace")
        .decode("latin-1")
    )


def _fmt_nok(v: Optional[float]) -> str:
    if v is None:
        return "-"
    return f"{v / 1e6:,.1f} MNOK".replace(",", " ")


def _fmt_pct(v: Optional[float]) -> str:
    if v is None:
        return "-"
    return f"{v * 100:.1f}%"


def _section_title(pdf: Any, title: str) -> None:
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(30, 60, 120)
    pdf.ln(4)
    pdf.cell(0, 8, _safe(title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(30, 60, 120)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(2)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 10)


def _kv_row(pdf: Any, label: str, value: str, bold_value: bool = False) -> None:
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(60, 6, _safe(label))
    pdf.set_font("Helvetica", "B" if bold_value else "", 10)
    pdf.cell(0, 6, _safe(value), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)


def _render_cover(pdf: Any, data: Dict[str, Any]) -> None:
    selskap = data["selskap"]
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(30, 60, 120)
    pdf.ln(30)
    pdf.cell(0, 12, "Anbudsunderlag", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, "for forsikring", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    pdf.set_font("Helvetica", "", 16)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 9, _safe(selskap.get("navn") or ""), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(
        0,
        7,
        f"Orgnr: {selskap.get('orgnr')}  -  Generert: {date.today().isoformat()}",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.set_text_color(0, 0, 0)
    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(
        0,
        5,
        _safe(
            "Dette dokumentet er et underlag for innhenting av forsikringstilbud. "
            "Det samler selskapsinformasjon, finansiell utvikling, risikoprofil, "
            "meglers vurdering og materielle hendelser de siste 30 dager."
        ),
        new_x="LMARGIN",
        new_y="NEXT",
    )


def _render_selskap(pdf: Any, data: Dict[str, Any]) -> None:
    _section_title(pdf, "1. Selskapsinformasjon")
    s = data["selskap"]
    _kv_row(pdf, "Navn", s.get("navn") or "-")
    _kv_row(pdf, "Orgnr", s.get("orgnr") or "-")
    _kv_row(pdf, "Org.form", s.get("organisasjonsform_kode") or "-")
    _kv_row(
        pdf,
        "Bransje",
        f"{s.get('naeringskode1') or '-'} — {s.get('naeringskode1_beskrivelse') or '-'}",
    )
    _kv_row(pdf, "Kommune", s.get("kommune") or "-")
    _kv_row(
        pdf,
        "Ansatte",
        str(s.get("antall_ansatte")) if s.get("antall_ansatte") is not None else "-",
    )
    if s.get("stiftelsesdato"):
        _kv_row(pdf, "Stiftelsesdato", str(s.get("stiftelsesdato")))
    members = s.get("board_members") or []
    if members:
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, _safe("Styremedlemmer"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        for m in members:
            pdf.cell(
                0,
                5,
                _safe(f"- {m.get('name', '')} ({m.get('role', '')})"),
                new_x="LMARGIN",
                new_y="NEXT",
            )


def _render_financials(pdf: Any, data: Dict[str, Any]) -> None:
    _section_title(pdf, "2. Okonomisk utvikling")
    rows = data["financials"]
    if not rows:
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(
            0,
            6,
            _safe("Ingen finansiell historikk lagret."),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        return
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(20, 6, "Ar", border=1)
    pdf.cell(35, 6, "Omsetning", border=1)
    pdf.cell(35, 6, "Resultat", border=1)
    pdf.cell(35, 6, "Egenkapital", border=1)
    pdf.cell(25, 6, "EK-andel", border=1)
    pdf.cell(20, 6, "Ansatte", border=1, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    for r in rows:
        pdf.cell(20, 6, str(r["year"]), border=1)
        pdf.cell(35, 6, _fmt_nok(r.get("revenue")), border=1)
        pdf.cell(35, 6, _fmt_nok(r.get("net_result")), border=1)
        pdf.cell(35, 6, _fmt_nok(r.get("equity")), border=1)
        pdf.cell(25, 6, _fmt_pct(r.get("equity_ratio")), border=1)
        pdf.cell(
            20,
            6,
            str(r.get("antall_ansatte") or "-"),
            border=1,
            new_x="LMARGIN",
            new_y="NEXT",
        )


def _render_altman_row(pdf: Any, altman: Optional[Dict[str, Any]]) -> None:
    if altman:
        zone_label = {
            "safe": "trygg sone",
            "grey": "grasone",
            "distress": "nodsone",
        }.get(altman["zone"], altman["zone"])
        _kv_row(pdf, "Altman Z-score", f"{altman['z_score']:.2f} ({zone_label})")
    else:
        _kv_row(
            pdf,
            "Altman Z-score",
            "Ikke tilgjengelig (modellen passer ikke for bank/forsikring)",
        )


def _render_peer_row(pdf: Any, peer: Optional[Dict[str, Any]]) -> None:
    metrics = (peer or {}).get("metrics") or {}
    eq = metrics.get("equity_ratio") or {}
    if eq.get("company") is not None and eq.get("peer_avg") is not None:
        _kv_row(
            pdf,
            "EK-andel vs peers",
            f"{_fmt_pct(eq['company'])} vs {_fmt_pct(eq['peer_avg'])} (peer-snitt)",
        )


def _render_risk_factors(pdf: Any, factors: List[Dict[str, Any]]) -> None:
    if not factors:
        return
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, _safe("Risikofaktorer"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    for f in factors[:12]:
        line = f"- {f.get('label', '')}  (+{f.get('points', 0)} p, {f.get('category', '')})"
        pdf.cell(0, 5, _safe(line), new_x="LMARGIN", new_y="NEXT")


def _render_risk(pdf: Any, data: Dict[str, Any]) -> None:
    _section_title(pdf, "3. Risikoprofil")
    r = data["risk"]
    if r.get("rule_score") is not None:
        _kv_row(
            pdf, "Regel-basert risikoscore", f"{r['rule_score']} / 20", bold_value=True
        )
    if r.get("equity_ratio") is not None:
        _kv_row(pdf, "Egenkapitalandel", _fmt_pct(r["equity_ratio"]))
    _render_altman_row(pdf, r.get("altman_z"))
    if r.get("pep_hits"):
        _kv_row(pdf, "PEP/sanksjonstreff", str(r["pep_hits"]))
    _render_peer_row(pdf, r.get("peer"))
    _render_risk_factors(pdf, r.get("rule_factors") or [])


def _render_needs(pdf: Any, data: Dict[str, Any]) -> None:
    _section_title(pdf, "4. Forsikringsbehov")
    needs = data["needs"]
    if not needs:
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(
            0,
            6,
            _safe("Ingen behovsanalyse tilgjengelig."),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        return
    pdf.set_font("Helvetica", "", 10)
    for n in needs[:10]:
        label = n.get("type") or n.get("label") or "-"
        sum_ = n.get("anbefalt_sum") or n.get("recommended_sum") or ""
        priority = n.get("prioritet") or n.get("priority") or ""
        tail = f"  [{priority}]" if priority else ""
        pdf.cell(
            0,
            6,
            _safe(f"- {label}: {sum_}{tail}"),
            new_x="LMARGIN",
            new_y="NEXT",
        )


def _render_notes(pdf: Any, data: Dict[str, Any]) -> None:
    _section_title(pdf, "5. Meglers kommentarer")
    notes = data["notes"]
    if not notes:
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(
            0,
            6,
            _safe("Ingen notater lagret for dette selskapet."),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        return
    pdf.set_font("Helvetica", "", 10)
    for n in notes[:5]:
        pdf.set_font("Helvetica", "B", 10)
        pdf.multi_cell(
            0, 5, _safe(f"Sp: {n.get('question', '')}"), new_x="LMARGIN", new_y="NEXT"
        )
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(
            0, 5, _safe(n.get("answer") or ""), new_x="LMARGIN", new_y="NEXT"
        )
        pdf.ln(1)


def _render_news(pdf: Any, data: Dict[str, Any]) -> None:
    _section_title(pdf, "6. Materielle hendelser (siste 30 dager)")
    news = data["material_news"]
    if not news:
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(
            0,
            6,
            _safe("Ingen materielle hendelser registrert siste 30 dager."),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        return
    pdf.set_font("Helvetica", "", 10)
    for n in news:
        pdf.set_font("Helvetica", "B", 10)
        pdf.multi_cell(
            0, 5, _safe(f"- {n.get('headline', '')}"), new_x="LMARGIN", new_y="NEXT"
        )
        pdf.set_font("Helvetica", "", 9)
        meta_bits = [n.get("source"), n.get("event_type"), n.get("published_at")]
        meta = "  |  ".join(b for b in meta_bits if b)
        if meta:
            pdf.cell(0, 5, _safe(meta), new_x="LMARGIN", new_y="NEXT")
        if n.get("summary"):
            pdf.multi_cell(0, 5, _safe(n["summary"]), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)


def _render_policies(pdf: Any, data: Dict[str, Any]) -> None:
    _section_title(pdf, "7. Eksisterende aktive poliser")
    policies = data["policies"]
    if not policies:
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(
            0,
            6,
            _safe("Ingen aktive poliser registrert."),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        return
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(50, 6, "Produkt", border=1)
    pdf.cell(55, 6, "Forsikringsselskap", border=1)
    pdf.cell(35, 6, "Arspremie", border=1)
    pdf.cell(30, 6, "Utlop", border=1, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    for p in policies:
        pdf.cell(50, 6, _safe(p.get("product") or "-"), border=1)
        pdf.cell(55, 6, _safe(p.get("insurer") or "-"), border=1)
        pdf.cell(35, 6, _fmt_nok(p.get("annual_premium_nok")), border=1)
        pdf.cell(
            30,
            6,
            _safe(p.get("end_date") or "-"),
            border=1,
            new_x="LMARGIN",
            new_y="NEXT",
        )


def generate_anbudspakke_pdf(data: Dict[str, Any]) -> bytes:
    """Render the structured anbudspakke payload to PDF bytes."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(15, 15, 15)

    pdf.add_page()
    _render_cover(pdf, data)

    pdf.add_page()
    _render_selskap(pdf, data)
    _render_financials(pdf, data)
    _render_risk(pdf, data)

    pdf.add_page()
    _render_needs(pdf, data)
    _render_notes(pdf, data)
    _render_news(pdf, data)
    _render_policies(pdf, data)

    return bytes(pdf.output())
