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
