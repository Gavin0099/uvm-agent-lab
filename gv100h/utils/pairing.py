import json
import hashlib
from typing import Dict, Any, Optional


def compute_canonical_pair_id(
    benchmark_task_id: str,
    repetition: int,
    base_commit: str,
    model_id: str,
    model_hash: str = "none",
    runtime_commit: str = "none",
    sampling: Optional[Dict[str, Any]] = None,
    token_budget: int = 8000,
    tool_budget: int = 20,
    benchmark_case_hash: str = "none",
    knowledge_manifest_hash: str = "none",
    execution_contract_hash: str = "none",
    runtime: str = "none",
    quantization: str = "none",
) -> str:
    """
    Deterministically computes a cryptographic pair_id from experiment invariant fields.
    Guarantees that Arm A and Arm B must share exact identical invariants to form a valid pair.
    """
    sampling_canonical = json.dumps(sampling or {}, sort_keys=True)
    payload = (
        f"{benchmark_task_id}|{repetition}|{base_commit}|{model_id}|{model_hash}|"
        f"{runtime_commit}|{sampling_canonical}|{token_budget}|{tool_budget}|"
        f"{benchmark_case_hash}|{knowledge_manifest_hash}|{execution_contract_hash}|"
        f"{runtime}|{quantization}"
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"pair-{digest[:16]}"

