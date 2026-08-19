"""Production 1 task × 1 repetition × 2 arms slice.

Not the dirty scripts/run_live_eval.py harness. A passing mock slice is
software E2E scaffold only: never universe_complete and never GO.
"""

from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from agent.runners.models import AgentExecutionContext, AgentRunResult
from agent.runners.openai_compatible_runner import OpenAICompatibleLLMRunner
from gv100h.governance.runtime_bridge import GovernanceRuntimeBridge
from gv100h.manifests.models import (
    EvidenceManifest,
    GV100HRunManifest,
    HardwareManifest,
    OutcomeManifest,
    SamplingConfig,
    TimingManifest,
)
from gv100h.manifests.validator import ManifestValidator
from gv100h.runner.verifier import FinalVerificationResult, IndependentVerifier
from gv100h.runner.worktree_runner import GitWorktreeRunner
from gv100h.utils.evidence_commit import compute_reconstructed_head_commit
from gv100h.utils.case_contract import compute_benchmark_case_hash
from gv100h.utils.pairing import compute_canonical_pair_id
from scripts.profile_runtime import sample_gpu_telemetry, sha256_file

ARMS = ("arm_a_prompt_only", "arm_b_governed_sidecar")
DEFAULT_MODEL_ID = "Qwen/Qwen3.8-27B"
DEFAULT_TARGET_REPO = "Gavin0099/uvm-agent-lab"
SAMPLING = {"temperature": 0.0, "top_p": 1.0, "max_tokens": 2048}
TOKEN_BUDGET = 8000
TOOL_BUDGET = 20


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _resolve_repo_root(repo_root: Optional[Union[str, Path]]) -> Path:
    if repo_root is not None:
        return Path(repo_root).resolve()
    return Path(__file__).resolve().parents[2]


def _git_sha(cwd: Path, ref: str = "HEAD") -> str:
    res = subprocess.run(
        ["git", "rev-parse", ref],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
    )
    return res.stdout.strip()


def _framework_commit(repo_root: Path) -> str:
    nested = repo_root / "additional" / "ai-governance-framework"
    if (nested / ".git").exists() or (nested / ".git").is_file():
        return _git_sha(nested)
    return _git_sha(repo_root)


def _load_case(case_path: Path) -> Dict[str, Any]:
    with open(case_path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"benchmark case is not a mapping: {case_path}")
    return data


def _write_bundle_file(path: Path, payload: bytes) -> None:
    path.write_bytes(payload)


def _hardware_manifest(initial: Dict[str, Any], final: Dict[str, Any]) -> HardwareManifest:
    observed_samples = [sample for sample in (initial, final) if sample.get("hardware_observed")]
    selected = final if final.get("hardware_observed") else initial
    gpus = selected.get("gpus", [])
    names = sorted({str(gpu.get("name", "unknown")) for gpu in gpus})
    all_gpu_samples = [gpu for sample in observed_samples for gpu in sample.get("gpus", [])]
    total_memory = max(
        (float(gpu.get("memory_total_mb", 0.0)) / 1024.0 for gpu in gpus),
        default=None,
    )
    peak_memory = max(
        (float(gpu.get("memory_used_mb", 0.0)) / 1024.0 for gpu in all_gpu_samples),
        default=None,
    )
    return HardwareManifest(
        gpu_count=len(gpus),
        gpu_model=", ".join(names) if names else "Unobserved Hardware",
        hardware_observed=bool(observed_samples),
        vram_total_gb=total_memory,
        vram_peak_used_gb=peak_memory,
    )


