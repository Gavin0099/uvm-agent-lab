# Gate 4: Dual GV100 NVLink Hardware Characterization Report

> **Hardware Target**: 2x NVIDIA Tesla/Quadro GV100 32GB HBM2 (64GB Total VRAM, NVLink 2.0 @ 200 GB/s).

## Current Deployment Recommendation (2026-08-19)

The active pre-GV100 route is `Qwen3.8-27B-Q4_K_M.gguf` served by llama.cpp on a single V100 with `q8_0` K/V cache, Flash Attention, and `parallel=1`.

1. Run MTP OFF as the control and `draft-mtp` n-max=2 as the paired comparison arm.
2. Measure 32K, 64K, and 128K as the primary sweep; use 192K and exploratory 256K only as stretch points, recording prefill and decode separately.
3. Keep q4/q5 KV experimental until the selected build has the relevant fix provenance and a passing local prefill benchmark.
4. Treat all community numbers as external references, not local Gate 4 qualification evidence.
5. Keep the Qwen2.5-Coder-32B AWQ TP=2 route as a secondary analytical/vLLM candidate.

## Legacy Analytical Context Scaling & VRAM Allocation Matrix

> The matrix below is retained for capacity planning only. It is not physical hardware evidence and does not override the active llama.cpp SSOT.

| Model | Precision | Context | TP Setup | Total VRAM / GPU | Fit in 32GB? | Est. tok/s | Gate 4 Feasibility |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`Qwen-2.5-Coder-32B`** | AWQ_4BIT | `32K` | TP=2 | **14.44 GB** | ✅ YES | 43.8 tok/s | ANALYTICAL FIT |
| **`Qwen-2.5-Coder-32B`** | AWQ_4BIT | `64K` | TP=2 | **18.44 GB** | ✅ YES | 43.8 tok/s | ANALYTICAL FIT |
| **`Qwen-2.5-Coder-32B`** | AWQ_4BIT | `128K` | TP=2 | **26.44 GB** | ✅ YES | 43.8 tok/s | ANALYTICAL FIT |
| **`Qwen-2.5-Coder-32B`** | INT8 | `32K` | TP=2 | **21.75 GB** | ✅ YES | 24.1 tok/s | ANALYTICAL FIT |
| **`Qwen-2.5-Coder-32B`** | FP16 | `32K` | TP=1 | **74.5 GB** | ❌ OOM | 15.0 tok/s | ANALYTICAL OOM |
| **`Qwen-2.5-Coder-32B`** | FP16 | `32K` | TP=2 | **38.0 GB** | ❌ OOM | 15.0 tok/s | ANALYTICAL OOM |
| **`Nemotron-4-15B`** | FP16 | `32K` | TP=2 | **19.0 GB** | ✅ YES | 26.1 tok/s | ANALYTICAL FIT |
| **`Nemotron-4-15B`** | FP16 | `64K` | TP=2 | **21.5 GB** | ✅ YES | 26.1 tok/s | ANALYTICAL FIT |
| **`DeepSeek-Coder-V2-Lite`** | FP16 | `64K` | TP=2 | **24.2 GB** | ✅ YES | 24.9 tok/s | ANALYTICAL FIT |

## 🎯 Gate 4 Hardware Conclusions

1. **Secondary analytical route**: `Qwen-2.5-Coder-32B-AWQ` at `TP=2` over NVLink remains a capacity-planning candidate; its synthetic estimates are not a runtime qualification result.
2. **Nemotron-4 15B in FP16**: Fits easily at TP=2 with ~18.5 GB / GPU, offering native unquantized precision.
3. **Hardware boundary**: Physical V100/NVLink observation, model artifact hashes, llama.cpp build provenance, prefill/decode telemetry, and stability evidence are still required before any Gate 4 GO.