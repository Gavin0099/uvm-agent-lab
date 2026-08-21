import json
from pathlib import Path

import yaml
import pytest
from jsonschema import validate

from gv100h.runner.validator_profiles import (
    resolve_validator_profile,
    validator_requires_eda,
)
from gv100h.runner.validator_plugins import LightweightValidator, create_validator
from scripts.run_case import run_benchmark


def _case_schema() -> dict:
    return json.loads(
        Path("benchmarks/schema/case_schema.json").read_text(encoding="utf-8")
    )


def test_lightweight_case_contract_does_not_require_eda_fields():
    case = {
        "id": "AGENT-CODE-001",
        "title": "Refactor a Python helper safely",
        "description": "Make a bounded Python change and prove it with lightweight checks.",
        "validator_profile": "lightweight",
        "task": {
            "type": "code_change",
            "goal": "Update the helper without changing its public behavior.",
        },
        "inputs": {
            "requirement_id": "AGENT-CODE-001",
            "target_file": "agent/tools/example.py",
        },
        "allowed_paths": ["agent/tools/"],
        "forbidden_paths": ["rtl/", ".git/"],
        "acceptance": {
            "build": "pass",
            "test": "pass",
            "lint": "optional",
        },
        "required_evidence": [
            "requirement_id",
            "git_diff",
            "build_log",
            "test_log",
        ],
    }

    validate(instance=case, schema=_case_schema())
    assert resolve_validator_profile(case) == "lightweight"
    assert validator_requires_eda("lightweight") is False


def test_legacy_uvm_cases_are_explicit_eda_profile():
    cases = sorted(Path("benchmarks/cases").glob("UVM-*.yaml"))
    assert cases
    for case_path in cases:
        case = yaml.safe_load(case_path.read_text(encoding="utf-8"))
        assert resolve_validator_profile(case) == "eda"
        assert validator_requires_eda("eda") is True


def test_private_legacy_task_shape_resolves_to_eda():
    assert resolve_validator_profile({"task_id": "ENG-BUG-001"}) == "eda"


def test_lightweight_scoring_uses_validator_status_not_eda_statuses(tmp_path, monkeypatch):
    case_path = tmp_path / "agent-case.yaml"
    case_path.write_text(
        yaml.safe_dump(
            {
                "id": "AGENT-CODE-001",
                "title": "Lightweight coding case",
                "description": "Exercise v1 validator scoring.",
                "validator_profile": "lightweight",
                "task": {"type": "code_change", "goal": "Make a safe change."},
                "inputs": {"requirement_id": "AGENT-CODE-001"},
                "allowed_paths": ["agent/tools/"],
                "forbidden_paths": ["rtl/"],
                "acceptance": {"build": "pass", "test": "pass"},
                "required_evidence": [
                    "requirement_id",
                    "git_diff",
                    "build_log",
                    "test_log",
                ],
            }
        ),
        encoding="utf-8",
    )

    class LightweightRunner:
        name = "lightweight-test-runner"

        def __init__(self, **_kwargs):
            pass

        def run_case(self, _case):
            return {
                "duration_seconds": 0.01,
                "governance_violations": [],
                "evidence": {
                    "requirement_id": "AGENT-CODE-001",
                    "git_diff": "diff --git a/example.py b/example.py",
                    "build_log": "py_compile passed",
                    "test_log": "pytest passed",
                },
                "execution": {
                    "compile_status": "not_run",
                    "simulation_status": "not_run",
                    "validator_status": "pass",
                    "step_count": 2,
                },
                "metrics": {},
            }

    monkeypatch.setattr("scripts.run_case.FakeAgentRunner", LightweightRunner)
    result = run_benchmark(str(case_path), runner_name="mock")

    assert result["validator_profile"] == "lightweight"
    assert result["metrics"]["validator_score"] == 100.0
    assert result["metrics"]["total_score"] == 100.0
    assert result["metrics"]["task_success"] is True


def test_lightweight_validator_runs_python_checks_without_eda(tmp_path):
    target = tmp_path / "example.py"
    target.write_text("value = 1\n", encoding="utf-8")
    validator = create_validator("lightweight", tmp_path)

    result = validator.verify_task(
        changed_paths=["example.py"],
        target_file="example.py",
        verification={
            "test": {
                "argv": ["python", "-c", "assert 1 + 1 == 2"],
            }
        },
    )

    assert isinstance(validator, LightweightValidator)
    assert result.validator_profile == "lightweight"
    assert result.eda_backend == "python_compiler"
    assert result.final_pass is True


def test_lightweight_validator_rejects_systemverilog_target(tmp_path):
    validator = create_validator("lightweight", tmp_path)

    with pytest.raises(ValueError, match="requires a Python target"):
        validator.verify_task(
            changed_paths=["uvm/tests/example.sv"],
            target_file="uvm/tests/example.sv",
        )
