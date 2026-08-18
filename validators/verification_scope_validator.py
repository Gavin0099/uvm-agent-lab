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
    guardrail = ScopeGuardrail(
        allowed_paths=["uvm/tests/"],
        forbidden_paths=["rtl/"],
        base_dir=str(PROJECT_ROOT)
    )

    # 1. Allowed testbench path check
    is_safe, safe_report = guardrail.check_path_access("uvm/tests/test.sv")
    if not is_safe or not safe_report.passed:
        print(f"[FAIL] Scope validation error on allowed path: {safe_report.violations}")
        return False

    # 2. Forbidden RTL path check
    is_blocked, blocked_report = guardrail.check_path_access("rtl/usb3_ctrl.sv")
    if is_blocked or blocked_report.passed:
        print("[FAIL] RTL path was improperly allowed!")
        return False

    # 3. Path traversal attack check
    is_traversal_blocked, traversal_report = guardrail.check_path_access("uvm/tests/../../rtl/usb3_ctrl.sv")
    if is_traversal_blocked or traversal_report.passed:
        print("[FAIL] Path traversal into RTL was improperly allowed!")
        return False

    print("[PASS] Verification Scope Guardrail validation passed.")
    return True


if __name__ == "__main__":
    success = validate_scope()
    sys.exit(0 if success else 1)
