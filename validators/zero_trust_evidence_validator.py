#!/usr/bin/env python3
"""
Zero-Trust Evidence Validator
Validates that required evidence fields exist and that simulation logs do not contain active errors.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.governance.evidence_verifier import EvidenceVerifier


def validate_evidence() -> bool:
    verifier = EvidenceVerifier()
    sample_evidence = {
        "requirement_id": "USB3-WR-001",
        "git_diff": "diff --git a/uvm/test.sv b/uvm/test.sv",
        "compile_log": "[VCS] Compiling... 0 Errors",
        "simulation_log": "[UVM_INFO] --- UVM_TEST_PASSED --- UVM_ERROR : 0",
    }
    result = verifier.verify_evidence(sample_evidence, expected_requirement_id="USB3-WR-001")
    if not result.is_valid:
        print(f"[FAIL] Evidence validation error: {result.violations}")
        return False

    print("[PASS] Zero-Trust Evidence Validator passed.")
    return True


if __name__ == "__main__":
    success = validate_evidence()
    sys.exit(0 if success else 1)
