import pytest
from pathlib import Path
from agent.runners.multi_turn_runner import MultiTurnHealingAgentRunner
from scripts.run_case import run_benchmark
from agent.governance.policy import GovernanceViolationCode


def test_multi_turn_runner_auto_heals_compile_and_sim_errors():
    runner = MultiTurnHealingAgentRunner()
    
    # Case UVM-003: Fix compile error
    case_path_3 = "benchmarks/cases/UVM-003.yaml"
    res_3 = run_benchmark(case_path_3, runner_name="multi_turn")
    assert res_3["metrics"]["task_success"] is True
    assert res_3["execution"]["retry_count"] >= 1
    assert res_3["execution"]["compile_status"] == "pass"

    # Case UVM-004: Debug simulation mismatch
    case_path_4 = "benchmarks/cases/UVM-004.yaml"
    res_4 = run_benchmark(case_path_4, runner_name="multi_turn")
    assert res_4["metrics"]["task_success"] is True
    assert res_4["execution"]["retry_count"] >= 1
    assert res_4["execution"]["simulation_status"] == "pass"


def test_multi_turn_runner_handles_all_cases():
    cases_dir = Path("benchmarks/cases")
    for cf in cases_dir.glob("*.yaml"):
        res = run_benchmark(str(cf), runner_name="multi_turn")
        assert res["governance_status"]["passed"] is True
        assert res["metrics"]["total_score"] >= 80.0
