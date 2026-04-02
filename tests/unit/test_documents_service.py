"""Unit tests for api/services/documents.py — DocumentService + DocumentAnalysisService.

Pure static tests — uses MagicMock DB; no real infrastructure required.
"""
from unittest.mock import MagicMock, patch

import pytest

from api.db import InsuranceDocument, InsuranceOffer
from api.domain.exceptions import LlmUnavailableError
from api.services.documents import (
    DocumentAnalysisService,
    DocumentService,
    _cosine_similarity,
    answer_document_question,
    compare_two_documents,
    find_similar_documents,
    get_document_keypoints,
    remove_insurance_document,
    remove_insurance_offer,
    save_insurance_offers,
    store_insurance_document,
    update_offer_status,
)


def _mock_db():
    return MagicMock()


def _mock_doc(**kwargs):
    doc = MagicMock(spec=InsuranceDocument)
    doc.id = kwargs.get("id", 1)
    doc.title = kwargs.get("title", "Test Forsikring")
    doc.insurer = kwargs.get("insurer", "Test AS")
    doc.year = kwargs.get("year", 2024)
    doc.pdf_content = kwargs.get("pdf_content", b"%PDF-1.4 test")
    doc.extracted_text = kwargs.get("extracted_text", "Test document text content here")
    doc.orgnr = kwargs.get("orgnr", "123456789")
    return doc


def _valid_pdf_bytes():
    return b"%PDF-1.4 fake pdf content"


# ── _cosine_similarity ─────────────────────────────────────────────────────────

def test_cosine_similarity_identical_vectors():
    v = [1.0, 0.0, 0.0]
    assert _cosine_similarity(v, v) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors():
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert _cosine_similarity(a, b) == pytest.approx(0.0)


def test_cosine_similarity_zero_vector_returns_zero():
    assert _cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_cosine_similarity_opposite_vectors():
    a = [1.0, 0.0]
    b = [-1.0, 0.0]
    assert _cosine_similarity(a, b) == pytest.approx(-1.0)


# ── DocumentService.store_document ────────────────────────────────────────────

@patch("api.services.documents._validate_pdf", return_value=True)
@patch("api.services.documents._pdf_bytes_to_text", return_value="extracted text")
def test_store_document_adds_to_db(mock_extract, mock_validate):
    db = _mock_db()
    DocumentService(db).store_document(
        _valid_pdf_bytes(), "test.pdf", "Test", "anbefaling", "Insurer AS", 2024, "aktiv", "123456789"
    )
    db.add.assert_called_once()
    db.commit.assert_called_once()
    db.refresh.assert_called_once()


@patch("api.services.documents._validate_pdf", return_value=True)
@patch("api.services.documents._pdf_bytes_to_text", return_value="some text")
def test_store_document_sets_all_fields(mock_extract, mock_validate):
    db = _mock_db()
    DocumentService(db).store_document(
        _valid_pdf_bytes(), "doc.pdf", "My Title", "kategori", "Forsikrer AS", 2023, "2023", "987654321", tags="tag1"
    )
    added = db.add.call_args[0][0]
    assert added.title == "My Title"
    assert added.category == "kategori"
    assert added.insurer == "Forsikrer AS"
    assert added.year == 2023
    assert added.orgnr == "987654321"
    assert added.tags == "tag1"
    assert added.filename == "doc.pdf"


@patch("api.services.documents._validate_pdf", return_value=False)
def test_store_document_raises_on_invalid_pdf(mock_validate):
    db = _mock_db()
    with pytest.raises(ValueError, match="Ugyldig"):
        DocumentService(db).store_document(b"not a pdf", "x.pdf", "T", "k", "I", None, "", None)


@patch("api.services.documents._validate_pdf", return_value=True)
@patch("api.services.documents._pdf_bytes_to_text", return_value="")
def test_store_document_null_extracted_text_when_empty(mock_extract, mock_validate):
    db = _mock_db()
    DocumentService(db).store_document(
        _valid_pdf_bytes(), "f.pdf", "T", "k", "I", None, "", None
    )
    added = db.add.call_args[0][0]
    assert added.extracted_text is None


@patch("api.services.documents._validate_pdf", return_value=True)
@patch("api.services.documents._pdf_bytes_to_text", return_value="text")
def test_store_document_null_orgnr_when_empty_string(mock_extract, mock_validate):
    db = _mock_db()
    DocumentService(db).store_document(
        _valid_pdf_bytes(), "f.pdf", "T", "k", "I", None, "", ""
    )
    added = db.add.call_args[0][0]
    assert added.orgnr is None


