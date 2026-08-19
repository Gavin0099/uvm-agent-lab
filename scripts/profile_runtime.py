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
from statistics import fmean
from pathlib import Path
from typing import Dict, Any, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gv100h.runtime.admission_matrix import RuntimeAdmissionMatrix
from gv100h.runtime.ssot import GV100H_BASELINE
from gv100h.utils.url import normalize_openai_base_url

EXPERIMENTAL_KV_CACHE_TYPES = frozenset({"q4_0", "q4_1", "q5_0", "q5_1"})


def normalize_kv_cache_type(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_")


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


def sample_gpu_telemetry() -> Dict[str, Any]:
    """
    Samples physical GPU telemetry using nvidia-smi if available.
    """
    if not shutil.which("nvidia-smi"):
        return {
            "telemetry_source": "unavailable_no_nvidia_smi",
            "hardware_observed": False,
            "gpu_count": 0,
            "gpus": []
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
            "gpus": gpus
        }
    except Exception as e:
        return {
            "telemetry_source": f"error: {str(e)}",
            "hardware_observed": False,
            "gpus": []
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
        "gpu_count": summary.get("gpu_telemetry", {}).get("initial", {}).get("gpu_count", 0) >= candidate.gpu_count,
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
        "model_artifact_hash": bool(summary.get("model_artifact_hash")),
        "kv_cache_pair_consistent": selected_k == selected_v,
        "experimental_kv_build_provenance": not experimental_kv or _has_build_provenance(summary, candidate),
        "experimental_kv_prefill_validation": not experimental_kv
        or summary.get("prefill_benchmark_passed") is True,
    }
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
) -> Dict[str, Any]:
    candidate = RuntimeAdmissionMatrix.get_candidate(candidate_name)
    effective_model_id = model_id or candidate.supported_models[0]
    norm_base = normalize_openai_base_url(api_base)
    url = f"{norm_base}/chat/completions"


    latencies = []
    success_count = 0
    corruption_count = 0
    prefill_tps_samples: List[float] = []
    prefill_latency_samples: List[float] = []
    prefill_token_samples: List[int] = []
    decode_tps_samples: List[float] = []
    decode_latency_samples: List[float] = []
    decode_token_samples: List[int] = []

    print(f"Profiling Candidate '{candidate.name}' ({candidate.runtime_type}, {candidate.quantization})...")
    print(f"Target Endpoint: {url}")
    print(f"Executing {num_requests} requests...")

    initial_telemetry = sample_gpu_telemetry()
    peak_vram_mb = 0.0

    for i in range(num_requests):
        payload = {
            "model": effective_model_id,
            "messages": [{"role": "user", "content": f"Ping request {i}: calculate checksum"}],
            "temperature": 0.0,
            "max_tokens": 128
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}

        t0 = time.time()
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status == 200:
                    resp_json = json.loads(resp.read().decode("utf-8"))
                    if "choices" in resp_json and len(resp_json["choices"]) > 0:
                        success_count += 1
                        timing = extract_response_timing(resp_json)
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
                else:
                    corruption_count += 1
        except Exception:
            corruption_count += 1

        duration = time.time() - t0
        latencies.append(duration)

        # Sample VRAM during run if GPU is available
        if i % 10 == 0:
            cur_telemetry = sample_gpu_telemetry()
            for g in cur_telemetry.get("gpus", []):
                if g["memory_used_mb"] > peak_vram_mb:
                    peak_vram_mb = g["memory_used_mb"]

    final_telemetry = sample_gpu_telemetry()

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
    artifact_hash = sha256_file(model_path)
    prefill_evidence = bool(effective_prefill_tps and effective_prefill_latency and effective_prefill_tokens)
    decode_evidence = decode_timing_observed
    summary = {
        "candidate": candidate.model_dump(),
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
            "external_reference_url": candidate.external_reference_url,
            "kv_cache_issue_url": candidate.kv_cache_issue_url,
            "kv_cache_fix_pr_url": candidate.kv_cache_fix_pr_url,
        },
        "total_requests": num_requests,
        "success_count": success_count,
        "corruption_count": corruption_count,
        "avg_latency_sec": round(avg_latency, 4),
        "model_artifact_hash": artifact_hash,
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
    )
