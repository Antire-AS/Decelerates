"""Integration test — InsuranceDocument upload/download/delete against
real Postgres + the LargeBinary pdf_content column.

The LargeBinary column (bytea in Postgres) handles multi-MB PDFs via
the pg-native binary protocol; this test proves a write-then-read
roundtrip preserves the bytes exactly. A subtle bug here would silently
corrupt every stored broker document.

Runs only when TEST_DATABASE_URL is set.
"""

import importlib
import io
import os
import sys

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="set TEST_DATABASE_URL=postgresql://... to run integration tests",
)

_ORGNR = "666222333"


@pytest.fixture(autouse=True)
def _restore_real_pdf_libs():
    """The global conftest stubs both `pdfplumber` and `fpdf` with
    MagicMock so unit tests run without the real packages. This
    integration test exercises DocumentService._validate_pdf (calls
    pdfplumber.open) AND builds a real PDF via fpdf2 — both need the real
    libraries (installed via pyproject.toml). Force-import both and
    patch the services namespace for the test's duration."""
    import api.services.documents as docs_mod

    sys.modules.pop("pdfplumber", None)
    sys.modules.pop("fpdf", None)
    real_pp = importlib.import_module("pdfplumber")
    real_fpdf = importlib.import_module("fpdf")
    sys.modules["pdfplumber"] = real_pp
    sys.modules["fpdf"] = real_fpdf
    original_pp = docs_mod.pdfplumber
    docs_mod.pdfplumber = real_pp
    try:
        yield
    finally:
        docs_mod.pdfplumber = original_pp


def _real_pdf_bytes() -> bytes:
    """Generate a real multi-page PDF via fpdf2. Called inside tests
    (NOT at module import) so the autouse fixture has had a chance to
    swap the conftest MagicMock back out for the real fpdf package."""
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=12)
    pdf.cell(
        0, 10, "Lifecycle test vilkar - side 1", new_x=XPos.LMARGIN, new_y=YPos.NEXT
    )
    pdf.cell(
        0,
        10,
        "Integration roundtrip for LargeBinary column.",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.add_page()
    pdf.cell(
        0,
        10,
        "Side 2 - bekrefter flersides PDF overlever bytea.",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    return bytes(pdf.output())  # fpdf2 2.8.x returns bytearray


@pytest.fixture
def auth_client(test_db):
    from api.auth import get_current_user
    from api.dependencies import get_db
    from api.db import InsuranceDocument
    from api.main import app
    from tests.integration.conftest import make_user

    test_db.query(InsuranceDocument).filter(InsuranceDocument.orgnr == _ORGNR).delete()
    test_db.commit()

    app.dependency_overrides[get_db] = lambda: test_db
    app.dependency_overrides[get_current_user] = lambda: make_user(
        "doc@lifecycle.test", "oid-doc-lc", 88820
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_insurance_document_upload_download_delete(auth_client):
    """POST the PDF, list it, stream-download it back, verify the bytes
    survived a LargeBinary roundtrip unchanged."""
    pdf_bytes = _real_pdf_bytes()
    assert pdf_bytes[:5] == b"%PDF-", f"bad header {pdf_bytes[:5]!r}"

    upload = auth_client.post(
        "/insurance-documents",
        data={
            "title": "Lifecycle test vilkår",
            "category": "vilkar",
            "insurer": "Testforsikring",
            "orgnr": _ORGNR,
            "year": "2026",
            "period": "aktiv",
        },
        files={
            "file": (
                "lifecycle-test.pdf",
                io.BytesIO(pdf_bytes),
                "application/pdf",
            )
        },
    )
    assert upload.status_code < 400, upload.text
    doc = upload.json()
    doc_id = doc["id"]
    assert doc["title"] == "Lifecycle test vilkår"

    # The POST response intentionally omits orgnr — verify it landed via
    # the list route, which filters by orgnr.
    listing = auth_client.get("/insurance-documents", params={"orgnr": _ORGNR})
    assert listing.status_code == 200
    ids = [d["id"] for d in listing.json()]
    assert doc_id in ids

    # Stream-download the PDF. bytea roundtrip must match byte-for-byte.
    pdf_resp = auth_client.get(f"/insurance-documents/{doc_id}/pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers.get("content-type", "").startswith("application/pdf")
    assert pdf_resp.content == pdf_bytes, (
        f"LargeBinary roundtrip mismatch: "
        f"sent {len(pdf_bytes)} bytes, got {len(pdf_resp.content)} back"
    )

    # DELETE removes the row.
    delete = auth_client.delete(f"/insurance-documents/{doc_id}")
    assert delete.status_code < 400

    listing2 = auth_client.get("/insurance-documents", params={"orgnr": _ORGNR})
    assert listing2.status_code == 200
    ids2 = [d["id"] for d in listing2.json()]
    assert doc_id not in ids2
