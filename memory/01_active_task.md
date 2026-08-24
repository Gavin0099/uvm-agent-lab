# Active Task

> **最後更新**: 2026-08-24
> **Owner**: Gavin0099
> **狀態**: Active (trust foundations merged; qualification paths incomplete; keep NO_GO)

## 🔒 Current Truth (2026-08-24)
- `main` is `a6f9962d1357c98f9aad8392d2763fcd7146f6d1`; PR #13, #14, and #15 were merged sequentially.
- PR #13 required CI passed. PR #14 and #15 were merged through explicit administrator bypass after GitHub checkout failed on the private `additional/ai-governance-framework` submodule; their full CI steps did not execute and are not claimed as PASS.
- Runtime model/process binding, receipt-backed memory provenance, and per-source corpus binding foundations are present. These are software trust foundations, not live qualification results.
- This repair replaces caller-supplied approval values with a committed, clean Git-tracked registry and binds receipt approval ID, registry bytes hash, registry Git blob OID, and last registry-change commit. Unrelated commits do not invalidate an unchanged registry; registry changes still invalidate receipts. The production registry remains empty until a real external checksum is reviewed and committed; no model approval is fabricated here.
- PR #8 and PR #9 remain merged; PR #13, #14, and #15 now extend main with runtime trust, memory receipt, and corpus binding foundations.
- Phase 1 software foundations are merged, but capability qualification is incomplete: PR #13 CI passed, while PR #14/#15 GitHub full CI stopped at private submodule checkout and did not execute their test steps.
- v1 critical path is intentionally limited to Local Model/Runtime, Spec QA/RAG, Local Coding Agent, Governance/Evidence, and GV100 Hardware Profiling. EDA compile/simulate/coverage remains a retained Phase 2 plugin.
- Benchmark contracts distinguish `lightweight` and `eda` validator profiles; the canonical v1 coding benchmark universe is `AGENT-CODE-001` through `AGENT-CODE-005`.
- Canonical coding cases are now real Python fixture tasks: bug fix, refactor, test coverage, configuration change, and bounded multi-file change. Cases `001` and `004` intentionally have red untouched baselines and become acceptance oracles after the agent change.
- `validator_profile` is a top-level schema property, required for `AGENT-*` cases; invalid explicit values fail closed instead of silently falling back. Legacy UVM/live-universe aggregators remain UVM-only.
- Phase 1 software status: `FOUNDATIONS_MERGED` / qualification paths incomplete.
- Gate 4 status: bounded hardware identity bring-up may start; formal model/runtime qualification remains pending.
- Hardware qualification: `NOT_READY` because real Qwen inference and physical GV100 telemetry have not run.
- Qualification decision: `NO_GO` until live model, hardware, Spec QA, Coding Agent, Governance/Evidence, and human-review evidence exist.
- Software evidence is not hardware qualification evidence. Do not claim live llama.cpp/vLLM execution, GPU/NVLink qualification, or `GO`.

## 📌 Project Overview
`uvm-agent-lab` is an industrial-grade evaluation and self-healing agent testbed for LLM-assisted IEEE 1800.2 UVM digital chip verification. It features deterministic benchmarking, multi-turn syntax/timing self-healing, functional coverage closure, real EDA toolchain adapters, MCP protocol knowledge integration, and zero-trust AI governance.

---

## 🧩 Implemented Foundations (not qualification evidence)

### 🟡 Phase 1: Deterministic Evaluation & Gates 0–4 foundations
- **Schema & Scoring**: Implemented `case_schema.json`, `result_schema.json`, and comprehensive scoring rubrics (`benchmarks/scoring.md`).
- **Gate 1 deterministic baseline**: `spec-reference-kit` and baseline RAG arms are implemented for controlled fixtures; this is not full POC-1 corpus or live Spec QA qualification evidence.
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
### 🟡 Phase 4: GV100H Local AI Agent POC foundations (qualification pending)
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
---

## 🎯 Next Steps & Future Roadmap
1. **Keep software feature changes frozen**: do not add unrelated framework features or benchmark surfaces.
2. **Resolve the private governance submodule checkout** before using GitHub full CI as qualification evidence.
3. **Build the Spec QA admission chain**: acquire official raw sources, produce the corpus binding receipt, and bind it to QA evaluation results.
4. **Complete profile-aware Coding Agent admission** for the canonical lightweight cases.
5. **Run bounded hardware bring-up** only after runtime/model trust-root evidence is available; keep formal qualification `NO_GO` until all required evidence exists.
