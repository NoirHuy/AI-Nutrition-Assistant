"""Automated pre/post benchmark report for the 4-phase pipeline (Week 4).

Runs deterministic preprocessing benchmarks on a list of reference files and
emits:

1. A JSON report (``benchmark_report.json``) with metrics per file.
2. A Markdown report (``benchmark_report.md``) friendly to stakeholders.

All metrics come from the deterministic Phase-1 baseline benchmarks plus the
post-processing metric snapshots. We do NOT make live LLM calls — that is
the job of ``test_full_pipeline.py`` (which patches them).

Usage:
    python tests/regression/benchmark_report.py \
        --output-dir tests/regression/results \
        --files tests/regression/fixtures/merck_diabetes_raw.txt \
                tests/regression/fixtures/merck_cardiology_raw.txt
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Path setup so we can import clean_prose etc.
EDC_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(EDC_ROOT))
sys.path.insert(0, str(EDC_ROOT / "medical_preprocessing_pipeline"))

from baseline_preprocessor import run_benchmark  # noqa: E402


def _summarize_per_file(per_file_metrics):
    """Aggregate per-file metrics into headline numbers."""
    if not per_file_metrics:
        return {
            "files_run": 0,
            "avg_length_reduction_pct": 0.0,
            "total_author_leakage": 0,
            "total_noise_leakage": 0,
            "total_sentences": 0,
        }
    n = len(per_file_metrics)
    return {
        "files_run": n,
        "avg_length_reduction_pct": round(
            sum(m["length_reduction_ratio"] for m in per_file_metrics) / n * 100,
            2,
        ),
        "total_author_leakage": sum(m["total_author_leakage_count"] for m in per_file_metrics),
        "total_noise_leakage": sum(m["total_noise_leakage_count"] for m in per_file_metrics),
        "total_sentences": sum(m["sentence_count"] for m in per_file_metrics),
    }


def _load_pre_fix_baseline(results_dir):
    """Look for a pre-fix baseline JSON; returns ``None`` if missing."""
    candidate = Path(results_dir) / "baseline_pre_fix.json"
    if candidate.exists():
        return json.loads(candidate.read_text(encoding="utf-8"))
    return None


def _build_markdown(json_report, pre_baseline):
    """Render the JSON report as a Markdown table for stakeholders."""
    head = json_report["headline"]
    per_file = json_report["per_file"]

    lines = []
    lines.append("# Pipeline Regression Benchmark Report\n")
    lines.append(
        f"_Generated_: {json_report['timestamp']}\n"
    )
    lines.append(
        f"_Files run_: {head['files_run']}\n"
    )

    lines.append("## Headline Metrics\n")
    lines.append("| Metric | Post-fix |")
    lines.append("|---|---|")
    lines.append(f"| Avg length reduction | {head['avg_length_reduction_pct']}% |")
    lines.append(f"| Total author leakage | {head['total_author_leakage']} |")
    lines.append(f"| Total noise leakage | {head['total_noise_leakage']} |")
    lines.append(f"| Total sentences | {head['total_sentences']} |")

    if pre_baseline is not None:
        pre = pre_baseline["metrics"]
        lines.append("\n## Pre-fix vs Post-fix\n")
        lines.append("| Metric | Pre-fix | Post-fix | Δ |")
        lines.append("|---|---|---|---|")
        delta_a = head["total_author_leakage"] - pre["total_author_leakage_count"]
        delta_n = head["total_noise_leakage"] - pre["total_noise_leakage_count"]
        lines.append(
            f"| Author leakage | {pre['total_author_leakage_count']} | "
            f"{head['total_author_leakage']} | {delta_a:+d} |"
        )
        lines.append(
            f"| Noise leakage | {pre['total_noise_leakage_count']} | "
            f"{head['total_noise_leakage']} | {delta_n:+d} |"
        )

    lines.append("\n## Per-file\n")
    lines.append("| File | Length Reduction | Sentences | Author Leakage | Noise Leakage |")
    lines.append("|---|---|---|---|---|")
    for p in per_file:
        name = os.path.basename(p["file"])
        m = p["metrics"]
        lines.append(
            f"| {name} | {m['length_reduction_ratio']*100:.1f}% | "
            f"{m['sentence_count']} | {m['total_author_leakage_count']} | "
            f"{m['total_noise_leakage_count']} |"
        )

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Generate pre/post benchmark report")
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to write benchmark_report.{json,md} into",
    )
    parser.add_argument(
        "--files",
        nargs="+",
        required=True,
        help="One or more raw text files to benchmark",
    )
    parser.add_argument(
        "--label",
        default="post_fix",
        choices=["post_fix", "pre_fix"],
        help="Label stored in the JSON. Use 'post_fix' by default.",
    )
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    per_file = []
    for fpath in args.files:
        report_path = out_dir / f"per_file_{Path(fpath).stem}.json"
        report = run_benchmark(fpath, str(report_path))
        per_file.append({
            "file": fpath,
            "metrics": report["metrics"],
            "sample_leakage": report.get("sample_leakage", []),
        })

    headline = _summarize_per_file([p["metrics"] for p in per_file])

    json_report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "label": args.label,
        "headline": headline,
        "per_file": per_file,
    }

    # JSON output
    label_suffix = "" if args.label == "post_fix" else "_" + args.label
    json_path = out_dir / f"benchmark_report{label_suffix}.json"
    json_path.write_text(
        json.dumps(json_report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Markdown output (only for post_fix to avoid clobbering baseline md)
    md_path = out_dir / "benchmark_report.md"
    pre_baseline = _load_pre_fix_baseline(out_dir)
    md_path.write_text(_build_markdown(json_report, pre_baseline), encoding="utf-8")

    print(f"JSON  report: {json_path}")
    print(f"Markdown report: {md_path}")
    print(f"Files run: {headline['files_run']}")
    print(f"Avg length reduction: {headline['avg_length_reduction_pct']}%")
    print(f"Total author leakage: {headline['total_author_leakage']}")
    print(f"Total noise leakage: {headline['total_noise_leakage']}")


if __name__ == "__main__":
    main()
