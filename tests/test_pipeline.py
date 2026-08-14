import pytest
import json
from pathlib import Path
from scripts.run_case import run_benchmark
from scripts.score_case import score_result
from retrieval.evaluator import Gate1RetrievalEvaluator


def test_end_to_end_mock_runner_all_cases():
    cases_dir = Path("benchmarks/cases")
    for cf in cases_dir.glob("*.yaml"):
        result = run_benchmark(str(cf), runner_name="mock")
        assert result["case_id"] is not None
        assert result["governance_status"]["passed"] is True
        assert result["metrics"]["total_score"] >= 80.0
        assert result["metrics"]["task_success"] is True


def test_governance_fault_mode_scope_violation():
    case_file = "benchmarks/cases/UVM-001.yaml"
    result = run_benchmark(case_file, runner_name="mock", fault_mode="scope_violation")
    assert result["governance_status"]["passed"] is False
    assert result["metrics"]["total_score"] == 0.0
    assert result["metrics"]["task_success"] is False


def test_governance_fault_mode_missing_evidence():
    case_file = "benchmarks/cases/UVM-001.yaml"
    result = run_benchmark(case_file, runner_name="mock", fault_mode="missing_evidence")
    assert result["governance_status"]["passed"] is False
    assert result["metrics"]["total_score"] < 80.0
    assert result["metrics"]["task_success"] is False


def test_gate1_retrieval_evaluator():
    evaluator = Gate1RetrievalEvaluator()
    summary = evaluator.evaluate()
    assert "spec-reference-kit" in summary
    assert summary["spec-reference-kit"]["recall@1"] == 100.0
    assert summary["spec-reference-kit"]["wrong_version_rate"] == 0.0
