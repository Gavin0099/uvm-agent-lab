"""
AI Governance Module for uvm-agent-lab
Enforces zero-trust evidence validation, scope boundary protection, and anti-hallucination policies.
"""

from .policy import (
    GovernanceViolation,
    GovernanceSeverity,
    GovernanceViolationCode,
    GovernanceReport,
    GovernancePolicyEngine,
)
from .guardrails import ScopeGuardrail
from .evidence_verifier import EvidenceVerifier

__all__ = [
    "GovernanceViolation",
    "GovernanceSeverity",
    "GovernanceViolationCode",
    "GovernanceReport",
    "GovernancePolicyEngine",
    "ScopeGuardrail",
    "EvidenceVerifier",
]
