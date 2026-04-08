"""
Stub out optional heavy dependencies so service modules can be imported
in tests without requiring google-genai, voyageai, anthropic, or pdfplumber.

The google.genai stub is set up so that both:
  from google import genai as google_genai   (used in services/llm.py)
  patch("google.genai.Client")               (used in test_llm.py)
refer to the SAME mock object, making patches work correctly.
"""
import os
import sys
from unittest.mock import MagicMock

import pytest

# Default the auth bypass for local test runs. CI sets these explicitly in
# .github/workflows/ci.yml. Production cannot honor AUTH_DISABLED — see
# api/auth.py::_is_auth_disabled and tests/unit/test_auth_safety.py.
os.environ.setdefault("AUTH_DISABLED", "1")
os.environ.setdefault("ENVIRONMENT", "development")

# google / google.genai — services/llm.py and services/pdf_extract.py
_google_genai = MagicMock()
_google_genai_types = MagicMock()

if "google" not in sys.modules:
    _google = MagicMock()
    sys.modules["google"] = _google
else:
    _google = sys.modules["google"]

# Ensure 'from google import genai' and sys.modules["google.genai"]
# resolve to the same object so patch("google.genai.Client") works.
_google.genai = _google_genai
sys.modules["google.genai"] = _google_genai
sys.modules["google.genai.types"] = _google_genai_types

# voyageai — services/llm.py
sys.modules.setdefault("voyageai", MagicMock())

# anthropic — services/llm.py
sys.modules.setdefault("anthropic", MagicMock())

# pdfplumber — services/pdf_extract.py
sys.modules.setdefault("pdfplumber", MagicMock())

# openai — services/llm.py (AzureOpenAI)
_openai_stub = MagicMock()
_openai_stub.AzureOpenAI = MagicMock
sys.modules.setdefault("openai", _openai_stub)

# azure.identity — blob_storage.py, document_intelligence.py
_azure_identity_stub = MagicMock()
_azure_identity_stub.DefaultAzureCredential = MagicMock
sys.modules.setdefault("azure", MagicMock())
sys.modules.setdefault("azure.identity", _azure_identity_stub)

# azure.storage.blob — blob_storage.py
_azure_blob_stub = MagicMock()
_azure_blob_stub.BlobServiceClient = MagicMock
sys.modules.setdefault("azure.storage", MagicMock())
sys.modules.setdefault("azure.storage.blob", _azure_blob_stub)

# azure.ai.documentintelligence — document_intelligence.py
_azure_di_stub = MagicMock()
_azure_di_stub.DocumentIntelligenceClient = MagicMock
sys.modules.setdefault("azure.ai", MagicMock())
sys.modules.setdefault("azure.ai.documentintelligence", _azure_di_stub)

# azure.core.credentials — document_intelligence.py (AzureKeyCredential)
_azure_core_creds_stub = MagicMock()
_azure_core_creds_stub.AzureKeyCredential = MagicMock
sys.modules.setdefault("azure.core", MagicMock())
sys.modules.setdefault("azure.core.credentials", _azure_core_creds_stub)
sys.modules.setdefault("azure.core.exceptions", MagicMock())

# azure.search.documents — search_service.py
_azure_search_stub = MagicMock()
_azure_search_stub.SearchClient = MagicMock
sys.modules.setdefault("azure.search", MagicMock())
sys.modules.setdefault("azure.search.documents", _azure_search_stub)
sys.modules.setdefault("azure.search.documents.models", MagicMock())

_azure_search_indexes_stub = MagicMock()
_azure_search_indexes_stub.SearchIndexClient = MagicMock
sys.modules.setdefault("azure.search.documents.indexes", _azure_search_indexes_stub)

_azure_search_indexes_models_stub = MagicMock()
for _cls in ("SearchIndex", "SimpleField", "SearchableField", "SearchField",
             "VectorSearch", "HnswAlgorithmConfiguration", "VectorSearchProfile"):
    setattr(_azure_search_indexes_models_stub, _cls, MagicMock)
sys.modules.setdefault("azure.search.documents.indexes.models", _azure_search_indexes_models_stub)

# azure.communication.email — notification_service.py
_azure_comm_email_stub = MagicMock()
_azure_comm_email_stub.EmailClient = MagicMock
sys.modules.setdefault("azure.communication", MagicMock())
sys.modules.setdefault("azure.communication.email", _azure_comm_email_stub)

# fpdf2 / fpdf — services/pdf_generate.py
sys.modules.setdefault("fpdf", MagicMock())

# pgvector — use the real installed package (required for integration tests that
# create Vector columns in PostgreSQL). Fall back to stub only if not installed.
try:
    import pgvector  # noqa: F401
except ImportError:
    sys.modules.setdefault("pgvector", MagicMock())
    sys.modules.setdefault("pgvector.sqlalchemy", MagicMock())


# ── Integration test fixtures ──────────────────────────────────────────────────
# Require TEST_DATABASE_URL — never runs against the production DB.
# All tests in test_integration.py are skipped when this is not set,
# so these fixtures are never called in that case.

_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "")


@pytest.fixture(scope="session", autouse=True)
def _configure_di_container_for_tests():
    """Pre-configure the DI container with empty adapter configs so route
    handlers that call `resolve(NotificationPort)` etc. don't crash during
    tests. Integration tests use `TestClient(app)` WITHOUT the context
    manager (see the `client` fixture below) which means the app's
    `on_startup` event — where `configure(AppConfig(...))` normally runs —
    never fires. Pre-2026-04-07 this was silently tolerated because the
    failing tests were admin-bypassed; now that branch protection actually
    gates merges, we need the container wired up for tests to pass.

    The adapters are created with empty configs so `is_configured()` returns
    False on both — anything that actually tries to SEND via the adapters
    will skip gracefully. For tests that need real adapter behaviour, they
    should patch the adapter class explicitly.
    """
    # Skip for pure unit tests that don't even import api.main — saves ~0.5s
    # of startup time on the fast test suite. Integration tests import it
    # transitively via TestClient(app) and need the configured container.
    try:
        from api.container import configure, AppConfig
    except Exception:
        yield
        return
    configure(AppConfig())
    yield


@pytest.fixture(scope="session")
def test_engine():
    """Session-scoped engine: enables pgvector extension and creates all tables once."""
    from sqlalchemy import create_engine, text
    from api.db import Base

    url = _TEST_DB_URL.replace("postgresql://", "postgresql+psycopg://", 1)
    engine = create_engine(url)
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def test_db(test_engine):
    """Function-scoped session. Rolls back after each test to keep the DB clean."""
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=test_engine)
    db = Session()
    yield db
    db.rollback()
    db.close()


@pytest.fixture
def client(test_db):
    """TestClient with get_db overridden to use the test session.
    Uses TestClient without a context manager to skip the on_startup event
    (which would otherwise connect to the production DB fallback URL)."""
    from fastapi.testclient import TestClient
    from api.main import app
    from api.dependencies import get_db

    app.dependency_overrides[get_db] = lambda: test_db
    yield TestClient(app)
    app.dependency_overrides.clear()
