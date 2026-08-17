"""Regression tests for Phase 3 — Debate Gate (Week 3 fixes).

Tests the new features added to ``AgentLLMDebateGate``:
1. Diversified sampling temperatures per agent (fix #6: groupthink mitigation)
2. Anti-conformity prompt template (do NOT change verdict on mere agreement)
3. Per-triple cache (fix: reduce API costs on re-runs)
4. End-to-end debate with a mocked LLM that returns scripted responses
"""

import asyncio
import sys
import os
from pathlib import Path

import pytest

# Add edc-main so we can import debate_gate
EDC_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(EDC_ROOT))

# Disable verbose logging during the tests so output stays readable
import logging
logging.disable(logging.CRITICAL)

from debate_gate.agent_debate_gate import (  # noqa: E402
    AgentLLMDebateGate,
    AgentPersona,
    ResponseParser,
    Verdict,
    DebateResult,
)


# ----------------------------------------------------------------- fixtures


@pytest.fixture
def debate_gate():
    schema = {
        "treated_by": "Subject disease is managed by Object drug/therapy",
        "has_adverse_effect": "Subject drug causes Object adverse event",
        "is_a": "Subject is a subtype/instance of Object",
    }
    return AgentLLMDebateGate(model_name="mock-model", schema=schema, max_rounds=2)


# ────────────────────────────────────────────────────────────────── W3.1


def test_agents_have_diversified_temperatures(debate_gate):
    """W3 fix #6: Clinical_Specialist / Ontology_Inspector must NOT be
    identical — they should differ from Medical_Skeptic to break groupthink.
    """
    by_name = {a.name: a for a in debate_gate.agents}

    assert by_name["Clinical_Specialist"].temperature == 0.2
    assert by_name["Ontology_Inspector"].temperature == 0.2
    assert by_name["Medical_Skeptic"].temperature == 0.5

    # Medical_Skeptic must differ from the other two (greater diversity).
    assert by_name["Medical_Skeptic"].temperature != by_name["Clinical_Specialist"].temperature
    assert by_name["Medical_Skeptic"].temperature != by_name["Ontology_Inspector"].temperature

    # And the two factual agents may be equal — that's intentional.
    # But the gap between factual and critic should be ≥ 0.3 to actually
    # change the output distribution.
    assert (
        by_name["Medical_Skeptic"].temperature - by_name["Clinical_Specialist"].temperature >= 0.3
    ), "Diversity gap too small — likely to keep producing groupthink"


# ────────────────────────────────────────────────────────────────── W3.2


def test_anti_conformity_clause_in_debate_prompt(debate_gate):
    """The debate prompt must include the anti-conformity clause."""
    # Get the module-level template
    from debate_gate.agent_debate_gate import _DEBATE_USER_TEMPLATE
    assert "CONCRETE factual error" in _DEBATE_USER_TEMPLATE
    assert "Mere agreement is not evidence" in _DEBATE_USER_TEMPLATE


# ────────────────────────────────────────────────────────────────── W3.3


def test_per_triple_cache_hit(debate_gate):
    """Calling verify_triple twice on the same triple should hit the cache
    on the second call and NOT make any extra LLM API calls.
    """
    triple = ("Metformin", "treated_by", "Type 2 diabetes")
    cached = DebateResult(
        triple=triple, accepted=True, fcs_score=85.0, vetoed=False,
        veto_agent=None, rounds_completed=1, consensus_reached=True,
        elapsed_seconds=0.1,
    )
    debate_gate._cache[(triple[0].lower(), triple[1].lower(), triple[2].lower())] = cached

    out = asyncio.run(debate_gate.verify_triple(triple, "Metformin is used for T2DM."))
    assert out is cached, "Cache MISS — expected the cached DebateResult to be returned verbatim"
    assert debate_gate._stats["cache_hits"] >= 1


def test_per_triple_cache_case_insensitive(debate_gate):
    """Cache key normalisation: 'Metformin', 'TREATED_BY', 'Type 2 Diabetes'
    and 'metformin', 'treated_by', 'type 2 diabetes' should all hit the same
    cache slot.
    """
    cached = DebateResult(
        triple=("X", "Y", "Z"), accepted=True, fcs_score=80.0, vetoed=False,
        veto_agent=None, rounds_completed=1, consensus_reached=True, elapsed_seconds=0.1,
    )
    debate_gate._cache[("metformin", "treated_by", "type 2 diabetes")] = cached

    out = asyncio.run(debate_gate.verify_triple(
        ("Metformin", "TREATED_BY", "Type 2 Diabetes"),
        "Context.",
    ))
    assert out is cached


# ────────────────────────────────────────────────────────────────── W3.4: end-to-end with mock LLM


