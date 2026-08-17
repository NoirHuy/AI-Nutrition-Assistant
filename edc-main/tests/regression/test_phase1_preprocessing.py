"""Regression tests for Phase 1 — Preprocessing.

Goals:
- The clean_medical_prose regex MUST generalize to author names beyond the
  hardcoded "ByErika" / "Reviewed ByGlenn".
- The table-detection logic should still work after refactoring.
- The sentence splitter MUST use deterministic nltk first, with a regex
  fallback. The fallback must remain non-empty.
- A regression baseline of sentence count is locked in so future changes
  can be diffed.
"""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.regression

from clean_prose import clean_medical_prose  # noqa: E402
from sentence_rewriter import split_sentences  # noqa: E402


# Author-signature patterns that MUST be removed.
AUTHOR_PATTERNS = [
    re.compile(r"\bByErika\b"),
    re.compile(r"\bByMary\b"),
    re.compile(r"\bByJohn\b"),
    re.compile(r"\bByMaria\b"),
    re.compile(r"\bReviewed\s+By[A-Z][a-z]+"),
    re.compile(r"\bBy[A-Z][a-z]+(?:\s+[A-Z]\.)?[a-z]+"),  # ByMary Ann H. Johnson
]


def _no_author_leakage(text: str) -> bool:
    return not any(p.search(text) for p in AUTHOR_PATTERNS)


# ------------------------------------------------------------ 12+ patterns


@pytest.mark.parametrize(
    "noise_line",
    [
        # ByErika F. Brutsaert (legacy)
        "ByErika F. Brutsaert, MD, New York Medical College",
        # Other author names (the regression target)
        "ByMary Ann H. Johnson, MD, Harvard Medical School",
        "ByJohn Michael Doe, MD, Stanford University",
        "ByMaria L. Rodriguez, MD, Johns Hopkins",
        # Reviewed By… variants
        "Reviewed ByGlenn D. Braunstein, MD, Cedars-Sinai Medical Center",
        "Reviewed ByRobert K. Smith, MD, Mayo Clinic",
        # Reviewed/Revised date line
        "Reviewed/Revised Dec 2025 | Modified Apr 2026",
        "Reviewed/Revised Jan 2026 | Modified Feb 2026",
        # Web navigation noise
        "View Patient Education",
        "Multimedia",
        "Disclaimer",
        "follow us on facebook",
        "Copyright © 2026 Merck & Co.",
    ],
)
def test_clean_prose_removes_noisy_lines(noise_line: str):
    """Each known noise pattern should be removed (12 patterns cover the suite)."""
    text = "Real medical content.\n" + noise_line + "\nMore real content."
    out = clean_medical_prose(text)
    assert noise_line.strip() not in out, (
        f"Noise line was NOT removed: {noise_line!r} -> output: {out!r}"
    )


# ------------------------------------------------------------ Author leakage


def test_author_leakage_other_authors(merck_diabetes_raw_path: Path):
    """Authors other than 'Erika' MUST be stripped too (the v1 regression)."""
    text = merck_diabetes_raw_path.read_text(encoding="utf-8")
    out = clean_medical_prose(text)
    assert _no_author_leakage(out), (
        f"Author signature still present in cleaned text:\n{out[:400]}"
    )


def test_author_leakage_cardiology(merck_cardiology_raw_path: Path):
    """Cardiology byline must be stripped (portability check)."""
    text = merck_cardiology_raw_path.read_text(encoding="utf-8")
    out = clean_medical_prose(text)
    assert _no_author_leakage(out), (
        f"Cardiology byline not removed:\n{out[:400]}"
    )


# ------------------------------------------------------------ Table detection


def test_markdown_table_still_detected():
    """The pipeline still recognises a markdown table separator line."""
    from main_pipeline import detect_table

    md = (
        "| Col A | Col B |\n"
        "|-------|-------|\n"
        "| 1      | 2     |\n"
    )
    assert detect_table(md) is True


# ------------------------------------------------------------ Sentence split


def test_sentence_split_resolves_medical_passage():
    """nltk-based split should produce multiple standalone sentences."""
    text = (
        "Type 2 diabetes mellitus is a chronic metabolic disorder. "
        "It is characterized by insulin resistance. "
        "Treatment includes diet and exercise. "
        "Metformin is the first-line medication."
    )
    sents = split_sentences(text)
    assert len(sents) >= 3, f"Expected ≥3 sentences, got {len(sents)}: {sents}"
    # None of the splits should be empty
    assert all(len(s.strip()) > 0 for s in sents)


def test_sentence_split_handles_empty():
    assert split_sentences("") == []
    assert split_sentences("   \n\t  ") == []


def test_sentence_split_falls_back_when_nltk_missing(monkeypatch):
    """When nltk cannot be loaded, the regex fallback must still produce sentences."""
    import sentence_rewriter as sr

    monkeypatch.setattr(sr, "_NLTK_SENT_TOKENIZER", False)
    text = (
        "Type 2 diabetes mellitus is characterized by insulin resistance. "
        "Treatment includes metformin. "
        "SGLT2 inhibitors reduce cardiovascular mortality."
    )
    sents = sr.split_sentences(text)
    assert len(sents) >= 2, f"Fallback split failed: {sents}"


# ------------------------------------------------------------ Real content preservation


