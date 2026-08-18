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


def profile_endpoint(
    api_base: str,
    model_id: str,
    candidate_name: str = "candidate_a_llama_cpp_gguf",
    num_requests: int = 100,
    output_file: str = "results/hardware/profile_summary.json"
) -> Dict[str, Any]:
    candidate = RuntimeAdmissionMatrix.get_candidate(candidate_name)
    url = f"{api_base.rstrip('/')}/v1/chat/completions"

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
            "model": model_id,
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
    summary = {
        "candidate": candidate.model_dump(),
        "model_id": model_id,
        "total_requests": num_requests,
        "success_count": success_count,
        "corruption_count": corruption_count,
        "avg_latency_sec": round(avg_latency, 4),
        "est_decode_tps": round(128.0 / avg_latency, 2) if avg_latency > 0 else 0.0,
        "gpu_telemetry": {
            "initial": initial_telemetry,
            "final": final_telemetry,
            "peak_vram_per_gpu_gb": round(peak_vram_mb / 1024.0, 2) if peak_vram_mb > 0 else None,
            "hardware_observed": initial_telemetry["hardware_observed"]
        },
        "gate_passed": success_count >= candidate.exit_gate_criteria["min_success_requests"] and corruption_count == 0,
        "hardware_observed": initial_telemetry["hardware_observed"]
    }

    out_p = Path(output_file)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with open(out_p, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"Completed profiling. Gate Passed: {summary['gate_passed']} | Hardware Observed: {summary['hardware_observed']}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", default="http://localhost:8000")
    parser.add_argument("--model-id", default="Qwen/Qwen3.8-35B-A3B")
    parser.add_argument("--candidate", default="candidate_a_llama_cpp_gguf")
    parser.add_argument("--requests", type=int, default=10)
    parser.add_argument("--output", default="results/hardware/profile_summary.json")
    args = parser.parse_args()

    profile_endpoint(args.api_base, args.model_id, args.candidate, args.requests, args.output)