class _ScriptedLLM:
    """Mock LLM that returns the next pre-canned response for each agent
    call (round, agent_name) → verbatim response string.
    """

    def __init__(self, scripts):
        # scripts: dict (round_num, agent_name) -> raw_response
        self.scripts = scripts
        self.calls = []  # log of (round, agent) for verification

    async def __call__(self, gate, agent, prompt):
        # Determine which round we're in by looking at prompt content
        # Round 1 prompts do NOT contain "Other Agents' Assessments"
        round_num = 2 if "Other Agents' Assessments" in prompt else 1
        self.calls.append((round_num, agent.name))
        key = (round_num, agent.name)
        return self.scripts.get(key, "Status: [UNCERTAIN] | Confidence: [CONFIDENCE: 30]")


@pytest.mark.asyncio
async def test_end_to_end_correct_triple_accepted(debate_gate):
    """Test 1: ground-truth correct triple → accepted with FCS > 80."""

    scripts = {
        (1, "Clinical_Specialist"):    "Text...\nTrạng thái: [ĐÚNG] | Độ tin cậy: [ĐỘ_TIN_CẬY: 92]",
        (1, "Ontology_Inspector"):     "Text...\nTrạng thái: [ĐÚNG] | Độ tin cậy: [ĐỘ_TIN_CẬY: 88]",
        (1, "Medical_Skeptic"):        "Text...\nTrạng thái: [ĐÚNG] | Độ tin cậy: [ĐỘ_TIN_CẬY: 80]",
    }

    # Patch the LLM call path
    async def _patched(agent, prompt):
        round_num = 2 if "Other Agents' Assessments" in prompt else 1
        return scripts[(round_num, agent.name)]

    debate_gate._query_agent_async = lambda a, p: _patched(a, p)

    result = await debate_gate.verify_triple(
        ("Metformin", "treated_by", "Type 2 Diabetes"),
        "Metformin is a first-line therapy for Type 2 Diabetes.",
    )
    assert result.accepted is True
    assert result.vetoed is False
    assert result.fcs_score > 80, f"Expected FCS > 80, got {result.fcs_score}"
    assert result.consensus_reached is True


@pytest.mark.asyncio
async def test_end_to_end_incorrect_triple_vetoed(debate_gate):
    """Test 2: ground-truth wrong triple → vetoed or rejected with low FCS."""
    scripts = {
        (1, "Clinical_Specialist"):    "Text...\nTrạng thái: [SAI] | Độ tin cậy: [ĐỘ_TIN_CẬY: 80]",
        (1, "Ontology_Inspector"):     "Text...\nTrạng thái: [SAI] | Độ tin cậy: [ĐỘ_TIN_CẬY: 85]",
        (1, "Medical_Skeptic"):        "Text...\nTrạng thái: [SAI] | Độ tin cậy: [ĐỘ_TIN_CẬY: 90]",
    }

    async def _patched(agent, prompt):
        round_num = 2 if "Other Agents' Assessments" in prompt else 1
        return scripts[(round_num, agent.name)]

    debate_gate._query_agent_async = lambda a, p: _patched(a, p)

    result = await debate_gate.verify_triple(
        ("Insulin", "is_a", "30 minutes"),
        "Insulin begins working within 30 minutes.",
    )
    assert result.accepted is False
    assert result.vetoed is True, "Should have triggered veto"
    assert result.veto_agent is not None
    assert result.fcs_score < 80


@pytest.mark.asyncio
async def test_end_to_end_ambiguous_triple_uncertain_no_crash(debate_gate):
    """Test 3: ambiguous triple → at least one UNCERTAIN; never crashes."""
    scripts = {
        (1, "Clinical_Specialist"):    "Text...\nTrạng thái: [KHÔNG_CHẮC_CHẮN] | Độ tin cậy: [ĐỘ_TIN_CẬY: 50]",
        (1, "Ontology_Inspector"):     "Text...\nTrạng thái: [ĐÚNG] | Độ tin cậy: [ĐỘ_TIN_CẬY: 65]",
        (1, "Medical_Skeptic"):        "Text...\nTrạng thái: [KHÔNG_CHẮC_CHẮN] | Độ tin cậy: [ĐỘ_TIN_CẬY: 45]",
    }

    async def _patched(agent, prompt):
        round_num = 2 if "Other Agents' Assessments" in prompt else 1
        return scripts[(round_num, agent.name)]

    debate_gate._query_agent_async = lambda a, p: _patched(a, p)

    result = await debate_gate.verify_triple(
        ("Patient", "treated_by", "Insulin pump"),
        "Some patient on insulin pump ...",
    )
    # Just doesn't crash; some verdict produced
    assert result.fcs_score >= 0
    assert isinstance(result.accepted, bool)


