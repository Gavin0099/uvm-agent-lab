import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

from scripts.create_gate4_model_manifest import build_manifest
from scripts.profile_runtime import (
    _run_profile_requests,
    context_aware_request_timeout,
    evaluate_profile_gate,
    profile_endpoint,
    sample_nvlink_topology,
)
from scripts.verify_gate4_model_manifest import build_receipt
from gv100h.runtime.admission_matrix import RuntimeAdmissionMatrix
from gv100h.runtime.model_provenance import verify_model_verification_receipt


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _schema(name: str) -> dict:
    return json.loads(
        (PROJECT_ROOT / "gv100h" / "schemas" / name).read_text(encoding="utf-8")
    )


def _manifest_and_receipt(tmp_path: Path) -> tuple[Path, Path, Path, str]:
    artifact = tmp_path / "Qwen3.8-27B-Q4_K_M.gguf"
    artifact.write_bytes(b"approved-model-bytes")
    artifact_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest_path = tmp_path / "manifest.json"
    receipt_path = tmp_path / "receipt.json"
    build_manifest(
        artifact,
        model_source="https://models.example.invalid/qwen38",
        model_revision="revision-20260820",
        output_path=manifest_path,
    )
    build_receipt(
        manifest_path,
        artifact,
        approved_sha256=artifact_hash,
        approved_source="https://models.example.invalid/qwen38",
        approved_revision="revision-20260820",
        verifier_id="release-checksum-verifier",
        verification_basis="vendor-release-checksum",
        output_path=receipt_path,
    )
    return artifact, manifest_path, receipt_path, artifact_hash


def test_gate4_manifest_receipt_and_context_schemas_validate_contracts(tmp_path):
    artifact, manifest_path, receipt_path, _ = _manifest_and_receipt(tmp_path)
    jsonschema.validate(
        json.loads(manifest_path.read_text(encoding="utf-8")),
        _schema("gate4_model_manifest.schema.json"),
    )
    jsonschema.validate(
        json.loads(receipt_path.read_text(encoding="utf-8")),
        _schema("gate4_model_verification_receipt.schema.json"),
    )

    prompt = "token " * 29491
    context = {
        "schema_version": "1",
        "context_length": 32768,
        "prompt": prompt,
        "prompt_hash": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "actual_prompt_tokens": 29491,
        "expected_response_sha256": "0" * 64,
    }
    jsonschema.validate(context, _schema("gate4_context_fixture.schema.json"))
    invalid_context = {**context, "actual_prompt_tokens": 29490}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid_context, _schema("gate4_context_fixture.schema.json"))


def test_receipt_rejects_wrong_approved_hash_source_and_revision(tmp_path):
    artifact, manifest_path, receipt_path, artifact_hash = _manifest_and_receipt(tmp_path)

    wrong_hash_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    wrong_hash_receipt["approved_artifact_sha256"] = "f" * 64
    wrong_hash_path = tmp_path / "wrong-hash.json"
    wrong_hash_path.write_text(json.dumps(wrong_hash_receipt), encoding="utf-8")
    with pytest.raises(ValueError, match="approved hash"):
        verify_model_verification_receipt(
            manifest_path,
            artifact,
            wrong_hash_path,
            expected_model_id="Qwen3.8-27B",
            expected_model_artifact="Qwen3.8-27B-Q4_K_M.gguf",
        )

    for field, expected_message in (
        ("model_source", "source"),
        ("model_revision", "revision"),
    ):
        mutated = json.loads(receipt_path.read_text(encoding="utf-8"))
        mutated[field] = "mismatched"
        mutated_path = tmp_path / f"wrong-{field}.json"
        mutated_path.write_text(json.dumps(mutated), encoding="utf-8")
        with pytest.raises(ValueError, match=expected_message):
            verify_model_verification_receipt(
                manifest_path,
                artifact,
                mutated_path,
                expected_model_id="Qwen3.8-27B",
                expected_model_artifact="Qwen3.8-27B-Q4_K_M.gguf",
            )


