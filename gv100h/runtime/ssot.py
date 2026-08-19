from dataclasses import dataclass, replace
from typing import Tuple


@dataclass(frozen=True)
class RuntimeProfile:
    """Canonical Gate 4 runtime profile projected into launch and profiler configs."""

    candidate_name: str
    model_id: str
    model_artifact: str
    runtime_type: str
    quantization: str
    tensor_parallel: int
    gpu_count: int
    target_hardware: str
    max_model_len: int
    baseline_context_length: int
    gpu_memory_utilization: float
    kv_cache_type: str
    kv_cache_type_k: str
    kv_cache_type_v: str
    kv_cache_variants: Tuple[str, ...]
    experimental_kv_cache_types: Tuple[str, ...]
    flash_attention: bool
    parallel: int
    mtp_enabled: bool
    spec_draft_n_max: int
    context_sweep: Tuple[int, ...]
    external_reference_url: str
    kv_cache_issue_url: str
    kv_cache_fix_pr_url: str


GV100H_BASELINE = RuntimeProfile(
    candidate_name="candidate_a_llama_cpp_gguf",
    model_id="Qwen3.8-27B",
    model_artifact="Qwen3.8-27B-Q4_K_M.gguf",
    runtime_type="llama.cpp",
    quantization="Q4_K_M",
    tensor_parallel=1,
    gpu_count=1,
    target_hardware="Tesla V100 32GB (single-GPU baseline; dual-GV100 expansion)",
    max_model_len=262144,
    baseline_context_length=131072,
    gpu_memory_utilization=0.90,
    kv_cache_type="Q8_0",
    kv_cache_type_k="q8_0",
    kv_cache_type_v="q8_0",
    kv_cache_variants=("q8_0",),
    experimental_kv_cache_types=("q4_0", "q4_1", "q5_0", "q5_1"),
    flash_attention=True,
    parallel=1,
    mtp_enabled=False,
    spec_draft_n_max=0,
    context_sweep=(131072, 196608, 262144),
    external_reference_url="https://github.com/sudoingX/qwen38-mtp/blob/master/sweeps/workstation.md",
    kv_cache_issue_url="https://github.com/ggml-org/llama.cpp/issues/27109",
    kv_cache_fix_pr_url="https://github.com/ggml-org/llama.cpp/issues/27140",
)


GV100_MTP_N2 = replace(
    GV100H_BASELINE,
    candidate_name="candidate_a_llama_cpp_gguf_mtp_n2",
    mtp_enabled=True,
    spec_draft_n_max=2,
)


# Compatibility alias for callers that used the old control name.
GV100_MTP_OFF = GV100H_BASELINE
