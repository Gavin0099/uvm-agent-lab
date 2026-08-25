from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
import yaml

from agent.governance.guardrails import ScopeGuardrail
from agent.runners.models import AgentExecutionContext
from agent.runners.openai_compatible_runner import OpenAICompatibleLLMRunner
from gv100h.coding_eval.single_pair_runner import run_single_ab_pair
from gv100h.manifests.validator import ManifestValidator


REPO_ROOT = Path(__file__).resolve().parents[2]
CASE_PATH = REPO_ROOT / "benchmarks" / "cases" / "AGENT-CODE-001.yaml"
TARGET_REL = "fixtures/coding_agent/AGENT_CODE_001/calculator.py"


def _case() -> dict:
    return yaml.safe_load(CASE_PATH.read_text(encoding="utf-8"))


def test_replay_log_normalization_ignores_only_pytest_duration():
    first = ".. [100%]\n2 passed in 0.04s\n"
    second = ".. [100%]\n2 passed in 0.31s\n"

    assert ManifestValidator._normalize_replay_log(first) == (
        ManifestValidator._normalize_replay_log(second)
    )
    assert ManifestValidator._normalize_replay_log(first) != "2 passed"


def test_runner_rejects_profile_mismatch(tmp_path: Path):
    case = _case()
    runner = OpenAICompatibleLLMRunner(
        mock_mode=True,
        validator_profile="eda",
    )

    with pytest.raises(ValueError, match="does not match benchmark case profile"):
        runner.run_case(
            case,
            context=AgentExecutionContext(workspace_root=tmp_path),
        )


def test_lightweight_runner_uses_coding_strategy_without_eda(tmp_path: Path):
    case = _case()
    target = tmp_path / TARGET_REL
    target.parent.mkdir(parents=True)
    target.write_text(
        "def safe_divide(numerator, denominator):\n"
        "    return 0 if denominator == 0 else numerator / denominator\n",
        encoding="utf-8",
    )
    runner = OpenAICompatibleLLMRunner(
        mock_mode=True,
        validator_profile="lightweight",
    )

    result = runner.run_case(
        case,
        context=AgentExecutionContext(
            workspace_root=tmp_path,
            sidecar_guardrail=ScopeGuardrail(
                allowed_paths=case["allowed_paths"],
                forbidden_paths=case["forbidden_paths"],
            ),
        ),
    )

    assert result.status == "completed"
    assert result.execution["validator_profile"] == "lightweight"
    assert result.execution["validator_status"] == "not_run"
    tool_names = [call["tool"] for call in result.execution["tool_calls"]]
    assert tool_names == ["read_file", "write_file"]
    assert "query_spec" not in tool_names
    assert "compile" not in tool_names
    assert "simulate" not in tool_names
    generated = target.read_text(encoding="utf-8")
    assert "def safe_divide" in generated
    assert "raise ValueError" in generated
    assert "class evaluated_test" not in generated


def test_agent_code_001_production_pair_uses_lightweight_validator(tmp_path: Path):
    result = run_single_ab_pair(
        task_id="AGENT-CODE-001",
        case_path=CASE_PATH,
        repetition=1,
        mode="mock",
        output_dir=tmp_path / "pair-output",
        repo_root=REPO_ROOT,
        model_id="Qwen/Qwen3.8-35B-A3B",
    )

    assert result["task_id"] == "AGENT-CODE-001"
    assert result["evidence_class"] == "synthetic_offline_scaffold"
    assert result["admissible_for_model_qualification"] is False
    assert len(result["manifests"]) == 2

    for manifest in result["manifests"]:
        assert manifest.task_id == "AGENT-CODE-001"
        assert manifest.outcome.status == "pass"
        assert manifest.evidence.eda_backend == "python_compiler"
        assert "py_compile" in manifest.evidence.build_command
        assert "pytest" in manifest.evidence.test_command

        bundle = Path(result["bundle_dirs"][manifest.experiment_arm])
        tool_trace = json.loads(
            (bundle / "tool_trace.json").read_text(encoding="utf-8")
        )
        tool_names = [call["tool"] for call in tool_trace["tool_calls"]]
        assert tool_names == ["read_file", "write_file"]
        assert "query_spec" not in tool_names
        assert "compile" not in tool_names
        assert "simulate" not in tool_names

        verification = json.loads(
            (bundle / "verification.json").read_text(encoding="utf-8")
        )
        assert verification["validator_profile"] == "lightweight"
        assert verification["final_pass"] is True

        snapshots = json.loads(
            (bundle / "file_snapshots.json").read_text(encoding="utf-8")
        )
        target_snapshot = next(
            item for item in snapshots["files"] if item["path"] == TARGET_REL
        )
        generated = base64.b64decode(target_snapshot["content_b64"]).decode(
            "utf-8"
        )
        assert "def safe_divide" in generated
        assert "raise ValueError" in generated
        assert "class evaluated_test" not in generated