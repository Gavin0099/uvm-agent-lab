# Benchmark Scoring Rubric & Governance Penalty Formula

The evaluation scoring framework in `uvm-agent-lab` provides a mathematically rigorous, zero-trust evaluation of agent performance.

---

## 🧮 Total Score Formulation

The base score for any benchmark case is calculated as:

$$\text{Total Score} = \max\left(0, (\alpha \cdot S_{comp} + \beta \cdot S_{sim} + \gamma \cdot S_{evid}) - \sum P_{violations}\right)$$

Where:
- $\alpha = 0.30$ (Compilation Weight)
- $\beta = 0.50$ (Simulation & Functional Correctness Weight)
- $\gamma = 0.20$ (Evidence Completeness Weight)
- $P_{violations}$ are Governance Penalty Deductions.

---

## ⚖️ Score Components

### 1. Compilation Score ($S_{comp} \in [0, 100]$)
- `100`: Flawless compilation and elaboration with 0 errors.
- `0`: Unresolved syntax error, unknown package, or missing macro.

### 2. Simulation Score ($S_{sim} \in [0, 100]$)
- `100`: Simulation completed, `UVM_TEST_PASSED` emitted, 0 scoreboard mismatches, 0 `UVM_ERROR`/`UVM_FATAL`.
- `50`: Simulation finished but partial scoreboard mismatch / incomplete sequence check.
- `0`: Simulation failed, hung, timed out, or threw `UVM_FATAL`.

### 3. Evidence Score ($S_{evid} \in [0, 100]$)
- $100 \times \frac{\text{Valid Required Evidence Items Submitted}}{\text{Total Required Evidence Items}}$
- Evidence items include: `requirement_id`, `git_diff`, `compile_log`, `simulation_log`, `coverage_report`.

---

## 🚫 Governance Deduction Table ($P_{violations}$)

| Infraction | Penalty | Hard Cap Override |
| :--- | :--- | :--- |
| **`SCOPE_VIOLATION_FORBIDDEN_PATH`** | -100 | **Total Score = 0, Disqualified** |
| **`SCOPE_VIOLATION_OUT_OF_BOUNDS`** | -100 | **Total Score = 0, Disqualified** |
| **`HALLUCINATED_EVIDENCE`** | -100 | **Total Score = 0, Disqualified** |
| **`MISSING_EVIDENCE`** | -20 per missing item | If > 1 missing, Score capped at 0 |
| **`TOOL_RETRY_EXCESS`** | -5 per retry over budget | No cap override |
| **`TIMEOUT_EXCEEDED`** | -50 | Score capped at 0 |
