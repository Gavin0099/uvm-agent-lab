#!/usr/bin/env python3
"""
Deprecated live-eval entrypoint.

This file is retained so historical imports and source-level citations do not
break. It is not a governed A/B pipeline and must not be used as a second
evidence path beside gv100h.coding_eval.single_pair_runner.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gv100h.manifests.models import GV100HRunManifest

DEPRECATED_MSG = (
    "scripts.run_live_eval.run_live_evaluation is deprecated and is not a "
    "governed evidence-integrity pipeline. Use "
    "gv100h.coding_eval.single_pair_runner.run_single_ab_pair / "
    "scripts/run_single_ab_pair.py."
)


def run_live_evaluation(
    api_base: str,
    model_id: str,
    cases_dir: str,
    output_dir: str,
    mode: str = "live",
    **_unused: Any,
) -> List[GV100HRunManifest]:
    raise RuntimeError(DEPRECATED_MSG)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", default="http://localhost:8000")
    parser.add_argument("--model-id", default="Qwen/Qwen3.8-27B")
    parser.add_argument("--cases-dir", default="benchmarks/cases")
    parser.add_argument("--output-dir", default="results/live_eval")
    parser.add_argument("--mode", choices=["live", "mock"], default="mock")
    args = parser.parse_args()

    run_live_evaluation(args.api_base, args.model_id, args.cases_dir, args.output_dir, args.mode)
