"""Domain exceptions — raised by the service layer, caught by routers.

No FastAPI or HTTP concepts here; routers map these to HTTPException.
"""


class BrokerError(Exception):
    """Base class for all domain errors."""


class NotFoundError(BrokerError):
    """A requested resource does not exist."""


class LlmUnavailableError(BrokerError):
    """No LLM API key is configured."""


class QuotaError(BrokerError):
    """All LLM models have exhausted their free-tier quota."""


class PdfExtractionError(BrokerError):
    """A PDF could not be parsed into financial figures."""


class ExternalApiError(BrokerError):
    """An external API returned an unexpected error."""
