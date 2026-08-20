# Active Task

<!-- governance:reviewer_verified -->

> **最後更新**: 2026-08-20
> **Owner**: Gavin0099
> **狀態**: Active (Gate 4 repair PR #8 open; qualification blocked; keep NO_GO)

## 🔒 Current Truth (2026-08-20)
- PR #6 runtime attestation and PR #7 Gate 4 execution-contract slices are merged into `main` at `ce200d58`, but post-merge review found that G4.1 must not be marked `CLOSED`.
- Repair branch `fix/gv100h-gate4-repair` completed the independent model provenance, harness-owned runtime execution, context-aware timeout evidence, raw profile re-evaluation, expected candidate identity, selected-pair NVLink evidence, and schema consistency hardening.
- Fresh read-only subagent review: `PASS`, no P0/P1 findings. Residual P2: the independent receipt still relies on organizational approval of the supplied external values, not a cryptographic signature.
- Repair PR: `#8` is open at `https://github.com/Gavin0099/uvm-agent-lab/pull/8`; no merge or branch-protection change was performed.
- Validation: final focused contract suite `25 passed`; final isolated tracked suite `213 passed`; 2 hardware-dependent tests skipped. CI benchmark/retrieval/validators/drift/quickstart steps passed.
- Gate 4 status: `CHANGES_REQUIRED` / `Gate4 bring-up partially ready`.
- Qualification status: `NOT_READY` / blocked by missing real runtime, exact GGUF, independent receipt, and physical GPU telemetry. Keep `NO_GO`.
- Software evidence is not hardware qualification evidence. Do not claim live llama.cpp/vLLM execution, GPU/NVLink qualification, or `GO`.

## 📌 Project Overview
`uvm-agent-lab` is an industrial-grade evaluation and self-healing agent testbed for LLM-assisted IEEE 1800.2 UVM digital chip verification. It features deterministic benchmarking, multi-turn syntax/timing self-healing, functional coverage closure, real EDA toolchain adapters, MCP protocol knowledge integration, and zero-trust AI governance.

---

## 🏗️ Completed Phases & Capabilities

### ✅ Phase 1: Deterministic Evaluation & Gates 0–4
- **Schema & Scoring**: Implemented `case_schema.json`, `result_schema.json`, and comprehensive scoring rubrics (`benchmarks/scoring.md`).
- **Gate 1 (Governed Knowledge Layer vs Baseline RAG)**: `spec-reference-kit` achieves 100% Recall@1 on approved verification specs while rejecting unapproved drafts, compared to 33.3% failure in baseline vector RAG.
- **Gate 2 (Multi-Turn Self-Healing Harness)**: `MultiTurnHealingAgentRunner` autonomously parses compiler errors, timing mismatches, and applies patches in iterative multi-turn loops.
- **Gate 3 (Model A/B Evaluation Suite)**: `OpenAICompatibleLLMRunner` enables headless A/B evaluation between commercial and open-source models with offline fallback.
- **Gate 4 (Dual GV100 NVLink Capacity Budgeting)**: Calculated memory budgets, AWQ 4-bit tensor parallelism (`TP=2`), and context scaling up to 128K tokens on 2× Quadro/Tesla GV100 32GB cards (Analytical Estimate; Physical Bare-Metal Qualification Pending).


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
  - Python REST API server (`dashboard/server.py`) serving dashboard assets, `/api/leaderboard`, `/api/summary`, etc.
- **UVM Fine-Tuning Kit (`dataset_gen/` & `scripts/train_dpo_qwen.py`)**:
  - `sft_generator.py`: Generates instruction-tuning datasets for UVM testbench and sequence authoring.
  - `dpo_generator.py`: Generates Direct Preference Optimization (DPO) chosen vs rejected pairs (rewarding zero-trust scope compliance, penalizing RTL tampering).
  - `export_dataset.py`: CLI for generating formatted JSONL datasets with train/eval splits.
  - `train_dpo_qwen.py`: Generates complete QLoRA 4-bit NF4 / FP16 DPO training recipes for Qwen-32B on Dual GV100.
- **Automated Functional Coverage Closure (`agent/coverage/`)**:
  - `coverage_parser.py`: Analyzes coverage databases and extracts unhit bins and cross-coverage holes.
  - `directed_seq_generator.py`: Autonomously synthesizes targeted SystemVerilog sequences with constrained randomization to hit specific unhit bins.
  - `closure_loop.py`: Executes iterative closed-loop coverage closure cycles until target coverage goals (e.g. 100%) are achieved.
- **Benchmark Leaderboard (`scripts/generate_leaderboard.py`)**:
  - Generates cross-configuration benchmark matrices and ranking (`benchmarks/LEADERBOARD.md`).

### ✅ Full AI Governance Framework Integration
- Pinned `https://github.com/Gavin0099/ai-governance-framework.git` as a Git submodule at `additional/ai-governance-framework`.
- Generated `.governance/baseline.yaml` and `.governance/version_manifest.yaml`.
- Configured domain contract `contract.yaml` for `digital-verification` with custom validators:
  - `validators/verification_scope_validator.py` (enforcing anti-RTL tampering and scope boundaries)
  - `validators/zero_trust_evidence_validator.py` (enforcing evidence packet integrity)
- Installed `.git/hooks/pre-commit` and `.git/hooks/pre-push` runtime hooks.
- Configured GitHub Actions CI/CD workflows (`.github/workflows/ci.yml`, `.github/workflows/governance-drift.yml`).
### ✅ Phase 4: GV100H Local AI Agent POC & M0.5 Admission Pipeline (2026-08-18)
- **Dynamic Task Contracts & Canonical Guardrails (`gv100h/governance/`)**:
  - `contract_router.py` dynamically resolves Development Governance Contracts (`GV100H-M0.5`) and Benchmark Execution Contracts.
  - Hardened `guardrails.py` with canonical path resolution and symlink traversal defenses.
- **Run Manifest & Strict Worktree Sandbox (`gv100h/runner/`, `schemas/`)**:
  - `GV100HRunManifest` JSON schema with cryptographic evidence hashes and invariant `pair_id` support.
  - `GitWorktreeRunner` executing in ephemeral sandboxes with real `git diff --binary` capture.
  - `IndependentVerifier` executing real EDA compilation & simulation within worktree sandboxes (`exit 0 != success`).
- **POC-1 USB Hub Spec QA Agent (`gv100h/spec_qa/`)**:
  - Table-aware `GovernedSpecRetriever` with physical knowledge manifest SHA-256 binding.
  - 30-question Golden Dataset & 5-tier deterministic evaluator.
  - Integration spec for VitePress UI with Same-Origin Proxy isolation (`docs/USB_SPEC_QA_INTEGRATION_SPEC.md`).
- **POC-2 VS Code Local Coding Agent (`gv100h/coding_eval/`)**:
  - Evaluated Cline & Continue with `interception_mode: POST_HOC`.
  - 10 representative engineering tasks with private benchmark isolation (`env://PRIVATE_BENCHMARK_ROOT`).
  - Deterministic `GovernanceABRunner` supporting paired live manifest aggregation.
- **Generic Qualification Policy & Offline Scaffold (not admitted)**:
  - `qualification_policy.yaml` exists with declared gates; human review still REJECTS the M0.5 `approved` receipt.
  - Keep `QualificationDecision = NO_GO — synthetic/offline scaffold only`. Do not treat Pipeline Admission as PASS.
- **Gate 4 G4.1 software slice**:
  - PR #7 is merged, but its execution contracts are not a qualification closeout; the repair PR must complete the trust-chain corrections before hardware bring-up.

---

## 🎯 Next Steps & Future Roadmap
1. **Review PR #8 (blocking)**: obtain human review and resolve any findings before merge.
2. **Physical bring-up**: supply and hash `llama-server`, the exact Qwen GGUF, independent verification receipt, and observed GPU telemetry.
3. **Qualification**: run the real context/profile sweep and live A/B evidence only after bring-up is ready; current qualification stays `NOT_READY` / `NO_GO`.
