#!/usr/bin/env python3
"""
Live A/B universe planner / runner.

This file is the P1 increment. It does not modify the dirty M0.5 harness
in scripts/run_live_eval.py. Default single-cell planning cannot claim a
complete 10x3x2 universe. --full-universe plans 60 runs and writes
universe_status.json once after all cells, never after each cell.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gv100h.coding_eval.live_universe import (
    UniverseCell,
    describe_live_invocation,
    full_universe_cells,
    merge_universe_status,
)


def write_universe_status(out_path: Path, status: Dict[str, Any]) -> Path:
    out_path.mkdir(parents=True, exist_ok=True)
    status_path = out_path / "universe_status.json"
    status_path.write_text(json.dumps(status, indent=2), encoding="utf-8")
    return status_path


def run_full_universe(
    *,
    cases_dir: str,
    output_dir: str,
    cell_runner: Callable[..., Sequence[Any]] | None = None,
    pair_runner: Callable[..., Dict[str, Any]] | None = None,
    runner_kwargs: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Plan the full universe, invoke cell_runner once per cell, then write
    a single aggregate universe_status.json. cell_runner must not write
    that file, or the last cell would overwrite the full plan.
    """
    case_registry = []
    for case_path in sorted(Path(cases_dir).glob("UVM-*.yaml")):
        import yaml

        case_data = yaml.safe_load(case_path.read_text(encoding="utf-8")) or {}
        task_id = case_data.get("id") or case_path.stem
        case_registry.append((str(task_id), case_path))
    task_count = len(case_registry)
    plan = describe_live_invocation(
        task_count=task_count,
        experiment_arm="unused",
        repetition=0,
        full_universe=True,
    )
    produced_cells: List[UniverseCell] = []
    task_ids: List[str] = []
    executed_runs = 0
    manifests: List[Any] = []
    kwargs = dict(runner_kwargs or {})

    if pair_runner is not None:
        for repetition in (1, 2, 3):
            for task_id, case_path in case_registry:
                pair_result = pair_runner(
                    task_id=task_id,
                    case_path=case_path,
                    repetition=repetition,
                    output_dir=output_dir,
                    **kwargs,
                )
                pair_manifests = list(pair_result.get("manifests", []))
                manifests.extend(pair_manifests)
                executed_runs += len(pair_manifests)
                task_ids.extend(
                    str(getattr(item, "benchmark_task_id", None) or getattr(item, "task_id", ""))
                    for item in pair_manifests
                )
        produced_cells = list(full_universe_cells())
    elif cell_runner is not None:
        for arm, rep in plan["planned_cells"]:
            cell_results = cell_runner(
                cases_dir=cases_dir,
                output_dir=output_dir,
                experiment_arm=arm,
                repetition=rep,
                **kwargs,
            )
            if cell_results:
                produced_cells.append((arm, rep))
                executed_runs += len(cell_results)
                for item in cell_results:
                    task_id = getattr(item, "benchmark_task_id", None) or getattr(item, "task_id", None)
                    if task_id:
                        task_ids.append(str(task_id))
    else:
        raise ValueError("run_full_universe requires pair_runner or cell_runner")

    status = merge_universe_status(
        plan,
        produced_cells,
        task_ids,
        executed_runs,
        manifests=manifests if pair_runner is not None else None,
        expected_task_ids=[task_id for task_id, _ in case_registry],
    )
    write_universe_status(Path(output_dir).resolve(), status)
    return status


