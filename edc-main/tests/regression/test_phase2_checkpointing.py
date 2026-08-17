"""Unit tests for the ``_maybe_write_checkpoint`` helper (Week 2 fix).

We re-implement the helper inline to keep this test independent of the
torch / datasets / accelerate dependency chain required by
``edc_framework``. The two implementations MUST be kept in sync; if the
real helper diverges, this test should be updated.
"""

import json
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.regression


def _maybe_write_checkpoint(checkpoint_dir, stage_name, input_text_list,
                            oie_raw_list, oie_triplets_list, extra=None):
    """Mirror of edc_framework.EDC._maybe_write_checkpoint."""
    if not checkpoint_dir:
        return None
    payload = {
        "stage": stage_name,
        "n_items": len(input_text_list),
        "oie_raw": oie_raw_list,
        "oie_validated": oie_triplets_list,
        "input_previews": [t[:120] for t in input_text_list],
    }
    if extra:
        payload.update(extra)
    out_path = os.path.join(checkpoint_dir, f"result_at_each_stage_partial__{stage_name}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return out_path


def test_checkpoint_skipped_when_disabled(tmp_path):
    """If ``checkpoint_dir`` is None/Falsy, no file is written."""
    result = _maybe_write_checkpoint(None, "stage_x", ["a", "b"], [], [])
    assert result is None


def test_checkpoint_writes_payload_with_expected_keys(tmp_path):
    """When enabled, the file contains the stage name and the triples."""
    out = _maybe_write_checkpoint(
        str(tmp_path),
        "after_validation",
        ["some text", "more text"],
        [[["S", "R", "O"]]] * 2,
        [[["S2", "R2", "O2"]]] * 2,
        extra={"canon_triplets": [["A"]]},
    )
    assert out is not None
    assert Path(out).exists()
    data = json.loads(Path(out).read_text(encoding="utf-8"))
    assert data["stage"] == "after_validation"
    assert data["n_items"] == 2
    assert "canon_triplets" in data
    assert len(data["oie_validated"]) == 2


def test_checkpoint_filename_contains_stage(tmp_path):
    """The filename encodes the stage for later resumption."""
    out = _maybe_write_checkpoint(str(tmp_path), "after_canonicalization", ["x"], [], [])
    assert "after_canonicalization" in out
