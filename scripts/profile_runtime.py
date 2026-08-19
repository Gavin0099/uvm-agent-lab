#!/usr/bin/env python3
"""
GV100H Runtime Profiler and Hardware Telemetry Collector
Executes consecutive requests against inference endpoints, queries NVML / nvidia-smi
for peak VRAM and temperature, and validates exit gate criteria.
"""

import sys
import time
import json
import shutil
import argparse
import subprocess
import urllib.request
from pathlib import Path
from typing import Dict, Any, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gv100h.runtime.admission_matrix import RuntimeAdmissionMatrix
from gv100h.runtime.ssot import GV100H_BASELINE
from gv100h.utils.url import normalize_openai_base_url


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


def compute_profile_metrics(avg_latency: float, peak_vram_mb: float) -> Dict[str, Any]:
    """
    Canonical hardware-profile fields consumed by generate_poc_report /
    QualificationPolicyEvaluator. Do not nest the live metrics only under
    gpu_telemetry or emit est_decode_tps without decode_tps.
    """
    decode_tps = round(128.0 / avg_latency, 2) if avg_latency > 0 else 0.0
    vram_peak = round(peak_vram_mb / 1024.0, 2) if peak_vram_mb > 0 else None
    return {
        "decode_tps": decode_tps,
        "est_decode_tps": decode_tps,
        "vram_peak_per_gpu_gb": vram_peak,
    }


def evaluate_profile_gate(candidate: Any, summary: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate hardware admission criteria from observed profile fields only."""
    criteria = candidate.exit_gate_criteria
    observed_vram = summary.get("vram_peak_per_gpu_gb")
    observed_tps = summary.get("decode_tps")
    checks = {
        "hardware_observed": summary.get("hardware_observed") is True,
        "gpu_count": summary.get("gpu_telemetry", {}).get("initial", {}).get("gpu_count", 0) >= candidate.gpu_count,
        "min_success_requests": summary.get("success_count", 0) >= criteria["min_success_requests"],
        "max_corruption_count": summary.get("corruption_count", 999999) <= criteria["max_corruption_count"],
        "max_vram_per_gpu_gb": observed_vram is not None and observed_vram <= criteria["max_vram_per_gpu_gb"],
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
    output_file: str = "results/hardware/profile_summary.json"
) -> Dict[str, Any]:
    candidate = RuntimeAdmissionMatrix.get_candidate(candidate_name)
    effective_model_id = model_id or candidate.supported_models[0]
    norm_base = normalize_openai_base_url(api_base)
    url = f"{norm_base}/chat/completions"


    latencies = []
    success_count = 0
    corruption_count = 0

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
    metrics = compute_profile_metrics(avg_latency, peak_vram_mb)
    summary = {
        "candidate": candidate.model_dump(),
        "model_id": effective_model_id,
        "runtime_profile": {
            "model_artifact": candidate.model_artifact,
            "mtp_enabled": candidate.mtp_enabled,
            "spec_draft_n_max": candidate.spec_draft_n_max,
            "kv_cache_type": candidate.kv_cache_type,
            "flash_attention": candidate.flash_attention,
            "parallel": candidate.parallel,
            "context_sweep": candidate.context_sweep,
            "external_reference_url": candidate.external_reference_url,
        },
        "total_requests": num_requests,
        "success_count": success_count,
        "corruption_count": corruption_count,
        "avg_latency_sec": round(avg_latency, 4),
        "decode_tps": metrics["decode_tps"],
        "est_decode_tps": metrics["est_decode_tps"],
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
    args = parser.parse_args()

    profile_endpoint(args.api_base, args.model_id, args.candidate, args.requests, args.output)
