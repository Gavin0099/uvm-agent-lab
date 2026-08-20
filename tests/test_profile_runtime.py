import hashlib
import json
import pytest

from scripts.profile_runtime import (
    compute_profile_metrics,
    evaluate_profile_gate,
    extract_response_timing,
    profile_endpoint,
    sample_nvlink_topology,
    validate_profile_response,
)
from gv100h.runtime.admission_matrix import RuntimeAdmissionMatrix
from gv100h.runtime.context_fixtures import load_context_fixture


def _summary(**overrides):
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
        "model_artifact_hash": "a" * 64,
        "model_provenance_ready": True,
        "model_provenance_independent": True,
        "kv_cache_type_k": "q8_0",
        "kv_cache_type_v": "q8_0",
        "vram_peak_per_gpu_gb": 18.0,
        "gpu_telemetry": {"initial": {"gpu_count": 1}},
        "response_oracle": "strict-v1",
        "expected_response_hash_bound": True,
        "context_fixture_bound": True,
        "launch_context_bound": True,
        "launch_profile_arm_consistent": True,
    }
    summary.update(overrides)
    return summary


def test_profile_gate_requires_all_observed_baseline_signals():
    candidate = RuntimeAdmissionMatrix.get_candidate("candidate_a_llama_cpp_gguf")

    result = evaluate_profile_gate(candidate, _summary())

    assert result["passed"] is True
    assert result["failed_checks"] == []


def test_profile_gate_rejects_missing_hardware_and_metrics():
    candidate = RuntimeAdmissionMatrix.get_candidate("candidate_a_llama_cpp_gguf")

    result = evaluate_profile_gate(
        candidate,
        _summary(
            hardware_observed=False,
            success_count=99,
            corruption_count=1,
            decode_tps=None,
            decode_tokens=None,
            decode_evidence=False,
            prefill_tps=None,
            prefill_latency_sec=None,
            prefill_tokens=None,
            prefill_evidence=False,
            model_artifact_hash=None,
            model_provenance_ready=False,
            vram_peak_per_gpu_gb=None,
            gpu_telemetry={"initial": {"gpu_count": 0}},
        ),
    )

    assert result["passed"] is False
    assert set(result["failed_checks"]) == {
        "hardware_observed",
        "gpu_count",
        "min_success_requests",
        "max_corruption_count",
        "max_vram_per_gpu_gb",
        "prefill_evidence",
        "decode_evidence",
        "model_artifact_hash",
        "target_decode_tps",
    }


def test_mtp_off_baseline_requires_throughput_and_stability():
    candidate = RuntimeAdmissionMatrix.get_candidate("candidate_a_llama_cpp_gguf")

    result = evaluate_profile_gate(candidate, _summary(decode_tps=31.0))

    assert result["passed"] is True
    assert result["checks"]["target_decode_tps"] is True


def test_profile_gate_rejects_q4_kv_without_patched_build_provenance():
    candidate = RuntimeAdmissionMatrix.get_candidate("candidate_a_llama_cpp_gguf")

    result = evaluate_profile_gate(
        candidate,
        _summary(kv_cache_type_k="q4_0", kv_cache_type_v="q4_0"),
    )

    assert result["passed"] is False
    assert "experimental_kv_build_provenance" in result["failed_checks"]
    assert "experimental_kv_prefill_validation" in result["failed_checks"]


def test_profile_gate_rejects_missing_response_oracle():
    candidate = RuntimeAdmissionMatrix.get_candidate("candidate_a_llama_cpp_gguf")

    result = evaluate_profile_gate(
        candidate,
        _summary(expected_response_hash_bound=False),
    )

    assert result["passed"] is False
    assert "response_oracle" in result["failed_checks"]


def test_dual_gpu_candidate_requires_nvlink_observation():
    candidate = RuntimeAdmissionMatrix.get_candidate("candidate_b_pinned_vllm_gptq")

    result = evaluate_profile_gate(
        candidate,
        _summary(
            gpu_telemetry={
                "initial": {
                    "gpu_count": 2,
                    "nvlink": {"nvlink_observed": False},
                }
            },
            kv_cache_type_k="engine_managed",
            kv_cache_type_v="engine_managed",
        ),
    )

    assert candidate.gpu_count == 2
    assert result["checks"]["nvlink_observed"] is False
    assert "nvlink_observed" in result["failed_checks"]


