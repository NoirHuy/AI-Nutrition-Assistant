"""
constants.py — Shared constants for the post_processing package.

Single source of truth for:
  - LOCAL_MEDICAL_ABBREVIATIONS: Clinical acronym expansion table
  - MEDICAL_STOPWORDS: Stopwords removed during deduplication normalization
  - MEDICAL_SAFE_TUIS: Valid UMLS Semantic Type Identifiers for clinical domain
  - CACHE_VERSION: Version tag for cache invalidation on schema changes

Previously these were duplicated across umls_normalizer.py and property_packer.py.
"""

import os
from pathlib import Path
from typing import Dict, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Cache versioning — bump this when the cache schema changes
# (e.g. new fields added to UMLS query results, TUI list expanded, etc.)
# Caches with a different version will be automatically invalidated.
# ─────────────────────────────────────────────────────────────────────────────
CACHE_VERSION: str = "2.0"

# ─────────────────────────────────────────────────────────────────────────────
# Semantic Types: Danh sách TUI hợp lệ cho miền y khoa lâm sàng
# Được mở rộng từ 4 lên 17 loại để bao phủ đầy đủ:
#   thuốc (T121, T200, T116, T125, T109, T123),
#   bệnh/triệu chứng (T047, T184, T033, T037),
#   thủ thuật/xét nghiệm (T061, T059, T060),
#   giải phẫu (T023, T029),
#   chỉ số lâm sàng (T034, T081)
# ─────────────────────────────────────────────────────────────────────────────
MEDICAL_SAFE_TUIS: frozenset = frozenset({
    # Bệnh lý & triệu chứng
    "T047",  # Disease or Syndrome
    "T184",  # Sign or Symptom
    "T033",  # Finding
    "T037",  # Injury or Poisoning
    # Thuốc & hoạt chất
    "T121",  # Pharmacologic Substance (metformin, glipizide...)
    "T200",  # Clinical Drug — biệt dược thương mại (Lantus, Januvia...)
    "T116",  # Amino Acid, Peptide, or Protein (insulin là một protein)
    "T125",  # Hormone (glucagon, insulin thuộc nhóm hormone)
    "T109",  # Organic Chemical (nhiều thuốc tổng hợp hữu cơ)
    "T123",  # Biologically Active Substance
    # Thủ thuật & xét nghiệm
    "T061",  # Therapeutic or Preventive Procedure
    "T059",  # Laboratory Procedure (HbA1c test, fasting glucose)
    "T060",  # Diagnostic Procedure
    # Giải phẫu
    "T023",  # Body Part, Organ, or Organ Component (pancreas, kidney...)
    "T029",  # Body Location or Region
    # Chỉ số & kết quả lâm sàng
    "T034",  # Laboratory or Test Result
    "T081",  # Quantitative Concept (HbA1c threshold value)
})

# ─────────────────────────────────────────────────────────────────────────────
# Medical Abbreviation Expansion Table
# Maps common clinical abbreviations / aliases → canonical lowercase form.
# Used in normalize_entity_for_dedup() and _expand_abbreviations().
#
# v2 (Week 4 fix #2 portability): the *full* abbreviation table is loaded
# from ``config/domain_rules.yaml`` (under ``local_medical_abbreviations``)
# when available — fall back to the table below when the YAML is missing.
# The defaults here match the historical diabetes behaviour so existing
# callers see no change.
# ─────────────────────────────────────────────────────────────────────────────


def _load_domain_abbreviations() -> Optional[Dict[str, str]]:
    """Load abbreviation overrides from the active domain rules YAML.

    Returns ``None`` when no YAML is found or PyYAML is missing.
    """
    try:
        import yaml
    except ImportError:
        return None
    candidates = [
        Path(__file__).resolve().parent.parent / "config" / "domain_rules.yaml",
        Path(__file__).resolve().parent.parent.parent / "config" / "domain_rules.yaml",
    ]
    for p in candidates:
        if not p.exists():
            continue
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        if isinstance(data, dict) and data.get("local_medical_abbreviations"):
            # YAML keys are uppercase canonical names; dedup uses lowercase
            return {k.lower(): v.lower() for k, v in data["local_medical_abbreviations"].items()}
    return None


