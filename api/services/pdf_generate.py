"""pdf_generate — backward-compat shim. Logic split into focused sub-modules.

Callers that import from this module continue to work unchanged:
    from api.services.pdf_generate import generate_risk_report_pdf, ...
"""
from api.services.pdf_base import (  # noqa: F401
    _safe, _section_title,
    _DARK_BLUE, _LIGHT_BLUE,
)
from api.services.pdf_sla import generate_sla_pdf as _generate_sla_pdf  # noqa: F401
from api.services.pdf_risk import generate_risk_report_pdf  # noqa: F401
from api.services.pdf_offer import (  # noqa: F401
    _extract_offer_summary,
    generate_forsikringstilbud_pdf,
)
from api.services.pdf_portfolio import generate_portfolio_pdf  # noqa: F401


# ── Service class ─────────────────────────────────────────────────────────────

class PdfGenerateService:
    """Thin class wrapper around module-level PDF generation helpers."""

    def generate_sla(self, agreement) -> bytes:
        return _generate_sla_pdf(agreement)

    def generate_risk_report(self, **kwargs) -> bytes:
        return generate_risk_report_pdf(**kwargs)

    def generate_forsikringstilbud(self, **kwargs) -> bytes:
        return generate_forsikringstilbud_pdf(**kwargs)

    def generate_portfolio(self, **kwargs) -> bytes:
        return generate_portfolio_pdf(**kwargs)
