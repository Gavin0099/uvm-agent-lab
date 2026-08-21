# Active Task

<!-- governance:reviewer_verified -->

> **最後更新**: 2026-08-21
> **Owner**: Gavin0099
> **狀態**: Active (Phase 1 software harness CLOSED; hardware bring-up pending; keep NO_GO)

## 🔒 Current Truth (2026-08-21)
- PR #6 runtime attestation, PR #7 Gate 4 execution contracts, PR #8 Gate 4 trust-root/durability repair, and PR #9 v1 scope/canonical coding benchmark are merged into `main` at `4546f8a` in order. No live hardware qualification is claimed.
- Gate 4 software trust chain is complete: independent model provenance, harness-owned runtime execution, context-aware timeout evidence, raw profile re-evaluation, expected candidate identity, selected-pair NVLink evidence, schema consistency, and registry durability are implemented and CI-validated.
- This repair replaces caller-supplied approval values with a committed, clean Git-tracked registry and binds receipt approval ID, registry bytes hash, registry Git blob OID, and last registry-change commit. Unrelated commits do not invalidate an unchanged registry; registry changes still invalidate receipts. The production registry remains empty until a real external checksum is reviewed and committed; no model approval is fabricated here.
- PR #8 and PR #9 are merged; main branch protection is restored to one required approval.
- Phase 1 software validation is complete: PR #8/PR #9 CI passed; Gate 4 durability and v1 validator suites passed; canonical lightweight coding cases are present.
- v1 critical path is intentionally limited to Local Model/Runtime, Spec QA/RAG, Local Coding Agent, Governance/Evidence, and GV100 Hardware Profiling. EDA compile/simulate/coverage remains a retained Phase 2 plugin.
- Benchmark contracts distinguish `lightweight` and `eda` validator profiles; the canonical v1 coding benchmark universe is `AGENT-CODE-001` through `AGENT-CODE-005`.
- Canonical coding cases are now real Python fixture tasks: bug fix, refactor, test coverage, configuration change, and bounded multi-file change. Cases `001` and `004` intentionally have red untouched baselines and become acceptance oracles after the agent change.
- `validator_profile` is a top-level schema property, required for `AGENT-*` cases; invalid explicit values fail closed instead of silently falling back. Legacy UVM/live-universe aggregators remain UVM-only.
- Phase 1 software closeout status: `CLOSED` / `PHASE_1_SOFTWARE_READY_FOR_HARDWARE_BRINGUP`.
- Gate 4 software readiness: `READY_FOR_BRINGUP`.
- Hardware qualification: `NOT_READY` because real Qwen inference and physical GV100 telemetry have not run.
- Qualification decision: `NO_GO` until live model, hardware, Spec QA, Coding Agent, Governance/Evidence, and human-review evidence exist.
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
1. **Software freeze**: do not add new framework features, EDA integrations, SFT/DPO, coverage, or dashboard work for Phase 1.
2. **Hardware identity**: verify dual GV100, 32GB memory, and NVLink with `nvidia-smi` and `nvidia-smi topo -m`.
3. **Runtime/model trust root**: build and hash `llama-server`; obtain the exact Qwen GGUF; populate the reviewed approval registry; generate manifest and verification receipt.
4. **First live cell**: run single-GV100 Q8 KV, 32K, MTP OFF smoke and stability profiling before MTP n=2 or longer contexts.
5. **Evidence campaign**: run 32K OFF, 32K MTP n=2, 64K, 128K; then live Spec QA and the five Coding Agent tasks before qualification review.
