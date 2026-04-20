"""Unit tests for ChatHistoryService's pure helpers + the format function."""

from types import SimpleNamespace

from api.services.chat_history import format_history_for_prompt


def _msg(role: str, content: str):
    return SimpleNamespace(role=role, content=content)


def test_format_empty_history_returns_empty_string() -> None:
    assert format_history_for_prompt([]) == ""


def test_format_user_and_assistant_turns() -> None:
    msgs = [
        _msg("user", "Hva er ansvarsforsikring?"),
        _msg("assistant", "Ansvarsforsikring dekker..."),
        _msg("user", "Og yrkesskade?"),
    ]
    out = format_history_for_prompt(msgs)
    assert out.startswith("Tidligere samtale:")
    assert "Bruker: Hva er ansvarsforsikring?" in out
    assert "Assistent: Ansvarsforsikring dekker..." in out
    assert "Bruker: Og yrkesskade?" in out


def test_format_treats_non_user_role_as_assistant() -> None:
    """Anything that isn't role='user' gets rendered as Assistent."""
    msgs = [_msg("system", "hidden"), _msg("tool", "result")]
    out = format_history_for_prompt(msgs)
    assert out.count("Assistent:") == 2
    assert "Bruker:" not in out


# ── ChatHistoryService CRUD (fake DB) ────────────────────────────────────────


class _FakeQuery:
    """Session shim that supports `.filter().filter().order_by().limit().all()`
    AND `.filter().delete(synchronize_session=...)`."""

    def __init__(self, rows: list):
        self._rows = rows

    def filter(self, *_conds):
        return self

    def order_by(self, *_args):
        return self

    def limit(self, _n):
        return self

    def all(self):
        return list(self._rows)

    def delete(self, **_kwargs):
        n = len(self._rows)
        self._rows.clear()
        return n


class _FakeDB:
    def __init__(self, rows=None):
        self._rows: list = rows or []
        self.added: list = []
        self.commits = 0

    def query(self, _model):
        return _FakeQuery(self._rows)

    def add(self, obj):
        self.added.append(obj)
        self._rows.append(obj)

    def commit(self):
        self.commits += 1


def test_append_turn_stores_user_and_assistant_rows() -> None:
    from api.services.chat_history import ChatHistoryService

    db = _FakeDB()
    svc = ChatHistoryService(db)  # type: ignore[arg-type]
    svc.append_turn(
        user_oid="u1",
        orgnr=None,
        question="Spørsmål?",
        answer="Svar.",
    )
    assert len(db.added) == 2
    roles = [r.role for r in db.added]
    assert roles == ["user", "assistant"]
    assert db.added[0].content == "Spørsmål?"
    assert db.added[1].content == "Svar."
    assert db.commits == 1


def test_load_history_returns_reversed_order() -> None:
    """DB returns newest-first (order_by desc); service reverses to chronological."""
    from api.services.chat_history import ChatHistoryService

    # Store rows in reverse chronological (newest first) like the real query
    msgs = [_msg("assistant", "3"), _msg("user", "2"), _msg("assistant", "1")]
    db = _FakeDB(rows=msgs)
    svc = ChatHistoryService(db)  # type: ignore[arg-type]
    out = svc.load_history(user_oid="u1", orgnr=None)
    # After reversal the oldest (msg "1") is first
    assert [m.content for m in out] == ["1", "2", "3"]


def test_clear_history_removes_matching_rows_and_returns_count() -> None:
    from api.services.chat_history import ChatHistoryService

    msgs = [_msg("user", "a"), _msg("assistant", "b"), _msg("user", "c")]
    db = _FakeDB(rows=msgs)
    svc = ChatHistoryService(db)  # type: ignore[arg-type]
    n = svc.clear_history(user_oid="u1", orgnr="987654321")
    assert n == 3
    assert db.commits == 1


def test_clear_history_knowledge_path_uses_is_null_branch() -> None:
    """orgnr=None triggers the `.orgnr.is_(None)` branch — just exercise it."""
    from api.services.chat_history import ChatHistoryService

    db = _FakeDB(rows=[_msg("user", "x")])
    svc = ChatHistoryService(db)  # type: ignore[arg-type]
    assert svc.clear_history(user_oid="u1", orgnr=None) == 1
