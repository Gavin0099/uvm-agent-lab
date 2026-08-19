import hashlib

import pytest

from gv100h.manifests.models import EvidenceManifest, GV100HRunManifest, HardwareManifest, OutcomeManifest
from gv100h.manifests.validator import ManifestValidationError, ManifestValidator


def _manifest_data():
    diff = b"diff --git a/uvm/tests/test.sv b/uvm/tests/test.sv\n+valid\n"
    return {
        "run_id": "strict-run",
        "task_id": "UVM-001",
        "experiment_arm": "arm_a_prompt_only",
        "target_repo": "test",
        "base_commit": "a" * 40,
        "model_id": "Qwen/Qwen3.8-27B",
        "runtime": "mock_replay",
        "framework_commit": "b" * 40,
        "contract_id": "contract",
        "hardware": {"gpu_count": 0, "gpu_model": "mock"},
        "evidence": {"git_diff_sha256": hashlib.sha256(diff).hexdigest()},
        "outcome": {"status": "fail", "false_success": False},
    }


def test_pydantic_rejects_unknown_manifest_field():
    data = _manifest_data()
    data["runtime_comit"] = "typo"

    with pytest.raises(Exception, match="extra_forbidden"):
        GV100HRunManifest.model_validate(data)


def test_json_schema_rejects_unknown_nested_evidence_field():
    data = _manifest_data()
    data["evidence"]["hardware_obseved"] = True

    with pytest.raises(ManifestValidationError, match="Schema validation error"):
        ManifestValidator().validate_manifest_dict(data)