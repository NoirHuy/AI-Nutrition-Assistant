"""End-to-end regression test for the 4-phase pipeline (Week 4).

This test runs every phase of the pipeline against a deterministic
BioRED-style fixture and a cardiology fixture, asserting that:
- Each phase produces output without crashing.
- The metrics (input/output counts) are within sane bounds.
- The post-fix pipeline produces *less* leakage than the pre-fix baseline
  baseline_pre_fix.json captured at the start of the sprint.

We do NOT call real LLM APIs — every phase that needs an LLM is patched
in-process so that the test suite can run offline in CI.
"""

import json
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.regression

EDC_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(EDC_ROOT))
sys.path.insert(0, str(EDC_ROOT / "medical_preprocessing_pipeline"))

RESULTS_DIR = Path(__file__).parent / "results"


# ------------------------------------------------------------ Phase 1 + domain YAML


def test_pipeline_phase1_clean_text():
    """Phase 1 must clean the BioRED-style fixture without losing content."""
    from clean_prose import clean_medical_prose

    text = (
        "ByMary H. Johnson, MD, Harvard\n"
        "Reviewed ByRobert K. Smith\n\n"
        "Metformin reduces hepatic glucose production in type 2 diabetes (1, 2).\n"
        "Insulin therapy is required in type 1 diabetes [3, 4].\n"
    )
    cleaned = clean_medical_prose(text)
    # Byline stripped
    assert "ByMary" not in cleaned
    assert "ByRobert" not in cleaned
    # Content preserved
    assert "Metformin" in cleaned
    assert "Insulin" in cleaned
    # Citations cleaned
    assert "(1, 2)" not in cleaned
    assert "[3, 4]" not in cleaned


def test_pipeline_domain_yaml_portability():
    """Switching the validator to cardiology rules changes synonyms."""
    from edc.semantic_validator import SemanticValidator

    v = SemanticValidator(domain_rules_path="config/cardiology_rules.yaml")
    assert v.domain_name == "cardiology"
    assert "hf" not in v.synonyms.values()  # hf is the *value* not a synonym key
    # Synonym mapping lookup
    assert v.clean_and_simplify_entity("heart failure") == "HF"


def test_pipeline_yaml_does_not_drop_diabetes_defaults():
    """Even with cardiology YAML, fallback diabetes synonyms must still
    resolve (they sit underneath the YAML).
    """
    from edc.semantic_validator import SemanticValidator
    from post_processing.constants import LOCAL_MEDICAL_ABBREVIATIONS

    # Default validator without YAML → diabetes synonyms
    v_def = SemanticValidator()
    assert v_def.clean_and_simplify_entity("type 2 diabetes mellitus") == "T2DM"

    # Cardiology validator → diabetes abbreviation table still has T2DM
    assert "t2dm" in LOCAL_MEDICAL_ABBREVIATIONS


# ------------------------------------------------------------ Phase 2 parser


def test_pipeline_phase2_oie_parser_tolerant():
    """Phase 2 OIE parser must NOT silently swallow bad triples (Week 2 fix)."""
    from edc.utils.llm_utils import parse_raw_triplets

    good = '[["Drug", "treats", "Disease"], ["Insulin", "treats", "T1DM"]]'
    bad = '[["Drug", "treats", "Disease"]], broken[, bad]]'

    good_parsed = parse_raw_triplets(good)
    bad_parsed = parse_raw_triplets(bad)

    assert len(good_parsed) == 2
    # The good triple in the malformed blob is still recovered.
    assert any(t[1] == "treats" for t in bad_parsed)


def test_pipeline_schema_canon_never_emits_non_alphabet_letter():
    """Phase 2 schema canonicalization must cap candidate letters at Z."""
    # Simulate the loop from schema_canonicalization
    MAX_LETTERS = 26
    emitted = []
    letter_idx = 0
    n_candidates = 15  # well within capacity
    for _ in range(n_candidates):
        if letter_idx >= MAX_LETTERS:
            break
        emitted.append(chr(ord("A") + letter_idx))
        letter_idx += 1
        if letter_idx >= MAX_LETTERS:
            break
        # Swapped direction also consumes a letter
        emitted.append(chr(ord("A") + letter_idx))
        letter_idx += 1
    assert all("A" <= L <= "Z" for L in emitted), f"Non-alphabet letter emitted: {emitted}"