def test_profile_gate_rejects_mismatched_launch_profile_arm():
    candidate = RuntimeAdmissionMatrix.get_candidate("candidate_a_llama_cpp_gguf")

    result = evaluate_profile_gate(
        candidate,
        _summary(launch_profile_arm_consistent=False),
    )

    assert result["passed"] is False
    assert "launch_profile_arm_consistent" in result["failed_checks"]


def test_profile_gate_rejects_metadata_only_context_sweep():
    candidate = RuntimeAdmissionMatrix.get_candidate("candidate_a_llama_cpp_gguf")

    result = evaluate_profile_gate(
        candidate,
        _summary(context_fixture_bound=False),
    )

    assert result["passed"] is False
    assert "context_fixture_bound" in result["failed_checks"]


def test_profile_response_oracle_rejects_model_and_content_corruption():
    base = {
        "model": "Qwen3.8-27B",
        "choices": [{"message": {"content": "stable checksum answer"}}],
    }
    expected_hash = hashlib.sha256(
        base["choices"][0]["message"]["content"].encode("utf-8")
    ).hexdigest()

    assert validate_profile_response(
        base,
        expected_model_id="Qwen3.8-27B",
        expected_response_sha256=expected_hash,
    )["valid"] is True
    assert validate_profile_response(
        {**base, "model": "wrong-model"},
        expected_model_id="Qwen3.8-27B",
    )["reason"] == "response_model_mismatch"
    assert validate_profile_response(
        {**base, "choices": [{"message": {"content": "\ufffd"}}]},
        expected_model_id="Qwen3.8-27B",
    )["reason"] == "content_malformed"
    assert validate_profile_response(
        base,
        expected_model_id="Qwen3.8-27B",
        expected_response_sha256="0" * 64,
    )["reason"] == "expected_response_hash_mismatch"


def test_context_fixture_binds_prompt_hash_and_expected_token_count(tmp_path):
    prompt = "context-token " * 30000
    fixture_path = tmp_path / "ctx_32k.json"
    fixture_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "context_length": 32768,
                "prompt": prompt,
                "prompt_hash": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "actual_prompt_tokens": 30000,
                "expected_response_sha256": "a" * 64,
            }
        ),
        encoding="utf-8",
    )

    fixture = load_context_fixture(fixture_path)

    assert fixture.context_length == 32768
    assert fixture.actual_prompt_tokens == 30000


def test_context_fixture_rejects_prompt_hash_mismatch(tmp_path):
    fixture_path = tmp_path / "ctx_32k.json"
    fixture_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "context_length": 32768,
                "prompt": "tampered prompt",
                "prompt_hash": "0" * 64,
                "actual_prompt_tokens": 30000,
                "expected_response_sha256": "a" * 64,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="prompt_hash"):
        load_context_fixture(fixture_path)


def test_context_fixture_rejects_underfilled_context_slot(tmp_path):
    prompt = "short prompt"
    fixture_path = tmp_path / "ctx_32k.json"
    fixture_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "context_length": 32768,
                "prompt": prompt,
                "prompt_hash": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "actual_prompt_tokens": 30000 - 1000,
                "expected_response_sha256": "a" * 64,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="does not exercise"):
        load_context_fixture(fixture_path)


