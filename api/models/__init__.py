"""Models package — domain-organized SQLAlchemy models.

All models are re-exported here so `from api.models import Company` works.
The api/db.py shim re-exports from this package for backward compatibility.
"""
# Base infrastructure
from api.models._base import Base, engine, SessionLocal, EMBEDDING_DIM, init_db  # noqa: F401

# Domain models — import order matters for FK resolution
from api.models.broker import BrokerFirm, UserRole, User, BrokerSettings, BrokerNote  # noqa: F401
from api.models.company import Company, CompanyHistory, CompanyPdfSource, CompanyNote, CompanyChunk  # noqa: F401
from api.models.crm import (  # noqa: F401
    ContactPerson, PolicyStatus, RenewalStage, Policy,
    ClaimStatus, Claim, ActivityType, Activity, ClientToken,
)
from api.models.portfolio import Portfolio, PortfolioCompany  # noqa: F401
from api.models.pipeline import PipelineStageKind, PipelineStage, Deal  # noqa: F401
from api.models.insurance import (  # noqa: F401
    OfferStatus, InsuranceOffer, InsuranceDocument,
    SubmissionStatus, Insurer, Submission, Recommendation,
)
from api.models.tender import (  # noqa: F401
    TenderStatus, Tender, TenderRecipientStatus, TenderRecipient, TenderOffer,
)
from api.models.coverage import CoverageAnalysis  # noqa: F401
from api.models.compliance import (  # noqa: F401
    SlaAgreement, IddBehovsanalyse, LawfulBasis, ConsentRecord, AuditLog,
)
from api.models.system import JobQueue, NotificationKind, Notification, SavedSearch  # noqa: F401
