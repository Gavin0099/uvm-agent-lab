from typing import List, Optional, Literal
from pydantic import BaseModel, ConfigDict, Field


class SamplingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    temperature: Optional[float] = 0.0
    top_p: Optional[float] = 1.0
    max_tokens: Optional[int] = 2048


class HardwareManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    gpu_count: int = Field(..., description="Number of GPUs detected/used")
    gpu_model: str = Field(..., description="GPU model string e.g. NVIDIA GV100 (32GB)")
    hardware_observed: Optional[bool] = None
    driver_version: Optional[str] = None
    cuda_version: Optional[str] = None
    vram_total_gb: Optional[float] = None
    vram_peak_used_gb: Optional[float] = None


class TimingManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ttft_ms: Optional[float] = None
    prompt_tps: Optional[float] = None
    decode_tps: Optional[float] = None
    wall_clock_sec: Optional[float] = None


class EvidenceManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_schema_version: Optional[Literal["2"]] = None
    git_diff_sha256: str = Field(..., description="SHA-256 hash of binary patch")
    changed_paths: List[str] = Field(default_factory=list)
    workspace_tree_sha256: Optional[str] = None
    target_file: Optional[str] = None
    target_file_sha256: Optional[str] = None
    file_snapshots_sha256: Optional[str] = None
    tool_trace_sha256: Optional[str] = None
    verification_sha256: Optional[str] = None
    endpoint_observed: Optional[bool] = None
    eda_backend: Optional[str] = None
    verification_level: Optional[str] = None
    verification_cwd: Optional[str] = None
    tool_path: Optional[str] = None
    eda_version: Optional[str] = None
    qualification_admissible: Optional[bool] = None
    build_command: Optional[str] = None
    build_exit_code: Optional[int] = None
    build_log_sha256: Optional[str] = None
    test_command: Optional[str] = None
    test_exit_code: Optional[int] = None
    test_log_sha256: Optional[str] = None
    runtime_attestation_sha256: Optional[str] = None
    endpoint_url: Optional[str] = None


class OutcomeManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["pass", "fail", "timeout", "scope_violation", "endpoint_unavailable"]
    false_success: bool = Field(..., description="True if agent claimed pass but verifier failed")
    failure_class: Optional[Literal[
        "MODEL_REASONING_FAIL",
        "TOOL_CALL_FAIL",
        "CONTEXT_FAIL",
        "BUILD_FAIL",
        "TEST_FAIL",
        "HALLUCINATED_SUCCESS",
        "SCOPE_VIOLATION",
        "TIMEOUT",
        "ENDPOINT_UNAVAILABLE"
    ]] = None
    human_acceptance_rating: Optional[Literal["A", "B", "C", "D"]] = None


class GV100HRunManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    task_id: str
    benchmark_task_id: Optional[str] = None
    pair_id: Optional[str] = None
    repetition: Optional[int] = 1
    experiment_arm: Literal["arm_a_prompt_only", "arm_b_governed_sidecar", "benchmark_baseline", "synthetic_replay"]
    target_repo: str
    base_commit: str
    head_commit: Optional[str] = None
    model_id: str
    model_hash: Optional[str] = None
    runtime: Literal["llama.cpp", "vllm", "sglang", "transformers", "mock_replay"]
    runtime_commit: Optional[str] = None
    token_budget: Optional[int] = None
    tool_budget: Optional[int] = None
    quantization: Optional[Literal["Q4_K_M", "Q8_0", "AWQ_4BIT", "GPTQ_4BIT", "FP16", "FP8", "NONE"]] = "NONE"
    framework_commit: str
    contract_id: str
    contract_hash: Optional[str] = None
    execution_contract_id: Optional[str] = None
    execution_contract_hash: Optional[str] = None
    benchmark_case_hash: Optional[str] = None
    knowledge_repo: Optional[str] = None
    knowledge_repo_commit: Optional[str] = None
    knowledge_manifest_hash: Optional[str] = None
    dataset_hash: Optional[str] = None
    client: Optional[Literal["cline", "continue", "direct_gateway", "harness_internal"]] = "harness_internal"
    client_version: Optional[str] = None
    interception_mode: Optional[Literal["ENFORCED", "POST_HOC", "UNSUPPORTED"]] = "POST_HOC"
    sampling: Optional[SamplingConfig] = Field(default_factory=SamplingConfig)
    hardware: HardwareManifest
    timing: Optional[TimingManifest] = Field(default_factory=TimingManifest)
    evidence: EvidenceManifest
    outcome: OutcomeManifest


