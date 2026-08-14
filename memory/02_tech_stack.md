# Tech Stack & Architectural Facts

<!-- governance:reviewer_verified -->

## 🛠️ System Specifications

- **Target Domain**: IEEE 1800.2 UVM (Universal Verification Methodology) & Digital ASIC/SoC Design Verification.
- **Language Stack**: Python 3.9+ (Host orchestration, agent harness, data pipelines) and SystemVerilog IEEE 1800-2017 (Verification code, sequences, assertions, testbenches).
- **Web Dashboard**: Vanilla CSS3 + Vanilla ES6 JavaScript (Zero third-party npm runtime dependencies, dark telemetry theme, native CSS grid/flexbox, SVG charts, responsive layouts).
- **Protocols & Interfaces**:
  - **MCP (Model Context Protocol)**: JSON-RPC 2.0 over stdio/HTTP for governed spec retrieval.
  - **OpenAI Compatible REST API**: Streaming and non-streaming completions for local and remote LLM runners.
  - **UVM CLI / EDA Harness**: Standardized subprocess execution and log streaming.

---

## 🏛️ Codebase Structure & Component Map

| Directory | Purpose & Key Modules |
| :--- | :--- |
| **`benchmarks/`** | Benchmark case definitions (`cases/UVM-001.yaml` ~ `UVM-010.yaml`), schemas (`case_schema.json`, `result_schema.json`), and scoring rules (`scoring.md`). |
| **`retrieval/`** | Knowledge retrieval engine: `spec-reference-kit` Canonical retriever vs Baseline Vector RAG evaluator (`retriever_evaluator.py`). |
| **`agent/`** | Core agent runners: `MultiTurnHealingAgentRunner`, `OpenAICompatibleLLMRunner`. |
| **`agent/adapters/mcp/`** | Model Context Protocol JSON-RPC 2.0 Server (`server.py`) and Client (`client.py`) for deterministic spec queries. |
| **`agent/coverage/`** | Functional coverage closure engine: `coverage_parser.py`, `directed_seq_generator.py`, `closure_loop.py`. |
| **`scripts/eda/`** | Real EDA toolchain adapters: `VerilatorAdapter`, `IcarusVerilogAdapter`, `SynopsysVCSAdapter`, `EDARouter`, and `SimStubEngine`. |
| **`dataset_gen/`** | Dataset synthesis kit for fine-tuning: `sft_generator.py`, `dpo_generator.py`, `export_dataset.py`. |
| **`dashboard/`** | Interactive monitoring & evaluation web UI (`index.html`, `styles.css`, `app.js`) and Python HTTP REST server (`server.py`). |
| **`deploy/`** | Dual GV100 inference infrastructure: `docker-compose.vllm.yml`, `vllm_config.yaml`, `scripts/serve_vllm.py`. |
| **`validators/`** | Domain verification validators: `verification_scope_validator.py`, `zero_trust_evidence_validator.py`. |
| **`governance/`** | AI Governance Policy-as-Code pack: `TESTING.md`, `ARCHITECTURE.md`, `framework.lock.json`, policies and rules. |
| **`memory/`** | Four-tier persistent memory layer (`01_active_task.md`, `02_tech_stack.md`, `02_workflow.md`, `03_knowledge_base.md`, `04_review_log.md`). |
| **`tests/`** | Comprehensive pytest suite (32 unit and governance integration tests). |

---

## ⚡ Hardware & Inference Qualification

### Dual Tesla/Quadro GV100 (64GB Total VRAM) Profile:
- **Architecture**: 2× NVIDIA GV100 Volta (32GB HBM2 per card, 819.2 GB/s bandwidth).
- **Interconnect**: NVLink 2.0 Bridge (100 GB/s bidirectional interconnect).
- **Target LLM**: `Qwen/Qwen2.5-Coder-32B-Instruct` or `nvidia/Mistral-NeMo-Minitron-15B`.
- **Quantization Strategy**: AWQ 4-bit (Activation-aware Weight Quantization).
- **Tensor Parallelism**: `TP=2` (weights sharded equally across both GV100s).
- **Memory Footprint**:
  - Model weights: ~18.5 GB total (~9.25 GB per GPU).
  - VRAM headroom: ~22.75 GB per GPU reserved for PyTorch activation buffers and Paged KV Cache.
- **Context Scaling**:
  - Supports 32K, 64K, and 128K token context windows with PagedAttention without triggering Out-Of-Memory (OOM).

---

## 🛡️ AI Governance & Security

- **Framework**: `Gavin0099/ai-governance-framework` as an official Git submodule (`additional/ai-governance-framework`).
- **Baseline**: Cryptographically hashed baseline file at `.governance/baseline.yaml`.
- **Version Manifest**: `.governance/version_manifest.yaml` declaring schema versions (`1.2.0` contract, `1.1.0` runtime).
- **Domain Contract**: `contract.yaml` configured for `digital-verification` with strict scope guardrails (`rtl/` modification prohibited).
