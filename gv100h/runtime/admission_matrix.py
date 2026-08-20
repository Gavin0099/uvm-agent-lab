import hashlib
import json
from typing import List, Dict, Any
from pydantic import BaseModel, Field

from gv100h.runtime.ssot import GV100H_BASELINE, GV100_MTP_N2


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
    launch_profile_id: str = ""
    gpu_count: int = 1
    selected_gpu_pair: List[int] = Field(default_factory=list)
    kv_cache_type: str = "F16"
    kv_cache_type_k: str = "q8_0"
    kv_cache_type_v: str = "q8_0"
    kv_cache_variants: List[str] = []
    experimental_kv_cache_types: List[str] = []
    flash_attention: bool = True
    parallel: int = 1
    mtp_enabled: bool = False
    spec_draft_n_max: int = 0
    context_sweep: List[int] = []
    stretch_context_sweep: List[int] = []
    external_reference_url: str = ""
    baseline_context_length: int = 131072
    kv_cache_issue_url: str = ""
    kv_cache_fix_pr_url: str = ""


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
            launch_profile_id="mtp_off",
            gpu_count=GV100H_BASELINE.gpu_count,
            kv_cache_type=GV100H_BASELINE.kv_cache_type,
            kv_cache_type_k=GV100H_BASELINE.kv_cache_type_k,
            kv_cache_type_v=GV100H_BASELINE.kv_cache_type_v,
            kv_cache_variants=list(GV100H_BASELINE.kv_cache_variants),
            experimental_kv_cache_types=list(GV100H_BASELINE.experimental_kv_cache_types),
            flash_attention=GV100H_BASELINE.flash_attention,
            parallel=GV100H_BASELINE.parallel,
            mtp_enabled=GV100H_BASELINE.mtp_enabled,
            spec_draft_n_max=GV100H_BASELINE.spec_draft_n_max,
            context_sweep=list(GV100H_BASELINE.context_sweep),
            stretch_context_sweep=list(GV100H_BASELINE.stretch_context_sweep),
            external_reference_url=GV100H_BASELINE.external_reference_url,
            baseline_context_length=GV100H_BASELINE.baseline_context_length,
            kv_cache_issue_url=GV100H_BASELINE.kv_cache_issue_url,
            kv_cache_fix_pr_url=GV100H_BASELINE.kv_cache_fix_pr_url,
            exit_gate_criteria={
                "min_success_requests": 100,
                "max_corruption_count": 0,
                "target_decode_tps": 15.0,
                "max_vram_per_gpu_gb": 24.0
            }
        ),
        RuntimeCandidate(
            name=GV100_MTP_N2.candidate_name,
            runtime_type=GV100_MTP_N2.runtime_type,
            quantization=GV100_MTP_N2.quantization,
            tensor_parallel=GV100_MTP_N2.tensor_parallel,
            target_hardware=GV100_MTP_N2.target_hardware,
            supported_models=[GV100_MTP_N2.model_id],
            positioning="MTP n-max=2 comparison arm for the Qwen3.8-27B V100 baseline",
            model_artifact=GV100_MTP_N2.model_artifact,
            launch_profile_id="mtp_n2",
            gpu_count=GV100_MTP_N2.gpu_count,
            kv_cache_type=GV100_MTP_N2.kv_cache_type,
            kv_cache_type_k=GV100_MTP_N2.kv_cache_type_k,
            kv_cache_type_v=GV100_MTP_N2.kv_cache_type_v,
            kv_cache_variants=list(GV100_MTP_N2.kv_cache_variants),
            experimental_kv_cache_types=list(GV100_MTP_N2.experimental_kv_cache_types),
            flash_attention=GV100_MTP_N2.flash_attention,
            parallel=GV100_MTP_N2.parallel,
            mtp_enabled=GV100_MTP_N2.mtp_enabled,
            spec_draft_n_max=GV100_MTP_N2.spec_draft_n_max,
            context_sweep=list(GV100_MTP_N2.context_sweep),
            stretch_context_sweep=list(GV100_MTP_N2.stretch_context_sweep),
            external_reference_url=GV100_MTP_N2.external_reference_url,
            baseline_context_length=GV100_MTP_N2.baseline_context_length,
            kv_cache_issue_url=GV100_MTP_N2.kv_cache_issue_url,
            kv_cache_fix_pr_url=GV100_MTP_N2.kv_cache_fix_pr_url,
            exit_gate_criteria={
                "min_success_requests": 100,
                "max_corruption_count": 0,
                "target_decode_tps": 15.0,
                "max_vram_per_gpu_gb": 24.0,
            },
        ),
        RuntimeCandidate(
            name="candidate_b_pinned_vllm_gptq",
            runtime_type="vllm_v0_pinned",
            quantization="GPTQ_4BIT",
            tensor_parallel=2,
            kv_cache_type="engine_managed",
            kv_cache_type_k="engine_managed",
            kv_cache_type_v="engine_managed",
            supported_models=["Qwen/Qwen3.8-35B-A3B", "Qwen/Qwen3.8-27B"],
            positioning="Experimental Throughput Acceleration",
            launch_profile_id="candidate_b_pinned_vllm_gptq",
            gpu_count=2,
            selected_gpu_pair=[0, 1],
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
            kv_cache_type="F16",
            launch_profile_id="candidate_c_transformers_reference",
            kv_cache_type_k="f16",
            kv_cache_type_v="f16",
            supported_models=["Qwen/Qwen3.8-27B"],
            positioning="Golden Output Reference / Ground Truth Baseline",
            gpu_count=2,
            selected_gpu_pair=[0, 1],
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


def normalize_profile_cache_type(value: str) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def canonical_profile_identity(
    candidate: RuntimeCandidate,
    *,
    model_id: str,
    kv_cache_type_k: str,
    kv_cache_type_v: str,
) -> Dict[str, Any]:
    """Return stable profile fields and digest used at qualification time."""

    fields = {
        "profile_id": candidate.name,
        "launch_profile_id": candidate.launch_profile_id or candidate.name,
        "model_id": model_id,
        "runtime_type": candidate.runtime_type,
        "quantization": candidate.quantization,
        "tensor_parallel": candidate.tensor_parallel,
        "gpu_count": candidate.gpu_count,
        "selected_gpu_pair": list(candidate.selected_gpu_pair),
        "parallel": candidate.parallel,
        "mtp_enabled": candidate.mtp_enabled,
        "spec_draft_n_max": candidate.spec_draft_n_max,
        "kv_cache_type_k": normalize_profile_cache_type(kv_cache_type_k),
        "kv_cache_type_v": normalize_profile_cache_type(kv_cache_type_v),
    }
    encoded = json.dumps(
        fields,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        **fields,
        "identity_sha256": hashlib.sha256(encoded).hexdigest(),
    }
