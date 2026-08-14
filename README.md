# uvm-agent-lab

> **Deterministic Evaluation and AI Governance Testbed for UVM AI Verification Agents**

`uvm-agent-lab` is an evaluation, harness, and AI governance platform engineered to determine whether and how AI verification agents can perform meaningful, robust, and safe Universal Verification Methodology (UVM) engineering tasks.

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
   - `missing evidence = fail`: Valid runs require proof: `requirement_id`, `git_diff`, `compile_log`, and `simulation_log`.
   - `hallucinated evidence = fail`: Logs and diffs are cryptographically checked against sandbox state; fabricated pass markers result in forfeiture.
3. **Architectural Decoupling**:
   - **`spec-reference-kit`**: Governed Knowledge Layer (authoritative specs, versioning, customer access rules).
   - **`uvm-agent-lab`**: Evaluation, Agent Harness, and Experiment Layer.
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
  - 5 synthetic UVM benchmark cases (`UVM-001` ~ `UVM-005`).
- **Gate 1 — Spec / Retrieval Evaluation**: 
  - Compare `spec-reference-kit` vs BM25 vs Vector RAG vs Hybrid.
  - Metrics: `Recall@1`, `Recall@3`, `wrong-version rate`, `wrong-authority rate`, `wrong-customer rate`.
- **Gate 2 — Agent Harness & Governance Stress Test**: 
  - Validate tool contracts (`read`, `search`, `edit`, `compile`, `simulate`, `read_log`, `retry`).
  - Enforce anti-hallucination, scope sandboxing, and timeout management.
- **Gate 3 — Model A/B Testing**: 
  - Multi-model evaluation under identical tool budgets (Qwen 27B, Nemotron Nano, GPT-OSS, etc.).
  - Metrics: `task_success`, `compile_success`, `simulation_success`, `retry_count`, `tool_errors`, `token_efficiency`, `latency`.
- **Gate 4 — GV100 Hardware Profiling**: 
  - Hardware benchmarks: VRAM footprint, TTFT, tok/s, 32K/64K/128K context scaling, TP=1 vs TP=2 NVLink.

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
│  └─ compatibility-matrix.md    # Simulator, tool, and model matrices
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
