# Agent Capabilities, Roles & Tool Contracts

This document establishes the operational contract, role definitions, and tool capabilities for verification agents operating inside `uvm-agent-lab`.

---

## 🤖 Agent Roles

| Role Name | Scope | Primary Objective | Allowed Paths | Forbidden Paths |
| :--- | :--- | :--- | :--- | :--- |
| **`TestcaseGeneratorAgent`** | UVM Test Layer | Create or update UVM testcases for specific requirement IDs. | `uvm/tests/`, `uvm/sequences/` | `rtl/`, `uvm/env/`, `uvm/agents/` |
| **`SequenceAuthorAgent`** | Sequence Layer | Author randomized, constrained, or backpressure sequences. | `uvm/sequences/` | `rtl/`, `uvm/tests/` |
| **`CompileFixAgent`** | Build & Interface | Fix compilation syntax, missing macros, or interface mismatches. | `uvm/` | `rtl/` |
| **`SimDebugAgent`** | Triage & Log Analysis | Root cause simulation mismatches and patch testbench timing/sampling. | `uvm/` | `rtl/` |
| **`CoverageClosureAgent`**| Functional Coverage | Add covergroups, bins, and cross-coverage without changing RTL logic. | `uvm/coverage/`, `uvm/env/` | `rtl/` |

---

## 🛠️ Tool Protocol & Schema

Agents interact with the verification environment exclusively via structured JSON toolcalls:

### 1. File Inspection & Search
- `read_file(path: str, start_line: int | None, end_line: int | None) -> str`
- `search_code(query: str, path: str, regex: bool) -> list[Match]`
- `list_files(directory: str) -> list[str]`

### 2. File Modification
- `edit_file(path: str, old_str: str, new_str: str) -> bool`
- `create_file(path: str, content: str) -> bool`

> ⚠️ **Governance Rule**: Any modification to a path contained in `forbidden_paths` triggers an immediate fatal violation.

### 3. Verification Execution
- `compile_testbench(target: str) -> CompileResult`
  - Returns: `{ "status": "pass"|"fail", "log": str, "errors": list[str] }`
- `run_simulation(test_name: str, seed: int, timeout_sec: int) -> SimResult`
  - Returns: `{ "status": "pass"|"fail"|"timeout", "log": str, "mismatches": int }`
- `read_log(log_path: str, grep_pattern: str | None) -> str`

### 4. Spec Retrieval
- `query_spec(requirement_id: str, section: str | None) -> SpecSnippet`
  - Interfaces with `spec-reference-kit` (or baseline retrievers).

---

## ⚖️ Governance & Evidence Submission Contract

Upon completion of any task, the agent must submit an **Evidence Packet**:

```json
{
  "requirement_id": "USB3-WR-001",
  "tool_calls_count": 5,
  "git_diff": "diff --git a/uvm/tests/usb3_warm_reset_test.sv b/uvm/tests/usb3_warm_reset_test.sv...",
  "compile_log": "[VCS-PASS] Compiling uvm/tests/usb3_warm_reset_test.sv... 0 Errors, 0 Warnings.",
  "simulation_log": "[UVM_INFO] UVM_TEST_PASSED @ 1420ns: Warm reset sequence completed successfully."
}
```

### Zero-Trust Evaluation Rules:
1. **Scope Compliance**: No unauthorized edits.
2. **Deterministic Diff**: Diffs must apply cleanly and produce the intended behavioral changes.
3. **Verified Execution**: `compile_log` and `simulation_log` are verified against the simulator sandbox hashes.
