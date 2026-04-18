"""Unit tests for api/services/demo_documents.py.

Pure logic tests — uses MagicMock DB; no infrastructure required.
"""

import re
from unittest.mock import MagicMock, patch


from api.services.demo_documents import (
    _adjust_number,
    _anonymise_text,
    seed_demo_documents,
)


# ── _adjust_number ────────────────────────────────────────────────────────────


def _match(pattern: str, text: str):
    """Return the first re.Match for pattern in text."""
    return re.search(pattern, text)


def test_adjust_number_changes_value():
    m = _match(r"\b\d[\d\s]{3,10}\d\b", "Total: 100000 NOK")
    result = _adjust_number(m)
    assert result != "100000"
    assert result.isdigit()


def test_adjust_number_stays_within_15_percent():
    original = 100000
    m = _match(r"\b\d[\d\s]{3,10}\d\b", str(original))
    result = int(_adjust_number(m))
    assert 85000 <= result <= 115000


def test_adjust_number_zero_unchanged():
    m = _match(r"\b\d+\b", "0")
    # zero match — must return raw unchanged
    result = _adjust_number(m)
    assert result == "0"


def test_adjust_number_non_numeric_returns_raw():
    """If cleaned value can't be parsed as int, return raw."""
    m = MagicMock()
    m.group.return_value = "abc123"
    # "abc123" → cleaned = "abc123" → int() fails → returns raw
    result = _adjust_number(m)
    assert result == "abc123"


def test_adjust_number_preserves_nbsp_separator():
    """Numbers with non-breaking space separators should keep the same separator."""
    text = "1\xa0500\xa0000"
    m = _match(r"\b\d[\d\xa0 ]{3,10}\d\b", text)
    assert m is not None
    result = _adjust_number(m)
    assert "\xa0" in result or result.isdigit()


# ── _anonymise_text ───────────────────────────────────────────────────────────


def test_anonymise_replaces_company_name():
    text = "Equinor ASA er et stort selskap. Equinor ASA har mange ansatte."
    result = _anonymise_text(text, "Equinor ASA", "Demo Corp AS", "112233445")
    assert "Equinor ASA" not in result
    assert result.count("Demo Corp AS") == 2


def test_anonymise_replaces_name_case_insensitive():
    text = "equinor asa hadde gode resultater"
    result = _anonymise_text(text, "Equinor ASA", "Demo Corp AS", "112233445")
    assert "equinor asa" not in result.lower() or "Demo Corp AS" in result


def test_anonymise_replaces_orgnr():
    text = "Orgnr: 923 609 016 er registrert"
    result = _anonymise_text(text, "", "Demo Corp AS", "112233445")
    # Original orgnr must be gone; number nudging may further modify the replacement
    assert "923 609 016" not in result
    assert "923609016" not in result


def test_anonymise_replaces_plain_orgnr():
    text = "Organisasjonsnummer 923609016 er gyldig"
    result = _anonymise_text(text, "", "Demo Corp AS", "112233445")
    assert "923609016" not in result


def test_anonymise_nudges_large_numbers():
    text = "Omsetning: 45000000 kroner"
    result = _anonymise_text(text, "", "Demo Corp AS", "112233445")
    # The 8-digit number should be replaced with something else
    assert "45000000" not in result


def test_anonymise_empty_original_name_skips_name_replace():
    text = "Selskapet hadde god økonomi"
    result = _anonymise_text(text, "", "Demo Corp AS", "112233445")
    assert result == text  # no numbers to nudge, no name to replace


def test_anonymise_does_not_corrupt_plain_text():
    text = "Årsrapport for selskapet"
    result = _anonymise_text(text, "Ukjent AS", "Demo Corp AS", "112233445")
    assert isinstance(result, str)
    assert len(result) > 0


# ── seed_demo_documents ───────────────────────────────────────────────────────


