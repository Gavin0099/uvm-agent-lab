import hashlib
import json
import pytest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gv100h.coding_eval.client_admission import ClientAdmissionSuite
from gv100h.coding_eval.governance_ab_runner import GovernanceABRunner
from gv100h.manifests.models import (
    EvidenceManifest,
    GV100HRunManifest,
    HardwareManifest,
    OutcomeManifest,
)
from gv100h.utils.pairing import compute_canonical_pair_id


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


def _dict_only_pair_manifests():
    pair_id = compute_canonical_pair_id(
        benchmark_task_id="UVM-001",
        repetition=1,
        base_commit="abc1234",
        model_id="Qwen/Qwen3.8-35B",
    )
    arm_a = GV100HRunManifest(
        run_id="run-a-1",
        task_id="UVM-001",
        pair_id=pair_id,
        experiment_arm="arm_a_prompt_only",
        target_repo="Gavin0099/uvm-agent-lab",
        base_commit="abc1234",
        model_id="Qwen/Qwen3.8-35B",
        runtime="mock_replay",
        framework_commit="3305b64",
        contract_id="EXEC-CONTRACT-UVM-001",
        hardware=HardwareManifest(gpu_count=0, gpu_model="Mock"),
        evidence=EvidenceManifest(git_diff_sha256="a" * 64),
        outcome=OutcomeManifest(status="pass", false_success=False),
    )
    arm_b = arm_a.model_copy(update={
        "run_id": "run-b-1",
        "experiment_arm": "arm_b_governed_sidecar",
        "evidence": EvidenceManifest(git_diff_sha256="b" * 64),
    })
    return arm_a, arm_b


def test_ab_runner_rejects_manifests_without_physical_bundle(tmp_path):
    """P0: schema-valid dict-only manifests must not be aggregated as live."""
    arm_a, arm_b = _dict_only_pair_manifests()
    m_dir = tmp_path / "dict_only"
    m_dir.mkdir()
    (m_dir / "arm_a_manifest.json").write_text(json.dumps(arm_a.model_dump()), encoding="utf-8")
    (m_dir / "arm_b_manifest.json").write_text(json.dumps(arm_b.model_dump()), encoding="utf-8")

    summary = GovernanceABRunner().run_ab_benchmark(runs_per_task=3, manifest_dir=str(m_dir))
    assert summary.admissible_for_model_qualification is False
    assert summary.is_synthetic_simulation is True
    assert summary.evidence_class == "synthetic_offline_scaffold"
    assert summary.arm_a_prompt_only["runs_per_arm_count"] == 30
    assert summary.arm_b_governed_sidecar["runs_per_arm_count"] == 30
    assert summary.arm_a_prompt_only["evidence_class"] == "synthetic_offline_scaffold"


def test_ab_runner_rejects_tampered_physical_bundle(tmp_path):
    """P0: hash-mismatch physical files must not enter live arm lists."""
    arm_dir = tmp_path / "tampered" / "arm_a"
    arm_dir.mkdir(parents=True)
    (arm_dir / "diff.patch").write_bytes(b"tampered-bytes")
    manifest = _dict_only_pair_manifests()[0].model_copy(update={
        "evidence": EvidenceManifest(
            git_diff_sha256=hashlib.sha256(b"original-bytes").hexdigest()
        )
    })
    (arm_dir / "manifest.json").write_text(json.dumps(manifest.model_dump()), encoding="utf-8")

    summary = GovernanceABRunner().run_ab_benchmark(
        runs_per_task=3, manifest_dir=str(tmp_path / "tampered")
    )
    assert summary.admissible_for_model_qualification is False
    assert summary.evidence_class == "synthetic_offline_scaffold"
    assert summary.arm_a_prompt_only["evidence_class"] == "synthetic_offline_scaffold"
