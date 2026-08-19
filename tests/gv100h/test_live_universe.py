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
    assert plan["planned_runs"] == 2
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


def test_run_live_evaluation_is_deprecated_fail_closed():
    from scripts.run_live_eval import run_live_evaluation

    try:
        run_live_evaluation(
            api_base="http://localhost:8000",
            model_id="unused",
            cases_dir="benchmarks/cases",
            output_dir="results/live_eval",
            mode="mock",
        )
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("deprecated run_live_evaluation must raise")
    assert "deprecated" in message
    assert "run_single_ab_pair" in message


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


def test_full_universe_pair_runner_executes_thirty_pairs_and_sixty_manifests(tmp_path):
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    for index in range(1, 11):
        (case_dir / f"UVM-{index:03d}.yaml").write_text(
            f"id: UVM-{index:03d}\n", encoding="utf-8"
        )

    class Manifest:
        def __init__(self, task_id, repetition, arm, pair_id):
            self.task_id = task_id
            self.benchmark_task_id = task_id
            self.repetition = repetition
            self.experiment_arm = arm
            self.pair_id = pair_id

    calls = []

    def pair_runner(*, task_id, case_path, repetition, **_kwargs):
        pair_id = f"pair-{task_id}-{repetition}"
        calls.append((task_id, repetition))
        return {
            "manifests": [
                Manifest(task_id, repetition, "arm_a_prompt_only", pair_id),
                Manifest(task_id, repetition, "arm_b_governed_sidecar", pair_id),
            ]
        }

    status = run_full_universe(
        cases_dir=str(case_dir),
        output_dir=str(tmp_path / "out"),
        pair_runner=pair_runner,
    )

    assert len(calls) == 30
    assert status["executed_runs"] == 60
    assert status["manifest_count"] == 60
    assert status["unique_pair_count"] == 30
    assert status["pair_shape_valid"] is True
    assert status["universe_complete_claim_allowed"] is True


def test_manifest_universe_rejects_duplicate_arm_and_short_execution(tmp_path):
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    for index in range(1, 11):
        (case_dir / f"UVM-{index:03d}.yaml").write_text(
            f"id: UVM-{index:03d}\n", encoding="utf-8"
        )

    class Manifest:
        def __init__(self, task_id, repetition, arm, pair_id):
            self.task_id = task_id
            self.benchmark_task_id = task_id
            self.repetition = repetition
            self.experiment_arm = arm
            self.pair_id = pair_id

    def pair_runner(*, task_id, repetition, **_kwargs):
        pair_id = f"pair-{task_id}-{repetition}"
        return {
            "manifests": [
                Manifest(task_id, repetition, "arm_a_prompt_only", pair_id),
                Manifest(task_id, repetition, "arm_a_prompt_only", pair_id),
            ]
        }

    status = run_full_universe(
        cases_dir=str(case_dir),
        output_dir=str(tmp_path / "out"),
        pair_runner=pair_runner,
    )

    assert status["executed_runs"] == 60
    assert status["duplicate_manifest_keys"]
    assert status["pair_shape_valid"] is False
    assert status["universe_complete_claim_allowed"] is False


def test_manifest_universe_rejects_missing_pair_execution(tmp_path):
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    for index in range(1, 11):
        (case_dir / f"UVM-{index:03d}.yaml").write_text(
            f"id: UVM-{index:03d}\n", encoding="utf-8"
        )

    class Manifest:
        def __init__(self, task_id, repetition, arm, pair_id):
            self.task_id = task_id
            self.benchmark_task_id = task_id
            self.repetition = repetition
            self.experiment_arm = arm
            self.pair_id = pair_id

    calls = 0

    def pair_runner(*, task_id, repetition, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 30:
            return {"manifests": []}
        pair_id = f"pair-{task_id}-{repetition}"
        return {
            "manifests": [
                Manifest(task_id, repetition, "arm_a_prompt_only", pair_id),
                Manifest(task_id, repetition, "arm_b_governed_sidecar", pair_id),
            ]
        }

    status = run_full_universe(
        cases_dir=str(case_dir),
        output_dir=str(tmp_path / "out"),
        pair_runner=pair_runner,
    )

    assert status["executed_runs"] == 58
    assert status["manifest_count"] == 58
    assert status["universe_complete_claim_allowed"] is False
