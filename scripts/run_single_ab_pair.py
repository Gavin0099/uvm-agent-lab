#!/usr/bin/env python3
"""Thin CLI for the 1 task × 1 repetition × 2 arms production slice."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gv100h.coding_eval.single_pair_runner import run_single_ab_pair


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one UVM task for one repetition across both A/B arms."
    )
    parser.add_argument("--task-id", default="UVM-001")
    parser.add_argument(
        "--case-path",
        default=str(PROJECT_ROOT / "benchmarks" / "cases" / "UVM-001.yaml"),
    )
    parser.add_argument("--repetition", type=int, default=1)
    parser.add_argument("--mode", choices=["live", "mock"], default="mock")
    parser.add_argument("--output-dir", default="results/single_ab_pair")
    parser.add_argument("--model-id", default="Qwen/Qwen3.8-27B")
    parser.add_argument("--runtime", choices=["llama.cpp", "vllm", "sglang", "transformers"], default=None)
    parser.add_argument("--quantization", choices=["Q4_K_M", "Q8_0", "AWQ_4BIT", "GPTQ_4BIT", "FP16", "FP8"], default=None)
    parser.add_argument("--model-hash", default=None)
    parser.add_argument("--model-artifact-path", default=None)
    parser.add_argument("--runtime-commit", default=None)
    parser.add_argument("--api-base", default="http://localhost:8000/v1")
    args = parser.parse_args()

    result = run_single_ab_pair(
        task_id=args.task_id,
        case_path=args.case_path,
        repetition=args.repetition,
        mode=args.mode,
        output_dir=args.output_dir,
        repo_root=PROJECT_ROOT,
        model_id=args.model_id,
        api_base=args.api_base,
        runtime=args.runtime,
        quantization=args.quantization,
        model_hash=args.model_hash,
        model_artifact_path=args.model_artifact_path,
        runtime_commit=args.runtime_commit,
    )
    printable = {
        "task_id": result["task_id"],
        "repetition": result["repetition"],
        "pair_id": result["pair_id"],
        "universe_complete_claim_allowed": result["universe_complete_claim_allowed"],
        "admissible_for_model_qualification": result["admissible_for_model_qualification"],
        "evidence_class": result["evidence_class"],
        "qualification_decision": result["qualification_decision"],
        "bundle_dirs": {arm: str(path) for arm, path in result["bundle_dirs"].items()},
    }
    print(json.dumps(printable, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
