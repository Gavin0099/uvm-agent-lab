# Architecture: Decoupled Knowledge and Local AI Qualification Layers

A critical architectural principle of `uvm-agent-lab` is the **strict separation** between the **Governed Knowledge Layer** (`spec-reference-kit`) and the **Local AI Qualification Layer** (`uvm-agent-lab`).

---

## 🏛️ System Boundary & Decoupling

```
+-------------------------------------------------------------------------+
|                  Governed Knowledge Layer: spec-reference-kit           |
|                                                                         |
|  - Authoritative Spec Repository (Word, PDF, Markdown, XML)             |
|  - Multi-tier Version & Customer Access Governance                      |
|  - Spec Section Indexing & Provenance Tracking                          |
|  - Output: Deterministic, Version-Pinned Snippets & Citations           |
+-------------------------------------------------------------------------+
                                    │
                  CLI / JSON Schema / MCP Interface
                                    │
                                    ▼
+-------------------------------------------------------------------------+
|                  Local AI Qualification Layer: uvm-agent-lab            |
|                                                                         |
|  - Local Model / Runtime and GV100 Hardware Profiling                    |
|  - Spec QA / RAG                                                         |
|  - Local Coding Agent Worktree Harness                                   |
|  - Zero-Trust Governance and Evidence                                    |
|  - LightweightValidator (v1)                                             |
|  - EDAValidator plugin (Phase 2: VCS/Verilator/Icarus/UVM/coverage)      |
+-------------------------------------------------------------------------+
```

---

## 🎯 Why This Separation is Mandatory

1. **Reusability across Engineering Disciplines**:
   - `spec-reference-kit` serves multiple downstream agents: UVM Verification, Embedded Firmware, Device Drivers, Customer FAE, and Automated Post-Silicon Debug.
   - If embedded in `uvm-agent-lab`, every domain would have to duplicate or couple with UVM testbenches.

2. **Prevention of Architectural Monoliths**:
   - Prevents conflating document ingestion/parsing with EDA simulator execution and model evaluation.

3. **Isolated Governance Boundaries**:
   - **Knowledge Governance** audits: Is this customer allowed to read v2.1? Is section 4.2 deprecated?
   - **Verification Governance** audits: Did the agent modify RTL? Did simulation pass with genuine evidence?

---

## 🧭 v1 Qualification Harness Boundary

The v1 critical path answers five bounded questions:

1. Can the local model/runtime run reliably on the target GV100 hardware?
2. Can it answer governed company specifications with correct citations, version scope, authority, and abstention?
3. Can it act as a useful local coding assistant inside a disposable worktree?
4. Can governance and evidence controls reject scope violations, fake success, and missing proof?
5. Can a lightweight validator measure syntax, tests, lint, deterministic assertions, and human-reviewable diffs?

The case contract carries an explicit `validator_profile`:

```text
lightweight -> file scope, git diff, syntax, pytest, lint, deterministic assertions
eda         -> compile, simulation, UVM, coverage, and tool-specific evidence
```

`EDAValidator` is a Phase 2 plugin boundary. Existing `scripts/eda/` adapters,
`EDARouter`, and UVM cases are retained as reusable capability, but EDA tool
availability is not a v1 GO/NO_GO dependency.

---

## 🔌 Inter-Layer Interface Protocol

The two layers communicate via standard JSON contracts:

### Request (Agent -> Knowledge Layer)
```json
{
  "query_type": "requirement_lookup",
  "requirement_id": "USB3-WR-001",
  "protocol": "USB3.2",
  "version": "1.0",
  "customer_tier": "tier_1_partner"
}
```

### Response (Knowledge Layer -> Agent)
```json
{
  "status": "success",
  "requirement_id": "USB3-WR-001",
  "spec_title": "USB 3.2 Gen2 Physical Layer",
  "section": "6.4.2",
  "authority_level": "authoritative",
  "text": "Upon assertion of Warm Reset, the Port Configuration SM must transition from U0 to Rx.Detect within 12ms without resetting sticky register values.",
  "canonical_hash": "sha256:4a8c9b2f..."
}
```