class _ProfileResponse:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_profile_endpoint_binds_context_prompt_and_response_hash(tmp_path, monkeypatch):
    prompt = "context-token " * 30000
    content = "stable checksum answer"
    fixture_path = tmp_path / "ctx_32k.json"
    fixture_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "context_length": 32768,
                "prompt": prompt,
                "prompt_hash": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "actual_prompt_tokens": 30000,
                "expected_response_sha256": hashlib.sha256(
                    content.encode("utf-8")
                ).hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    captured = {}
    response = _ProfileResponse(
        {
            "model": "Qwen3.8-27B",
            "choices": [{"message": {"content": content}}],
            "timings": {
                "prompt_n": 30000,
                "prompt_ms": 10.0,
                "predicted_n": 4,
                "predicted_ms": 100.0,
            },
        }
    )

    def fake_urlopen(request, timeout):
        captured["request"] = request
        return response

    monkeypatch.setattr("scripts.profile_runtime.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr(
        "scripts.profile_runtime.sample_gpu_telemetry",
        lambda: {
            "hardware_observed": False,
            "gpu_count": 0,
            "gpus": [],
            "nvlink": {"nvlink_observed": False},
        },
    )
    launch_config = tmp_path / "llama.yaml"
    launch_config.write_text(
        """launch_template:\n  - llama-server\n  - -m\n  - '{model_artifact}'\n  - -c\n  - '{context_length}'\nprofiles:\n  mtp_off:\n    spec_type: none\n    spec_draft_n_max: 0\n    launch_args:\n      - --spec-type\n      - '{spec_type}'\n      - --spec-draft-n-max\n      - '{spec_draft_n_max}'\n""",
        encoding="utf-8",
    )

    summary = profile_endpoint(
        "http://localhost:8000",
        model_id="Qwen3.8-27B",
        num_requests=1,
        output_file=str(tmp_path / "profile.json"),
        context_fixture_path=str(fixture_path),
        api_key="test-token",
        launch_profile_config_path=str(launch_config),
        launch_profile_id="mtp_off",
    )

    request_payload = json.loads(captured["request"].data.decode("utf-8"))
    assert request_payload["messages"][0]["content"] == prompt
    assert captured["request"].get_header("Authorization") == "Bearer test-token"
    assert summary["context_fixture_bound"] is True
    assert summary["launch_context_bound"] is True
    assert summary["context_cell"]["actual_prompt_tokens"] == 30000
    assert summary["success_count"] == 1
    assert summary["corruption_count"] == 0


def test_sample_nvlink_topology_requires_observed_nvlink(monkeypatch):
    class _TopoResult:
        returncode = 0
        stdout = "GPU0    GPU1\nGPU0    X      NV1\nGPU1    NV1    X\n"

    monkeypatch.setattr("scripts.profile_runtime.shutil.which", lambda _name: "nvidia-smi")
    monkeypatch.setattr("scripts.profile_runtime.subprocess.run", lambda *args, **kwargs: _TopoResult())

    topology = sample_nvlink_topology(2)

    assert topology["nvlink_observed"] is True
    assert topology["nvlink_links"] == ["NV1"]
    assert len(topology["topology_sha256"]) == 64


def test_profile_gate_accepts_q4_kv_only_with_fix_and_prefill_evidence():
    candidate = RuntimeAdmissionMatrix.get_candidate("candidate_a_llama_cpp_gguf")

    result = evaluate_profile_gate(
        candidate,
        _summary(
            kv_cache_type_k="q4_0",
            kv_cache_type_v="q4_0",
            llama_cpp_commit="patched-llama-cpp-commit",
            llama_server_version="llama-server build",
            kv_cache_fix_reference=candidate.kv_cache_fix_pr_url,
            kv_cache_fix_verified=True,
            prefill_benchmark_passed=True,
        ),
    )

    assert result["passed"] is True


def test_profile_timing_extracts_prefill_and_decode_evidence():
    timing = extract_response_timing(
        {
            "usage": {"prompt_tokens": 1000, "completion_tokens": 128},
            "timings": {
                "prompt_ms": 500.0,
                "predicted_ms": 4000.0,
            },
        }
    )

    assert timing["prefill_tokens"] == 1000
    assert timing["prefill_latency_sec"] == 0.5
    assert timing["prefill_tps"] == 2000.0
    assert timing["decode_tokens"] == 128
    assert timing["decode_latency_sec"] == 4.0
    assert timing["decode_tps"] == 32.0


def test_missing_decode_timing_is_estimated_end_to_end_not_decode_evidence():
    metrics = compute_profile_metrics(
        avg_latency=4.0,
        peak_vram_mb=1024.0,
        decode_tokens=128,
        decode_timing_observed=False,
    )

    assert metrics["decode_tps"] is None
    assert metrics["est_decode_tps"] is None
    assert metrics["estimated_end_to_end_tps"] == 32.0