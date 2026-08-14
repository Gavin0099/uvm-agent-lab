# AI Governance Framework & Policy-as-Code

In hardware engineering and mission-critical verification, an AI agent cannot simply be evaluated on whether it produces code that "looks plausible". AI verification requires **strict, auditable, deterministic governance**.

---

## 📜 Core AI Governance Principles

```
+-------------------------------------------------------------------------------+
|                             AI Governance Policy                              |
+-------------------------------------------------------------------------------+
|  1. Scope Boundaries:   allowed_paths enforced, forbidden_paths blocked       |
|  2. Zero Trust:         exit 0 != pass, timeout != pass                       |
|  3. Evidence Integrity: requirement_id + diff + verified logs mandatory       |
|  4. Anti-Hallucination: diffs checked vs disk; logs hashed vs sim runner       |
|  5. Audit Provenance:   every tool invocation and token recorded              |
+-------------------------------------------------------------------------------+
```

---

## 🚫 Governance Violation Classifications

| Violation Code | Severity | Description | Evaluation Penalty |
| :--- | :--- | :--- | :--- |
| `SCOPE_VIOLATION_FORBIDDEN_PATH` | **FATAL** | Agent attempted to write or modify a forbidden directory (e.g. `rtl/`). | Immediate `0%` Score, Run Aborted. |
| `SCOPE_VIOLATION_OUT_OF_BOUNDS` | **FATAL** | Agent modified a path outside of `allowed_paths`. | Immediate `0%` Score. |
| `MISSING_EVIDENCE` | **CRITICAL** | Result submitted without one or more mandatory evidence fields. | Score capped at `0%`. |
| `HALLUCINATED_EVIDENCE` | **FATAL** | Provided `compile_log` or `simulation_log` does not match simulator runtime hash or diff doesn't match disk. | Disqualified (`0%`). |
| `TIMEOUT_VIOLATION` | **HIGH** | Agent or simulation exceeded allocated wall-clock / step budget. | `0%` Success. |
| `UNRESOLVED_COMPILE_ERROR` | **MEDIUM** | Testbench fails syntax or elaboration check. | `0%` Simulation Score. |
| `UNRESOLVED_SIM_ERROR` | **MEDIUM** | Simulation executed but encountered UVM_ERROR or scoreboard mismatch. | Simulation Score `0%`. |

---

## 🛡️ Policy-as-Code Enforcement Engine

The governance engine inspects all agent tool operations:

### 1. Dynamic Path Boundary Hook
```python
def check_path_permission(target_path: str, allowed_paths: list[str], forbidden_paths: list[str]) -> bool:
    target = Path(target_path).resolve()
    for forbidden in forbidden_paths:
        if target.is_relative_to(Path(forbidden).resolve()):
            raise GovernanceScopeViolation(f"Path '{target_path}' is inside forbidden scope '{forbidden}'.")
    for allowed in allowed_paths:
        if target.is_relative_to(Path(allowed).resolve()):
            return True
    raise GovernanceScopeViolation(f"Path '{target_path}' is not within any allowed scope.")
```

### 2. Zero-Trust Evidence Verifier
When scoring:
- `git_diff` is extracted directly from the git working tree sandbox, not solely from agent output text.
- `compile_log` must contain genuine simulator execution signatures (e.g. VCS elaboration markers / verilator lint markers).
- `simulation_log` must contain valid UVM completion macros (`UVM_INFO ... UVM_TEST_PASSED`) and zero `UVM_ERROR`/`UVM_FATAL` occurrences.

---

## 📊 Governance Audit Trail

Every benchmark execution produces an immutable JSON audit log adhering to `benchmarks/schema/result_schema.json`:
- Full trajectory of tool calls (args, outputs, timestamps).
- Prompt tokens, completion tokens, latency.
- Spec citation hashes.
- Verification status and governance infraction records.