_LOCAL_DIABETES_RAW: Dict[str, str] = {
    # Diabetes diseases
    "t2dm": "type 2 diabetes mellitus",
    "t1dm": "type 1 diabetes mellitus",
    "dm": "diabetes mellitus",
    "dm2": "type 2 diabetes mellitus",
    "dm1": "type 1 diabetes mellitus",
    "niddm": "type 2 diabetes mellitus",
    "iddm": "type 1 diabetes mellitus",
    "dka": "diabetic ketoacidosis",
    "hhs": "hyperosmolar hyperglycemic state",
    # Biomarkers & labs
    "hba1c": "hemoglobin a1c",
    "a1c": "hemoglobin a1c",
    "fbg": "fasting blood glucose",
    "fpg": "fasting plasma glucose",
    "bg": "blood glucose",
    "ppg": "postprandial glucose",
    "ogtt": "oral glucose tolerance test",
    "ldl": "ldl cholesterol",
    "hdl": "hdl cholesterol",
    "tg": "triglycerides",
    "egfr": "estimated glomerular filtration rate",
    "gfr": "glomerular filtration rate",
    "bmi": "body mass index",
    "sbp": "systolic blood pressure",
    "dbp": "diastolic blood pressure",
    "bp": "blood pressure",
    # Drugs
    "metformin hcl": "metformin",
    "glp-1": "glucagon-like peptide-1",
    "glp1": "glucagon-like peptide-1",
    "sglt2": "sglt2 inhibitor",
    "sglt-2": "sglt2 inhibitor",
    "dpp-4": "dpp-4 inhibitor",
    "dpp4": "dpp-4 inhibitor",
    "tzds": "thiazolidinedione",
    "tld": "thiazolidinedione",
    "su": "sulphonylurea",
    "sua": "sulphonylurea",
    "sulfonylurea": "sulphonylurea",
    "insulin nph": "nph insulin",
    "nph": "nph insulin",
    "mdii": "multiple daily injections",
    "csii": "continuous subcutaneous insulin infusion",
    "ace-i": "ace inhibitor",
    "arb": "angiotensin receptor blocker",
    "ccb": "calcium channel blocker",
    "statin": "statin",
    "asa": "aspirin",
}


# Note: dict literal above is `_LOCAL_DIABETES_RAW`; ``LOCAL_MEDICAL_ABBREVIATIONS``
# below is the public-facing mapping that also folds in YAML overrides.


def get_local_medical_abbreviations() -> Dict[str, str]:
    """Return the abbreviation table, augmented by the active domain YAML.

    Loaded lazily so test runs without the YAML file don't pay the import
    cost of PyYAML.
    """
    overrides = _load_domain_abbreviations()
    if overrides is None:
        return dict(_LOCAL_DIABETES_RAW)
    # YAML is the source of truth for portability; diabetes defaults are
    # merged underneath so any abbreviation not in the YAML still resolves.
    return {**dict(_LOCAL_DIABETES_RAW), **overrides}


# Bug #5 fix (2026-08-17): callers used to read the frozen
# ``LOCAL_MEDICAL_ABBREVIATIONS`` dict that was captured at import time.
# That meant switching the active YAML at runtime had no effect on code
# that had already cached the reference. The recommended pattern now is:
#   from post_processing.constants import get_local_medical_abbreviations
#   abbrev = get_local_medical_abbreviations()      # always fresh
#
# The ``LOCAL_MEDICAL_ABBREVIATIONS`` symbol is preserved for backward
# compatibility — it now points at a *mutable* dict that is rebroadcast
# whenever ``refresh_local_medical_abbreviations()`` is called, so any
# caller using ``.get`` / iteration sees the latest values without
# re-importing.
LOCAL_MEDICAL_ABBREVIATIONS: Dict[str, str] = get_local_medical_abbreviations()


def refresh_local_medical_abbreviations() -> Dict[str, str]:
    """Reload the YAML-driven abbreviation table in place.

    Returns the *same* dict that ``LOCAL_MEDICAL_ABBREVIATIONS`` points
    to so callers can either grab it directly or rely on the module-level
    name.

    Use this when a long-running process switches domains at runtime.
    """
    fresh = get_local_medical_abbreviations()
    LOCAL_MEDICAL_ABBREVIATIONS.clear()
    LOCAL_MEDICAL_ABBREVIATIONS.update(fresh)
    return LOCAL_MEDICAL_ABBREVIATIONS

# ─────────────────────────────────────────────────────────────────────────────
# Medical stopwords — removed before canonical comparison to reduce false negatives
# ─────────────────────────────────────────────────────────────────────────────
MEDICAL_STOPWORDS: frozenset = frozenset({
    "the", "a", "an", "of", "with", "in", "and", "or", "to", "for",
    "mellitus", "syndrome", "disease", "disorder", "condition",
    "associated", "related", "induced", "dependent", "independent",
})

# ─────────────────────────────────────────────────────────────────────────────
# Protected medical terms — words that should NOT be stemmed because removing
# common suffixes would destroy their meaning (e.g. "glucose" → "glucoe")
# ─────────────────────────────────────────────────────────────────────────────
STEM_PROTECTED_TERMS: frozenset = frozenset({
    "glucose", "dextrose", "fructose", "lactose", "sucrose", "maltose",
    "galactose", "trehalose", "ribose",
    "lipase", "amylase", "protease", "kinase",
    "diabetes", "prediabetes",
    "diagnosis", "prognosis",
    "acidosis", "ketoacidosis", "alkalosis",
    "fibrosis", "sclerosis", "stenosis", "thrombosis", "necrosis",
    "hypoxia", "anoxia",
    "anemia",
    "plus", "nexus", "bolus", "corpus", "sinus", "fetus", "stimulus",
})