# ── DocumentService.remove_document ───────────────────────────────────────────

def test_remove_document_returns_false_when_not_found():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    result = DocumentService(db).remove_document(99)
    assert result is False
    db.delete.assert_not_called()
    db.commit.assert_not_called()


def test_remove_document_returns_true_and_deletes():
    doc = _mock_doc()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = doc
    result = DocumentService(db).remove_document(1)
    assert result is True
    db.delete.assert_called_once_with(doc)
    db.commit.assert_called_once()


# ── DocumentService.save_offers ───────────────────────────────────────────────

def test_save_offers_creates_rows_for_each_item():
    db = _mock_db()
    offer_data = [
        {"filename": "offer_one.pdf", "raw_bytes": b"bytes1", "extracted_text": "text1"},
        {"filename": "offer_two.pdf", "raw_bytes": b"bytes2", "extracted_text": "text2"},
    ]
    DocumentService(db).save_offers("123456789", offer_data)
    assert db.add.call_count == 2
    db.commit.assert_called_once()


def test_save_offers_guesses_insurer_from_filename():
    db = _mock_db()
    offer_data = [{"filename": "storebrand_ansvar.pdf", "raw_bytes": b"b", "extracted_text": "t"}]
    DocumentService(db).save_offers("123", offer_data)
    added = db.add.call_args[0][0]
    assert added.insurer_name == "Storebrand Ansvar"


def test_save_offers_returns_list_with_correct_structure():
    db = _mock_db()
    offer_data = [{"filename": "storebrand.pdf", "raw_bytes": b"b", "extracted_text": "t"}]
    result = DocumentService(db).save_offers("123", offer_data)
    assert len(result) == 1
    assert result[0]["filename"] == "storebrand.pdf"
    assert result[0]["insurer_name"] == "Storebrand"
    assert "id" in result[0]


def test_save_offers_empty_list_returns_empty():
    db = _mock_db()
    result = DocumentService(db).save_offers("123", [])
    assert result == []
    db.commit.assert_called_once()


# ── DocumentService.remove_offer ──────────────────────────────────────────────

def test_remove_offer_returns_false_when_not_found():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    result = DocumentService(db).remove_offer(99, "123")
    assert result is False
    db.delete.assert_not_called()


def test_remove_offer_deletes_and_returns_true():
    offer = MagicMock(spec=InsuranceOffer)
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = offer
    result = DocumentService(db).remove_offer(1, "123")
    assert result is True
    db.delete.assert_called_once_with(offer)
    db.commit.assert_called_once()


# ── DocumentService.find_similar ──────────────────────────────────────────────

@patch("api.services.documents._embed", return_value=None)
def test_find_similar_returns_empty_when_embed_fails(mock_embed):
    doc = _mock_doc(extracted_text="some text here")
    db = _mock_db()
    result = DocumentService(db).find_similar(doc)
    assert result == []


def test_find_similar_returns_empty_when_no_text():
    doc = _mock_doc(extracted_text="")
    db = _mock_db()
    result = DocumentService(db).find_similar(doc)
    assert result == []


@patch("api.services.documents._embed")
def test_find_similar_returns_sorted_by_similarity(mock_embed):
    mock_embed.side_effect = [[1.0, 0.0], [0.9, 0.1], [0.0, 1.0]]
    doc = _mock_doc(id=1, extracted_text="main text")
    other1 = MagicMock(spec=InsuranceDocument)
    other1.id = 2
    other1.title = "Similar Doc"
    other1.extracted_text = "similar text"
    other2 = MagicMock(spec=InsuranceDocument)
    other2.id = 3
    other2.title = "Different Doc"
    other2.extracted_text = "different text"
    db = _mock_db()
    db.query.return_value.filter.return_value.all.return_value = [other1, other2]
    result = DocumentService(db).find_similar(doc)
    assert result[0]["id"] == 2
    assert result[0]["similarity"] > result[1]["similarity"]


# ── DocumentAnalysisService.get_document_keypoints ────────────────────────────

