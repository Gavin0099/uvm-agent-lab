import pytest
import json
import jsonschema
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.mark.contract
def test_run_manifest_schema_validation():
    schema_file = PROJECT_ROOT / "gv100h" / "schemas" / "run_manifest.schema.json"
    assert schema_file.exists()

    with open(schema_file, "r", encoding="utf-8") as f:
        schema = json.load(f)

    # Valid manifest instance
    valid_manifest = {
        "run_id": "run-123456",
        "task_id": "GV100H-M3-CASE-001",
        "experiment_arm": "arm_b_governed_sidecar",
        "target_repo": "Gavin0099/uvm-agent-lab",
        "base_commit": "2fadd2ca0e928261568c075ebaa559759018763f",
        "head_commit": "3305b640d17ca253e632093d434ae029f920c3e3",
        "model_id": "Qwen/Qwen3.8-35B-A3B",
        "model_hash": "sha256:abc123",
        "runtime": "llama.cpp",
        "runtime_commit": "b2345",
        "quantization": "Q4_K_M",
        "framework_commit": "3305b640d17ca253e632093d434ae029f920c3e3",
        "contract_id": "GV100H-M3",
        "contract_hash": "sha256:def456",
        "knowledge_repo": "Gavin0099/usb-if-hub-spec-reference",
        "knowledge_repo_commit": "commit-789",
        "knowledge_manifest_hash": "sha256:ghi789",
        "dataset_hash": "sha256:jkl012",
        "client": "cline",
        "client_version": "3.2.0",
        "interception_mode": "POST_HOC",
        "sampling": {
            "temperature": 0.0,
            "max_tokens": 2048
        },
        "hardware": {
            "gpu_count": 2,
            "gpu_model": "GV100",
            "driver_version": "535.129.03",
            "cuda_version": "12.2"
        },
        "evidence": {
            "git_diff_sha256": "sha256:diff123",
            "changed_paths": ["gv100h/test.py"],
            "build_command": "pytest",
            "build_exit_code": 0,
            "build_log_sha256": "sha256:log123"
        },
        "outcome": {
            "status": "pass",
            "false_success": False,
            "human_acceptance_rating": "A"
        }
    }

    # Should validate without raising jsonschema.ValidationError
    jsonschema.validate(instance=valid_manifest, schema=schema)