def test_clean_prose_preserves_real_medical_content():
    text = (
        "ByErika F. Brutsaert, MD, New York Medical College\n"
        "Reviewed ByGlenn D. Braunstein, MD, Cedars-Sinai Medical Center\n\n"
        "Diabetes mellitus is a metabolic disease characterized by elevated blood glucose.\n"
        "Insulin therapy is required in type 1 diabetes but not always in type 2 diabetes."
    )
    out = clean_medical_prose(text)
    assert "Diabetes mellitus is a metabolic disease" in out
    assert "Insulin therapy is required in type 1 diabetes" in out
    assert "ByErika" not in out
    assert "ByGlenn" not in out


# ------------------------------------------------------------ Bug #1 regression guard
# https://en.wikipedia.org/wiki/Byline_(publishing) — the byline pattern used
# to drop real medical sentences that started with "Bypass" or "Bystander"
# because ``re.IGNORECASE`` was applied to ``By[A-Z][a-z]+``.

@pytest.mark.parametrize(
    "line",
    [
        "Bypass surgery is indicated in coronary artery disease.",
        "Bystander CPR is essential during cardiac arrest.",
        "Bypass grafting improved 5-year survival.",
        "Bystander intervention reduces mortality.",
    ],
)
def test_clean_prose_does_not_swallow_byline_like_medical_terms(line):
    """Medical sentences whose first word starts with ``By`` followed by a
    capital letter must be preserved.

    Regression guard for the v2 regex that applied ``re.IGNORECASE`` to a
    sub-pattern intended only for author bylines — it silently deleted
    legitimate clinical content.
    """
    out = clean_medical_prose(line + "\nFollow-up: stable.")
    assert line in out, f"clean_prose ate a legitimate medical sentence: {line!r}"
    assert "Follow-up: stable." in out


# Bug #1v2 regression guard: titles / section headers without trailing
# punctuation must also be preserved. The v3 fix relied on the trailing
# period to reject a byline match; section headings like "Bypass Surgery
# Techniques" have no such delimiter and were still being deleted.

@pytest.mark.parametrize(
    "title",
    [
        "Bypass Surgery Techniques",
        "Bystander CPR Steps",
        "Bypass Graft Indications",
        "Bystander Intervention Outcomes",
        "Byetta Therapy Overview",        # legitimate medical term
    ],
)
def test_clean_prose_preserves_periodless_titles_starting_with_by(title):
    """Section headers / titles whose first word starts with ``By``
    followed by a capital letter, with no trailing period, must be kept.

    Regression guard for v3 — the credential requirement was insufficient
    when the line had no terminal punctuation.
    """
    out = clean_medical_prose(title + "\nSubsequent sentence.")
    assert title in out, (
        f"clean_prose ate a periodless medical title: {title!r}\nGot: {out!r}"
    )


@pytest.mark.parametrize(
    "byline",
    [
        "ByMary Ann H. Johnson, MD, Harvard Medical School",
        "Reviewed ByRobert K. Smith, MD, Mayo Clinic",
        "ByErika F. Brutsaert, MD, New York Medical College",
        "by Erika F. Brutsaert, MD, New York Medical College",  # lowercase
        "Reviewed/Revised Jan 2026 | Modified Feb 2026",
    ],
)
def test_clean_prose_still_deletes_legitimate_bylines(byline):
    """The v4 regex tightening must not break the legitimate byline
    removal — these are real Merck/Medscape bylines that v2/v3 also
    correctly deleted."""
    out = clean_medical_prose(byline + "\nFollow-up: stable.")
    assert "Follow-up: stable." in out
    # The byline's distinctive author tokens must be gone. We pick a
    # token that uniquely identifies the byline (not a generic word
    # like ``MD`` that might appear in the kept content).
    distinctive_tokens = [
        t for t in byline.split()
        if len(t) > 2 and not t.endswith(",") and t not in {"MD", "PhD", "Prof", "and", "the"}
    ]
    for token in distinctive_tokens:
        # Strip trailing punctuation for the assertion
        clean_token = token.rstrip(",.")
        # Skip the lowercase variant's "by" — it might overlap with English "by"
        if clean_token.lower() == "by":
            continue
        assert clean_token not in out, (
            f"byline token {clean_token!r} leaked through: {out!r}"
        )


# ------------------------------------------------------------ Citation cleanup


def test_clean_prose_cleans_inline_citations():
    text = (
        "Diabetes mellitus (1) is a metabolic disease. "
        "Recent studies [3, 4] confirm this finding. "
        "It affects 11% to 14% of adults (2, 5)."
    )
    out = clean_medical_prose(text)
    assert "(1)" not in out
    assert "[3, 4]" not in out
    assert "(2, 5)" not in out
    # Real content preserved
    assert "Diabetes mellitus" in out
    assert "11% to 14% of adults" in out


# ------------------------------------------------------------ Regression baseline


def test_sentence_count_baseline_locked(biored_diabetes_sample_path: Path):
    """Lock sentence-count baseline for the BioRED-style sample so future changes can be diffed."""
    text = biored_diabetes_sample_path.read_text(encoding="utf-8")
    sents = split_sentences(text)
    # The fixture contains exactly 5 well-formed sentences.
    assert len(sents) == 5, (
        f"Baseline drift! Expected 5 sentences, got {len(sents)}. Sentences: {sents}"
    )
