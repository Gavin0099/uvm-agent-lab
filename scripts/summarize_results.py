#!/usr/bin/env python3
"""
Summarize Benchmark Execution Results into Markdown and JSON Leaderboards.
"""

import argparse
import json
import sys
from pathlib import Path


def summarize_results(results_dir: str, output_md: str = None):
    res_path = Path(results_dir)
    json_files = sorted(list(res_path.glob("*_result.json")))

    if not json_files:
        print(f"No result files found in {results_dir}")
        return

    results = []
    for f in json_files:
        try:
            with open(f, "r", encoding="utf-8") as jf:
                results.append(json.load(jf))
        except Exception:
            continue

    total_cases = len(results)
    passed_cases = sum(1 for r in results if r.get("metrics", {}).get("task_success", False))
    gov_passed = sum(1 for r in results if r.get("governance_status", {}).get("passed", False))
    avg_score = sum(r.get("metrics", {}).get("total_score", 0.0) for r in results) / max(1, total_cases)

    # Generate Markdown Table
    md_lines = [
        "# Benchmark Execution Summary",
        "",
        f"- **Total Cases**: {total_cases}",
        f"- **Task Success Rate**: {passed_cases}/{total_cases} ({passed_cases/max(1, total_cases)*100:.1f}%)",
        f"- **Governance Compliance**: {gov_passed}/{total_cases} ({gov_passed/max(1, total_cases)*100:.1f}%)",
        f"- **Average Score**: {avg_score:.2f} / 100",
        "",
        "## Detailed Results Table",
        "",
        "| Case ID | Runner | Comp | Sim | Evid Score | Gov Status | Total Score | Status |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    ]

    for r in results:
        cid = r.get("case_id", "N/A")
        runner = r.get("runner_name", "N/A")
        comp = r.get("execution", {}).get("compile_status", "N/A")
        sim = r.get("execution", {}).get("simulation_status", "N/A")
        evid_score = r.get("metrics", {}).get("evidence_score", 0.0)
        gov_ok = "PASS" if r.get("governance_status", {}).get("passed") else "VIOLATION"
        score = r.get("metrics", {}).get("total_score", 0.0)
        status = "PASSED" if r.get("metrics", {}).get("task_success") else "FAILED"

        md_lines.append(f"| `{cid}` | {runner} | {comp} | {sim} | {evid_score:.1f} | {gov_ok} | **{score:.1f}** | {status} |")

    report_content = "\n".join(md_lines)
    print(report_content)

    if output_md:
        with open(output_md, "w", encoding="utf-8") as f:
            f.write(report_content)
        print(f"\nSaved summary report to {output_md}")


def main():
    parser = argparse.ArgumentParser(description="Summarize Benchmark Run Results")
    parser.add_argument("--results-dir", default="results", help="Directory with result JSONs")
    parser.add_argument("--output-md", help="Path to save summary markdown report")
    args = parser.parse_args()

    summarize_results(args.results_dir, args.output_md)


if __name__ == "__main__":
    main()
