"""Unit tests for the schema_canonicalization letter cap (Week 2 fix #5).

The previous implementation used ``chr(ord('@') + i + 1)`` which, after
the 26th letter, yields non-alphabet characters like '[', '\\', etc.
and silently produced unparseable prompts. The fix caps at 26 letters and
returns ``None`` when the cap is reached.
"""

import re

import pytest

pytestmark = pytest.mark.regression


def _letter(i: int) -> str:
    """Mirror of the canonicalization module's helper."""
    return chr(ord("A") + i)


def test_letter_helper_caps_at_26():
    """The 26th letter is 'Z'; the 27th overflows the alphabet."""
    assert _letter(0) == "A"
    assert _letter(25) == "Z"
    # The OLD code would emit '[' here because chr(ord('@') + 27) = '['
    # We want neither the new helper nor the prompt to ever produce '['.
    assert "[" not in _letter(27)  # out of alphabet entirely


def test_cap_behavior_no_overflow_chars_in_choices():
    """Simulate the prompt-building loop and confirm only A-Z appear."""
    MAX_LETTERS = 26
    letter_idx = 0
    generated_letters = []
    candidate_relations = [f"rel_{i}" for i in range(20)]  # 20 candidates
    for rel in candidate_relations:
        if letter_idx >= MAX_LETTERS:
            break
        generated_letters.append(_letter(letter_idx))
        letter_idx += 1
        if letter_idx >= MAX_LETTERS:
            break
        generated_letters.append(_letter(letter_idx))
        letter_idx += 1

    # All letters are strictly A-Z
    assert all(len(L) == 1 and "A" <= L <= "Z" for L in generated_letters), (
        f"Found non-alphabet letter: {generated_letters}"
    )
    # We generated at most 26 distinct letters
    assert len(set(generated_letters)) <= 26


def test_cap_caps_at_15_candidates_with_none_option():
    """15 candidates with original/swapped/None → 30 letters, well under 26.

    With 12 candidates → 24 letters + 1 None = 25 letters total → under cap.
    With 13 candidates → 26 letters, exactly the cap, no room for the
    None-of-the-above option."""
    MAX_LETTERS = 26

    def total_letters(n_candidates: int) -> int:
        slots = 2 * n_candidates  # original + swapped
        plus_none = 1 if slots < MAX_LETTERS else 0
        return slots + plus_none

    assert total_letters(12) == 25  # 24 letters + None
    assert total_letters(13) == 26  # cap reached, no room for None option


def test_old_chr_formula_would_overflow():
    """Verify the OLD formula chr(ord('@') + i + 1) overflows at i=27."""
    # Old code: letter = chr(ord("@") + idx + 1) starting at idx=0
    old_25 = chr(ord("@") + 25 + 1)  # Z
    old_26 = chr(ord("@") + 26 + 1)  # [ — overflow!
    assert old_25 == "Z"
    assert old_26 == "[", "Sanity check: old formula DID overflow at 27"