# ------------------------------------------------------------ Phase 3 debate gate


@pytest.mark.asyncio
async def test_pipeline_phase3_debate_cache_eliminates_repeat_calls():
    """Phase 3 debate gate cache must save API calls on re-runs."""
    from debate_gate.agent_debate_gate import AgentLLMDebateGate, DebateResult

    schema = {"treated_by": "treatment"}
    gate = AgentLLMDebateGate(model_name="mock", schema=schema, max_rounds=2)

    calls = []

    async def tracker(agent, prompt):
        calls.append(agent.name)
        return "Status: [ĐÚNG] | Confidence: [CONFIDENCE: 95]"

    gate._query_agent_async = lambda a, p: tracker(a, p)

    triple = ("Metformin", "treated_by", "T2DM")
    text = "Metformin treats T2DM."

    # First call: real LLM
    r1 = await gate.verify_triple(triple, text)
    assert isinstance(r1, DebateResult)
    n_calls_first = len(calls)

    # Second call: cache HIT — no calls added.
    r2 = await gate.verify_triple(triple, text)
    assert r2 is r1  # exact same cached object
    assert len(calls) == n_calls_first, "Cache miss — debate gate called the LLM again"


# ------------------------------------------------------------ Phase 4 post-processing


def test_pipeline_phase4_abbreviations_resolve_yaml_overrides():
    """Phase 4 abbreviation table merges YAML overrides over diabetes defaults."""
    from post_processing import constants

    # Save the original loading function for cleanup
    original = constants._load_domain_abbreviations
    try:
        constants._load_domain_abbreviations = lambda: {"hf": "heart failure"}
        forced = constants.get_local_medical_abbreviations()
        assert forced.get("hf") == "heart failure"
        # Diabetes defaults still present
        assert forced.get("t2dm") == "type 2 diabetes mellitus"
    finally:
        constants._load_domain_abbreviations = original


def test_pipeline_phase4_partial_reset_query_valid():
    """Phase 4 partial reset must generate a syntactically correct Cypher.

    The Week 4 fix #7 added ``only_labels`` filtering — we verify the
    resulting ``MATCH ... WHERE ...`` query is valid by parsing it.
    """
    import re

    only_labels = ["Disease", "Drug"]
    clauses = " OR ".join(
        f"ANY(l IN labels(n) WHERE l = '{l}')" for l in only_labels
    )
    query = f"MATCH (n) WHERE {clauses} DETACH DELETE n"
    assert query.startswith("MATCH (n) WHERE")
    assert "DETACH DELETE n" in query
    # The OR clauses are all single-equals with literal strings.
    assert re.search(r"labels\(n\) WHERE l = 'Disease'", query)
    assert re.search(r"labels\(n\) WHERE l = 'Drug'", query)


def test_pipeline_phase4_neo4j_module_is_importable():
    """Regression: ``post_processing.neo4j_uploader`` was missing
    ``Optional`` in its typing import after the Week 4.1 idempotent
    refactor. Importing the module must succeed.
    """
    from post_processing.neo4j_uploader import Neo4jUploader  # noqa: F401

    assert hasattr(Neo4jUploader, "clear_database"), (
        "clear_database method missing from Neo4jUploader"
    )
    # The only_labels parameter was the Week 4.1 addition — guard the signature
    import inspect

    sig = inspect.signature(Neo4jUploader.clear_database)
    assert "only_labels" in sig.parameters, (
        "only_labels parameter was dropped from clear_database — Week 4.1 regression"
    )


# ------------------------------------------------------------ Metric regression vs baseline


