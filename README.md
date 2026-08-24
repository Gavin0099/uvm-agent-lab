# uvm-agent-lab

> **Local AI Agent Qualification Harness for GV100, Spec QA, Coding Agent, and Governed Evidence**

`uvm-agent-lab` is a deterministic, zero-trust harness for answering whether a local model is useful as a company Spec QA assistant and coding assistant on target hardware. UVM/EDA validation remains supported through an explicit Phase 2 plugin boundary; it is not a v1 GO/NO_GO dependency.

## Current Qualification State (2026-08-24)

- PR #13 through PR #19 are merged sequentially; this binding slice is based on main at `1ce9006`.
- Runtime model binding, memory receipt provenance, per-source corpus binding foundations, and the Spec QA admission gate are merged.
- Official raw USB 2.0 Rev 2.0, USB 3.2 Rev 1.1, and SuperSpeed Hub LVS Rev 1.15 artifacts are physically bound in operator-controlled private staging; raw bytes are not committed to this public repository.
- `additional/ai-governance-framework` is publicly checkoutable, and the post-PR17 full GitHub workflow executes checkout, pytest, benchmark, validators, and governance checks successfully.
- Final Qualification is `NO_GO`; mock, deterministic, and local focused results are not live model, hardware, or internal-pilot qualification evidence.

---

## 🎯 Core Philosophy & AI Governance Principles

Instead of rushing to benchmark massive LLMs on raw GPUs, `uvm-agent-lab` establishes a **Zero-Trust, Governed Evaluation Harness** first. 

### Key Governance Tenets:
1. **Scope Boundary Enforcement**:
   - Verification tasks must strictly respect path boundaries.
   - For example: Modifying `rtl/` when creating a UVM testcase is an immediate **Scope Violation (`SCOPE_VIOLATION_FAIL`)**.
2. **Evidence-Based Acceptance (Zero Trust)**:
   - `exit 0 ≠ success`: A process exiting cleanly does not prove correctness.
   - `timeout ≠ pass`: Incomplete runs cannot be scored optimistically.
    - `missing evidence = fail`: Valid runs require profile-appropriate proof: `requirement_id`, `git_diff`, and build/test/lint/validator evidence; EDA profiles additionally require compile/simulation evidence.
   - `hallucinated evidence = fail`: Logs and diffs are cryptographically checked against sandbox state; fabricated pass markers result in forfeiture.
3. **Architectural Decoupling**:
   - **`spec-reference-kit`**: Governed Knowledge Layer (authoritative specs, versioning, customer access rules).
    - **`uvm-agent-lab`**: Local Model/Runtime, Spec QA, Coding Agent, Governance/Evidence, and Hardware Qualification Harness.
   - Inter-system communication occurs solely over structured protocols (CLI, JSON/YAML, MCP).

---

## 🏛️ Gated Evaluation Roadmap (Gate 0 — Gate 4)

```
[Gate 0: Benchmark Schema] ──> [Gate 1: Spec / Retrieval] ──> [Gate 2: Agent Harness & Governance]
                                                                        │
                                                                        ▼
                                [Gate 4: GV100 Hardware] <──── [Gate 3: Model A/B]
```

- **Gate 0 — Benchmark Definition**: 
  - Standardized benchmark schemas (`case_schema.json`, `result_schema.json`).
  - Existing UVM cases (`UVM-001` ~ `UVM-010`) remain available as legacy Phase 2 EDA fixtures; their compile/simulation acceptance infers the `eda` profile without changing pinned case content.
- **Gate 1 — Spec / Retrieval Evaluation**: 
  - Compare `spec-reference-kit` vs BM25 vs Vector RAG vs Hybrid.
  - Metrics: `Recall@1`, `Recall@3`, `wrong-version rate`, `wrong-authority rate`, `wrong-customer rate`.
- **Gate 2 — Agent Harness & Governance Stress Test**: 
  - Validate worktree, static checks, tests, lint, scope, timeout, and evidence contracts.
  - Enforce anti-hallucination and false-success defenses without requiring an EDA installation.
- **Gate 3 — Model A/B Testing**: 
  - Planned live evaluation under identical tool budgets using coding-agent tasks, paired treatment arms, and durable evidence.
  - Metrics: `task_success`, `test_pass`, `scope_violation`, `false_success`, `retry_count`, `token_efficiency`, `latency`, and human acceptance.
  - Current claim ceiling: scripted one-shot generation and mock scaffolding are not coding-agent qualification evidence.
- **Gate 4 — GV100 Hardware Profiling**: 
  - Active pre-hardware candidate: Qwen3.8-27B Q4_K_M GGUF with llama.cpp and q8_0 K/V, single-V100 first.
  - Hardware benchmarks: VRAM footprint, TTFT, prefill/decode timing, 32K/64K/128K primary sweep, 192K/256K stretch, then dual-GV100/NVLink expansion.

  ### v1 critical path

  ```text
  Local Model / Runtime
    ├── Spec QA / RAG
    ├── Local Coding Agent
    ├── Governance + Evidence
    └── Hardware Profiling
      └── Qualification Engine
  ```

  `LightweightValidator` is the v1 profile: file scope, git diff, syntax, pytest, lint, and deterministic assertions. `EDAValidator` is a Phase 2 plugin for Verilator, Icarus, VCS, UVM simulation, and coverage. Existing EDA adapters are retained, but their availability is not a v1 blocking dependency.

