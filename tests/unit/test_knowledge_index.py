"""Unit tests for api/services/knowledge_index.py.

Pure static tests — BlobStorageService, _embed, and SearchService are all mocked.
"""

from unittest.mock import MagicMock, patch


from api.services.knowledge_index import (
    _fmt_time,
    _source_exists,
    _split_text,
    clear_knowledge,
    get_stats,
    index_all,
    index_insurance_documents,
    index_video_transcripts,
)


def _mock_db():
    return MagicMock()


# ── _fmt_time ─────────────────────────────────────────────────────────────────


def test_fmt_time_zero():
    assert _fmt_time(0) == "0:00"


def test_fmt_time_seconds_only():
    assert _fmt_time(45) == "0:45"


def test_fmt_time_minutes_and_seconds():
    assert _fmt_time(125) == "2:05"


def test_fmt_time_exactly_one_hour():
    assert _fmt_time(3600) == "1:00:00"


def test_fmt_time_hours_minutes_seconds():
    assert _fmt_time(3661) == "1:01:01"


def test_fmt_time_59_minutes_59_seconds():
    assert _fmt_time(3599) == "59:59"


# ── _split_text ───────────────────────────────────────────────────────────────


def test_split_text_short_returns_single_chunk():
    text = "Short text."
    result = _split_text(text)
    assert result == ["Short text."]


def test_split_text_exactly_chunk_size_returns_one():
    text = "x" * 1800
    assert len(_split_text(text)) == 1


def test_split_text_long_text_produces_multiple_chunks():
    text = "a" * 4000
    parts = _split_text(text)
    assert len(parts) > 1


def test_split_text_each_chunk_within_size_limit():
    text = "b" * 5000
    for chunk in _split_text(text):
        assert len(chunk) <= 1800


def test_split_text_overlap_means_total_chars_exceed_original():
    text = "c" * 3600
    parts = _split_text(text)
    # With overlap the sum of chunk lengths > original length
    assert sum(len(p) for p in parts) > len(text)


def test_split_text_empty_string():
    assert _split_text("") == [""]


# ── _source_exists ────────────────────────────────────────────────────────────


def test_source_exists_returns_true_when_chunk_found():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = MagicMock()
    assert _source_exists("doc::1::Title::Insurer::2024", db) is True


def test_source_exists_returns_false_when_not_found():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    assert _source_exists("doc::99::Missing::X::2020", db) is False


# ── clear_knowledge ───────────────────────────────────────────────────────────


def test_clear_knowledge_deletes_each_row_and_commits():
    rows = [MagicMock(), MagicMock(), MagicMock()]
    db = _mock_db()
    db.query.return_value.filter.return_value.all.return_value = rows
    count = clear_knowledge(db)
    assert count == 3
    assert db.delete.call_count == 3
    db.commit.assert_called_once()


def test_clear_knowledge_returns_zero_when_empty():
    db = _mock_db()
    db.query.return_value.filter.return_value.all.return_value = []
    assert clear_knowledge(db) == 0
    db.commit.assert_called_once()


# ── index_insurance_documents ─────────────────────────────────────────────────


def _mock_insurance_doc(**kwargs):
    doc = MagicMock()
    doc.id = kwargs.get("id", 1)
    doc.title = kwargs.get("title", "Test Policy")
    doc.insurer = kwargs.get("insurer", "Insurer AS")
    doc.year = kwargs.get("year", 2024)
    doc.category = kwargs.get("category", "vilkår")
    doc.extracted_text = kwargs.get("extracted_text", "Policy text content here.")
    return doc


def test_index_insurance_documents_indexes_new_doc():
    doc = _mock_insurance_doc()
    db = _mock_db()
    db.query.return_value.filter.return_value.all.return_value = [doc]

    with patch("api.services.knowledge_index._source_exists", return_value=False):
        with patch("api.services.knowledge_index._store_chunk") as mock_store:
            count = index_insurance_documents(db)

    assert count == 1
    mock_store.assert_called_once()
    db.commit.assert_called()


def test_index_insurance_documents_skips_already_indexed():
    doc = _mock_insurance_doc()
    db = _mock_db()
    db.query.return_value.filter.return_value.all.return_value = [doc]

    with patch("api.services.knowledge_index._source_exists", return_value=True):
        with patch("api.services.knowledge_index._store_chunk") as mock_store:
            count = index_insurance_documents(db)

    assert count == 0
    mock_store.assert_not_called()


def test_index_insurance_documents_returns_zero_when_no_docs():
    db = _mock_db()
    db.query.return_value.filter.return_value.all.return_value = []

    with patch("api.services.knowledge_index._store_chunk") as mock_store:
        count = index_insurance_documents(db)

    assert count == 0
    mock_store.assert_not_called()


def test_index_insurance_documents_source_key_contains_doc_id_and_title():
    doc = _mock_insurance_doc(id=42, title="My Policy", insurer="Gjensidige", year=2023)
    db = _mock_db()
    db.query.return_value.filter.return_value.all.return_value = [doc]

    with patch("api.services.knowledge_index._source_exists", return_value=False):
        with patch("api.services.knowledge_index._store_chunk") as mock_store:
            index_insurance_documents(db)

    source_arg = mock_store.call_args[0][1]
    assert "42" in source_arg
    assert "My Policy" in source_arg


def test_index_insurance_documents_indexes_multiple_docs():
    docs = [_mock_insurance_doc(id=i) for i in range(1, 4)]
    db = _mock_db()
    db.query.return_value.filter.return_value.all.return_value = docs

    with patch("api.services.knowledge_index._source_exists", return_value=False):
        with patch("api.services.knowledge_index._store_chunk") as mock_store:
            count = index_insurance_documents(db)

    assert count == 3
    assert mock_store.call_count == 3