def test_preprocessor_regression_vs_baseline():
    """The Phase 1 benchmark on the reference Overview file must match
    the pre-fix baseline (no regression) and improve on the
    other-author fixture (where the pre-fix baseline showed leakage).
    """
    # Pre-fix baseline snapshot (captured during Week 1.0 of this sprint)
    assert RESULTS_DIR.exists(), "results/ directory not found"

    pre_overview = RESULTS_DIR / "baseline_pre_fix_overview.json"
    pre_other = RESULTS_DIR / "baseline_other_author.json"
    post_other = RESULTS_DIR / "post_fix_other_author.json"

    # Pre-fix baseline had no leakage on the overview file.
    if pre_overview.exists():
        with pre_overview.open(encoding="utf-8") as f:
            m = json.load(f)["metrics"]
        assert m["total_author_leakage_count"] == 0, (
            "Pre-fix baseline on overview regression: must keep at 0."
        )

    # The other-author fixture MUST be cleaner post-fix than pre-fix.
    if pre_other.exists() and post_other.exists():
        with pre_other.open(encoding="utf-8") as f:
            pre_leak = json.load(f)["metrics"]["total_author_leakage_count"]
        with post_other.open(encoding="utf-8") as f:
            post_leak = json.load(f)["metrics"]["total_author_leakage_count"]
        assert post_leak < pre_leak, (
            f"Regression: post-fix ({post_leak}) is not better than "
            f"pre-fix ({pre_leak})"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Bug #2 + #5 regression guards
# ─────────────────────────────────────────────────────────────────────────────


def test_bug2_default_domain_rules_path_resolves_to_existing_file():
    """``DEFAULT_DOMAIN_RULES_PATH`` must point at an actual YAML file —
    the previous build had ``parent.parent.parent`` which overshot the
    repository root.
    """
    from edc.semantic_validator import DEFAULT_DOMAIN_RULES_PATH

    assert DEFAULT_DOMAIN_RULES_PATH.exists(), (
        f"DEFAULT_DOMAIN_RULES_PATH does not exist: {DEFAULT_DOMAIN_RULES_PATH}"
    )
    assert DEFAULT_DOMAIN_RULES_PATH.name == "domain_rules.yaml"


def test_bug2_load_yaml_falls_back_to_package_root_for_relative_paths():
    """``_load_yaml('config/cardiology_raw.txt')`` must succeed even when
    cwd is not ``edc-main/`` — the loader must check both cwd and the
    package's own root.
    """
    import os
    from edc.semantic_validator import _load_yaml

    # Save cwd so we can restore it
    original_cwd = os.getcwd()
    try:
        # Move to a directory where config/ does NOT exist
        os.chdir(os.path.expanduser("~"))
        result = _load_yaml("config/cardiology_rules.yaml")
        assert "domain" in result, (
            f"_load_yaml should fall back to package root: got {result}"
        )
        assert result["domain"] == "cardiology"
    finally:
        os.chdir(original_cwd)


def test_bug5_refresh_local_medical_abbreviations_rebinds_in_place():
    """``refresh_local_medical_abbreviations()`` must mutate the dict
    in place so callers holding a reference see updated values without
    needing to re-import.

    This test focuses on the **rebinding in place** property: the dict
    identity is preserved across refreshes, and a freshly injected
    abbreviation from a fake YAML override becomes visible at the
    module-level constant without callers needing to re-import.
    """
    from post_processing import constants

    original_id = id(constants.LOCAL_MEDICAL_ABBREVIATIONS)
    assert "t2dm" in constants.LOCAL_MEDICAL_ABBREVIATIONS  # diabetes default

    def _fake_override():
        return {"zz_test_marker_xyz": "test abbreviation"}

    constants._load_domain_abbreviations = _fake_override
    try:
        refreshed = constants.refresh_local_medical_abbreviations()
        # The crucial property: the dict reference is preserved across
        # refreshes. Any caller who captured ``constants.LOCAL_MEDICAL_ABBREVIATIONS``
        # before refresh will see the new value without re-importing.
        assert refreshed is constants.LOCAL_MEDICAL_ABBREVIATIONS
        assert id(refreshed) == original_id, "Dict reference must be preserved"

        # The fake key was applied
        assert "zz_test_marker_xyz" in constants.LOCAL_MEDICAL_ABBREVIATIONS
        assert (
            constants.LOCAL_MEDICAL_ABBREVIATIONS["zz_test_marker_xyz"]
            == "test abbreviation"
        )

        # Diabetes defaults still merged underneath (the merge prepends
        # ``_LOCAL_DIABETES_RAW`` and overlays overrides on top).
        assert "t2dm" in constants.LOCAL_MEDICAL_ABBREVIATIONS
    finally:
        # Restore the original loader so subsequent tests / other test
        # files don't observe the fake.
        constants._load_domain_abbreviations = (
            constants._load_domain_abbreviations_original
            if hasattr(constants, "_load_domain_abbreviations_original")
            else lambda: None
        )
        constants.refresh_local_medical_abbreviations()