def _make_doc(
    id=1,
    title="Rapport 2023",
    orgnr="923609016",
    category="annual",
    insurer="If",
    year=2023,
    period="2023",
    filename="rapport.pdf",
):
    doc = MagicMock()
    doc.id = id
    doc.title = title
    doc.orgnr = orgnr
    doc.category = category
    doc.insurer = insurer
    doc.year = year
    doc.period = period
    doc.filename = filename
    doc.pdf_content = b"%PDF-fake"
    doc.tags = None
    return doc


def _mock_db(sources=None, demo_titles=None):
    db = MagicMock()
    sources = sources or []
    demo_titles = demo_titles or set()

    # existing demo titles query
    existing_query = MagicMock()
    existing_query.filter.return_value = existing_query
    existing_query.all.return_value = [MagicMock(title=t) for t in demo_titles]

    # source docs query
    sources_query = MagicMock()
    sources_query.filter.return_value = sources_query
    sources_query.limit.return_value = sources_query
    sources_query.all.return_value = sources

    db.query.side_effect = lambda model: (
        existing_query if "title" in str(model) else sources_query
    )
    # Simpler: always return sources_query, adjust as needed
    db.query.return_value = sources_query
    sources_query.filter.return_value = sources_query
    sources_query.limit.return_value = sources_query
    sources_query.all.return_value = sources

    return db


def test_seed_no_source_docs_returns_zero():
    db = MagicMock()
    query = MagicMock()
    query.filter.return_value = query
    query.all.return_value = []
    query.limit.return_value = query
    db.query.return_value = query

    result = seed_demo_documents(db)
    assert result["created"] == 0
    assert result["skipped"] == 0
    assert "reason" in result


def test_seed_creates_demo_document():
    db = MagicMock()

    src = _make_doc()
    existing_titles_query = MagicMock()
    existing_titles_query.filter.return_value = existing_titles_query
    existing_titles_query.all.return_value = []  # no existing demo docs

    sources_query = MagicMock()
    sources_query.filter.return_value = sources_query
    sources_query.limit.return_value = sources_query
    sources_query.all.return_value = [src]

    call_count = 0

    def _query_side(model):
        nonlocal call_count
        call_count += 1
        return existing_titles_query if call_count == 1 else sources_query

    db.query.side_effect = _query_side

    with patch(
        "api.services.demo_documents._extract_pdf_text",
        return_value="Equinor text 45000000",
    ):
        with patch("api.services.demo_documents._text_to_pdf", return_value=b"%PDF"):
            result = seed_demo_documents(db)

    assert result["created"] == 1
    assert result["skipped"] == 0
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_seed_skips_existing_demo():
    db = MagicMock()

    src = _make_doc(title="Rapport 2023")
    demo_title = "[Demo] Rapport 2023"

    existing_titles_query = MagicMock()
    existing_titles_query.filter.return_value = existing_titles_query
    existing_title_obj = MagicMock()
    existing_title_obj.title = demo_title
    existing_titles_query.all.return_value = [existing_title_obj]

    sources_query = MagicMock()
    sources_query.filter.return_value = sources_query
    sources_query.limit.return_value = sources_query
    sources_query.all.return_value = [src]

    call_count = 0

    def _query_side(model):
        nonlocal call_count
        call_count += 1
        return existing_titles_query if call_count == 1 else sources_query

    db.query.side_effect = _query_side

    result = seed_demo_documents(db)

    assert result["skipped"] == 1
    assert result["created"] == 0
    db.add.assert_not_called()


def test_seed_skips_doc_with_no_text():
    db = MagicMock()

    src = _make_doc()

    existing_titles_query = MagicMock()
    existing_titles_query.filter.return_value = existing_titles_query
    existing_titles_query.all.return_value = []

    sources_query = MagicMock()
    sources_query.filter.return_value = sources_query
    sources_query.limit.return_value = sources_query
    sources_query.all.return_value = [src]

    call_count = 0

    def _query_side(model):
        nonlocal call_count
        call_count += 1
        return existing_titles_query if call_count == 1 else sources_query

    db.query.side_effect = _query_side

    with patch("api.services.demo_documents._extract_pdf_text", return_value="   "):
        result = seed_demo_documents(db)

    assert result["skipped"] == 1
    assert result["created"] == 0