# ── index_video_transcripts ───────────────────────────────────────────────────


def test_index_video_transcripts_returns_zero_when_blob_not_configured():
    db = _mock_db()
    mock_svc = MagicMock()
    mock_svc.is_configured.return_value = False
    with patch(
        "api.services.knowledge_index.BlobStorageService", return_value=mock_svc
    ):
        assert index_video_transcripts(db) == 0


def test_index_video_transcripts_indexes_valid_section():
    sections = [
        {
            "title": "Chapter 1",
            "start_seconds": 60,
            "description": "Overview of insurance",
            "entries": [{"text": "Key insight here"}],
        }
    ]
    mock_svc = MagicMock()
    mock_svc.is_configured.return_value = True
    mock_svc.list_blobs.return_value = ["ffsformidler_sections.json"]
    mock_svc.download_json.return_value = sections
    db = _mock_db()

    with patch(
        "api.services.knowledge_index.BlobStorageService", return_value=mock_svc
    ):
        with patch("api.services.knowledge_index._source_exists", return_value=False):
            with patch("api.services.knowledge_index._store_chunk") as mock_store:
                count = index_video_transcripts(db)

    assert count == 1
    mock_store.assert_called_once()


def test_index_video_transcripts_skips_untitled_sections():
    sections = [
        {"title": "", "start_seconds": 0, "entries": [{"text": "ignored text"}]}
    ]
    mock_svc = MagicMock()
    mock_svc.is_configured.return_value = True
    mock_svc.list_blobs.return_value = ["ffsformidler_sections.json"]
    mock_svc.download_json.return_value = sections
    db = _mock_db()

    with patch(
        "api.services.knowledge_index.BlobStorageService", return_value=mock_svc
    ):
        with patch("api.services.knowledge_index._store_chunk"):
            count = index_video_transcripts(db)

    assert count == 0


def test_index_video_transcripts_skips_short_body():
    sections = [{"title": "Chapter", "start_seconds": 0, "entries": [{"text": "Hi"}]}]
    mock_svc = MagicMock()
    mock_svc.is_configured.return_value = True
    mock_svc.list_blobs.return_value = ["ffsformidler_sections.json"]
    mock_svc.download_json.return_value = sections
    db = _mock_db()

    with patch(
        "api.services.knowledge_index.BlobStorageService", return_value=mock_svc
    ):
        with patch("api.services.knowledge_index._source_exists", return_value=False):
            with patch("api.services.knowledge_index._store_chunk"):
                count = index_video_transcripts(db)

    assert count == 0


def test_index_video_transcripts_skips_already_indexed_source():
    sections = [
        {
            "title": "Chapter",
            "start_seconds": 0,
            "description": "Long enough description here",
            "entries": [],
        }
    ]
    mock_svc = MagicMock()
    mock_svc.is_configured.return_value = True
    mock_svc.list_blobs.return_value = ["ffskunde_sections.json"]
    mock_svc.download_json.return_value = sections
    db = _mock_db()

    with patch(
        "api.services.knowledge_index.BlobStorageService", return_value=mock_svc
    ):
        with patch("api.services.knowledge_index._source_exists", return_value=True):
            with patch("api.services.knowledge_index._store_chunk"):
                count = index_video_transcripts(db)

    assert count == 0


def test_index_video_transcripts_handles_exception_gracefully():
    mock_svc = MagicMock()
    mock_svc.is_configured.return_value = True
    mock_svc.list_blobs.side_effect = Exception("Blob unavailable")
    db = _mock_db()

    with patch(
        "api.services.knowledge_index.BlobStorageService", return_value=mock_svc
    ):
        count = index_video_transcripts(db)

    assert count == 0
    db.rollback.assert_called_once()


# ── get_stats ─────────────────────────────────────────────────────────────────


def test_get_stats_counts_by_source_type():
    doc_chunk = MagicMock()
    doc_chunk.source = "doc::1::Title::Insurer::2024"
    video_chunk = MagicMock()
    video_chunk.source = "video::VideoName::120::Chapter"
    other_chunk = MagicMock()
    other_chunk.source = "video::Other::0::Section"
    db = _mock_db()
    db.query.return_value.filter.return_value.all.return_value = [
        doc_chunk,
        video_chunk,
        other_chunk,
    ]

    result = get_stats(db)

    assert result["total_chunks"] == 3
    assert result["doc_chunks"] == 1
    assert result["video_chunks"] == 2


def test_get_stats_returns_zeros_when_empty():
    db = _mock_db()
    db.query.return_value.filter.return_value.all.return_value = []
    assert get_stats(db) == {"total_chunks": 0, "doc_chunks": 0, "video_chunks": 0}


# ── index_all ─────────────────────────────────────────────────────────────────


def test_index_all_returns_combined_counts():
    db = _mock_db()
    with patch(
        "api.services.knowledge_index.index_insurance_documents", return_value=3
    ):
        with patch(
            "api.services.knowledge_index.index_video_transcripts", return_value=7
        ):
            result = index_all(db)
    assert result == {"docs_chunks": 3, "video_chunks": 7}


def test_index_all_calls_both_indexers():
    db = _mock_db()
    with patch(
        "api.services.knowledge_index.index_insurance_documents", return_value=0
    ) as mock_docs:
        with patch(
            "api.services.knowledge_index.index_video_transcripts", return_value=0
        ) as mock_vids:
            index_all(db)
    mock_docs.assert_called_once_with(db)
    mock_vids.assert_called_once_with(db)
