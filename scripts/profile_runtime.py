#!/usr/bin/env python3
"""
GV100H Runtime Profiler and Hardware Telemetry Collector
Executes consecutive requests against inference endpoints, queries NVML / nvidia-smi
for peak VRAM and temperature, and validates exit gate criteria.
"""

import sys
import time
import json
import hashlib
import shutil
import argparse
import subprocess
import urllib.request
import re
from datetime import datetime, timezone
from statistics import fmean
from pathlib import Path
from typing import Dict, Any, List, Optional, Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gv100h.runtime.admission_matrix import (
    RuntimeAdmissionMatrix,
    canonical_profile_identity,
)
from gv100h.runtime.context_fixtures import load_context_fixture
from gv100h.runtime.launch_profiles import resolve_launch_command
from gv100h.runtime.model_provenance import (
    load_model_manifest,
    verify_model_verification_receipt,
)
from gv100h.runtime.attestation import RuntimeProcessAttestor, finalize_attestation
from gv100h.runtime.ssot import GV100H_BASELINE
from gv100h.utils.url import normalize_openai_base_url

EXPERIMENTAL_KV_CACHE_TYPES = frozenset({"q4_0", "q4_1", "q5_0", "q5_1"})


def normalize_kv_cache_type(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def parse_runtime_command_json(value: str) -> List[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(
            "--runtime-command-json must contain valid JSON"
        ) from exc
    if (
        not isinstance(parsed, list)
        or not parsed
        or any(not isinstance(item, str) or not item for item in parsed)
    ):
        raise argparse.ArgumentTypeError(
            "--runtime-command-json must be a non-empty JSON array of non-empty strings"
        )
    return parsed


def context_aware_request_timeout(context_length: Optional[int]) -> float:
    """Return a request budget that scales with the prompt context slot."""

    effective_context = context_length or 32768
    return float(max(120, round(effective_context / 32768 * 120)))


def sha256_file(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    file_path = Path(path)
    if not file_path.is_file():
        return None
    digest = hashlib.sha256()
    with file_path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_llama_server_version(executable: Optional[str] = None) -> Optional[str]:
    command = executable or shutil.which("llama-server")
    if not command:
        return None
    for flag in ("--version", "-v"):
        try:
            result = subprocess.run(
                [command, flag], capture_output=True, text=True, timeout=10
            )
        except (OSError, subprocess.SubprocessError):
            continue
        output = (result.stdout or result.stderr).strip()
        if result.returncode == 0 and output:
            return output.splitlines()[0]
    return None


def extract_response_timing(response: Dict[str, Any]) -> Dict[str, Any]:
    timings = response.get("timings")
    if not isinstance(timings, dict):
        return {}

    usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
    prompt_tokens = timings.get("prompt_n", usage.get("prompt_tokens"))
    decode_tokens = timings.get("predicted_n", usage.get("completion_tokens"))
    prompt_ms = timings.get("prompt_ms")
    decode_ms = timings.get("predicted_ms")
    prefill_tps = timings.get("prompt_per_second")
    decode_tps = timings.get("predicted_per_second")

    if prefill_tps is None and prompt_tokens and prompt_ms:
        prefill_tps = float(prompt_tokens) / (float(prompt_ms) / 1000.0)
    if decode_tps is None and decode_tokens and decode_ms:
        decode_tps = float(decode_tokens) / (float(decode_ms) / 1000.0)

    return {
        "prefill_tokens": int(prompt_tokens) if prompt_tokens else None,
        "prefill_latency_sec": float(prompt_ms) / 1000.0 if prompt_ms else None,
        "prefill_tps": float(prefill_tps) if prefill_tps else None,
        "decode_tokens": int(decode_tokens) if decode_tokens else None,
        "decode_latency_sec": float(decode_ms) / 1000.0 if decode_ms else None,
        "decode_tps": float(decode_tps) if decode_tps else None,
    }


def validate_profile_response(
    response: Dict[str, Any],
    *,
    expected_model_id: str,
    expected_response_sha256: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate response semantics before counting a request as successful."""

    if not isinstance(response, dict):
        return {"valid": False, "reason": "response_not_object"}
    if response.get("model") != expected_model_id:
        return {"valid": False, "reason": "response_model_mismatch"}
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return {"valid": False, "reason": "choices_missing"}
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        return {"valid": False, "reason": "content_missing"}
    if "\ufffd" in content or any(
        ord(char) < 32 and char not in "\n\r\t" for char in content
    ):
        return {"valid": False, "reason": "content_malformed"}
    tokens = content.split()
    if len(tokens) >= 12:
        max_repetition = max(tokens.count(token) for token in set(tokens))
        if max_repetition / len(tokens) >= 0.8:
            return {"valid": False, "reason": "content_repetition"}
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    if expected_response_sha256 and content_hash.lower() != expected_response_sha256.lower():
        return {"valid": False, "reason": "expected_response_hash_mismatch"}
    return {
        "valid": True,
        "reason": None,
        "content_sha256": content_hash,
    }


def _normalize_selected_gpu_pair(
    selected_gpu_pair: Optional[Sequence[int]],
) -> Optional[List[int]]:
    if selected_gpu_pair is None:
        return None
    pair = list(selected_gpu_pair)
    if (
        len(pair) != 2
        or pair[0] == pair[1]
        or any(not isinstance(index, int) or index < 0 for index in pair)
    ):
        raise ValueError("selected_gpu_pair must contain two distinct non-negative GPU indices")
    return pair


def _parse_nvlink_topology_matrix(output: str) -> Dict[str, Any]:
    lines = [line.split() for line in output.splitlines() if line.split()]
    header_index = next(
        (
            index
            for index, tokens in enumerate(lines)
            if sum(token.startswith("GPU") for token in tokens) >= 2
        ),
        None,
    )
    if header_index is None:
        return {"gpu_ids": [], "relations": {}}

    headers = [
        int(token[3:])
        for token in lines[header_index]
        if token.startswith("GPU") and token[3:].isdigit()
    ]
    relations: Dict[str, str] = {}
    for tokens in lines[header_index + 1 :]:
        if not tokens or not tokens[0].startswith("GPU"):
            continue
        row_id = tokens[0][3:]
        if not row_id.isdigit():
            continue
        for column_index, column_id in enumerate(headers):
            cell_position = column_index + 1
            if cell_position < len(tokens):
                relations[f"{int(row_id)}->{column_id}"] = tokens[cell_position]
    return {
        "gpu_ids": headers,
        "relations": relations,
    }


def sample_nvlink_topology(
    gpu_count: int = 0,
    selected_gpu_pair: Optional[Sequence[int]] = None,
) -> Dict[str, Any]:
    """Capture nvidia-smi topology evidence without inferring it from GPU count."""

    normalized_pair = _normalize_selected_gpu_pair(selected_gpu_pair)
    if not shutil.which("nvidia-smi"):
        return {
            "telemetry_source": "unavailable_no_nvidia_smi",
            "gpu_count": gpu_count,
            "nvlink_observed": False,
            "nvlink_links": [],
            "selected_gpu_pair": normalized_pair,
            "selected_pair_nvlink_observed": False,
        }
    try:
        result = subprocess.run(
            ["nvidia-smi", "topo", "-m"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "telemetry_source": "nvidia_smi_topology_failed",
            "gpu_count": gpu_count,
            "nvlink_observed": False,
            "nvlink_links": [],
            "selected_gpu_pair": normalized_pair,
            "selected_pair_nvlink_observed": False,
            "error": str(exc),
        }
    if result.returncode != 0:
        return {
            "telemetry_source": "nvidia_smi_topology_failed",
            "gpu_count": gpu_count,
            "nvlink_observed": False,
            "nvlink_links": [],
            "selected_gpu_pair": normalized_pair,
            "selected_pair_nvlink_observed": False,
        }
    links = sorted(set(re.findall(r"\bNV\d+\b", result.stdout)))
    parsed = _parse_nvlink_topology_matrix(result.stdout)
    effective_pair = normalized_pair
    if effective_pair is None and gpu_count >= 2 and len(parsed["gpu_ids"]) >= 2:
        effective_pair = parsed["gpu_ids"][:2]
    relations = parsed["relations"]
    selected_relations = {}
    selected_pair_observed = False
    if effective_pair is not None:
        selected_relations = {
            f"{effective_pair[0]}->{effective_pair[1]}": relations.get(
                f"{effective_pair[0]}->{effective_pair[1]}"
            ),
            f"{effective_pair[1]}->{effective_pair[0]}": relations.get(
                f"{effective_pair[1]}->{effective_pair[0]}"
            ),
        }
        selected_pair_observed = all(
            isinstance(relation, str) and relation.startswith("NV")
            for relation in selected_relations.values()
        )
    return {
        "telemetry_source": "nvidia_smi_topology_live",
        "gpu_count": gpu_count,
        "nvlink_observed": selected_pair_observed,
        "nvlink_links": links,
        "gpu_ids": parsed["gpu_ids"],
        "selected_gpu_pair": effective_pair,
        "selected_pair_relations": selected_relations,
        "selected_pair_nvlink_observed": selected_pair_observed,
        "topology_sha256": hashlib.sha256(result.stdout.encode("utf-8")).hexdigest(),
    }


def sample_gpu_telemetry(
    selected_gpu_pair: Optional[Sequence[int]] = None,
) -> Dict[str, Any]:
    """
    Samples physical GPU telemetry using nvidia-smi if available.
    """
    if not shutil.which("nvidia-smi"):
        return {
            "telemetry_source": "unavailable_no_nvidia_smi",
            "hardware_observed": False,
            "gpu_count": 0,
            "gpus": [],
            "nvlink": sample_nvlink_topology(0, selected_gpu_pair),
        }

    try:
        cmd = [
            "nvidia-smi",
            "--query-gpu=index,name,memory.used,memory.total,temperature.gpu,utilization.gpu",
            "--format=csv,noheader,nounits"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return {"telemetry_source": "nvidia_smi_failed", "hardware_observed": False, "gpus": []}

        gpus = []
        for line in result.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 6:
                gpus.append({
                    "index": int(parts[0]),
                    "name": parts[1],
                    "memory_used_mb": float(parts[2]),
                    "memory_total_mb": float(parts[3]),
                    "temperature_c": float(parts[4]),
                    "gpu_utilization_pct": float(parts[5])
                })

        return {
            "telemetry_source": "nvidia_smi_live",
            "hardware_observed": len(gpus) > 0,
            "gpu_count": len(gpus),
            "gpus": gpus,
            "nvlink": sample_nvlink_topology(len(gpus), selected_gpu_pair),
        }
    except Exception as e:
        return {
            "telemetry_source": f"error: {str(e)}",
            "hardware_observed": False,
            "gpus": [],
            "nvlink": sample_nvlink_topology(0, selected_gpu_pair),
        }


def compute_profile_metrics(
    avg_latency: float,
    peak_vram_mb: float,
    *,
    prefill_latency_sec: Optional[float] = None,
    prefill_tokens: Optional[int] = None,
    prefill_tps: Optional[float] = None,
    decode_latency_sec: Optional[float] = None,
    decode_tokens: int = 128,
    decode_tps: Optional[float] = None,
    decode_timing_observed: bool = True,
) -> Dict[str, Any]:
    """
    Canonical hardware-profile fields consumed by generate_poc_report /
    QualificationPolicyEvaluator. Do not nest the live metrics only under
    gpu_telemetry or emit est_decode_tps without decode_tps.
    """
    observed_decode_tps = decode_tps if decode_timing_observed else None
    estimated_end_to_end_tps = None
    if not decode_timing_observed:
        estimated_end_to_end_tps = decode_tokens / avg_latency if avg_latency > 0 else None
    elif observed_decode_tps is None:
        decode_duration = (
            decode_latency_sec
            if decode_latency_sec and decode_latency_sec > 0
            else avg_latency
        )
        observed_decode_tps = decode_tokens / decode_duration if decode_duration > 0 else None
    observed_prefill_tps = prefill_tps
    if observed_prefill_tps is None and prefill_latency_sec and prefill_latency_sec > 0 and prefill_tokens:
        observed_prefill_tps = prefill_tokens / prefill_latency_sec
    vram_peak = round(peak_vram_mb / 1024.0, 2) if peak_vram_mb > 0 else None
    return {
        "prefill_tps": round(observed_prefill_tps, 2) if observed_prefill_tps else None,
        "prefill_latency_sec": round(prefill_latency_sec, 4) if prefill_latency_sec else None,
        "prefill_tokens": prefill_tokens,
        "decode_tps": round(observed_decode_tps, 2) if observed_decode_tps else None,
        "est_decode_tps": round(observed_decode_tps, 2) if observed_decode_tps else None,
        "estimated_end_to_end_tps": (
            round(estimated_end_to_end_tps, 2) if estimated_end_to_end_tps else None
        ),
        "decode_latency_sec": round(decode_latency_sec, 4) if decode_latency_sec else None,
        "decode_tokens": decode_tokens,
        "vram_peak_per_gpu_gb": vram_peak,
    }


def _has_build_provenance(summary: Dict[str, Any], candidate: Any) -> bool:
    provenance = summary.get("build_provenance")
    provenance = provenance if isinstance(provenance, dict) else {}
    commit = summary.get("llama_cpp_commit") or provenance.get("llama_cpp_commit")
    version = summary.get("llama_server_version") or provenance.get("llama_server_version")
    fix_reference = summary.get("kv_cache_fix_reference") or provenance.get("fix_reference")
    fix_verified = summary.get("kv_cache_fix_verified")
    if fix_verified is None:
        fix_verified = provenance.get("fix_verified")
    return bool(
        commit
        and version
        and fix_verified is True
        and fix_reference == candidate.kv_cache_fix_pr_url
    )


def _selected_kv_types(summary: Dict[str, Any], candidate: Any) -> tuple[str, str]:
    profile = summary.get("runtime_profile")
    profile = profile if isinstance(profile, dict) else {}
    selected_k = profile.get("kv_cache_type_k") or summary.get("kv_cache_type_k")
    selected_v = profile.get("kv_cache_type_v") or summary.get("kv_cache_type_v")
    fallback = profile.get("kv_cache_type") or summary.get("kv_cache_type") or candidate.kv_cache_type_k
    return normalize_kv_cache_type(selected_k or fallback), normalize_kv_cache_type(selected_v or fallback)


def evaluate_profile_gate(candidate: Any, summary: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate hardware admission criteria from observed profile fields only."""
    criteria = candidate.exit_gate_criteria
    observed_vram = summary.get("vram_peak_per_gpu_gb")
    observed_tps = summary.get("decode_tps")
    selected_k, selected_v = _selected_kv_types(summary, candidate)
    experimental_kv = selected_k in EXPERIMENTAL_KV_CACHE_TYPES or selected_v in EXPERIMENTAL_KV_CACHE_TYPES
    checks = {
        "hardware_observed": summary.get("hardware_observed") is True,
        "gpu_count": summary.get("gpu_telemetry", {}).get("initial", {}).get("gpu_count", 0)
        >= max(candidate.gpu_count, candidate.tensor_parallel),
        "min_success_requests": summary.get("success_count", 0) >= criteria["min_success_requests"],
        "max_corruption_count": summary.get("corruption_count", 999999) <= criteria["max_corruption_count"],
        "max_vram_per_gpu_gb": observed_vram is not None and observed_vram <= criteria["max_vram_per_gpu_gb"],
        "prefill_evidence": summary.get("prefill_evidence") is True
        or (
            (summary.get("prefill_tps", 0) or 0) > 0
            and (summary.get("prefill_latency_sec", 0) or 0) > 0
        ),
        "decode_evidence": summary.get("decode_evidence") is True
        or (
            (summary.get("decode_tps", 0) or 0) > 0
            and (summary.get("decode_tokens", 0) or 0) > 0
        ),
        "model_artifact_hash": summary.get("model_provenance_ready") is True,
        "model_provenance_independent": summary.get("model_provenance_independent") is True,
        "runtime_process_owned": summary.get("runtime_process_owned") is True,
        "runtime_attestation_bound": summary.get("runtime_attestation_bound") is True,
        "kv_cache_pair_consistent": selected_k == selected_v,
        "experimental_kv_build_provenance": not experimental_kv or _has_build_provenance(summary, candidate),
        "experimental_kv_prefill_validation": not experimental_kv
        or summary.get("prefill_benchmark_passed") is True,
        "response_oracle": (
            summary.get("response_oracle") == "strict-v1"
            and summary.get("expected_response_hash_bound") is True
        ),
        "context_fixture_bound": summary.get("context_fixture_bound") is True,
        "launch_context_bound": summary.get("launch_context_bound") is True,
        "launch_profile_arm_consistent": summary.get("launch_profile_arm_consistent") is True,
    }
    initial_nvlink = summary.get("gpu_telemetry", {}).get("initial", {}).get("nvlink", {})
    required_gpu_pair = list(getattr(candidate, "selected_gpu_pair", []))
    checks["nvlink_observed"] = (
        max(candidate.gpu_count, candidate.tensor_parallel) < 2
        or (
            initial_nvlink.get("selected_gpu_pair") == required_gpu_pair
            and initial_nvlink.get("selected_pair_nvlink_observed") is True
        )
    )
    if criteria.get("comparison_only"):
        checks["target_decode_tps"] = True
    else:
        checks["target_decode_tps"] = (
            observed_tps is not None and observed_tps >= criteria["target_decode_tps"]
        )
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
    }


def _sample_gpu_telemetry_for_pair(
    selected_gpu_pair: Optional[Sequence[int]],
) -> Dict[str, Any]:
    if not selected_gpu_pair:
        return sample_gpu_telemetry()
    return sample_gpu_telemetry(selected_gpu_pair=selected_gpu_pair)


def _run_profile_requests(
    *,
    url: str,
    effective_model_id: str,
    prompt_content: str,
    num_requests: int,
    api_key: str,
    request_timeout_sec: float,
    expected_response_sha256: Optional[str],
    context_fixture: Any,
    runtime_attestation_seed: Optional[Dict[str, Any]],
    runtime_process: Optional[RuntimeProcessAttestor],
    selected_gpu_pair: Optional[Sequence[int]],
) -> Dict[str, Any]:
    latencies: List[float] = []
    success_count = 0
    corruption_count = 0
    corruption_reasons: List[str] = []
    prefill_tps_samples: List[float] = []
    prefill_latency_samples: List[float] = []
    prefill_token_samples: List[int] = []
    decode_tps_samples: List[float] = []
    decode_latency_samples: List[float] = []
    decode_token_samples: List[int] = []
    runtime_attestation = None
    initial_telemetry: Dict[str, Any] = {}
    final_telemetry: Dict[str, Any] = {}
    peak_vram_mb = 0.0

    try:
        initial_telemetry = _sample_gpu_telemetry_for_pair(selected_gpu_pair)
        for index in range(num_requests):
            payload = {
                "model": effective_model_id,
                "messages": [{"role": "user", "content": prompt_content}],
                "temperature": 0.0,
                "max_tokens": 128,
            }
            data = json.dumps(payload).encode("utf-8")
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }

            started_at = time.time()
            try:
                request = urllib.request.Request(
                    url,
                    data=data,
                    headers=headers,
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=request_timeout_sec) as response:
                    if response.status == 200:
                        response_json = json.loads(response.read().decode("utf-8"))
                        validation = validate_profile_response(
                            response_json,
                            expected_model_id=effective_model_id,
                            expected_response_sha256=expected_response_sha256,
                        )
                        timing = extract_response_timing(response_json)
                        if (
                            validation["valid"]
                            and context_fixture is not None
                            and timing.get("prefill_tokens")
                            != context_fixture.actual_prompt_tokens
                        ):
                            validation = {
                                "valid": False,
                                "reason": "context_prompt_token_mismatch",
                            }
                        if validation["valid"] and runtime_attestation_seed is not None:
                            try:
                                runtime_attestation = finalize_attestation(
                                    runtime_attestation_seed,
                                    endpoint_url=url.removesuffix("/chat/completions"),
                                    models_endpoint_response=runtime_attestation_seed[
                                        "models_endpoint_response"
                                    ],
                                    response_model=response_json.get("model", ""),
                                    observed_at=datetime.now(timezone.utc).isoformat(),
                                )
                            except (KeyError, TypeError, ValueError):
                                validation = {
                                    "valid": False,
                                    "reason": "runtime_attestation_binding_failed",
                                }
                        if validation["valid"]:
                            success_count += 1
                            if timing.get("prefill_tps"):
                                prefill_tps_samples.append(timing["prefill_tps"])
                            if timing.get("prefill_latency_sec"):
                                prefill_latency_samples.append(timing["prefill_latency_sec"])
                            if timing.get("prefill_tokens"):
                                prefill_token_samples.append(timing["prefill_tokens"])
                            if timing.get("decode_tps"):
                                decode_tps_samples.append(timing["decode_tps"])
                            if timing.get("decode_latency_sec"):
                                decode_latency_samples.append(timing["decode_latency_sec"])
                            if timing.get("decode_tokens"):
                                decode_token_samples.append(timing["decode_tokens"])
                        else:
                            corruption_count += 1
                            corruption_reasons.append(validation["reason"])
                    else:
                        corruption_count += 1
                        corruption_reasons.append(f"http_status_{response.status}")
            except json.JSONDecodeError:
                corruption_count += 1
                corruption_reasons.append("invalid_json")
            except Exception:
                corruption_count += 1
                corruption_reasons.append("request_exception")

            latencies.append(time.time() - started_at)
            if index % 10 == 0:
                current_telemetry = _sample_gpu_telemetry_for_pair(selected_gpu_pair)
                for gpu in current_telemetry.get("gpus", []):
                    if gpu["memory_used_mb"] > peak_vram_mb:
                        peak_vram_mb = gpu["memory_used_mb"]

        final_telemetry = _sample_gpu_telemetry_for_pair(selected_gpu_pair)
        return {
            "latencies": latencies,
            "success_count": success_count,
            "corruption_count": corruption_count,
            "corruption_reasons": corruption_reasons,
            "prefill_tps_samples": prefill_tps_samples,
            "prefill_latency_samples": prefill_latency_samples,
            "prefill_token_samples": prefill_token_samples,
            "decode_tps_samples": decode_tps_samples,
            "decode_latency_samples": decode_latency_samples,
            "decode_token_samples": decode_token_samples,
            "runtime_attestation": runtime_attestation,
            "initial_telemetry": initial_telemetry,
            "final_telemetry": final_telemetry,
            "peak_vram_mb": peak_vram_mb,
        }
    finally:
        if runtime_process is not None:
            runtime_process.stop()


def profile_endpoint(
    api_base: str,
    model_id: Optional[str] = None,
    candidate_name: str = GV100H_BASELINE.candidate_name,
    num_requests: int = 100,
    output_file: str = "results/hardware/profile_summary.json",
    model_path: Optional[str] = None,
    llama_server_path: Optional[str] = None,
    llama_cpp_commit: Optional[str] = None,
    llama_server_version: Optional[str] = None,
    kv_cache_type_k: Optional[str] = None,
    kv_cache_type_v: Optional[str] = None,
    prefill_tps: Optional[float] = None,
    prefill_latency_sec: Optional[float] = None,
    prefill_tokens: Optional[int] = None,
    prefill_benchmark_passed: Optional[bool] = None,
    kv_cache_fix_verified: Optional[bool] = None,
    expected_response_sha256: Optional[str] = None,
    api_key: str = "EMPTY",
    context_fixture_path: Optional[str] = None,
    model_manifest_path: Optional[str] = None,
    model_verification_receipt_path: Optional[str] = None,
    launch_profile_config_path: Optional[str] = None,
    launch_profile_id: Optional[str] = None,
    runtime_command: Optional[List[str]] = None,
    runtime: Optional[str] = None,
    runtime_commit: Optional[str] = None,
    runtime_version: Optional[str] = None,
    request_timeout_sec: Optional[float] = None,
    runtime_startup_timeout_sec: int = 60,
    require_harness_owned_runtime: bool = True,
) -> Dict[str, Any]:
    candidate = RuntimeAdmissionMatrix.get_candidate(candidate_name)
    effective_model_id = model_id or candidate.supported_models[0]
    context_fixture = load_context_fixture(context_fixture_path) if context_fixture_path else None
    timeout_was_explicit = request_timeout_sec is not None
    if request_timeout_sec is None:
        request_timeout_sec = context_aware_request_timeout(
            context_fixture.context_length if context_fixture is not None else candidate.baseline_context_length
        )
    elif request_timeout_sec <= 0:
        raise ValueError("request_timeout_sec must be greater than zero")
    if context_fixture is not None:
        allowed_contexts = set(candidate.context_sweep) | set(candidate.stretch_context_sweep)
        if context_fixture.context_length not in allowed_contexts:
            raise ValueError(
                f"context fixture length {context_fixture.context_length} is not in candidate sweep"
            )
        if expected_response_sha256 and (
            expected_response_sha256.lower() != context_fixture.expected_response_sha256.lower()
        ):
            raise ValueError("expected response hash does not match context fixture")
        expected_response_sha256 = context_fixture.expected_response_sha256
    prompt_content = (
        context_fixture.prompt
        if context_fixture is not None
        else "Ping request: calculate checksum"
    )
    norm_base = normalize_openai_base_url(api_base)
    runtime_process = None
    runtime_attestation_seed = None
    runtime_attestation = None
    if runtime_command is not None and (
        not isinstance(runtime_command, list)
        or not runtime_command
        or any(not isinstance(item, str) or not item for item in runtime_command)
    ):
        raise ValueError(
            "runtime_command must be a non-empty list of non-empty strings"
        )
    runtime_process_owned = runtime_command is not None
    if require_harness_owned_runtime and not runtime_command:
        raise ValueError(
            "formal Gate 4 profiling requires a harness-owned runtime_command"
        )
    launch_profile = None
    launch_context_bound = False
    launch_profile_arm_consistent = False
    if context_fixture is not None:
        if not launch_profile_config_path or not launch_profile_id:
            raise ValueError(
                "context fixture execution requires launch_profile_config_path and launch_profile_id"
            )
        launch_profile = resolve_launch_command(
            launch_profile_config_path,
            profile_id=launch_profile_id,
            model_artifact=candidate.model_artifact,
            context_length=context_fixture.context_length,
        )
        resolved_argv = launch_profile["resolved_launch_argv"]
        launch_context_bound = any(
            resolved_argv[index:index + 2] in (
                ["-c", str(context_fixture.context_length)],
                ["--ctx-size", str(context_fixture.context_length)],
            )
            for index in range(len(resolved_argv) - 1)
        )
        launch_profile_arm_consistent = (
            launch_profile["profile_id"] == (candidate.launch_profile_id or candidate.name)
            and launch_profile["spec_draft_n_max"] == candidate.spec_draft_n_max
            and launch_profile.get("spec_type")
            == ("draft-mtp" if candidate.mtp_enabled else "none")
            and [
                "--spec-type",
                launch_profile.get("spec_type"),
                "--spec-draft-n-max",
                str(launch_profile["spec_draft_n_max"]),
            ] == resolved_argv[-4:]
        )
    model_manifest = None
    model_manifest_error = "approved model provenance manifest not supplied"
    model_provenance_independent = False
    model_receipt_error = "independent model verification receipt not supplied"
    if model_manifest_path:
        try:
            model_manifest = load_model_manifest(model_manifest_path)
            model_manifest.validate_ssot(
                model_id=effective_model_id,
                model_artifact=candidate.model_artifact,
            )
            if not model_path:
                raise ValueError("model_path is required with a model provenance manifest")
            model_manifest.verify_artifact(model_path)
            model_manifest_error = None
        except ValueError as exc:
            model_manifest_error = str(exc)
        else:
            if model_verification_receipt_path:
                try:
                    verify_model_verification_receipt(
                        model_manifest_path,
                        model_path,
                        model_verification_receipt_path,
                        expected_model_id=effective_model_id,
                        expected_model_artifact=candidate.model_artifact,
                    )
                    model_provenance_independent = True
                    model_receipt_error = None
                except ValueError as exc:
                    model_receipt_error = str(exc)

    if runtime_command:
        if not model_path:
            raise ValueError("runtime_command profiling requires model_path")
        if launch_profile is not None and list(runtime_command) != launch_profile["resolved_launch_argv"]:
            raise ValueError("runtime_command does not match resolved launch profile argv")
        runtime_process = RuntimeProcessAttestor(
            runtime_command,
            runtime=runtime or candidate.runtime_type,
            runtime_commit=runtime_commit or "",
            runtime_version=runtime_version or "",
            model_id=effective_model_id,
            model_path=model_path,
            endpoint_url=norm_base,
            api_key=api_key,
            cwd=Path(model_path).resolve().parent,
            startup_timeout_sec=runtime_startup_timeout_sec,
        )
        runtime_attestation_seed = runtime_process.start()

    url = f"{norm_base}/chat/completions"


    print(f"Profiling Candidate '{candidate.name}' ({candidate.runtime_type}, {candidate.quantization})...")
    print(f"Target Endpoint: {url}")
    print(f"Executing {num_requests} requests...")

    observations = _run_profile_requests(
        url=url,
        effective_model_id=effective_model_id,
        prompt_content=prompt_content,
        num_requests=num_requests,
        api_key=api_key,
        request_timeout_sec=request_timeout_sec,
        expected_response_sha256=expected_response_sha256,
        context_fixture=context_fixture,
        runtime_attestation_seed=runtime_attestation_seed,
        runtime_process=runtime_process,
        selected_gpu_pair=candidate.selected_gpu_pair,
    )
    latencies = observations["latencies"]
    success_count = observations["success_count"]
    corruption_count = observations["corruption_count"]
    corruption_reasons = observations["corruption_reasons"]
    prefill_tps_samples = observations["prefill_tps_samples"]
    prefill_latency_samples = observations["prefill_latency_samples"]
    prefill_token_samples = observations["prefill_token_samples"]
    decode_tps_samples = observations["decode_tps_samples"]
    decode_latency_samples = observations["decode_latency_samples"]
    decode_token_samples = observations["decode_token_samples"]
    runtime_attestation = observations["runtime_attestation"]
    initial_telemetry = observations["initial_telemetry"]
    final_telemetry = observations["final_telemetry"]
    peak_vram_mb = observations["peak_vram_mb"]

    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    effective_prefill_tps = prefill_tps or (fmean(prefill_tps_samples) if prefill_tps_samples else None)
    effective_prefill_latency = prefill_latency_sec or (
        fmean(prefill_latency_samples) if prefill_latency_samples else None
    )
    effective_prefill_tokens = prefill_tokens or (
        round(fmean(prefill_token_samples)) if prefill_token_samples else None
    )
    effective_decode_tps = fmean(decode_tps_samples) if decode_tps_samples else None
    effective_decode_latency = fmean(decode_latency_samples) if decode_latency_samples else None
    effective_decode_tokens = round(fmean(decode_token_samples)) if decode_token_samples else 128
    decode_timing_observed = bool(
        decode_tps_samples and decode_latency_samples and decode_token_samples
    )
    metrics = compute_profile_metrics(
        avg_latency,
        peak_vram_mb,
        prefill_latency_sec=effective_prefill_latency,
        prefill_tokens=effective_prefill_tokens,
        prefill_tps=effective_prefill_tps,
        decode_latency_sec=effective_decode_latency,
        decode_tokens=effective_decode_tokens,
        decode_tps=effective_decode_tps if decode_timing_observed else None,
        decode_timing_observed=decode_timing_observed,
    )
    effective_server_version = llama_server_version or collect_llama_server_version(llama_server_path)
    selected_k = normalize_kv_cache_type(kv_cache_type_k or candidate.kv_cache_type_k)
    selected_v = normalize_kv_cache_type(kv_cache_type_v or candidate.kv_cache_type_v)
    profile_identity = canonical_profile_identity(
        candidate,
        model_id=effective_model_id,
        kv_cache_type_k=selected_k,
        kv_cache_type_v=selected_v,
    )
    artifact_hash = sha256_file(model_path)
    prefill_evidence = bool(effective_prefill_tps and effective_prefill_latency and effective_prefill_tokens)
    decode_evidence = decode_timing_observed
    summary = {
        "candidate": candidate.model_dump(),
        "candidate_name": candidate.name,
        "profile_identity": profile_identity,
        "model_id": effective_model_id,
        "runtime_profile": {
            "model_artifact": candidate.model_artifact,
            "mtp_enabled": candidate.mtp_enabled,
            "spec_draft_n_max": candidate.spec_draft_n_max,
            "kv_cache_type": candidate.kv_cache_type,
            "kv_cache_type_k": selected_k,
            "kv_cache_type_v": selected_v,
            "kv_cache_variants": candidate.kv_cache_variants,
            "experimental_kv_cache_types": candidate.experimental_kv_cache_types,
            "flash_attention": candidate.flash_attention,
            "parallel": candidate.parallel,
            "context_sweep": candidate.context_sweep,
            "selected_gpu_pair": list(candidate.selected_gpu_pair),
            "external_reference_url": candidate.external_reference_url,
            "kv_cache_issue_url": candidate.kv_cache_issue_url,
            "kv_cache_fix_pr_url": candidate.kv_cache_fix_pr_url,
        },
        "total_requests": num_requests,
        "success_count": success_count,
        "corruption_count": corruption_count,
        "avg_latency_sec": round(avg_latency, 4),
        "model_artifact_hash": artifact_hash,
        "model_provenance_ready": model_manifest is not None and model_manifest_error is None,
        "model_provenance_independent": model_provenance_independent,
        "model_provenance": {
            "manifest_path": str(Path(model_manifest_path).resolve())
            if model_manifest_path
            else None,
            "model_source": model_manifest.model_source if model_manifest else None,
            "model_revision": model_manifest.model_revision if model_manifest else None,
            "model_artifact": model_manifest.model_artifact if model_manifest else None,
            "expected_sha256": model_manifest.model_sha256 if model_manifest else None,
            "provenance_class": model_manifest.provenance_class if model_manifest else None,
            "independent_verification": (
                model_provenance_independent
            ),
            "error": model_manifest_error,
            "receipt_path": str(Path(model_verification_receipt_path).resolve())
            if model_verification_receipt_path
            else None,
            "receipt_error": model_receipt_error,
        },
        "llama_cpp_commit": llama_cpp_commit,
        "llama_server_version": effective_server_version,
        "build_provenance": {
            "llama_cpp_commit": llama_cpp_commit,
            "llama_server_version": effective_server_version,
            "issue_reference": candidate.kv_cache_issue_url,
            "fix_reference": candidate.kv_cache_fix_pr_url,
            "fix_verified": kv_cache_fix_verified is True,
        },
        "prefill_benchmark_passed": prefill_benchmark_passed,
        "response_oracle": "strict-v1",
        "expected_response_hash_bound": bool(expected_response_sha256),
        "context_fixture_bound": context_fixture is not None,
        "launch_context_bound": launch_context_bound,
        "launch_profile_arm_consistent": launch_profile_arm_consistent,
        "launch_profile": launch_profile,
        "runtime_process_owned": runtime_process_owned,
        "runtime_attestation_bound": runtime_attestation is not None,
        "runtime_attestation": runtime_attestation,
        "runtime_attestation_sha256": (
            hashlib.sha256(
                json.dumps(
                    runtime_attestation,
                    ensure_ascii=True,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            if runtime_attestation is not None
            else None
        ),
        "request_timeout_sec": request_timeout_sec,
        "request_timeout_source": (
            "explicit" if timeout_was_explicit else "context_aware_default"
        ),
        "context_cell": (
            {
                "context_length": context_fixture.context_length,
                "prompt_hash": context_fixture.prompt_hash,
                "actual_prompt_tokens": context_fixture.actual_prompt_tokens,
                "expected_response_sha256": context_fixture.expected_response_sha256,
            }
            if context_fixture is not None
            else None
        ),
        "corruption_reasons": corruption_reasons,
        "prefill_evidence": prefill_evidence,
        "decode_evidence": decode_evidence,
        "prefill_tps": metrics["prefill_tps"],
        "prefill_latency_sec": metrics["prefill_latency_sec"],
        "prefill_tokens": metrics["prefill_tokens"],
        "decode_tps": metrics["decode_tps"],
        "est_decode_tps": metrics["est_decode_tps"],
        "estimated_end_to_end_tps": metrics["estimated_end_to_end_tps"],
        "decode_latency_sec": metrics["decode_latency_sec"],
        "decode_tokens": metrics["decode_tokens"],
        "vram_peak_per_gpu_gb": metrics["vram_peak_per_gpu_gb"],
        "gpu_telemetry": {
            "initial": initial_telemetry,
            "final": final_telemetry,
            "peak_vram_per_gpu_gb": metrics["vram_peak_per_gpu_gb"],
            "hardware_observed": initial_telemetry["hardware_observed"]
        },
        "hardware_observed": initial_telemetry["hardware_observed"]
    }
    summary["gate_evaluation"] = evaluate_profile_gate(candidate, summary)
    summary["gate_passed"] = summary["gate_evaluation"]["passed"]

    out_p = Path(output_file)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with open(out_p, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"Completed profiling. Gate Passed: {summary['gate_passed']} | Hardware Observed: {summary['hardware_observed']}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", default="http://localhost:8000")
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--candidate", default=GV100H_BASELINE.candidate_name)
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--output", default="results/hardware/profile_summary.json")
    parser.add_argument("--model-path", default=None)
    parser.add_argument("--llama-server-path", default=None)
    parser.add_argument("--llama-cpp-commit", default=None)
    parser.add_argument("--llama-server-version", default=None)
    parser.add_argument("--kv-cache-type-k", default=None)
    parser.add_argument("--kv-cache-type-v", default=None)
    parser.add_argument("--prefill-tps", type=float, default=None)
    parser.add_argument("--prefill-latency-sec", type=float, default=None)
    parser.add_argument("--prefill-tokens", type=int, default=None)
    parser.add_argument("--prefill-benchmark-passed", action="store_true", default=None)
    parser.add_argument("--kv-cache-fix-verified", action="store_true", default=None)
    parser.add_argument("--expected-response-sha256", default=None)
    parser.add_argument("--api-key", default="EMPTY")
    parser.add_argument("--context-fixture", default=None)
    parser.add_argument("--model-manifest", default=None)
    parser.add_argument("--model-verification-receipt", default=None)
    parser.add_argument("--launch-profile-config", default=None)
    parser.add_argument("--launch-profile-id", default=None)
    parser.add_argument("--runtime-command-json", type=parse_runtime_command_json, default=None)
    parser.add_argument("--runtime", default=None)
    parser.add_argument("--runtime-commit", default=None)
    parser.add_argument("--runtime-version", default=None)
    parser.add_argument("--request-timeout-sec", type=float, default=None)
    parser.add_argument("--runtime-startup-timeout-sec", type=int, default=60)
    args = parser.parse_args()

    profile_endpoint(
        args.api_base,
        args.model_id,
        args.candidate,
        args.requests,
        args.output,
        model_path=args.model_path,
        llama_server_path=args.llama_server_path,
        llama_cpp_commit=args.llama_cpp_commit,
        llama_server_version=args.llama_server_version,
        kv_cache_type_k=args.kv_cache_type_k,
        kv_cache_type_v=args.kv_cache_type_v,
        prefill_tps=args.prefill_tps,
        prefill_latency_sec=args.prefill_latency_sec,
        prefill_tokens=args.prefill_tokens,
        prefill_benchmark_passed=args.prefill_benchmark_passed,
        kv_cache_fix_verified=args.kv_cache_fix_verified,
        expected_response_sha256=args.expected_response_sha256,
        api_key=args.api_key,
        context_fixture_path=args.context_fixture,
        model_manifest_path=args.model_manifest,
        model_verification_receipt_path=args.model_verification_receipt,
        launch_profile_config_path=args.launch_profile_config,
        launch_profile_id=args.launch_profile_id,
        runtime_command=args.runtime_command_json,
        runtime=args.runtime,
        runtime_commit=args.runtime_commit,
        runtime_version=args.runtime_version,
        request_timeout_sec=args.request_timeout_sec,
        runtime_startup_timeout_sec=args.runtime_startup_timeout_sec,
    )
