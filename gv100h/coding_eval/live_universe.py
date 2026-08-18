"""
Live A/B universe contract for run_live_eval.

Qualification requires 10 tasks × 3 repetitions × 2 arms = 60 paired runs
(30 per arm). A single --experiment-arm/--repetition invocation is one cell
and must not be reported as a complete universe.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

FULL_UNIVERSE_ARMS: Tuple[str, str] = (
    "arm_a_prompt_only",
    "arm_b_governed_sidecar",
)
FULL_UNIVERSE_REPETITIONS: Tuple[int, int, int] = (1, 2, 3)
REQUIRED_TASK_COUNT = 10
REQUIRED_RUNS_PER_ARM = REQUIRED_TASK_COUNT * len(FULL_UNIVERSE_REPETITIONS)
REQUIRED_TOTAL_RUNS = REQUIRED_RUNS_PER_ARM * len(FULL_UNIVERSE_ARMS)

UniverseCell = Tuple[str, int]


def full_universe_cells() -> List[UniverseCell]:
    return [(arm, rep) for arm in FULL_UNIVERSE_ARMS for rep in FULL_UNIVERSE_REPETITIONS]


def describe_live_invocation(
    *,
    task_count: int,
    experiment_arm: str,
    repetition: int,
    full_universe: bool,
) -> Dict[str, Any]:
    """
    Classify a CLI invocation. Never upgrades a single-cell run to complete.
    """
    if full_universe:
        cells = full_universe_cells()
        planned_runs = task_count * len(cells)
        complete = (
            task_count == REQUIRED_TASK_COUNT
            and planned_runs == REQUIRED_TOTAL_RUNS
        )
        return {
            "universe_mode": "full",
            "universe_complete_claim_allowed": complete,
            "planned_cells": cells,
            "planned_runs": planned_runs,
            "required_total_runs": REQUIRED_TOTAL_RUNS,
            "required_runs_per_arm": REQUIRED_RUNS_PER_ARM,
            "reason": None if complete else (
                f"full-universe plan requires {REQUIRED_TASK_COUNT} tasks "
                f"and {REQUIRED_TOTAL_RUNS} runs; got task_count={task_count}, "
                f"planned_runs={planned_runs}"
            ),
        }

    cells = [(experiment_arm, repetition)]
    return {
        "universe_mode": "single_cell",
        "universe_complete_claim_allowed": False,
        "planned_cells": cells,
        "planned_runs": task_count * len(cells),
        "required_total_runs": REQUIRED_TOTAL_RUNS,
        "required_runs_per_arm": REQUIRED_RUNS_PER_ARM,
        "reason": (
            "single --experiment-arm/--repetition cannot produce the "
            f"{REQUIRED_TASK_COUNT}x{len(FULL_UNIVERSE_REPETITIONS)}x"
            f"{len(FULL_UNIVERSE_ARMS)} universe"
        ),
    }


def merge_universe_status(
    plan: Dict[str, Any],
    produced_cells: Iterable[UniverseCell],
    task_ids: Sequence[str],
    executed_runs: int,
) -> Dict[str, Any]:
    """
    Final status must be computed once from the aggregate plan + produced cells.
    Callers must not let a later single-cell plan overwrite a full-universe plan.
    """
    produced = summarize_produced_universe(produced_cells, task_ids)
    return {
        **plan,
        **produced,
        "executed_runs": executed_runs,
        "universe_complete_claim_allowed": bool(
            plan.get("universe_complete_claim_allowed")
            and produced.get("universe_complete_claim_allowed")
        ),
    }


def summarize_produced_universe(
    cells: Iterable[UniverseCell],
    task_ids: Sequence[str],
) -> Dict[str, Any]:
    produced = set(cells)
    expected = set(full_universe_cells())
    unique_tasks = {tid for tid in task_ids if tid}
    complete = produced == expected and len(unique_tasks) == REQUIRED_TASK_COUNT
    return {
        "universe_complete_claim_allowed": complete,
        "produced_cells": sorted(produced),
        "missing_cells": sorted(expected - produced),
        "tasks_covered_count": len(unique_tasks),
        "required_task_count": REQUIRED_TASK_COUNT,
    }
