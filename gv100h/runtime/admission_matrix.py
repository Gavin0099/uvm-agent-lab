from typing import List, Dict, Any
from pydantic import BaseModel

from gv100h.runtime.ssot import GV100H_BASELINE, GV100_MTP_OFF


class RuntimeCandidate(BaseModel):
    name: str
    runtime_type: str
    quantization: str
    tensor_parallel: int
    target_hardware: str = "Dual NVIDIA GV100 (Volta CC 7.0)"
    supported_models: List[str]
    positioning: str
    exit_gate_criteria: Dict[str, Any]
    model_artifact: str = ""
    gpu_count: int = 1
    kv_cache_type: str = "F16"
    flash_attention: bool = True
    parallel: int = 1
    mtp_enabled: bool = False
    spec_draft_n_max: int = 0
    context_sweep: List[int] = []
    external_reference_url: str = ""


class RuntimeAdmissionMatrix:
    """
    Admission Matrix for Volta CC 7.0 (Dual GV100 32GB NVLink).
    """

    CANDIDATES = [
        RuntimeCandidate(
            name=GV100H_BASELINE.candidate_name,
            runtime_type=GV100H_BASELINE.runtime_type,
            quantization=GV100H_BASELINE.quantization,
            tensor_parallel=GV100H_BASELINE.tensor_parallel,
            target_hardware=GV100H_BASELINE.target_hardware,
            supported_models=[GV100H_BASELINE.model_id],
            positioning="Baseline Qualification & Correctness First",
            model_artifact=GV100H_BASELINE.model_artifact,
            gpu_count=GV100H_BASELINE.gpu_count,
            kv_cache_type=GV100H_BASELINE.kv_cache_type,
            flash_attention=GV100H_BASELINE.flash_attention,
            parallel=GV100H_BASELINE.parallel,
            mtp_enabled=GV100H_BASELINE.mtp_enabled,
            spec_draft_n_max=GV100H_BASELINE.spec_draft_n_max,
            context_sweep=list(GV100H_BASELINE.context_sweep),
            external_reference_url=GV100H_BASELINE.external_reference_url,
            exit_gate_criteria={
                "min_success_requests": 100,
                "max_corruption_count": 0,
                "target_decode_tps": 15.0,
                "max_vram_per_gpu_gb": 24.0
            }
        ),
        RuntimeCandidate(
            name=GV100_MTP_OFF.candidate_name,
            runtime_type=GV100_MTP_OFF.runtime_type,
            quantization=GV100_MTP_OFF.quantization,
            tensor_parallel=GV100_MTP_OFF.tensor_parallel,
            target_hardware=GV100_MTP_OFF.target_hardware,
            supported_models=[GV100_MTP_OFF.model_id],
            positioning="MTP OFF control for the Qwen3.8-27B V100 baseline",
            model_artifact=GV100_MTP_OFF.model_artifact,
            gpu_count=GV100_MTP_OFF.gpu_count,
            kv_cache_type=GV100_MTP_OFF.kv_cache_type,
            flash_attention=GV100_MTP_OFF.flash_attention,
            parallel=GV100_MTP_OFF.parallel,
            mtp_enabled=GV100_MTP_OFF.mtp_enabled,
            spec_draft_n_max=GV100_MTP_OFF.spec_draft_n_max,
            context_sweep=list(GV100_MTP_OFF.context_sweep),
            external_reference_url=GV100_MTP_OFF.external_reference_url,
            exit_gate_criteria={
                "min_success_requests": 100,
                "max_corruption_count": 0,
                "target_decode_tps": 0.0,
                "max_vram_per_gpu_gb": 24.0,
                "comparison_only": True,
            },
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
