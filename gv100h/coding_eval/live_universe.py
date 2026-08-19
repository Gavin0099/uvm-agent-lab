"""
Live A/B universe contract for run_live_eval.

Qualification requires 10 tasks × 3 repetitions × 2 arms = 60 paired runs
(30 per arm). A single --experiment-arm/--repetition invocation is one cell
and must not be reported as a complete universe.
"""

from __future__ import annotations

from collections import Counter, defaultdict
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
        "planned_runs": len(FULL_UNIVERSE_ARMS),
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
    manifests: Optional[Sequence[Any]] = None,
    expected_task_ids: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    Final status must be computed once from the aggregate plan + produced cells.
    Callers must not let a later single-cell plan overwrite a full-universe plan.
    """
    if manifests is not None:
        produced = summarize_manifest_universe(
            manifests,
            expected_task_ids or sorted({task_id for task_id in task_ids if task_id}),
        )
    else:
        produced = summarize_produced_universe(produced_cells, task_ids)
        produced["executed_runs_exact"] = executed_runs == plan.get("required_total_runs")
        produced["manifest_count"] = executed_runs
    return {
        **plan,
        **produced,
        "executed_runs": executed_runs,
        "universe_complete_claim_allowed": bool(
            plan.get("universe_complete_claim_allowed")
            and produced.get("universe_complete_claim_allowed")
            and executed_runs == plan.get("required_total_runs")
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


def summarize_manifest_universe(
    manifests: Sequence[Any],
    expected_task_ids: Sequence[str],
) -> Dict[str, Any]:
    expected_tasks = set(expected_task_ids)
    expected_keys = {
        (task_id, repetition, arm)
        for task_id in expected_tasks
        for repetition in FULL_UNIVERSE_REPETITIONS
        for arm in FULL_UNIVERSE_ARMS
    }
    records = []
    for manifest in manifests:
        records.append(
            (
                getattr(manifest, "benchmark_task_id", None)
                or getattr(manifest, "task_id", None),
                getattr(manifest, "repetition", None),
                getattr(manifest, "experiment_arm", None),
                getattr(manifest, "pair_id", None),
            )
        )

    manifest_keys = [(task_id, repetition, arm) for task_id, repetition, arm, _ in records]
    key_counts = Counter(manifest_keys)
    duplicate_keys = sorted(key for key, count in key_counts.items() if count > 1)
    unique_keys = set(manifest_keys)
    pair_members = defaultdict(set)
    for task_id, repetition, arm, pair_id in records:
        if pair_id:
            pair_members[pair_id].add((task_id, repetition, arm))

    expected_pair_count = len(expected_tasks) * len(FULL_UNIVERSE_REPETITIONS)
    pair_shape_valid = all(
        len(members) == len(FULL_UNIVERSE_ARMS)
        and {member[2] for member in members} == set(FULL_UNIVERSE_ARMS)
        and len({(member[0], member[1]) for member in members}) == 1
        for members in pair_members.values()
    )
    complete = (
        unique_keys == expected_keys
        and not duplicate_keys
        and len(records) == REQUIRED_TOTAL_RUNS
        and len(pair_members) == expected_pair_count
        and pair_shape_valid
        and all(pair_id for *_, pair_id in records)
    )
    return {
        "universe_complete_claim_allowed": complete,
        "produced_cells": sorted(
            {(arm, repetition) for _, repetition, arm, _ in records if arm and repetition}
        ),
        "missing_cells": [],
        "tasks_covered_count": len({task_id for task_id, *_ in records if task_id}),
        "required_task_count": len(expected_tasks),
        "manifest_count": len(records),
        "expected_manifest_count": REQUIRED_TOTAL_RUNS,
        "unique_pair_count": len(pair_members),
        "expected_pair_count": expected_pair_count,
        "duplicate_manifest_keys": duplicate_keys,
        "unexpected_manifest_keys": sorted(unique_keys - expected_keys),
        "missing_manifest_keys": sorted(expected_keys - unique_keys),
        "pair_shape_valid": pair_shape_valid,
    }
