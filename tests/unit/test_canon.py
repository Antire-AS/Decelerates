"""Unit tests for api/services/canon.py — UI audit F06 follow-up.

These tests are the lockfile that prevents the next "Tryg vs Tryg Forsikring"
analytics regression. If a synonym is removed or the canonical form is
renamed, these fail and the PR is blocked.
"""

import pytest

from api.services.canon import canonical_insurer_name, canonical_product_name


# ── Insurer canonicalisation ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "variant,canonical",
    [
        ("Tryg", "Tryg Forsikring"),
        ("Tryg Forsikring", "Tryg Forsikring"),
        ("tryg", "Tryg Forsikring"),  # case-insensitive
        ("TRYG FORSIKRING", "Tryg Forsikring"),
        ("  Tryg  ", "Tryg Forsikring"),  # whitespace-tolerant
        ("Tryg Forsikring AS", "Tryg Forsikring"),
        ("Gjensidige", "Gjensidige Forsikring"),
        ("Gjensidige Forsikring", "Gjensidige Forsikring"),
        ("If", "If Skadeforsikring"),
        ("If Skade", "If Skadeforsikring"),
        ("if skadeforsikring", "If Skadeforsikring"),
        ("Fremtind", "Fremtind Forsikring"),
        ("Storebrand", "Storebrand Forsikring"),
        ("Codan", "Codan Forsikring"),
    ],
)
def test_canonical_insurer_name_known_variants(variant, canonical):
    assert canonical_insurer_name(variant) == canonical


def test_canonical_insurer_name_passthrough_unknown():
    """An unknown insurer is preserved verbatim, not silently renamed."""
    assert canonical_insurer_name("Some New Carrier") == "Some New Carrier"
    assert canonical_insurer_name("Knif Trygghet") == "Knif Trygghet"


def test_canonical_insurer_name_none():
    assert canonical_insurer_name(None) is None


def test_canonical_insurer_name_empty():
    """Empty / whitespace-only collapses to empty so callers can tell it apart from None."""
    assert canonical_insurer_name("") == ""
    assert canonical_insurer_name("   ") == ""


# ── Product type canonicalisation ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "variant,canonical",
    [
        ("Avbruddsforsikring", "Driftsavbruddsforsikring"),
        ("Driftsavbruddsforsikring", "Driftsavbruddsforsikring"),
        ("avbruddsforsikring", "Driftsavbruddsforsikring"),
        ("Tingsforsikring", "Tingsskadeforsikring"),
        ("Tingsskadeforsikring", "Tingsskadeforsikring"),
        ("Styreansvar", "Styreansvarsforsikring"),
        ("Styreansvarsforsikring", "Styreansvarsforsikring"),
        ("Styreansvar (D&O)", "Styreansvarsforsikring"),
        ("D&O", "Styreansvarsforsikring"),
    ],
)
def test_canonical_product_name_known_variants(variant, canonical):
    assert canonical_product_name(variant) == canonical


def test_canonical_product_name_passthrough_unknown():
    assert canonical_product_name("Cyberforsikring") == "Cyberforsikring"
    assert canonical_product_name("Yrkesskade") == "Yrkesskade"


def test_canonical_product_name_none():
    assert canonical_product_name(None) is None


def test_canonical_product_name_empty():
    assert canonical_product_name("") == ""
    assert canonical_product_name("   ") == ""
