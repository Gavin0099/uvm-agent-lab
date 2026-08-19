import pytest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gv100h.runtime.admission_matrix import RuntimeAdmissionMatrix
from gv100h.health.vram_tracker import DualGV100VRAMTracker
from gv100h.runtime.ssot import GV100H_BASELINE, GV100_MTP_N2


@pytest.mark.contract
def test_runtime_admission_matrix_candidates():
    candidates = RuntimeAdmissionMatrix.list_candidates()
    assert len(candidates) >= 3
    
    cand_a = RuntimeAdmissionMatrix.get_candidate("candidate_a_llama_cpp_gguf")
    assert cand_a.runtime_type == "llama.cpp"
    assert cand_a.quantization == "Q4_K_M"
    assert cand_a.exit_gate_criteria["max_corruption_count"] == 0


@pytest.mark.contract
def test_gv100_baseline_is_qwen38_q8_kv_with_mtp_control_and_n2_arm():
    cand_a = RuntimeAdmissionMatrix.get_candidate(GV100H_BASELINE.candidate_name)
    cand_n2 = RuntimeAdmissionMatrix.get_candidate(GV100_MTP_N2.candidate_name)

    assert cand_a.model_artifact == "Qwen3.8-27B-Q4_K_M.gguf"
    assert cand_a.runtime_type == "llama.cpp"
    assert cand_a.mtp_enabled is False
    assert cand_a.spec_draft_n_max == 0
    assert cand_a.kv_cache_type == "Q8_0"
    assert cand_a.baseline_context_length == 32768
    assert cand_a.context_sweep == [32768, 65536, 131072]
    assert cand_a.stretch_context_sweep == [196608, 262144]
    assert cand_a.parallel == 1
    assert cand_n2.mtp_enabled is True
    assert cand_n2.spec_draft_n_max == 2
    assert cand_n2.kv_cache_type == "Q8_0"
    assert cand_n2.model_artifact == cand_a.model_artifact
    assert cand_n2.kv_cache_type_k == cand_a.kv_cache_type_k
    assert cand_n2.kv_cache_type_v == cand_a.kv_cache_type_v
    assert cand_n2.context_sweep == cand_a.context_sweep
    assert cand_a.kv_cache_variants == ["q8_0"]
    assert cand_a.experimental_kv_cache_types == ["q4_0", "q4_1", "q5_0", "q5_1"]


@pytest.mark.contract
def test_dual_gv100_vram_estimation():
    # Test 35B model with Q4_K_M at 32K context
    budget = DualGV100VRAMTracker.estimate_memory_budget(
        model_name="Qwen/Qwen3.8-35B-A3B",
        quantization="Q4_K_M",
        context_length=32768,
        tensor_parallel=2
    )
    assert budget["is_feasible"] is True
    assert budget["peak_vram_per_gpu_gb"] < 32.0

    # Test 35B model with FP16 (should flag OOM risk on 32GB cards)
    budget_fp16 = DualGV100VRAMTracker.estimate_memory_budget(
        model_name="Qwen/Qwen3.8-35B-A3B",
        quantization="FP16",
        context_length=32768,
        tensor_parallel=2
    )
    assert budget_fp16["is_feasible"] is False
    assert "OOM" in budget_fp16["recommendation"]
