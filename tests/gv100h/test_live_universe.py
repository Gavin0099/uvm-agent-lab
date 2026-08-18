import json
from pathlib import Path

from gv100h.coding_eval.live_universe import (
    REQUIRED_TOTAL_RUNS,
    describe_live_invocation,
    full_universe_cells,
    merge_universe_status,
    summarize_produced_universe,
)
from scripts.run_live_universe import run_full_universe, write_universe_status


def test_default_single_cell_cannot_claim_full_universe():
    plan = describe_live_invocation(
        task_count=10,
        experiment_arm="arm_b_governed_sidecar",
        repetition=1,
        full_universe=False,
    )
    assert plan["universe_mode"] == "single_cell"
    assert plan["universe_complete_claim_allowed"] is False
    assert plan["planned_cells"] == [("arm_b_governed_sidecar", 1)]
    assert plan["planned_runs"] == 10
    assert plan["required_total_runs"] == REQUIRED_TOTAL_RUNS
    assert "cannot produce" in plan["reason"]


def test_full_universe_plan_is_sixty_runs_when_ten_tasks_present():
    plan = describe_live_invocation(
        task_count=10,
        experiment_arm="unused",
        repetition=0,
        full_universe=True,
    )
    assert plan["universe_mode"] == "full"
    assert plan["universe_complete_claim_allowed"] is True
    assert len(plan["planned_cells"]) == 6
    assert plan["planned_runs"] == 60
    assert plan["planned_cells"] == full_universe_cells()


def test_full_universe_plan_incomplete_when_task_count_wrong():
    plan = describe_live_invocation(
        task_count=1,
        experiment_arm="unused",
        repetition=0,
        full_universe=True,
    )
    assert plan["universe_complete_claim_allowed"] is False
    assert plan["planned_runs"] == 6


def test_produced_universe_requires_all_cells_and_ten_tasks():
    complete = summarize_produced_universe(full_universe_cells(), [f"UVM-{i:03d}" for i in range(1, 11)])
    assert complete["universe_complete_claim_allowed"] is True
    incomplete = summarize_produced_universe(
        [("arm_b_governed_sidecar", 1)],
        [f"UVM-{i:03d}" for i in range(1, 11)],
    )
    assert incomplete["universe_complete_claim_allowed"] is False
    assert ("arm_a_prompt_only", 1) in incomplete["missing_cells"]


def test_cli_help_exposes_full_universe_flag():
    source = Path("scripts/run_live_universe.py").read_text(encoding="utf-8")
    assert "--full-universe" in source
    assert "describe_live_invocation" in source
    dirty_harness = Path("scripts/run_live_eval.py").read_text(encoding="utf-8")
    assert "--full-universe" not in dirty_harness
    assert "describe_live_invocation" not in dirty_harness


def test_last_cell_cannot_overwrite_full_universe_status(tmp_path: Path):
    task_ids = [f"UVM-{i:03d}" for i in range(1, 11)]

    def cell_runner(*, experiment_arm, repetition, **_kwargs):
        single = describe_live_invocation(
            task_count=10,
            experiment_arm=experiment_arm,
            repetition=repetition,
            full_universe=False,
        )
        # A buggy cell would write this single_cell plan into the same file.
        write_universe_status(
            tmp_path,
            merge_universe_status(single, [(experiment_arm, repetition)], task_ids, 10),
        )
        return [type("M", (), {"task_id": tid, "benchmark_task_id": tid})() for tid in task_ids]

    status = run_full_universe(
        cases_dir="benchmarks/cases",
        output_dir=str(tmp_path),
        cell_runner=cell_runner,
    )
    on_disk = json.loads((tmp_path / "universe_status.json").read_text(encoding="utf-8"))
    assert status["universe_mode"] == "full"
    assert on_disk["universe_mode"] == "full"
    assert on_disk["planned_runs"] == 60
    assert on_disk["universe_complete_claim_allowed"] is True
    assert len(on_disk["produced_cells"]) == 6
