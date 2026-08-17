# -*- coding: utf-8 -*-
"""
clean_prose.py v2 — Specialized medical prose text cleaner.

Removes:
- Web scraping noise (navigation menus, social media footers, empty pipes)
- Citations (parenthetical and bracketed numeric refs)
- Author/reviewer bios (generalized to ANY byline pattern: ByMary, ByJohn, ...)

Backward compatible: callable signature is unchanged.
"""

import re


# Generalized byline / signature patterns (v4 — tightened 2026-08-17)
#
# History:
# v2 used ``re.IGNORECASE`` on a pattern including ``By[A-Z][a-z]+`` which
# silently matched legitimate clinical sentences like ``Bypass surgery...``
# or ``Bystander CPR...`` (Bug #1).
# v3 added a credential requirement (MD/PhD/Prof/...) so a sentence like
# ``Bypass surgery is indicated in CAD.`` was preserved by the trailing
# period — but section headers and titles without terminal punctuation
# such as ``Bypass Surgery Techniques`` were still swallowed (Bug #1v2).
# v4 (this version) — the global ``re.IGNORECASE`` is dropped entirely.
# The leading ``By`` is matched by an explicit character class ``[Bb]y``
# (handles both ``ByErika`` and ``by Erika``), and only the
# ``Reviewed/Revised`` branches use ``(?i:...)`` because that metadata
# is genuinely case-insensitive in scraped medical prose.
GENERIC_AUTHOR_SIGNATURE_PATTERN = re.compile(
    r"^\s*"
    r"(?:"
    r"[Bb]y\s+[A-Z][a-z]+"                              # By Erika, by John
    r"|[Bb]y[A-Z][a-z]+"                                 # ByErika, ByMary, byErika
    r"|(?i:Reviewed\s*/?\s*Revised).*"                   # Reviewed/Revised Jan 2026
    r"|(?i:Reviewed)\s+[Bb]y\s*[A-Z][a-z]+"              # Reviewed By Robert / Reviewed byRobert
    r")"
    r"(?:\s+[A-Z]\.?|\s+[A-Z][a-z]+)*"                   # optional initials / surnames
    r"(?:,\s*(?:MD|PhD|Prof(?:essor)?|FACP|FACS|MBBS|DO|DDS|RN|RPh)\b.*)?"
    r"\s*$",
    # NOTE: no global ``re.IGNORECASE`` — the ``By`` branches use ``[Bb]y``
    # and the metadata branches opt into case-insensitivity via ``(?i:...)``.
)


def clean_medical_prose(text: str) -> str:
    """Cleans raw scraped medical prose text by removing website noise,
    social media tags, disclaimers, copyrights, author/reviewer bios,
    empty/pipe lines, and cleaning citations.
    """
    if not text:
        return ""

    lines = text.split("\n")
    cleaned_lines = []

    # Noise line patterns
    noise_patterns = [
        re.compile(r"^\s*\|\s*$"),  # Single pipes
        re.compile(r"^\s*(View Patient Education|Multimedia|About|Disclaimer|Cookie Preferences|quizzes_lightbulb_red|Test your Knowledge.*)\s*$", re.I),
        re.compile(r"^\s*(video|multimedia|About|Disclaimer|Cookie Preferences)\s*$", re.I),
        re.compile(r"^\s*follow us on (facebook|youtube|x|instagram)\s*$", re.I),
        re.compile(r"^\s*Copyright\s*[©Ⓒ()]\s*.*$", re.I),
        GENERIC_AUTHOR_SIGNATURE_PATTERN,
        re.compile(r"^\s*(In this topic|Other topics in this chapter)\s*$", re.I),
        re.compile(r"^\s*This icon serves as a link to download.*$", re.I),
        re.compile(r"^Diabetes in children and adolescents is discussed in detail elsewhere\.$", re.I),
    ]

    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue

        # Check if line matches any noise pattern
        is_noise = False
        for pattern in noise_patterns:
            if pattern.match(stripped):
                is_noise = True
                break

        if is_noise:
            continue

        # Clean inline citation numbers e.g. (1, 2), (3), [4]
        # Clean parentheses citations like "(1, 2)" or "(1)"
        line_cleaned = re.sub(r"\s*\(\d+(?:\s*,\s*\d+)*\)", "", line)
        # Clean bracket citations like "[1]" or "[1, 2]"
        line_cleaned = re.sub(r"\s*\[\d+(?:\s*,\s*\d+)*\]", "", line_cleaned)

        cleaned_lines.append(line_cleaned)

    # Collapse multiple consecutive empty lines
    collapsed_lines = []
    prev_was_empty = False
    for line in cleaned_lines:
        if line.strip() == "":
            if not prev_was_empty:
                collapsed_lines.append("")
                prev_was_empty = True
        else:
            collapsed_lines.append(line)
            prev_was_empty = False

    return "\n".join(collapsed_lines).strip()
