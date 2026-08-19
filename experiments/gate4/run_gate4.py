#!/usr/bin/env python3
"""
Gate 4 Experiment Runner: Dual GV100 NVLink Hardware Characterization
Profiles VRAM footprints, KV cache scaling across 32K/64K/128K contexts,
and evaluates TP=1 vs TP=2 NVLink speedup and precision modes (AWQ / INT8 / FP16).
"""

import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from experiments.gate4.hardware_profiler import HardwareProfiler


def main():
    configurations = [
        ("Qwen-2.5-Coder-32B", "AWQ_4BIT", 32768, 2),
        ("Qwen-2.5-Coder-32B", "AWQ_4BIT", 65536, 2),
        ("Qwen-2.5-Coder-32B", "AWQ_4BIT", 131072, 2),
        ("Qwen-2.5-Coder-32B", "INT8", 32768, 2),
        ("Qwen-2.5-Coder-32B", "FP16", 32768, 1),
        ("Qwen-2.5-Coder-32B", "FP16", 32768, 2),
        ("Nemotron-4-15B", "FP16", 32768, 2),
        ("Nemotron-4-15B", "FP16", 65536, 2),
        ("DeepSeek-Coder-V2-Lite", "FP16", 65536, 2),
    ]

    matrix_results = []
    for model, prec, ctx, tp in configurations:
        res = HardwareProfiler.calculate_vram_requirement(
            model_name=model,
            context_length=ctx,
            precision_mode=prec,
            tensor_parallel=tp
        )
        matrix_results.append({
            "model": model,
            "precision": prec,
            "context": f"{int(ctx/1024)}K",
            "tp": f"TP={tp}",
            "result": res
        })

    out_dir = Path("experiments/gate4")
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "gate4_hardware_scores.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(matrix_results, f, indent=2)

    # Generate Markdown Table
    md_lines = [
        "# Gate 4: Dual GV100 NVLink Hardware Characterization Report",
        "",
        "> **Hardware Target**: 2x NVIDIA Tesla/Quadro GV100 32GB HBM2 (64GB Total VRAM, NVLink 2.0 @ 200 GB/s).",
        "",
        "## Current Deployment Recommendation (2026-08-19)",
        "",
        "The active pre-GV100 route is `Qwen3.8-27B-Q4_K_M.gguf` served by llama.cpp on a single V100 with `q8_0` K/V cache, Flash Attention, and `parallel=1`.",
        "",
        "1. Run MTP OFF as the control and `draft-mtp` n-max=2 as the paired comparison arm.",
        "2. Measure 32K, 64K, and 128K as the primary sweep; use 192K and exploratory 256K only as stretch points, recording prefill and decode separately.",
        "3. Keep q4/q5 KV experimental until the selected build has the relevant fix provenance and a passing local prefill benchmark.",
        "4. Treat all community numbers as external references, not local Gate 4 qualification evidence.",
        "5. Keep the Qwen2.5-Coder-32B AWQ TP=2 route as a secondary analytical/vLLM candidate.",
        "",
        "## Legacy Analytical Context Scaling & VRAM Allocation Matrix",
        "",
        "> The matrix below is retained for capacity planning only. It is not physical hardware evidence and does not override the active llama.cpp SSOT.",
        "",
        "| Model | Precision | Context | TP Setup | Total VRAM / GPU | Fit in 32GB? | Est. tok/s | Gate 4 Feasibility |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    ]

    for item in matrix_results:
        m = item["model"]
        p = item["precision"]
        c = item["context"]
        tp_str = item["tp"]
        r = item["result"]

        fit_str = "✅ YES" if r["fits_in_memory"] else "❌ OOM"
        
        if r["fits_in_memory"]:
            status = "ANALYTICAL FIT"
        else:
            status = "ANALYTICAL OOM"

        md_lines.append(
            f"| **`{m}`** | {p} | `{c}` | {tp_str} | **{r['total_vram_per_gpu_gb']} GB** | {fit_str} | {r['est_tokens_per_sec']} tok/s | {status} |"
        )

    md_lines.extend([
        "",
        "## 🎯 Gate 4 Hardware Conclusions",
        "",
        "1. **Secondary analytical route**: `Qwen-2.5-Coder-32B-AWQ` at `TP=2` over NVLink remains a capacity-planning candidate; its synthetic estimates are not a runtime qualification result.",
        "2. **Nemotron-4 15B in FP16**: Fits easily at TP=2 with ~18.5 GB / GPU, offering native unquantized precision.",
        "3. **Hardware boundary**: Physical V100/NVLink observation, model artifact hashes, llama.cpp build provenance, prefill/decode telemetry, and stability evidence are still required before any Gate 4 GO.",
    ])

    report_md = "\n".join(md_lines)
    report_path = out_dir / "gate4_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    print(report_md)
    print(f"\nSaved Gate 4 report to {report_path}")


if __name__ == "__main__":
    main()
