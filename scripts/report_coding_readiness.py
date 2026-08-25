#!/usr/bin/env python3
"""Report v1 Coding Agent capability readiness separately from legacy EDA smoke."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gv100h.coding_eval.single_pair_runner import run_single_ab_pair


CANONICAL_CASE_IDS = tuple(
    f"AGENT-CODE-{index:03d}" for index in range(1, 6)
)


def _load_case(case_path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(case_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"case is not a mapping: {case_path}")
    return payload


def _manifest_summary(result: dict[str, Any]) -> dict[str, Any]:
    manifests = result.get("manifests", [])
    statuses = [manifest.outcome.status for manifest in manifests]
    profiles = []
    for manifest in manifests:
        arm = getattr(manifest, "experiment_arm", None)
        bundle = result.get("bundle_dirs", {}).get(arm) if arm else None
        verification_path = Path(bundle) / "verification.json" if bundle else None
        if verification_path and verification_path.is_file():
            verification = json.loads(verification_path.read_text(encoding="utf-8"))
            profiles.append(verification.get("validator_profile"))
        else:
            profiles.append(getattr(manifest.evidence, "validator_profile", None))
    ready = (
        len(manifests) == 2
        and all(status == "pass" for status in statuses)
        and profiles == ["lightweight", "lightweight"]
    )
    return {
        "status": "READY" if ready else "NOT_READY",
        "manifest_count": len(manifests),
        "manifest_statuses": statuses,
        "validator_profiles": profiles,
        "evidence_class": result.get("evidence_class"),
        "qualification_decision": result.get("qualification_decision"),
    }


def assess_case(
    *,
    case_path: Path,
    repo_root: Path,
    mode: str,
    model_id: str,
) -> dict[str, Any]:
    case_id = case_path.stem
    try:
        case = _load_case(case_path)
        if case.get("id") != case_id:
            raise ValueError(
                f"case id {case.get('id')!r} does not match filename {case_id!r}"
            )
        if case.get("validator_profile") != "lightweight":
            raise ValueError("canonical coding case must declare lightweight profile")
        with tempfile.TemporaryDirectory(prefix="coding_readiness_") as output_dir:
            result = run_single_ab_pair(
                task_id=case_id,
                case_path=case_path,
                repetition=1,
                mode=mode,
                output_dir=Path(output_dir),
                repo_root=repo_root,
                model_id=model_id,
            )
            summary = _manifest_summary(result)
        return {"case_id": case_id, **summary}
    except Exception as exc:
        return {
            "case_id": case_id,
            "status": "NOT_READY",
            "error": f"{type(exc).__name__}: {exc}",
        }


def build_report(
    *,
    cases_dir: Path,
    repo_root: Path,
    mode: str,
    model_id: str,
) -> dict[str, Any]:
    cases = {
        case_id: cases_dir / f"{case_id}.yaml"
        for case_id in CANONICAL_CASE_IDS
    }
    results = []
    for case_id in CANONICAL_CASE_IDS:
        case_path = cases[case_id]
        if not case_path.is_file():
            results.append({
                "case_id": case_id,
                "status": "NOT_READY",
                "error": f"missing canonical case: {case_path}",
            })
            continue
        results.append(
            assess_case(
                case_path=case_path,
                repo_root=repo_root,
                mode=mode,
                model_id=model_id,
            )
        )
    overall_status = (
        "READY" if all(item["status"] == "READY" for item in results) else "NOT_READY"
    )
    return {
        "report_type": "v1_coding_agent_capability_readiness",
        "status": overall_status,
        "mode": mode,
        "cases": results,
        "claim_ceiling": "readiness_report_only; not_model_or_hardware_qualification",
        "not_claimed": [
            "live_model_inference",
            "hardware_qualification",
            "qualification_GO",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report v1 Coding Agent readiness without changing legacy CI status."
    )
    parser.add_argument("--cases-dir", type=Path, default=Path("benchmarks/cases"))
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--mode", choices=["mock", "live"], default="mock")
    parser.add_argument("--model-id", default="Qwen/Qwen3.8-27B")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--fail-on-not-ready",
        action="store_true",
        help="Return 1 when readiness is NOT_READY; default is report-only.",
    )
    args = parser.parse_args()

    report = build_report(
        cases_dir=args.cases_dir,
        repo_root=args.repo_root.resolve(),
        mode=args.mode,
        model_id=args.model_id,
    )
    serialized = json.dumps(report, indent=2, sort_keys=True)
    print(serialized)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    if args.fail_on_not_ready and report["status"] != "READY":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())