import re
import hashlib
from typing import Dict, Any, List, Tuple
from .policy import GovernanceViolationCode, GovernanceSeverity, GovernanceReport


class EvidenceVerifier:
    """
    Zero-Trust Evidence Auditor.
    Validates that evidence packets are authentic, non-empty, and free of hallucinations.
    """

    @staticmethod
    def compute_evidence_hash(evidence_str: str) -> str:
        return hashlib.sha256(evidence_str.encode("utf-8")).hexdigest()

    def verify_evidence_packet(
        self,
        evidence: Dict[str, Any],
        required_items: List[str],
        expected_requirement_id: str,
        expected_log_hash: str = None,
    ) -> Tuple[float, GovernanceReport]:
        """
        Returns (evidence_score [0..100], governance_report).
        """
        report = GovernanceReport()
        valid_items_count = 0

        # 1. Check completeness of required evidence items
        for item in required_items:
            val = evidence.get(item)
            if not val or (isinstance(val, str) and not val.strip()):
                report.add_violation(
                    code=GovernanceViolationCode.MISSING_EVIDENCE,
                    severity=GovernanceSeverity.CRITICAL,
                    message=f"Mandatory evidence item '{item}' is missing or empty.",
                    target=item,
                )
            else:
                valid_items_count += 1

        # 2. Check Requirement ID match
        submitted_req_id = evidence.get("requirement_id")
        if submitted_req_id and submitted_req_id != expected_requirement_id:
            report.add_violation(
                code=GovernanceViolationCode.HALLUCINATED_EVIDENCE,
                severity=GovernanceSeverity.FATAL,
                message=f"Requirement ID mismatch: Expected '{expected_requirement_id}', got '{submitted_req_id}'.",
                target="requirement_id",
            )

        # 3. Check for genuine compilation errors
        compile_log = evidence.get("compile_log", "")
        sim_log = evidence.get("simulation_log", "")

        if "Error-[" in compile_log or "compilation failed" in compile_log.lower():
            report.add_violation(
                code=GovernanceViolationCode.UNRESOLVED_COMPILE_ERROR,
                severity=GovernanceSeverity.HIGH,
                message="Compilation log contains fatal syntax/elaboration errors.",
                target="compile_log",
            )

        # 4. Check for genuine simulation errors
        has_uvm_test_failed = "--- UVM_TEST_FAILED ---" in sim_log
        has_nonzero_error_count = bool(re.search(r"UVM_ERROR\s*:\s*([1-9]\d*)", sim_log))
        has_nonzero_fatal_count = bool(re.search(r"UVM_FATAL\s*:\s*([1-9]\d*)", sim_log))
        # Active runtime UVM_ERROR messages (e.g. UVM_ERROR fixtures/uvm/... or UVM_ERROR @ 100ns)
        has_active_uvm_error = bool(re.search(r"^UVM_ERROR\s+(?:@|[a-zA-Z0-9_/\\.]+\()", sim_log, re.MULTILINE))

        if has_uvm_test_failed or has_nonzero_error_count or has_nonzero_fatal_count or has_active_uvm_error:
            report.add_violation(
                code=GovernanceViolationCode.UNRESOLVED_SIM_ERROR,
                severity=GovernanceSeverity.HIGH,
                message="Simulation log contains unresolved UVM_ERROR, UVM_FATAL, or test failure report.",
                target="simulation_log",
            )

        # 5. Optional hash verification for anti-hallucination
        if expected_log_hash and evidence.get("log_hash"):
            if evidence.get("log_hash") != expected_log_hash:
                report.add_violation(
                    code=GovernanceViolationCode.HALLUCINATED_EVIDENCE,
                    severity=GovernanceSeverity.FATAL,
                    message="Simulation log hash does not match sandbox execution hash.",
                    target="log_hash",
                )

        evidence_score = (valid_items_count / max(1, len(required_items))) * 100.0
        return evidence_score, report
