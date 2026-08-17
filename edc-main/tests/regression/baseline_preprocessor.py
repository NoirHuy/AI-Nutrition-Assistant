"""Baseline benchmark for Phase 1 preprocessing.

Measures deterministic quality metrics on a set of reference files BEFORE
and AFTER the fixes. Outputs a JSON report that gets compared against
post-fix results.

Metrics:
- noise_leakage: count of web-scraping noise patterns still present in output
- sentence_count: number of sentences after split
- author_metadata_leakage: count of "ByErika", "Reviewed ByGlenn" patterns
- empty_paragraph_ratio: ratio of empty paragraphs to total paragraphs

Usage:
    python tests/regression/baseline_preprocessor.py \
        --input edc-main/datasets/disease/diabetes/merckmanuals_professionl_version/Type_2_Diabetes_Mellitus.txt \
        --output tests/regression/results/baseline_pre_fix.json
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure we can import the clean_prose module
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "medical_preprocessing_pipeline"))

from clean_prose import clean_medical_prose


# Patterns the clean_prose SHOULD remove but currently misses
AUTHOR_PATTERNS = [
    re.compile(r"\bBy[A-Z][a-z]+\b"),          # ByErika, ByMary
    re.compile(r"\bReviewed\s+By[A-Z][a-z]+"), # Reviewed ByGlenn
    re.compile(r"\bByErika\b"),
    re.compile(r"\bReviewed\s+By[A-Z]\.\s*[A-Z][a-z]+"),  # Reviewed ByA. Smith
]

# Patterns that SHOULD be removed (already covered by clean_prose)
KNOWN_NOISE_PATTERNS = [
    re.compile(r"^\s*\|\s*$", re.MULTILINE),
    re.compile(r"^\s*View Patient Education", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*Multimedia\s*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*Disclaimer\s*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*follow us on", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*Copyright", re.MULTILINE | re.IGNORECASE),
]

# Real biomedical content (should NOT be removed)
REAL_CONTENT_PATTERNS = [
    re.compile(r"\bdiabetes mellitus\b", re.IGNORECASE),
    re.compile(r"\binsulin\b", re.IGNORECASE),
    re.compile(r"\bglucose\b", re.IGNORECASE),
]


def count_pattern_matches(text: str, patterns: list[re.Pattern]) -> dict:
    """Return count of matches per pattern label."""
    counts = {}
    for pat in patterns:
        label = pat.pattern[:30]
        counts[label] = len(pat.findall(text))
    return counts


def compute_metrics(input_text: str, output_text: str) -> dict:
    """Compute deterministic quality metrics on input/output pair."""
    # Leakage: noise patterns that survived
    author_leakage = count_pattern_matches(output_text, AUTHOR_PATTERNS)
    noise_leakage = count_pattern_matches(output_text, KNOWN_NOISE_PATTERNS)

    # Sentence counting (very simple heuristic)
    sentences = re.split(r"(?<=[.!?])\s+", output_text.strip())
    sentence_count = len([s for s in sentences if s.strip()])

    # Empty paragraph ratio
    paragraphs = [p for p in output_text.split("\n\n") if p.strip()]
    empty_paragraphs = len([p for p in output_text.split("\n\n") if not p.strip()])
    total_paragraphs = len(paragraphs) + empty_paragraphs
    empty_ratio = empty_paragraphs / total_paragraphs if total_paragraphs > 0 else 0.0

    # Real content preservation
    real_content_present = count_pattern_matches(output_text, REAL_CONTENT_PATTERNS)

    return {
        "input_length": len(input_text),
        "output_length": len(output_text),
        "length_reduction_ratio": 1 - (len(output_text) / max(len(input_text), 1)),
        "sentence_count": sentence_count,
        "empty_paragraph_ratio": round(empty_ratio, 4),
        "author_metadata_leakage": author_leakage,
        "noise_leakage": noise_leakage,
        "real_content_present": real_content_present,
        "total_author_leakage_count": sum(author_leakage.values()),
        "total_noise_leakage_count": sum(noise_leakage.values()),
    }


def run_benchmark(input_path: str, output_path: str) -> dict:
    """Run baseline benchmark on a single file."""
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    with open(input_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    # Step 1: Apply current clean_medical_prose
    cleaned = clean_medical_prose(raw_text)

    # Step 2: Compute metrics
    metrics = compute_metrics(raw_text, cleaned)

    # Step 3: Aggregate report
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_file": input_path,
        "clean_prose_version": "baseline (pre-fix)",
        "metrics": metrics,
        "sample_leakage": _extract_leakage_samples(raw_text, cleaned),
    }

    # Step 4: Save
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return report


def _extract_leakage_samples(raw_text: str, cleaned: str, max_samples: int = 5) -> list:
    """Return a few sample lines that contain leakage patterns."""
    samples = []
    for line in cleaned.split("\n"):
        for pat in AUTHOR_PATTERNS:
            if pat.search(line):
                samples.append(line.strip()[:120])
                break
        if len(samples) >= max_samples:
            break
    return samples


def main():
    parser = argparse.ArgumentParser(description="Phase 1 baseline benchmark")
    parser.add_argument("--input", required=True, help="Path to raw medical text file")
    parser.add_argument("--output", required=True, help="Path to output JSON report")
    args = parser.parse_args()

    try:
        report = run_benchmark(args.input, args.output)
        metrics = report["metrics"]
        print("=" * 60)
        print(f"Baseline Benchmark (pre-fix): {args.input}")
        print("=" * 60)
        print(f"Input length:  {metrics['input_length']} chars")
        print(f"Output length: {metrics['output_length']} chars")
        print(f"Reduction:     {metrics['length_reduction_ratio'] * 100:.1f}%")
        print(f"Sentences:     {metrics['sentence_count']}")
        print(f"Author leakage: {metrics['total_author_leakage_count']}")
        print(f"Noise leakage:  {metrics['total_noise_leakage_count']}")
        if report["sample_leakage"]:
            print("Sample leakage lines:")
            for s in report["sample_leakage"]:
                print(f"  - {s}")
        print(f"\nReport saved to: {args.output}")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
