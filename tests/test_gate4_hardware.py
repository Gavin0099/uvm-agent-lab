import pytest
from experiments.gate4.hardware_profiler import HardwareProfiler


def test_qwen_32b_precision_and_tensor_parallel():
    # FP16 TP=1 should OOM on single 32GB GV100
    fp16_tp1 = HardwareProfiler.calculate_vram_requirement(
        model_name="Qwen-2.5-Coder-32B",
        context_length=32768,
        precision_mode="FP16",
        tensor_parallel=1
    )
    assert fp16_tp1["fits_in_memory"] is False

    # AWQ 4-bit TP=2 over NVLink fits easily with >15 GB headroom
    awq_tp2 = HardwareProfiler.calculate_vram_requirement(
        model_name="Qwen-2.5-Coder-32B",
        context_length=32768,
        precision_mode="AWQ_4BIT",
        tensor_parallel=2
    )
    assert awq_tp2["fits_in_memory"] is True
    assert awq_tp2["headroom_gb"] > 15.0


def test_nemotron_15b_fp16_tp2():
    # Nemotron-15B in FP16 TP=2 fits comfortably on dual GV100
    tp2 = HardwareProfiler.calculate_vram_requirement(
        model_name="Nemotron-4-15B",
        context_length=32768,
        precision_mode="FP16",
        tensor_parallel=2
    )
    assert tp2["fits_in_memory"] is True
    assert tp2["headroom_gb"] > 10.0


def test_128k_context_scaling():
    awq_tp2_128k = HardwareProfiler.calculate_vram_requirement(
        model_name="Qwen-2.5-Coder-32B",
        context_length=131072,
        precision_mode="AWQ_4BIT",
        tensor_parallel=2
    )
    assert awq_tp2_128k["fits_in_memory"] is True
    assert awq_tp2_128k["kv_cache_vram_per_gpu_gb"] <= 16.0
    assert awq_tp2_128k["headroom_gb"] > 4.0