def _build_file_snapshots(worktree_path: Path, changed_paths: List[str]) -> bytes:
    files = []
    for changed_path in sorted(changed_paths):
        target = worktree_path / changed_path
        if target.is_symlink():
            files.append({
                "kind": "symlink",
                "path": changed_path,
                "target": target.readlink().as_posix(),
            })
        elif target.is_file():
            content = target.read_bytes()
            files.append({
                "content_b64": base64.b64encode(content).decode("ascii"),
                "kind": "file",
                "path": changed_path,
                "sha256": _sha256_bytes(content),
                "size": len(content),
            })
        else:
            files.append({"kind": "missing", "path": changed_path})
    return json.dumps(
        {"files": files},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _run_one_arm(
    *,
    arm: str,
    case_data: Dict[str, Any],
    task_id: str,
    pair_id: str,
    repetition: int,
    mode: str,
    model_id: str,
    base_commit: str,
    framework_commit: str,
    bundle_dir: Path,
    worktree_mgr: GitWorktreeRunner,
    runner: OpenAICompatibleLLMRunner,
    bridge: GovernanceRuntimeBridge,
    validator: ManifestValidator,
    runtime: str,
    quantization: str,
    model_hash: Optional[str],
    runtime_commit: Optional[str],
) -> GV100HRunManifest:
    worktree_path, resolved_sha = worktree_mgr.create_worktree(base_commit)
    if resolved_sha != base_commit:
        worktree_mgr.cleanup_worktree(worktree_path)
        raise RuntimeError(
            f"worktree base drifted: expected {base_commit}, got {resolved_sha}"
        )

    t0 = time.time()
    run_id = f"run-{uuid.uuid4().hex[:12]}"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    initial_hardware = sample_gpu_telemetry() if mode == "live" else {
        "hardware_observed": False,
        "gpu_count": 0,
        "gpus": [],
    }

    try:
        _is_admitted, guardrail, gov_ctx = bridge.pre_benchmark_execution_check(
            benchmark_task_id=task_id,
            worktree_root=str(worktree_path),
            case_data=case_data,
        )
        sidecar = guardrail if arm == "arm_b_governed_sidecar" else None
        treatment = "governed_sidecar" if arm == "arm_b_governed_sidecar" else "prompt_only"
        context = AgentExecutionContext(
            workspace_root=worktree_path,
            sidecar_guardrail=sidecar,
            treatment=treatment,
            token_budget=TOKEN_BUDGET,
            tool_budget=TOOL_BUDGET,
            timeout_sec=120,
        )
        agent_result: AgentRunResult = runner.run_case(case_data, context=context)
        elapsed = time.time() - t0
        final_hardware = sample_gpu_telemetry() if mode == "live" else initial_hardware

        raw_diff, changed_paths, worktree_digest = worktree_mgr.extract_worktree_diff(
            worktree_path, base_commit
        )
        reconstructed_head_commit = compute_reconstructed_head_commit(
            worktree_path,
            base_commit,
        )
        if isinstance(raw_diff, str):
            diff_bytes = raw_diff.encode("utf-8")
        else:
            diff_bytes = bytes(raw_diff)

        is_scope_compliant, _msg = bridge.post_benchmark_execution_check(
            benchmark_task_id=task_id,
            changed_paths=changed_paths,
            guardrail=guardrail,
        )
        target_rel = case_data.get("inputs", {}).get("target_file")
        verifier_res: FinalVerificationResult = IndependentVerifier(
            workspace_root=worktree_path, mode=mode
        ).verify_task(
            changed_paths=changed_paths,
            target_file=target_rel,
            verification=case_data.get("verification"),
        )

        if not is_scope_compliant:
            final_status = "scope_violation"
            false_success = agent_result.agent_claimed_outcome == "success"
            failure_class = "SCOPE_VIOLATION"
        elif not verifier_res.final_pass:
            final_status = "fail"
            false_success = agent_result.agent_claimed_outcome == "success"
            failure_class = verifier_res.failure_class or "BUILD_FAIL"
        else:
            final_status = "pass"
            false_success = False
            failure_class = None

        build_log_bytes = verifier_res.build_log.encode("utf-8")
        sim_log_bytes = verifier_res.test_log.encode("utf-8")
        workspace_tree_bytes = worktree_mgr.build_workspace_tree_snapshot(
            worktree_path, changed_paths
        )
        workspace_tree_sha256 = _sha256_bytes(workspace_tree_bytes)
        if workspace_tree_sha256 != worktree_digest:
            raise RuntimeError("workspace tree digest changed during evidence capture")
        file_snapshots_bytes = _build_file_snapshots(worktree_path, changed_paths)
        endpoint_observed = bool(agent_result.execution.get("endpoint_observed", False))
        tool_trace_bytes = json.dumps(
            {**agent_result.execution, "endpoint_observed": endpoint_observed},
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        ).encode("utf-8")
        verification_bytes = json.dumps(
            {**verifier_res.model_dump(), "endpoint_observed": endpoint_observed},
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        ).encode("utf-8")
        target_rel = str(target_rel).replace("\\", "/")
        target_bytes = (worktree_path / target_rel).read_bytes()
        _write_bundle_file(bundle_dir / "diff.patch", diff_bytes)
        _write_bundle_file(bundle_dir / "build.log", build_log_bytes)
        _write_bundle_file(bundle_dir / "simulation.log", sim_log_bytes)
        _write_bundle_file(bundle_dir / "workspace_tree.json", workspace_tree_bytes)
        _write_bundle_file(bundle_dir / "file_snapshots.json", file_snapshots_bytes)
        _write_bundle_file(bundle_dir / "tool_trace.json", tool_trace_bytes)
        _write_bundle_file(bundle_dir / "verification.json", verification_bytes)

        manifest = GV100HRunManifest(
            run_id=run_id,
            task_id=task_id,
            benchmark_task_id=task_id,
            pair_id=pair_id,
            repetition=repetition,
            experiment_arm=arm,
            target_repo=DEFAULT_TARGET_REPO,
            base_commit=base_commit,
            head_commit=reconstructed_head_commit,
            model_id=model_id,
            benchmark_case_hash=compute_benchmark_case_hash(case_data),
            runtime=runtime,
            runtime_commit=runtime_commit,
            model_hash=model_hash,
            quantization=quantization,
            token_budget=TOKEN_BUDGET,
            tool_budget=TOOL_BUDGET,
            framework_commit=framework_commit,
            contract_id=gov_ctx["execution_contract_id"],
            contract_hash=gov_ctx["execution_contract_hash"],
            execution_contract_id=gov_ctx["execution_contract_id"],
            execution_contract_hash=gov_ctx["execution_contract_hash"],
            interception_mode=agent_result.execution.get(
                "interception_mode", gov_ctx["interception_mode"]
            ),
            sampling=SamplingConfig(**SAMPLING),
            hardware=_hardware_manifest(initial_hardware, final_hardware),
            timing=TimingManifest(wall_clock_sec=round(elapsed, 2)),
            evidence=EvidenceManifest(
                evidence_schema_version="2",
                git_diff_sha256=_sha256_bytes(diff_bytes),
                changed_paths=changed_paths,
                workspace_tree_sha256=workspace_tree_sha256,
                target_file=target_rel,
                target_file_sha256=_sha256_bytes(target_bytes),
                file_snapshots_sha256=_sha256_bytes(file_snapshots_bytes),
                tool_trace_sha256=_sha256_bytes(tool_trace_bytes),
                verification_sha256=_sha256_bytes(verification_bytes),
                endpoint_observed=endpoint_observed,
                eda_backend=verifier_res.eda_backend,
                verification_level=verifier_res.verification_level,
                verification_cwd=verifier_res.verification_cwd,
                tool_path=verifier_res.tool_path,
                eda_version=verifier_res.eda_version,
                qualification_admissible=verifier_res.qualification_admissible,
                build_command=verifier_res.build_command,
                build_exit_code=verifier_res.build_exit_code,
                build_log_sha256=_sha256_bytes(build_log_bytes),
                test_command=verifier_res.test_command,
                test_exit_code=verifier_res.test_exit_code,
                test_log_sha256=_sha256_bytes(sim_log_bytes),
            ),
            outcome=OutcomeManifest(
                status=final_status,
                false_success=false_success,
                failure_class=failure_class,
            ),
        )
        validator.validate_manifest_dict(manifest.model_dump())
        validator.validate_manifest_bundle(
            manifest,
            bundle_dir,
            require_integrity=True,
            repo_root=worktree_mgr.repo_root,
            replay_verification=True,
        )
        _write_bundle_file(
            bundle_dir / "manifest.json",
            json.dumps(manifest.model_dump(), indent=2).encode("utf-8"),
        )
        return manifest
    finally:
        worktree_mgr.cleanup_worktree(worktree_path)


def run_single_ab_pair(
    *,
    task_id: str = "UVM-001",
    case_path: Union[str, Path],
    repetition: int = 1,
    mode: str = "mock",
    output_dir: Union[str, Path],
    repo_root: Optional[Union[str, Path]] = None,
    model_id: str = DEFAULT_MODEL_ID,
    api_base: str = "http://localhost:8000/v1",
    runtime: Optional[str] = None,
    quantization: Optional[str] = None,
    model_hash: Optional[str] = None,
    model_artifact_path: Optional[Union[str, Path]] = None,
    runtime_commit: Optional[str] = None,
) -> Dict[str, Any]:
    if mode not in {"mock", "live"}:
        raise ValueError(f"Unknown mode '{mode}'. Must be 'live' or 'mock'.")
    if repetition < 1:
        raise ValueError("repetition must be >= 1")

    if model_hash is None and model_artifact_path is not None:
        model_hash = sha256_file(str(model_artifact_path))
    if mode == "live":
        missing = [
            name for name, value in {
                "runtime": runtime,
                "quantization": quantization,
                "model_hash": model_hash,
                "runtime_commit": runtime_commit,
            }.items() if not value
        ]
        if missing:
            raise ValueError(
                "Live pair execution requires explicit provenance: "
                + ", ".join(missing)
            )
    else:
        runtime = "mock_replay"
        quantization = "NONE"

    repo = _resolve_repo_root(repo_root)
    case_file = Path(case_path).resolve()
    case_data = _load_case(case_file)
    if case_data.get("id") and case_data["id"] != task_id:
        raise ValueError(f"case id {case_data['id']!r} does not match task_id {task_id!r}")

    out_path = Path(output_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    base_commit = _git_sha(repo)
    framework_commit = _framework_commit(repo)
    bridge = GovernanceRuntimeBridge()
    _pair_admitted, _pair_guardrail, pair_gov_ctx = bridge.pre_benchmark_execution_check(
        benchmark_task_id=task_id,
        worktree_root=str(repo),
        case_data=case_data,
    )
    pair_id = compute_canonical_pair_id(
        benchmark_task_id=task_id,
        repetition=repetition,
        base_commit=base_commit,
        model_id=model_id,
        model_hash=model_hash or "none",
        runtime_commit=runtime_commit or "none",
        sampling=SAMPLING,
        token_budget=TOKEN_BUDGET,
        tool_budget=TOOL_BUDGET,
        benchmark_case_hash=compute_benchmark_case_hash(case_data),
        execution_contract_hash=pair_gov_ctx["execution_contract_hash"],
    )

    validator = ManifestValidator()
    worktree_mgr = GitWorktreeRunner(str(repo))
    runner = OpenAICompatibleLLMRunner(
        name=model_id.split("/")[-1],
        api_base=api_base,
        model_id=model_id,
        mock_mode=(mode == "mock"),
    )

    manifests: List[GV100HRunManifest] = []
    bundle_dirs: Dict[str, Path] = {}
    for arm in ARMS:
        bundle = out_path / task_id / pair_id / f"rep-{repetition}" / arm
        bundle_dirs[arm] = bundle
        manifests.append(
            _run_one_arm(
                arm=arm,
                case_data=case_data,
                task_id=task_id,
                pair_id=pair_id,
                repetition=repetition,
                mode=mode,
                model_id=model_id,
                base_commit=base_commit,
                framework_commit=framework_commit,
                bundle_dir=bundle,
                worktree_mgr=worktree_mgr,
                runner=runner,
                bridge=bridge,
                validator=validator,
                runtime=runtime,
                quantization=quantization,
                model_hash=model_hash,
                runtime_commit=runtime_commit,
            )
        )

    validator.validate_manifest_set(manifests, require_complete_pairs=True)

    return {
        "task_id": task_id,
        "repetition": repetition,
        "pair_id": pair_id,
        "manifests": manifests,
        "bundle_dirs": bundle_dirs,
        "output_dir": out_path,
        "universe_complete_claim_allowed": False,
        "admissible_for_model_qualification": False,
        "evidence_class": "synthetic_offline_scaffold",
        "qualification_decision": "NO_GO",
        "planned_runs": 2,
        "required_total_runs": 60,
    }