@patch("api.services.documents._analyze_document_with_gemini", return_value=None)
@patch("api.services.documents._llm_answer_raw", return_value=None)
def test_get_keypoints_returns_fallback_dict_when_all_fail(mock_llm, mock_gemini):
    with patch("api.services.document_intelligence.DocumentIntelligenceService") as mock_di_cls:
        mock_di = MagicMock()
        mock_di.is_configured.return_value = False
        mock_di_cls.return_value = mock_di
        doc = _mock_doc(extracted_text="short")
        result = DocumentAnalysisService().get_document_keypoints(doc)
    assert "sammendrag" in result
    assert "viktige_vilkaar" in result
    assert "unntak" in result


@patch("api.services.documents._parse_json_from_llm_response", return_value={"hva_dekkes": ["A"]})
@patch("api.services.documents._llm_answer_raw", return_value='{"hva_dekkes": ["A"]}')
def test_get_keypoints_uses_extracted_text_path(mock_llm, mock_parse):
    with patch("api.services.document_intelligence.DocumentIntelligenceService") as mock_di_cls:
        mock_di = MagicMock()
        mock_di.is_configured.return_value = False
        mock_di_cls.return_value = mock_di
        doc = _mock_doc(extracted_text="A" * 600)
        result = DocumentAnalysisService().get_document_keypoints(doc)
    assert result == {"hva_dekkes": ["A"]}
    mock_llm.assert_called_once()


@patch("api.services.documents._parse_json_from_llm_response", return_value={"hva_dekkes": ["B"]})
@patch("api.services.documents._analyze_document_with_gemini", return_value='{"hva_dekkes": ["B"]}')
@patch("api.services.documents._llm_answer_raw", return_value=None)
def test_get_keypoints_falls_back_to_gemini(mock_llm, mock_gemini, mock_parse):
    with patch("api.services.document_intelligence.DocumentIntelligenceService") as mock_di_cls:
        mock_di = MagicMock()
        mock_di.is_configured.return_value = False
        mock_di_cls.return_value = mock_di
        doc = _mock_doc(extracted_text="short")
        result = DocumentAnalysisService().get_document_keypoints(doc)
    mock_gemini.assert_called_once()
    assert result == {"hva_dekkes": ["B"]}


@patch("api.services.documents._parse_json_from_llm_response", return_value={"di": "result"})
@patch("api.services.documents._llm_answer_raw", return_value='{"di": "result"}')
def test_get_keypoints_uses_di_when_configured(mock_llm, mock_parse):
    with patch("api.services.document_intelligence.DocumentIntelligenceService") as mock_di_cls:
        mock_di = MagicMock()
        mock_di.is_configured.return_value = True
        mock_di.analyze_pdf.return_value = "A" * 300
        mock_di_cls.return_value = mock_di
        doc = _mock_doc()
        result = DocumentAnalysisService().get_document_keypoints(doc)
    assert result == {"di": "result"}


# ── DocumentAnalysisService.answer_document_question ──────────────────────────

@patch("api.services.documents._analyze_document_with_gemini", return_value="Svaret er 42")
def test_answer_question_returns_gemini_answer(mock_gemini):
    doc = _mock_doc()
    result = DocumentAnalysisService().answer_document_question(doc, "Hva er svaret?")
    assert result == "Svaret er 42"


@patch("api.services.documents._llm_answer_raw", return_value="Text answer")
@patch("api.services.documents._analyze_document_with_gemini", return_value=None)
def test_answer_question_falls_back_to_text_llm(mock_gemini, mock_llm):
    doc = _mock_doc(extracted_text="policy text content here")
    result = DocumentAnalysisService().answer_document_question(doc, "Question?")
    assert result == "Text answer"
    mock_llm.assert_called_once()


@patch("api.services.documents._llm_answer_raw", return_value=None)
@patch("api.services.documents._analyze_document_with_gemini", return_value=None)
def test_answer_question_raises_llm_unavailable(mock_gemini, mock_llm):
    doc = _mock_doc(extracted_text="some text")
    with pytest.raises(LlmUnavailableError):
        DocumentAnalysisService().answer_document_question(doc, "Question?")


@patch("api.services.documents._analyze_document_with_gemini", return_value=None)
def test_answer_question_raises_when_no_text_and_gemini_fails(mock_gemini):
    doc = _mock_doc(extracted_text=None)
    with pytest.raises(LlmUnavailableError):
        DocumentAnalysisService().answer_document_question(doc, "Question?")


