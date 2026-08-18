import pytest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gv100h.coding_eval.client_admission import ClientAdmissionSuite
from gv100h.coding_eval.governance_ab_runner import GovernanceABRunner


@pytest.mark.contract
def test_client_admission_evaluations():
    cline_eval = ClientAdmissionSuite.evaluate_cline()
    assert cline_eval.client_name == "cline"
    assert cline_eval.overall_admitted is True
    assert cline_eval.interception_mode == "POST_HOC"

    cont_eval = ClientAdmissionSuite.evaluate_continue()
    assert cont_eval.client_name == "continue"
    assert cont_eval.interception_mode == "POST_HOC"


@pytest.mark.contract
def test_historical_tasks_schema():
    runner = GovernanceABRunner()
    tasks = runner.task_data["tasks"]
    assert len(tasks) == 10
    
    categories = {t["category"] for t in tasks}
    assert "bug_fix" in categories
    assert "small_feature" in categories
    assert "refactor" in categories
    assert "failure_recovery" in categories
    assert "multi_file" in categories


@pytest.mark.contract
def test_governance_ab_experiment_runner():
    runner = GovernanceABRunner()
    summary = runner.run_ab_benchmark(runs_per_task=3)
    assert summary.total_runs_per_arm == 30
    
    # Arm A vs Arm B
    assert summary.arm_a_prompt_only["false_success_rate"] > 0.0
    assert summary.arm_b_governed_sidecar["false_success_rate"] == 0.0
    assert summary.arm_b_governed_sidecar["scope_violations_count"] == 0
    assert summary.arm_b_governed_sidecar["human_acceptance_a_b_rate"] >= 70.0