def test_receipt_requires_explicit_verified_status_claim(tmp_path):
    artifact, manifest_path, receipt_path, _ = _manifest_and_receipt(tmp_path)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt.pop("verification_status")
    receipt.pop("independent_verification")
    invalid_path = tmp_path / "missing-status.json"
    invalid_path.write_text(json.dumps(receipt), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid model verification receipt"):
        verify_model_verification_receipt(
            manifest_path,
            artifact,
            invalid_path,
            expected_model_id="Qwen3.8-27B",
            expected_model_artifact="Qwen3.8-27B-Q4_K_M.gguf",
        )


def test_dual_gpu_gate_requires_the_declared_selected_pair():
    candidate = RuntimeAdmissionMatrix.get_candidate("candidate_b_pinned_vllm_gptq")
    summary = {
        "hardware_observed": True,
        "success_count": 100,
        "corruption_count": 0,
        "decode_tps": 31.0,
        "decode_tokens": 128,
        "decode_evidence": True,
        "prefill_tps": 1000.0,
        "prefill_latency_sec": 0.1,
        "prefill_tokens": 100,
        "prefill_evidence": True,
        "model_provenance_ready": True,
        "model_provenance_independent": True,
        "runtime_process_owned": True,
        "runtime_attestation_bound": True,
        "kv_cache_type_k": "engine_managed",
        "kv_cache_type_v": "engine_managed",
        "vram_peak_per_gpu_gb": 18.0,
        "response_oracle": "strict-v1",
        "expected_response_hash_bound": True,
        "context_fixture_bound": True,
        "launch_context_bound": True,
        "launch_profile_arm_consistent": True,
        "gpu_telemetry": {
            "initial": {
                "gpu_count": 2,
                "nvlink": {
                    "selected_gpu_pair": [0, 1],
                    "selected_pair_nvlink_observed": True,
                },
            }
        },
    }
    assert evaluate_profile_gate(candidate, summary)["passed"] is True
    summary["gpu_telemetry"]["initial"]["nvlink"]["selected_gpu_pair"] = [1, 2]
    result = evaluate_profile_gate(candidate, summary)
    assert result["checks"]["nvlink_observed"] is False


def test_context_aware_timeout_scales_with_context_slot():
    assert context_aware_request_timeout(32768) == 120.0
    assert context_aware_request_timeout(65536) == 240.0
    assert context_aware_request_timeout(131072) == 480.0


def test_formal_profile_requires_harness_owned_runtime(tmp_path):
    with pytest.raises(ValueError, match="harness-owned runtime_command"):
        profile_endpoint(
            "http://localhost:8000/v1",
            num_requests=0,
            output_file=str(tmp_path / "profile.json"),
        )


def test_profile_request_cleanup_runs_for_unexpected_exception(monkeypatch):
    class _Runtime:
        stopped = False

        def stop(self):
            self.stopped = True

    runtime = _Runtime()

    def unexpected_failure(*_args, **_kwargs):
        raise KeyboardInterrupt()

    monkeypatch.setattr(
        "scripts.profile_runtime.sample_gpu_telemetry",
        lambda: {"hardware_observed": False, "gpus": []},
    )
    monkeypatch.setattr(
        "scripts.profile_runtime.urllib.request.urlopen",
        unexpected_failure,
    )

    with pytest.raises(KeyboardInterrupt):
        _run_profile_requests(
            url="http://localhost:8000/v1/chat/completions",
            effective_model_id="Qwen3.8-27B",
            prompt_content="probe",
            num_requests=1,
            api_key="EMPTY",
            request_timeout_sec=120.0,
            expected_response_sha256=None,
            context_fixture=None,
            runtime_attestation_seed=None,
            runtime_process=runtime,
            selected_gpu_pair=None,
        )
    assert runtime.stopped is True


def test_topology_binds_selected_pair_in_raw_evidence(monkeypatch):
    class _TopoResult:
        returncode = 0
        stdout = "GPU0    GPU1\nGPU0    X      NV1\nGPU1    NV1    X\n"

    monkeypatch.setattr("scripts.profile_runtime.shutil.which", lambda _name: "nvidia-smi")
    monkeypatch.setattr("scripts.profile_runtime.subprocess.run", lambda *args, **kwargs: _TopoResult())

    topology = sample_nvlink_topology(2, selected_gpu_pair=[0, 1])
    assert topology["selected_gpu_pair"] == [0, 1]
    assert topology["selected_pair_relations"] == {"0->1": "NV1", "1->0": "NV1"}
    assert topology["selected_pair_nvlink_observed"] is True