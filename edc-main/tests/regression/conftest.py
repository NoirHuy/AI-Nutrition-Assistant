"""Pytest fixtures and configuration for regression tests.

Goals:
- Make every test deterministic: mock API keys so accidental calls blow up
  loudly instead of leaking real costs.
- Provide quick access to reference medical text fixtures.
"""

import os
import sys
from pathlib import Path

import pytest

# Add edc-main to sys.path so we can import edc.* modules
EDC_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(EDC_ROOT))
sys.path.insert(0, str(EDC_ROOT / "medical_preprocessing_pipeline"))

# Mark all tests in the regression folder so we can run them with
# `pytest tests/regression -m regression`
pytest_plugins = []


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "regression: deterministic regression tests"
    )
    # Provide a fake API key so any code path that *reads* the env does not
    # crash. Tests that actually need to LLM-call will use monkeypatched
    # fakes, NOT the real provider.
    os.environ.setdefault("OPENAI_API_KEY", "test-key-do-not-use")
    os.environ.setdefault("OPENROUTER_API_KEY", "test-key-do-not-use")
    os.environ.setdefault("GROQ_API_KEY", "test-key-do-not-use")


# --- Fixtures ----------------------------------------------------------------


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to the directory of fixed input/output fixtures."""
    return FIXTURES_DIR


@pytest.fixture
def biored_diabetes_sample_path() -> Path:
    """BioRED-style diabetes sample (small, deterministic)."""
    return FIXTURES_DIR / "biored_diabetes_sample.txt"


@pytest.fixture
def merck_diabetes_raw_path() -> Path:
    """Merck Manual-style raw diabetes article (includes author signature)."""
    return FIXTURES_DIR / "merck_diabetes_raw_by_other_author.txt"


@pytest.fixture
def merck_cardiology_raw_path() -> Path:
    """Merck Manual-style raw cardiology article (for portability testing)."""
    return FIXTURES_DIR / "merck_cardiology_raw.txt"


@pytest.fixture
def load_text_fixture():
    """Return a small loader that reads a fixture by name."""

    def _load(name: str) -> str:
        path = FIXTURES_DIR / name
        return path.read_text(encoding="utf-8")

    return _load
