# Active Task

<!-- governance:reviewer_verified -->

## 📌 Project Overview
`uvm-agent-lab` is an industrial-grade evaluation and self-healing agent testbed for LLM-assisted IEEE 1800.2 UVM digital chip verification. It features deterministic benchmarking, multi-turn syntax/timing self-healing, functional coverage closure, real EDA toolchain adapters, MCP protocol knowledge integration, and zero-trust AI governance.

---

## 🏗️ Completed Phases & Capabilities

### ✅ Phase 1: Deterministic Evaluation & Gates 0–4
- **Schema & Scoring**: Implemented `case_schema.json`, `result_schema.json`, and comprehensive scoring rubrics (`benchmarks/scoring.md`).
- **Gate 1 (Governed Knowledge Layer vs Baseline RAG)**: `spec-reference-kit` achieves 100% Recall@1 on approved verification specs while rejecting unapproved drafts, compared to 33.3% failure in baseline vector RAG.
- **Gate 2 (Multi-Turn Self-Healing Harness)**: `MultiTurnHealingAgentRunner` autonomously parses compiler errors, timing mismatches, and applies patches in iterative multi-turn loops.
- **Gate 3 (Model A/B Evaluation Suite)**: `OpenAICompatibleLLMRunner` enables headless A/B evaluation between commercial and open-source models with offline fallback.
- **Gate 4 (Dual GV100 NVLink Qualification)**: Validated memory budgets, AWQ 4-bit tensor parallelism (`TP=2`), and context scaling up to 128K tokens on 2× Quadro/Tesla GV100 32GB cards.

### ✅ Phase 2: Industrial Toolchain, MCP & Advanced Benchmarks
- **Real EDA Toolchain Adapters (`scripts/eda/`)**:
  - `VerilatorAdapter` (`--lint-only` fast syntax and type validation)
  - `IcarusVerilogAdapter` (`iverilog` + `vvp` simulation)
  - `SynopsysVCSAdapter` (enterprise-grade UVM compilation and batch execution)
  - `EDARouter` (automatic fallback router to `SimStubEngine` when native toolchains are absent)
- **Model Context Protocol (MCP) Server & Client (`agent/adapters/mcp/`)**:
  - JSON-RPC 2.0 protocol implementation with tool discovery (`query_spec`, `search_spec_symbols`, `get_register_def`) and provenance tracking.
- **Dual GV100 vLLM Serving Infrastructure (`deploy/`)**:
  - Production `docker-compose.vllm.yml`, `vllm_config.yaml`, and launcher `scripts/serve_vllm.py` optimized for AWQ 4-bit at `TP=2`.
- **Industrial Benchmark Expansion (`UVM-006` to `UVM-010`)**:
  - `UVM-006`: UVM Register Abstraction Layer (RAL) Frontdoor/Backdoor Access
  - `UVM-007`: SystemVerilog Assertions (SVA) & Interface Protocol Checking
  - `UVM-008`: Constrained-Random Verification with Weighted Distributions
  - `UVM-009`: Error Injection & Fault Tolerance (Parity Error Handling)
  - `UVM-010`: Multi-Agent Crossbar Interconnect & Scoreboard Verification

### ✅ Phase 3: Web Dashboard, SFT/DPO Kit & Coverage Closure
- **Interactive Web Dashboard (`dashboard/`)**:
  - Single-page application built with Vanilla CSS / JS featuring dark telemetry aesthetics, responsive layout, real-time benchmark execution, case inspector, pass rate charts, and token cost breakdown.
  - Python REST API server (`dashboard/server.py`) serving dashboard assets and `/api/run`, `/api/cases`, `/api/results`, `/api/summary` endpoints.
- **UVM Fine-Tuning Kit (`dataset_gen/`)**:
  - `sft_generator.py`: Generates instruction-tuning datasets for UVM testbench and sequence authoring.
  - `dpo_generator.py`: Generates Direct Preference Optimization (DPO) chosen vs rejected pairs (rewarding zero-trust scope compliance, penalizing RTL tampering and hallucinatory spec assumptions).
  - `export_dataset.py`: CLI for generating formatted JSONL datasets with train/eval splits.
- **Automated Functional Coverage Closure (`agent/coverage/`)**:
  - `coverage_parser.py`: Analyzes coverage databases and extracts unhit bins and cross-coverage holes.
  - `directed_seq_generator.py`: Autonomously synthesizes targeted SystemVerilog sequences with constrained randomization to hit specific unhit bins.
  - `closure_loop.py`: Executes iterative closed-loop coverage closure cycles until target coverage goals (e.g. 100%) are achieved.
- **Live Evaluation Harness (`scripts/run_live_eval.py`)**:
  - CLI runner for evaluating real and simulated agent models across benchmark suites.

### ✅ Full AI Governance Framework Integration
- Pinned `https://github.com/Gavin0099/ai-governance-framework.git` as a Git submodule at `additional/ai-governance-framework`.
- Generated `.governance/baseline.yaml` and `.governance/version_manifest.yaml`.
- Configured domain contract `contract.yaml` for `digital-verification` with custom validators:
  - `validators/verification_scope_validator.py` (enforcing anti-RTL tampering and scope boundaries)
  - `validators/zero_trust_evidence_validator.py` (enforcing evidence packet integrity)
- Installed `.git/hooks/pre-commit` and `.git/hooks/pre-push` runtime hooks.
- Attained **`full_candidate`** status in `human_readable_adoption_summary` with **18/18 drift checks PASS** and **32/32 pytest tests PASS**.

---

## 🎯 Next Steps & Future Roadmap
1. **Cloud CI/CD Workflow**: Configure GitHub Actions matrix (`.github/workflows/ci.yml`) to run `pytest -v tests/` and `governance_drift_checker.py` on all Pull Requests.
2. **Live EDA Cluster Integration**: Connect `SynopsysVCSAdapter` and `VerilatorAdapter` to live compute nodes with licensed VCS / Verdi toolchains.
3. **Model Fine-Tuning Run**: Train a dedicated domain model (e.g. `Qwen2.5-Coder-32B-UVM`) on the generated DPO/SFT datasets and evaluate on Dual GV100.
