import pytest
from agent.governance.guardrails import ScopeGuardrail
from agent.governance.evidence_verifier import EvidenceVerifier
from agent.governance.policy import GovernanceViolationCode, GovernanceSeverity


def test_scope_guardrail_blocks_forbidden_path():
    guardrail = ScopeGuardrail(
        allowed_paths=["uvm/tests/", "uvm/sequences/"],
        forbidden_paths=["rtl/", "uvm/env/"]
    )

    # Allowed access
    allowed, report = guardrail.check_path_access("uvm/tests/my_test.sv")
    assert allowed is True
    assert len(report.violations) == 0

    # Forbidden path access (RTL touch)
    forbidden_allowed, report = guardrail.check_path_access("rtl/core.sv")
    assert forbidden_allowed is False
    assert len(report.violations) == 1
    assert report.violations[0].code == GovernanceViolationCode.SCOPE_VIOLATION_FORBIDDEN_PATH
    assert report.violations[0].severity == GovernanceSeverity.FATAL


def test_scope_guardrail_blocks_out_of_bounds_path():
    guardrail = ScopeGuardrail(
        allowed_paths=["uvm/tests/"],
        forbidden_paths=["rtl/"]
    )

    allowed, report = guardrail.check_path_access("scripts/deploy.sh")
    assert allowed is False
    assert len(report.violations) == 1
    assert report.violations[0].code == GovernanceViolationCode.SCOPE_VIOLATION_OUT_OF_BOUNDS


def test_evidence_verifier_passes_valid_evidence():
    verifier = EvidenceVerifier()
    evidence = {
        "requirement_id": "USB3-WR-001",
        "git_diff": "diff --git a/test.sv b/test.sv",
        "compile_log": "0 Errors, 0 Warnings.",
        "simulation_log": "--- UVM_TEST_PASSED ---",
    }
    score, report = verifier.verify_evidence_packet(
        evidence=evidence,
        required_items=["requirement_id", "git_diff", "compile_log", "simulation_log"],
        expected_requirement_id="USB3-WR-001"
    )
    assert score == 100.0
    assert report.passed is True
    assert len(report.violations) == 0


def test_evidence_verifier_detects_missing_evidence():
    verifier = EvidenceVerifier()
    evidence = {
        "requirement_id": "USB3-WR-001",
        # missing compile_log, simulation_log, git_diff
    }
    score, report = verifier.verify_evidence_packet(
        evidence=evidence,
        required_items=["requirement_id", "git_diff", "compile_log", "simulation_log"],
        expected_requirement_id="USB3-WR-001"
    )
    assert score == 25.0
    assert report.passed is False
    missing_codes = [v.code for v in report.violations]
    assert GovernanceViolationCode.MISSING_EVIDENCE in missing_codes


def test_evidence_verifier_detects_hallucinated_requirement_id():
    verifier = EvidenceVerifier()
    evidence = {
        "requirement_id": "WRONG-ID-999",
        "git_diff": "valid diff",
        "compile_log": "0 Errors",
        "simulation_log": "UVM_TEST_PASSED",
    }
    score, report = verifier.verify_evidence_packet(
        evidence=evidence,
        required_items=["requirement_id", "git_diff"],
        expected_requirement_id="USB3-WR-001"
    )
    assert report.fatal is True
    assert report.violations[0].code == GovernanceViolationCode.HALLUCINATED_EVIDENCE
