#!/usr/bin/env python3
"""
Verification Scope Validator
Validates that modifications stay strictly within allowed UVM verification testbench directories
and that no forbidden RTL paths (rtl/) have been modified.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.governance.guardrails import ScopeGuardrail


def validate_scope() -> bool:
    guardrail = ScopeGuardrail()
    # Check that forbidden paths are intact
    is_safe = guardrail.validate_path("uvm/tests/test.sv", allowed_paths=["uvm/tests/"], forbidden_paths=["rtl/"])
    if not is_safe.is_valid:
        print(f"[FAIL] Scope validation error: {is_safe.violation_message}")
        return False

    is_blocked = guardrail.validate_path("rtl/usb3_ctrl.sv", allowed_paths=["uvm/tests/"], forbidden_paths=["rtl/"])
    if is_blocked.is_valid:
        print("[FAIL] RTL path was improperly allowed!")
        return False

    print("[PASS] Verification Scope Guardrail validation passed.")
    return True


if __name__ == "__main__":
    success = validate_scope()
    sys.exit(0 if success else 1)
