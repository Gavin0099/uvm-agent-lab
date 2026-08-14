# Architecture: Decoupled Knowledge and Verification Layers

A critical architectural principle of `uvm-agent-lab` is the **strict separation** between the **Governed Knowledge Layer** (`spec-reference-kit`) and the **Verification Agent Evaluation Layer** (`uvm-agent-lab`).

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
|                  Verification Agent Layer: uvm-agent-lab                |
|                                                                         |
|  - Benchmark Suites (UVM-001 .. UVM-xxx)                                |
|  - Agent Harness & Tool Orchestrator                                    |
|  - Zero-Trust AI Governance Engine                                      |
|  - Compile / Simulation Stubs & EDA Wrappers (VCS/Verilator/Xcelium)     |
|  - Metric Aggregation & Hardware Profiling                              |
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