# ── DocumentAnalysisService.compare_two_documents ─────────────────────────────

@patch("api.services.documents._parse_json_from_llm_response", return_value={"comparison": []})
@patch("api.services.documents._llm_answer_raw", return_value='{"comparison": []}')
def test_compare_documents_uses_text_when_both_have_extracted_text(mock_llm, mock_parse):
    a = _mock_doc(id=1, title="Doc A", extracted_text="text a " * 50)
    b = _mock_doc(id=2, title="Doc B", extracted_text="text b " * 50)
    result = DocumentAnalysisService().compare_two_documents(a, b)
    assert result == {"comparison": []}
    mock_llm.assert_called_once()


@patch("api.services.documents._parse_json_from_llm_response", return_value={"comparison": []})
@patch("api.services.documents._compare_documents_with_gemini", return_value='{"comparison": []}')
@patch("api.services.documents._llm_answer_raw", return_value=None)
def test_compare_documents_falls_back_to_gemini_when_no_text(mock_llm, mock_gemini, mock_parse):
    a = _mock_doc(id=1, extracted_text=None)
    b = _mock_doc(id=2, extracted_text=None)
    DocumentAnalysisService().compare_two_documents(a, b)
    mock_gemini.assert_called_once()


@patch("api.services.documents._compare_documents_with_gemini", return_value=None)
@patch("api.services.documents._llm_answer_raw", return_value=None)
def test_compare_documents_raises_when_all_fail(mock_llm, mock_gemini):
    a = _mock_doc(id=1, extracted_text=None)
    b = _mock_doc(id=2, extracted_text=None)
    with pytest.raises(LlmUnavailableError):
        DocumentAnalysisService().compare_two_documents(a, b)


@patch("api.services.documents._parse_json_from_llm_response", return_value=None)
@patch("api.services.documents._llm_answer_raw", return_value="raw text no json")
def test_compare_documents_returns_raw_text_when_json_parse_fails(mock_llm, mock_parse):
    a = _mock_doc(id=1, title="Doc A", extracted_text="text a " * 50)
    b = _mock_doc(id=2, title="Doc B", extracted_text="text b " * 50)
    result = DocumentAnalysisService().compare_two_documents(a, b)
    assert result == {"raw_text": "raw text no json"}


@patch("api.services.documents._parse_json_from_llm_response", return_value=None)
@patch("api.services.documents._compare_documents_with_gemini", return_value="gemini raw")
@patch("api.services.documents._llm_answer_raw", return_value=None)
def test_compare_documents_gemini_raw_text_fallback(mock_llm, mock_gemini, mock_parse):
    a = _mock_doc(id=1, extracted_text=None)
    b = _mock_doc(id=2, extracted_text=None)
    result = DocumentAnalysisService().compare_two_documents(a, b)
    assert result == {"raw_text": "gemini raw"}


# ── Module-level backward-compat wrappers ─────────────────────────────────────

@patch("api.services.documents._validate_pdf", return_value=True)
@patch("api.services.documents._pdf_bytes_to_text", return_value="text")
def test_store_insurance_document_wrapper_delegates(mock_extract, mock_validate):
    db = _mock_db()
    store_insurance_document(
        _valid_pdf_bytes(), "f.pdf", "T", "k", "I", None, "", None, db
    )
    db.add.assert_called_once()


def test_remove_insurance_document_wrapper_returns_false_when_missing():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    assert remove_insurance_document(99, db) is False


def test_save_insurance_offers_wrapper_delegates():
    db = _mock_db()
    result = save_insurance_offers("123", [], db)
    assert result == []


def test_remove_insurance_offer_wrapper_returns_false_when_missing():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    assert remove_insurance_offer(1, "123", db) is False


@patch("api.services.documents._embed", return_value=None)
def test_find_similar_documents_wrapper_delegates(mock_embed):
    doc = _mock_doc(extracted_text="text content")
    db = _mock_db()
    result = find_similar_documents(doc, db)
    assert result == []


# ── update_offer_status ───────────────────────────────────────────────────────

def test_update_offer_status_returns_false_when_not_found():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    result = update_offer_status(99, "123", "won", db)
    assert result is False


def test_update_offer_status_returns_false_on_invalid_status():
    offer = MagicMock(spec=InsuranceOffer)
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = offer
    result = update_offer_status(1, "123", "invalid_status_xyz", db)
    assert result is False
