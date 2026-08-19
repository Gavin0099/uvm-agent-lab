from scripts.profile_runtime import evaluate_profile_gate
from gv100h.runtime.admission_matrix import RuntimeAdmissionMatrix


def _summary(**overrides):
    summary = {
        "hardware_observed": True,
        "success_count": 100,
        "corruption_count": 0,
        "decode_tps": 31.0,
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
        "target_decode_tps",
    }


def test_mtp_off_control_skips_throughput_target_but_requires_stability():
    candidate = RuntimeAdmissionMatrix.get_candidate("candidate_a_llama_cpp_gguf_mtp_off")

    result = evaluate_profile_gate(candidate, _summary(decode_tps=0.0))

    assert result["passed"] is True
    assert result["checks"]["target_decode_tps"] is True