def _import_pair_runner() -> Callable[..., Dict[str, Any]]:
    from gv100h.coding_eval.single_pair_runner import run_single_ab_pair

    return run_single_ab_pair


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Plan or run the 10x3x2 live A/B universe without claiming completeness from a single cell."
    )
    parser.add_argument("--api-base", default="http://localhost:8000/v1")
    parser.add_argument("--model-id", default="Qwen/Qwen3.8-27B")
    parser.add_argument("--runtime", choices=["llama.cpp", "vllm", "sglang", "transformers"], default="llama.cpp")
    parser.add_argument("--quantization", choices=["Q4_K_M", "Q8_0", "AWQ_4BIT", "GPTQ_4BIT", "FP16", "FP8"], default="Q4_K_M")
    parser.add_argument("--model-hash", default=None)
    parser.add_argument("--model-artifact-path", default=None)
    parser.add_argument("--runtime-commit", default=None)
    parser.add_argument("--cases-dir", default="benchmarks/cases")
    parser.add_argument("--output-dir", default="results/live_eval")
    parser.add_argument("--mode", choices=["live", "mock"], default="mock")
    parser.add_argument("--experiment-arm", choices=["arm_a_prompt_only", "arm_b_governed_sidecar"], default="arm_b_governed_sidecar")
    parser.add_argument("--repetition", type=int, default=1)
    parser.add_argument("--task-id", default=None)
    parser.add_argument(
        "--full-universe",
        action="store_true",
        help="Run both arms x repetitions 1-3. Default single-cell cannot claim a complete 30-pair universe.",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Write universe_status.json from the plan without invoking the dirty live harness.",
    )
    args = parser.parse_args(argv)

    cases = sorted(Path(args.cases_dir).glob("UVM-*.yaml"))
    plan = describe_live_invocation(
        task_count=len(cases),
        experiment_arm=args.experiment_arm,
        repetition=args.repetition,
        full_universe=args.full_universe,
    )
    print(
        f"[UNIVERSE] mode={plan['universe_mode']} planned_runs={plan['planned_runs']} "
        f"complete_claim_allowed={plan['universe_complete_claim_allowed']}"
    )
    if plan.get("reason"):
        print(f"[UNIVERSE] {plan['reason']}")

    if args.plan_only:
        status = merge_universe_status(plan, [], [], 0)
        path = write_universe_status(Path(args.output_dir).resolve(), status)
        print(f"[UNIVERSE] wrote {path}")
        return 0

    if args.full_universe:
        status = run_full_universe(
            cases_dir=args.cases_dir,
            output_dir=args.output_dir,
            pair_runner=_import_pair_runner(),
            runner_kwargs={
                "api_base": args.api_base,
                "model_id": args.model_id,
                "mode": args.mode,
                "runtime": args.runtime,
                "quantization": args.quantization,
                "model_hash": args.model_hash,
                "model_artifact_path": args.model_artifact_path,
                "runtime_commit": args.runtime_commit,
            },
        )
    else:
        pair_runner = _import_pair_runner()
        case_registry = []
        import yaml

        for case_path in cases:
            case_data = yaml.safe_load(case_path.read_text(encoding="utf-8")) or {}
            case_registry.append((str(case_data.get("id") or case_path.stem), case_path))
        selected_task = args.task_id or (case_registry[0][0] if case_registry else None)
        selected_case = next(
            (case_path for task_id, case_path in case_registry if task_id == selected_task),
            None,
        )
        if selected_task is None or selected_case is None:
            raise ValueError("No benchmark case matches --task-id")
        pair_result = pair_runner(
            task_id=selected_task,
            case_path=selected_case,
            output_dir=args.output_dir,
            api_base=args.api_base,
            model_id=args.model_id,
            mode=args.mode,
            repetition=args.repetition,
            runtime=args.runtime,
            quantization=args.quantization,
            model_hash=args.model_hash,
            model_artifact_path=args.model_artifact_path,
            runtime_commit=args.runtime_commit,
        )
        manifests = list(pair_result.get("manifests", []))
        task_ids = [
            str(getattr(item, "benchmark_task_id", None) or getattr(item, "task_id", ""))
            for item in manifests
            if getattr(item, "benchmark_task_id", None) or getattr(item, "task_id", None)
        ]
        status = merge_universe_status(
            plan,
            [],
            task_ids,
            len(manifests),
            manifests=manifests,
            expected_task_ids=[selected_task],
        )
        write_universe_status(Path(args.output_dir).resolve(), status)

    print(
        f"[UNIVERSE] complete_claim_allowed={status['universe_complete_claim_allowed']} "
        f"executed_runs={status.get('executed_runs')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