---

## 📂 Repository Layout

```
uvm-agent-lab/
├─ README.md                     # Vision, Architecture, Governance & Quickstart
├─ PLAN.md                       # Roadmap & verification timeline
├─ AGENTS.md                     # Agent contracts, role definitions & tool schemas
├─ pyproject.toml / requirements.txt
│
├─ docs/
│  ├─ architecture.md            # Knowledge vs Evaluation layer separation
│  ├─ governance.md              # Policy-as-Code & Evidence Rules
│  ├─ evaluation-strategy.md     # Gate 0-4 evaluation methodology
│  ├─ hardware-plan.md           # GV100 profiling and NVLink tests
│  ├─ compatibility-matrix.md    # Simulator, tool, and model matrices
│  ├─ USB_SPEC_QA_INTEGRATION_SPEC.md # Spec QA deployment boundary
│  └─ USB_SPEC_QA_POC1_SCOPE.md  # POC-1 corpus and acceptance contract
│
├─ benchmarks/
│  ├─ cases/
│  │  ├─ UVM-001.yaml            # Task: Create warm reset testcase
│  │  ├─ UVM-002.yaml            # Task: Add randomized backpressure sequence
│  │  ├─ UVM-003.yaml            # Task: Fix compile signature / macro error
│  │  ├─ UVM-004.yaml            # Task: Debug simulation timing mismatch
│  │  └─ UVM-005.yaml            # Task: Close cross-coverage bin without touching RTL
│  ├─ schema/
│  │  ├─ case_schema.json        # Benchmark case JSON schema
│  │  └─ result_schema.json      # Agent result & evidence JSON schema
│  └─ scoring.md                 # Scoring rubric & penalty calculation
│
├─ fixtures/
│  ├─ synthetic-spec/            # Versioned spec fixtures (USB3, AXI)
│  ├─ rtl/                       # Verifiable SystemVerilog RTL modules
│  ├─ uvm/                       # Mini UVM testbench hierarchy
│  └─ logs/                      # Sample reference compile & simulation logs
│
├─ agent/
│  ├─ governance/                # Guardrails, evidence verification & policy engine
│  ├─ tools/                     # Read, Search, Edit, Compile, Simulate, ReadLog
│  ├─ prompts/                   # Governed system and task prompt templates
│  ├─ runners/                   # Fake/Mock runner, deterministic baseline, LLM stub
│  └─ adapters/                  # spec-reference-kit CLI/JSON/MCP adapters
│
├─ retrieval/
│  ├─ canonical/                 # Canonical spec-reference-kit retriever
│  ├─ bm25/                      # BM25 baseline retriever
│  ├─ vector/                    # Vector retriever stub
│  ├─ hybrid/                    # Hybrid retriever
│  └─ evaluator.py               # Gate 1 retrieval evaluation suite
│
├─ experiments/
│  ├─ gate0/                     # Gate 0 validation scripts
│  ├─ gate1/                     # Gate 1 retrieval benchmark results
│  ├─ gate2/                     # Gate 2 harness & governance validation
│  ├─ gate3/                     # Gate 3 Model A/B experiments
│  └─ gate4/                     # Gate 4 GV100 hardware performance logs
│
├─ gv100h/
│  ├─ runtime/                   # Runtime/model attestation and profiling
│  ├─ spec_qa/                   # Governed retrieval, corpus lock, and QA evaluation
│  ├─ coding_eval/               # Coding Agent evaluation harness
│  └─ qualification/             # Qualification policy and decision engine
│
├─ artifacts/evidence/           # Durable validation receipts and run evidence
│
├─ results/                      # Execution outputs and run logs
│
└─ scripts/
   ├─ run_case.py                # Benchmark runner CLI
   ├─ score_case.py              # Zero-trust scoring CLI
   ├─ summarize_results.py       # Aggregate results reporter
   └─ sim_stub.py                # Deterministic simulation stub (VCS/Verilator mock)
```

---

## 🚀 Quickstart

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

The commands below exercise deterministic or mock harness paths. They do not
constitute live model, GPU, Spec QA, Coding Agent, or internal-pilot
qualification evidence.

### 2. Run Single Case with Governed Mock Agent
```bash
python scripts/run_case.py --case benchmarks/cases/UVM-001.yaml --runner mock --output results/UVM-001_run.json
```

### 3. Score Benchmark Result
```bash
python scripts/score_case.py --case benchmarks/cases/UVM-001.yaml --result results/UVM-001_run.json
```

### 4. Run All Benchmark Suites & Summarize
```bash
python scripts/run_case.py --all --runner mock --output-dir results/
python scripts/summarize_results.py --results-dir results/
```

### 5. Run Test Suite
```bash
pytest tests/
```
