#!/usr/bin/env python3
"""
Zero-Trust Evidence Validator
Validates that required evidence fields exist, requirement IDs match,
and simulation logs do not contain active errors or fabricated signals.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.governance.evidence_verifier import EvidenceVerifier


def validate_evidence() -> bool:
    verifier = EvidenceVerifier()
    required_items = ["requirement_id", "git_diff", "compile_log", "simulation_log"]
    
    # 1. Valid Evidence Packet
    sample_evidence = {
        "requirement_id": "USB3-WR-001",
        "git_diff": "diff --git a/uvm/test.sv b/uvm/test.sv",
        "compile_log": "[VCS] Compiling... 0 Errors",
        "simulation_log": "[UVM_INFO] --- UVM_TEST_PASSED --- UVM_ERROR : 0",
    }
    score, report = verifier.verify_evidence_packet(
        evidence=sample_evidence,
        required_items=required_items,
        expected_requirement_id="USB3-WR-001"
    )
    if not report.passed or score < 100.0:
        print(f"[FAIL] Valid evidence failed verification: {report.violations}")
        return False

    # 2. Missing Evidence Packet (Negative check)
    missing_evidence = {
        "requirement_id": "USB3-WR-001",
        "git_diff": "",
        "compile_log": "[VCS] Compiling...",
        "simulation_log": "[UVM_INFO] UVM_TEST_PASSED",
    }
    score_missing, report_missing = verifier.verify_evidence_packet(
        evidence=missing_evidence,
        required_items=required_items,
        expected_requirement_id="USB3-WR-001"
    )
    if report_missing.passed:
        print("[FAIL] Missing evidence packet was improperly allowed!")
        return False

    print("[PASS] Zero-Trust Evidence Validator passed.")
    return True


if __name__ == "__main__":
    success = validate_evidence()
    sys.exit(0 if success else 1)
