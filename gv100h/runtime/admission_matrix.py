from typing import List, Dict, Any
from pydantic import BaseModel


class RuntimeCandidate(BaseModel):
    name: str
    runtime_type: str
    quantization: str
    tensor_parallel: int
    target_hardware: str = "Dual NVIDIA GV100 (Volta CC 7.0)"
    supported_models: List[str]
    positioning: str
    exit_gate_criteria: Dict[str, Any]


class RuntimeAdmissionMatrix:
    """
    Admission Matrix for Volta CC 7.0 (Dual GV100 32GB NVLink).
    """

    CANDIDATES = [
        RuntimeCandidate(
            name="candidate_a_llama_cpp_gguf",
            runtime_type="llama.cpp",
            quantization="Q4_K_M",
            tensor_parallel=2,
            supported_models=["Qwen/Qwen3.8-35B-A3B", "Qwen/Qwen3.8-27B"],
            positioning="Baseline Qualification & Correctness First",
            exit_gate_criteria={
                "min_success_requests": 100,
                "max_corruption_count": 0,
                "target_decode_tps": 15.0,
                "max_vram_per_gpu_gb": 24.0
            }
        ),
        RuntimeCandidate(
            name="candidate_b_pinned_vllm_gptq",
            runtime_type="vllm_v0_pinned",
            quantization="GPTQ_4BIT",
            tensor_parallel=2,
            supported_models=["Qwen/Qwen3.8-35B-A3B", "Qwen/Qwen3.8-27B"],
            positioning="Experimental Throughput Acceleration",
            exit_gate_criteria={
                "min_success_requests": 100,
                "max_corruption_count": 0,
                "target_decode_tps": 25.0,
                "max_vram_per_gpu_gb": 28.0
            }
        ),
        RuntimeCandidate(
            name="candidate_c_transformers_reference",
            runtime_type="transformers_ref",
            quantization="FP16",
            tensor_parallel=2,
            supported_models=["Qwen/Qwen3.8-27B"],
            positioning="Golden Output Reference / Ground Truth Baseline",
            exit_gate_criteria={
                "min_success_requests": 10,
                "max_corruption_count": 0,
                "target_decode_tps": 5.0,
                "max_vram_per_gpu_gb": 30.0
            }
        )
    ]

    @classmethod
    def list_candidates(cls) -> List[RuntimeCandidate]:
        return cls.CANDIDATES

    @classmethod
    def get_candidate(cls, name: str) -> RuntimeCandidate:
        for c in cls.CANDIDATES:
            if c.name == name:
                return c
        raise KeyError(f"Candidate '{name}' not in Admission Matrix.")
