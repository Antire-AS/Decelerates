"""Unit tests for the AI-finanskommentar prompt builder.

The bug: history rows from company_history (PDF-extracted) store revenue
under `revenue`, not `sum_driftsinntekter`. The commentary prompt used to
only read the BRREG-shaped keys, so for any PDF-only company the LLM
received nothing but "N/A" and correctly reported "no data available" —
even though the chart immediately above the commentary showed 5 years of
real numbers.
"""

from __future__ import annotations

from api.routers.financials import (
    _build_commentary_prompt,
    _fmt_nok,
    _history_row_fields,
)


# ── NOK formatter ────────────────────────────────────────────────────────────


def test_fmt_nok_uses_thin_space_thousands():
    assert _fmt_nok(86_537_000_000) == "86 537 000 000 NOK"


def test_fmt_nok_returns_na_on_none():
    assert _fmt_nok(None) == "N/A"


def test_fmt_nok_renders_small_values():
    assert _fmt_nok(1234) == "1 234 NOK"


# ── Key merging — the actual bug ────────────────────────────────────────────


def test_history_row_fields_reads_brreg_shape():
    row = {
        "year": 2023,
        "sum_driftsinntekter": 81_697_000_000,
        "sum_egenkapital": 269_296_000_000,
        "sum_eiendeler": 3_500_000_000_000,
    }
    assert _history_row_fields(row) == (
        81_697_000_000,
        269_296_000_000,
        3_500_000_000_000,
    )


def test_history_row_fields_falls_back_to_pdf_extracted_shape():
    """This is the regression — PDF-extracted rows store values under
    `revenue`/`equity`/`total_assets`. Without the fallback, every field
    returns None and the prompt is full of N/As."""
    row = {
        "year": 2024,
        "revenue": 86_537_000_000,
        "equity": 283_325_000_000,
        "total_assets": 3_614_125_000_000,
    }
    assert _history_row_fields(row) == (
        86_537_000_000,
        283_325_000_000,
        3_614_125_000_000,
    )


def test_history_row_fields_prefers_brreg_keys_when_both_present():
    """BRREG numbers are authoritative when we have them; PDF-extracted
    values are just the fallback."""
    row = {
        "year": 2024,
        "sum_driftsinntekter": 1_000,
        "revenue": 2_000,
        "sum_egenkapital": 3_000,
        "equity": 4_000,
        "sum_eiendeler": 5_000,
        "total_assets": 6_000,
    }
    assert _history_row_fields(row) == (1_000, 3_000, 5_000)


# ── End-to-end prompt string ────────────────────────────────────────────────


def test_commentary_prompt_includes_real_numbers_from_pdf_extracted_history():
    """The regression test. Prompt should mention the actual revenue, NOT
    a string of N/A placeholders."""
    history = [
        {
            "year": 2024,
            "revenue": 86_537_000_000,
            "equity": 283_325_000_000,
            "total_assets": 3_614_125_000_000,
        },
        {
            "year": 2023,
            "revenue": 81_697_000_000,
            "equity": 269_296_000_000,
            "total_assets": 3_500_000_000_000,
        },
    ]
    prompt = _build_commentary_prompt("DNB Bank ASA", "984851006", history)
    assert "86 537 000 000" in prompt
    assert "81 697 000 000" in prompt
    assert "DNB Bank ASA" in prompt
    assert "984851006" in prompt


def test_commentary_prompt_renders_na_only_for_rows_with_no_data():
    history = [
        {"year": 2020},  # genuinely empty — N/A is the honest answer
        {"year": 2021, "revenue": 55_915_000_000},
    ]
    prompt = _build_commentary_prompt("Acme AS", "123456789", history)
    # The 2020 line gets N/A for all three — fine
    assert "- 2020: omsetning N/A, egenkapital N/A, eiendeler N/A" in prompt
    # But 2021 has real data
    assert "55 915 000 000" in prompt


def test_commentary_prompt_preserves_chronological_order():
    history = [
        {"year": 2022, "revenue": 100},
        {"year": 2023, "revenue": 200},
        {"year": 2024, "revenue": 300},
    ]
    prompt = _build_commentary_prompt("Acme AS", "123456789", history)
    pos_2022 = prompt.index("2022")
    pos_2023 = prompt.index("2023")
    pos_2024 = prompt.index("2024")
    assert pos_2022 < pos_2023 < pos_2024
