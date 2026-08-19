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
    gpu_memory_utilization: float
    kv_cache_type: str
    flash_attention: bool
    parallel: int
    mtp_enabled: bool
    spec_draft_n_max: int
    context_sweep: Tuple[int, ...]
    external_reference_url: str


GV100H_BASELINE = RuntimeProfile(
    candidate_name="candidate_a_llama_cpp_gguf",
    model_id="Qwen3.8-27B",
    model_artifact="Qwen3.8-27B-Q4_K_M.gguf",
    runtime_type="llama.cpp",
    quantization="Q4_K_M",
    tensor_parallel=1,
    gpu_count=1,
    target_hardware="Tesla V100 32GB (single-GPU baseline; dual-GV100 expansion)",
    max_model_len=32768,
    gpu_memory_utilization=0.90,
    kv_cache_type="F16",
    flash_attention=True,
    parallel=1,
    mtp_enabled=True,
    spec_draft_n_max=2,
    context_sweep=(32768, 65536, 131072, 262144),
    external_reference_url="https://github.com/sudoingX/qwen38-mtp/blob/master/sweeps/workstation.md",
)


GV100_MTP_OFF = replace(
    GV100H_BASELINE,
    candidate_name="candidate_a_llama_cpp_gguf_mtp_off",
    mtp_enabled=False,
    spec_draft_n_max=0,
)
