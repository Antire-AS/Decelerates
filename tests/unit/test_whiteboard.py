"""Unit tests for WhiteboardService.

Focuses on the pure prompt-builder helper. DB CRUD is covered via
integration tests against a real Postgres, so we don't test those here.
"""

from types import SimpleNamespace

from api.services.whiteboard import _build_whiteboard_prompt


def _wb(items, notes=""):
    """Minimal fake CompanyWhiteboard row — only the fields _build_whiteboard_prompt touches."""
    return SimpleNamespace(items=items, notes=notes)


def test_build_prompt_with_facts_and_notes() -> None:
    wb = _wb(
        items=[
            {"label": "Omsetning", "value": "42 MNOK", "source_tab": "Økonomi"},
            {"label": "Risikoscore", "value": "12/20", "source_tab": "Oversikt"},
        ],
        notes="Kunden har uttrykt bekymring for ansvarsforsikring.",
    )
    prompt = _build_whiteboard_prompt(wb, "Test AS")
    assert "Test AS" in prompt
    assert "Omsetning: 42 MNOK" in prompt
    assert "(fra Økonomi)" in prompt
    assert "Risikoscore: 12/20" in prompt
    assert "ansvarsforsikring" in prompt
    assert "[OPPGAVE]" in prompt


def test_build_prompt_empty_items_and_notes() -> None:
    """An empty whiteboard still produces a valid prompt — caller filters these out earlier."""
    wb = _wb(items=[], notes="")
    prompt = _build_whiteboard_prompt(wb, "Tom AS")
    assert "Tom AS" in prompt
    assert "(ingen fakta lagt til)" in prompt
    assert "(ingen notater)" in prompt


def test_build_prompt_skips_malformed_items() -> None:
    wb = _wb(
        items=[
            {"label": "Gyldig", "value": "1", "source_tab": "T1"},
            {"label": "", "value": "ingen-etikett"},
            {"label": "ingen-verdi", "value": ""},
            "ikke-en-dict",
        ],
        notes="",
    )
    prompt = _build_whiteboard_prompt(wb, "Co")
    assert "Gyldig: 1" in prompt
    assert "ingen-etikett" not in prompt
    assert "ingen-verdi" not in prompt


def test_build_prompt_no_source_tab_hides_suffix() -> None:
    wb = _wb(items=[{"label": "Navn", "value": "Test AS"}], notes="")
    prompt = _build_whiteboard_prompt(wb, "Test AS")
    assert "Navn: Test AS" in prompt
    assert "(fra " not in prompt


# ── WhiteboardService CRUD (fake in-memory DB) ───────────────────────────────


class _FakeQuery:
    """Minimal SQLAlchemy session shim — ignores filter conditions and
    returns the single stored row. Each test populates db._store directly."""

    def __init__(self, store: list):
        self._store = store

    def filter(self, *_conds):
        return self

    def first(self):
        return self._store[0] if self._store else None


class _FakeDB:
    def __init__(self):
        self._store: list = []
        self.added: list = []
        self.deleted: list = []
        self.commits = 0

    def query(self, _model):
        return _FakeQuery(self._store)

    def add(self, obj):
        self.added.append(obj)
        self._store.append(obj)

    def delete(self, obj):
        self.deleted.append(obj)
        if obj in self._store:
            self._store.remove(obj)

    def commit(self):
        self.commits += 1

    def refresh(self, obj):
        return obj


def test_service_upsert_creates_new_row() -> None:
    from api.services.whiteboard import WhiteboardService

    db = _FakeDB()
    svc = WhiteboardService(db)  # type: ignore[arg-type]
    wb = svc.upsert(
        orgnr="123456789",
        user_oid="usr",
        items=[{"label": "X", "value": "Y"}],
        notes="note",
    )
    assert len(db.added) == 1
    assert wb.orgnr == "123456789"
    assert wb.notes == "note"
    assert db.commits == 1


def test_service_upsert_updates_existing_row() -> None:
    from api.services.whiteboard import WhiteboardService
    from api.models.broker import CompanyWhiteboard

    existing = CompanyWhiteboard(
        orgnr="123456789",
        user_oid="usr",
        items=[{"label": "old", "value": "v"}],
        notes="old note",
    )
    db = _FakeDB()
    db._store.append(existing)
    svc = WhiteboardService(db)  # type: ignore[arg-type]
    wb = svc.upsert(
        orgnr="123456789",
        user_oid="usr",
        items=[{"label": "new", "value": "v2"}],
        notes="new note",
    )
    assert db.added == []
    assert wb is existing
    assert wb.items == [{"label": "new", "value": "v2"}]
    assert wb.notes == "new note"


def test_service_delete_returns_false_when_not_found() -> None:
    from api.services.whiteboard import WhiteboardService

    db = _FakeDB()
    svc = WhiteboardService(db)  # type: ignore[arg-type]
    assert svc.delete("123456789", "usr") is False
    assert db.deleted == []


def test_service_delete_removes_existing_row() -> None:
    from api.services.whiteboard import WhiteboardService
    from api.models.broker import CompanyWhiteboard

    existing = CompanyWhiteboard(orgnr="123456789", user_oid="usr", items=[])
    db = _FakeDB()
    db._store.append(existing)
    svc = WhiteboardService(db)  # type: ignore[arg-type]
    assert svc.delete("123456789", "usr") is True
    assert db.deleted == [existing]


def test_generate_ai_summary_returns_none_on_empty() -> None:
    from api.services.whiteboard import WhiteboardService
    from api.models.broker import CompanyWhiteboard

    existing = CompanyWhiteboard(orgnr="123456789", user_oid="usr", items=[], notes="")
    db = _FakeDB()
    db._store.append(existing)
    svc = WhiteboardService(db)  # type: ignore[arg-type]
    assert svc.generate_ai_summary("123456789", "usr") is None


def test_generate_ai_summary_handles_llm_exception(monkeypatch) -> None:
    from api.services import whiteboard as wbmod
    from api.services.whiteboard import WhiteboardService
    from api.models.broker import CompanyWhiteboard

    existing = CompanyWhiteboard(
        orgnr="123456789",
        user_oid="usr",
        items=[{"label": "x", "value": "y"}],
        notes="",
    )
    db = _FakeDB()
    db._store.append(existing)

    def _boom(_prompt):
        raise RuntimeError("llm offline")

    monkeypatch.setattr(wbmod, "_llm_answer_raw", _boom)
    svc = WhiteboardService(db)  # type: ignore[arg-type]
    assert svc.generate_ai_summary("123456789", "usr") is None


def test_generate_ai_summary_persists_answer(monkeypatch) -> None:
    from api.services import whiteboard as wbmod
    from api.services.whiteboard import WhiteboardService
    from api.models.broker import CompanyWhiteboard

    existing = CompanyWhiteboard(
        orgnr="123456789",
        user_oid="usr",
        items=[{"label": "Omsetning", "value": "42 MNOK"}],
        notes="",
    )
    db = _FakeDB()
    db._store.append(existing)
    monkeypatch.setattr(wbmod, "_llm_answer_raw", lambda _p: "AI said: X Y Z.")
    svc = WhiteboardService(db)  # type: ignore[arg-type]
    answer = svc.generate_ai_summary("123456789", "usr", company_name="DNB")
    assert answer == "AI said: X Y Z."
    assert existing.ai_summary == "AI said: X Y Z."