@pytest.mark.asyncio
async def test_cache_hit_saves_api_calls(debate_gate):
    """Test 4: pre-seeding the cache yields a cache HIT without any agent call."""
    triple = ("X", "treated_by", "Y")
    cached = DebateResult(
        triple=triple, accepted=True, fcs_score=85.0, vetoed=False,
        veto_agent=None, rounds_completed=1, consensus_reached=True, elapsed_seconds=0.05,
    )
    debate_gate._cache[(triple[0].lower(), triple[1].lower(), triple[2].lower())] = cached

    calls = []
    async def _tracking(agent, prompt):
        calls.append(agent.name)
        return "Status: [ĐÚNG] | Confidence: [CONFIDENCE: 99]"

    debate_gate._query_agent_async = lambda a, p: _tracking(a, p)

    # Call verify_triple directly — should hit cache and not call any agent
    out = await debate_gate.verify_triple(triple, "...")
    assert out is cached, "Expected cache hit"
    assert calls == [], f"Cache miss — recorded LLM calls: {calls}"


# ─────────────────────────────────────────────────────────────────────────────
# Bug #4 regression: bounded LRU cache + clear_cache() public API
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cache_is_bounded_by_max_size():
    """The per-triple cache must evict LRU entries beyond ``max_cache_size``
    so a long-running extraction cannot exhaust memory."""
    from debate_gate.agent_debate_gate import AgentLLMDebateGate

    gate = AgentLLMDebateGate(
        model_name="mock",
        schema={"treated_by": "t"},
        max_rounds=1,
    )
    # Force a tiny cache for the test
    gate._cache_max_size = 3

    async def _scripted(agent, prompt):
        return "Status: [ĐÚNG] | Confidence: [CONFIDENCE: 90]"

    gate._query_agent_async = lambda a, p: _scripted(a, p)

    # Verify 5 unique triples — the first 2 must be evicted
    for i in range(5):
        await gate.verify_triple((f"S{i}", "treated_by", f"O{i}"), "ctx")

    info = gate.cache_info()
    assert info["size"] <= info["max_size"] <= 3, (
        f"Cache exceeded bound: {info}"
    )
    assert info["size"] == 3, f"Expected 3 entries after eviction, got {info['size']}"
    # The 2 oldest triples (S0, S1) must have been evicted, while the
    # 3 newest (S2, S3, S4) remain.
    keys = list(gate._cache.keys())
    assert ("s2", "treated_by", "o2") in keys
    assert ("s3", "treated_by", "o3") in keys
    assert ("s4", "treated_by", "o4") in keys
    assert ("s0", "treated_by", "o0") not in keys
    assert ("s1", "treated_by", "o1") not in keys


@pytest.mark.asyncio
async def test_clear_cache_resets_state():
    """``clear_cache()`` must drop all entries AND reset hit/miss counters."""
    from debate_gate.agent_debate_gate import AgentLLMDebateGate

    gate = AgentLLMDebateGate(model_name="mock", schema={"x": "y"}, max_rounds=1)

    async def _ok(agent, prompt):
        return "Status: [ĐÚNG] | Confidence: [CONFIDENCE: 90]"

    gate._query_agent_async = lambda a, p: _ok(a, p)

    # Populate cache
    for i in range(3):
        await gate.verify_triple((f"A{i}", "x", f"B{i}"), "ctx")

    assert gate.cache_info()["size"] == 3
    assert gate._stats["cache_misses"] >= 3

    gate.clear_cache()

    assert gate.cache_info()["size"] == 0
    assert gate._stats["cache_hits"] == 0
    assert gate._stats["cache_misses"] == 0


@pytest.mark.asyncio
async def test_cache_hit_marks_lru_position():
    """Re-accessing an older entry promotes it to most-recently-used so
    it survives subsequent evictions."""
    from debate_gate.agent_debate_gate import AgentLLMDebateGate

    gate = AgentLLMDebateGate(model_name="mock", schema={"x": "y"}, max_rounds=1)
    gate._cache_max_size = 3

    async def _ok(agent, prompt):
        return "Status: [ĐÚNG] | Confidence: [CONFIDENCE: 90]"

    gate._query_agent_async = lambda a, p: _ok(a, p)

    # Fill with 3 entries
    for i in range(3):
        await gate.verify_triple((f"S{i}", "x", f"O{i}"), "ctx")

    # Re-touch S0 — should move to MRU end
    r0 = await gate.verify_triple(("S0", "x", "O0"), "ctx")
    assert r0.accepted

    # Add S3 — should evict S1 (oldest after touching S0)
    await gate.verify_triple(("S3", "x", "O3"), "ctx")

    keys = list(gate._cache.keys())
    assert ("s0", "x", "o0") in keys, "S0 should be promoted, not evicted"
    assert ("s1", "x", "o1") not in keys, "S1 should be evicted as oldest"
