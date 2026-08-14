# Hardware Execution Plan: Dual GV100 Testbed

This document specifies the hardware evaluation strategy for deploying local open-weights LLMs for UVM agent workloads on **dual NVIDIA Tesla GV100 (32GB HBM2 each, 64GB total VRAM, connected via NVLink)**.

---

## 🖥️ Target Hardware Architecture

- **GPUs**: 2x NVIDIA Tesla GV100 32GB HBM2 (Volta architecture).
- **Interconnect**: NVLink Bridge (up to 200 GB/s bidirectional).
- **System Memory**: 128GB+ DDR4 ECC.
- **Inference Engines**: vLLM, SGLang, Ollama, or llama.cpp.

---

## 🔬 Benchmark Scenarios (Gate 4)

### 1. Model Quantization & Precision Matrix
| Model Architecture | Parameter Count | Precision | VRAM Target (TP=1) | VRAM Target (TP=2 NVLink) | Feasibility |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Qwen 2.5 Coder** | 14B | FP16 / BF16 | ~28 GB | ~14 GB / GPU | Highly Viable |
| **Qwen 2.5 Coder** | 32B | FP16 | OOM (>60 GB) | ~34 GB total (17 GB / GPU) | Viable (TP=2) |
| **Qwen 2.5 Coder** | 32B | AWQ / INT4 | ~20 GB | ~10 GB / GPU | High Throughput |
| **Nemotron-4** | 15B | FP16 | ~30 GB | ~15 GB / GPU | Viable |
| **DeepSeek Coder V2 Lite**| 16B MoE (2.4B active) | FP16 | ~32 GB | ~16 GB / GPU | Viable |

---

## ⚡ Context Scaling & KV Cache Profiling

Verification tasks require ingesting large SystemVerilog files, UVM packages, and simulation logs. We evaluate KV cache memory footprints across context lengths:

1. **32K Context**: Baseline for single testcase + interface + short log.
2. **64K Context**: Required for multi-sequence verification + comprehensive spec chapters.
3. **128K Context**: Stress test with extensive UVM trace logs and waveform transition dumps.

### Measured Metrics:
- **TTFT (Time-to-First-Token)** at 32K, 64K, 128K context.
- **Generation Throughput (tokens/sec)** at batch size = 1 and batch size = 4.
- **NVLink Interconnect Overhead**: Latency penalty of TP=2 vs TP=1.
