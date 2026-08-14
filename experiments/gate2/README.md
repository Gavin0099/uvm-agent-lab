# Gate 2: Agent Harness & Governance Stress Test

## Objective
Verify the harness state machine, tool contracts (`read`, `search`, `edit`, `compile`, `simulate`, `read_log`), anti-hallucination auditor, and path boundary guardrails.

## Acceptance Criteria
- `exit 0 ≠ success` enforcement
- Scope violation detection on forbidden path touch
- Missing evidence penalty enforcement
- Hallucinated evidence detection and immediate disqualification

## Verification Command
```bash
pytest tests/test_governance.py tests/test_pipeline.py
```
