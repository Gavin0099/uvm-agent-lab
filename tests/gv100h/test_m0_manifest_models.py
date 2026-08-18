import pytest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gv100h.manifests.models import GV100HRunManifest, HardwareManifest, EvidenceManifest, OutcomeManifest
from gv100h.manifests.validator import ManifestValidator, ManifestValidationError


@pytest.mark.unit
def test_manifest_models_valid_instantiation():
    validator = ManifestValidator()
    manifest_data = {
        "run_id": "run-123456abcdef",
        "task_id": "ENG-BUG-001",
        "experiment_arm": "arm_b_governed_sidecar",
        "target_repo": "Gavin0099/uvm-agent-lab",
        "base_commit": "12340ae1632e8cac55d68a6a67bd2f2ae8ba684e",
        "model_id": "Qwen/Qwen3.8-35B-A3B",
        "runtime": "llama.cpp",
        "framework_commit": "3305b640d17ca253e632093d434ae029f920c3e3",
        "contract_id": "GV100H-M3",
        "hardware": {
            "gpu_count": 2,
            "gpu_model": "NVIDIA GV100 (32GB)"
        },
        "evidence": {
            "git_diff_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "changed_paths": ["uvm/tests/test1.sv"]
        },
        "outcome": {
            "status": "pass",
            "false_success": False
        }
    }

    manifest = validator.validate_manifest_dict(manifest_data)
    assert manifest.run_id == "run-123456abcdef"
    assert manifest.outcome.status == "pass"


@pytest.mark.unit
def test_manifest_models_corrupted_false_success_raises():
    validator = ManifestValidator()
    corrupted_data = {
        "run_id": "run-corrupt-001",
        "task_id": "ENG-BUG-001",
        "experiment_arm": "arm_b_governed_sidecar",
        "target_repo": "Gavin0099/uvm-agent-lab",
        "base_commit": "12340ae1632e8cac55d68a6a67bd2f2ae8ba684e",
        "model_id": "Qwen/Qwen3.8-35B-A3B",
        "runtime": "llama.cpp",
        "framework_commit": "3305b640d17ca253e632093d434ae029f920c3e3",
        "contract_id": "GV100H-M3",
        "hardware": {
            "gpu_count": 2,
            "gpu_model": "NVIDIA GV100 (32GB)"
        },
        "evidence": {
            "git_diff_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        },
        "outcome": {
            "status": "pass",
            "false_success": True  # Corrupted: pass + false_success = True
        }
    }

    # Should raise error during set validation
    m = GV100HRunManifest.model_validate(corrupted_data)
    with pytest.raises(ManifestValidationError, match="Corrupted outcome"):
        validator.validate_manifest_set([m])