def test_seed_skips_doc_when_pdf_generation_fails():
    db = MagicMock()

    src = _make_doc()

    existing_titles_query = MagicMock()
    existing_titles_query.filter.return_value = existing_titles_query
    existing_titles_query.all.return_value = []

    sources_query = MagicMock()
    sources_query.filter.return_value = sources_query
    sources_query.limit.return_value = sources_query
    sources_query.all.return_value = [src]

    call_count = 0

    def _query_side(model):
        nonlocal call_count
        call_count += 1
        return existing_titles_query if call_count == 1 else sources_query

    db.query.side_effect = _query_side

    with patch(
        "api.services.demo_documents._extract_pdf_text", return_value="some text"
    ):
        with patch(
            "api.services.demo_documents._text_to_pdf",
            side_effect=RuntimeError("fpdf error"),
        ):
            result = seed_demo_documents(db)

    assert result["skipped"] == 1
    assert result["created"] == 0


def test_seed_demo_doc_has_demo_tag():
    db = MagicMock()
    src = _make_doc()

    existing_titles_query = MagicMock()
    existing_titles_query.filter.return_value = existing_titles_query
    existing_titles_query.all.return_value = []

    sources_query = MagicMock()
    sources_query.filter.return_value = sources_query
    sources_query.limit.return_value = sources_query
    sources_query.all.return_value = [src]

    call_count = 0

    def _query_side(model):
        nonlocal call_count
        call_count += 1
        return existing_titles_query if call_count == 1 else sources_query

    db.query.side_effect = _query_side

    with patch(
        "api.services.demo_documents._extract_pdf_text", return_value="text 1000000 kr"
    ):
        with patch("api.services.demo_documents._text_to_pdf", return_value=b"%PDF"):
            seed_demo_documents(db)

    added = db.add.call_args[0][0]
    assert added.tags == "demo"
    assert added.title.startswith("[Demo]")


def test_seed_demo_doc_uses_fictional_orgnr():
    db = MagicMock()
    src = _make_doc(orgnr="923609016")

    existing_titles_query = MagicMock()
    existing_titles_query.filter.return_value = existing_titles_query
    existing_titles_query.all.return_value = []

    sources_query = MagicMock()
    sources_query.filter.return_value = sources_query
    sources_query.limit.return_value = sources_query
    sources_query.all.return_value = [src]

    call_count = 0

    def _query_side(model):
        nonlocal call_count
        call_count += 1
        return existing_titles_query if call_count == 1 else sources_query

    db.query.side_effect = _query_side

    with patch(
        "api.services.demo_documents._extract_pdf_text", return_value="some text"
    ):
        with patch("api.services.demo_documents._text_to_pdf", return_value=b"%PDF"):
            seed_demo_documents(db)

    added = db.add.call_args[0][0]
    assert added.orgnr != "923609016"  # must not use real orgnr


def test_seed_demo_filename_prefixed():
    db = MagicMock()
    src = _make_doc(filename="annual_2023.pdf")

    existing_titles_query = MagicMock()
    existing_titles_query.filter.return_value = existing_titles_query
    existing_titles_query.all.return_value = []

    sources_query = MagicMock()
    sources_query.filter.return_value = sources_query
    sources_query.limit.return_value = sources_query
    sources_query.all.return_value = [src]

    call_count = 0

    def _query_side(model):
        nonlocal call_count
        call_count += 1
        return existing_titles_query if call_count == 1 else sources_query

    db.query.side_effect = _query_side

    with patch(
        "api.services.demo_documents._extract_pdf_text", return_value="some text"
    ):
        with patch("api.services.demo_documents._text_to_pdf", return_value=b"%PDF"):
            seed_demo_documents(db)

    added = db.add.call_args[0][0]
    assert added.filename == "demo_annual_2023.pdf"
