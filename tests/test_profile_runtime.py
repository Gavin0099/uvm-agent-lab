from scripts.profile_runtime import (
    compute_profile_metrics,
    evaluate_profile_gate,
    extract_response_timing,
)
from gv100h.runtime.admission_matrix import RuntimeAdmissionMatrix


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
        "kv_cache_type_k": "q8_0",
        "kv_cache_type_v": "q8_0",
        "vram_peak_per_gpu_gb": 18.0,
        "gpu_telemetry": {"initial": {"gpu_count": 1}},
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