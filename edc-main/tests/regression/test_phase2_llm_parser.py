"""Bug #3v2 regression guard: ``parse_raw_triplets`` must handle a trailing
comma followed by arbitrary whitespace before ``]`` — not only the
immediately-adjacent case.

History:
- v1 (pre-fix) used ``bracketed_str.rstrip(",]") + "]"``. Python's
  ``rstrip`` stops at the first character NOT in the set, so a triple
  like ``["Insulin", "treats", "T1D", ]`` (with whitespace between the
  comma and the bracket) was silently NOT repaired by this branch.
  The outer ``except Exception`` fallback to ``_split_unquoted_top_level_commas``
  happened to recover the correct parts, which masked the bug from the
  test suite — but the inner fix was broken.
- v2 (this version) uses ``re.sub(r",\\s*\\]$", "]", bracketed_str.strip())``
  which matches the comma, any whitespace, and the closing bracket
  regardless of intervening characters.
"""

import pytest

from edc.utils.llm_utils import parse_raw_triplets


# Cases that exercise the trailing-comma fix
@pytest.mark.parametrize(
    "triplet_str,expected",
    [
        # The original case from the bug report
        (
            '["Insulin", "treats", "T1D", ]',
            [["Insulin", "treats", "T1D"]],
        ),
        # Newline between comma and bracket
        (
            '["A", "B", "C",\n]',
            [["A", "B", "C"]],
        ),
        # Multi-space between comma and bracket
        (
            '["A", "B", "C",     ]',
            [["A", "B", "C"]],
        ),
        # Tab between comma and bracket
        (
            '["A", "B", "C",\t]',
            [["A", "B", "C"]],
        ),
        # Multiple whitespace kinds mixed
        (
            '["Insulin", "treats", "T1D",  \n  ]',
            [["Insulin", "treats", "T1D"]],
        ),
        # No trailing comma — must still parse correctly
        (
            '["Insulin", "treats", "T1D"]',
            [["Insulin", "treats", "T1D"]],
        ),
        # Multiple triples in one string, one with whitespace + comma
        (
            '["A", "B", "C", ]\n["D", "E", "F"]',
            [["A", "B", "C"], ["D", "E", "F"]],
        ),
    ],
)
def test_parse_raw_triplets_handles_trailing_comma_whitespace(triplet_str, expected):
    """Trailing-comma + whitespace must be repaired correctly by the
    ``re.sub`` fix, not just by the secondary unquoted-split fallback.
    """
    parsed = parse_raw_triplets(triplet_str)
    assert parsed == expected, (
        f"Failed to parse {triplet_str!r}: got {parsed}, expected {expected}"
    )
