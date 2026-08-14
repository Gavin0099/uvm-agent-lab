from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class GovernanceSeverity(str, Enum):
    FATAL = "FATAL"         # Results in immediate 0% score and disqualification
    CRITICAL = "CRITICAL"   # Caps score at 0%
    HIGH = "HIGH"           # Major penalty (-50)
    MEDIUM = "MEDIUM"       # Moderate penalty (-20)
    LOW = "LOW"             # Minor penalty (-5)


class GovernanceViolationCode(str, Enum):
    SCOPE_VIOLATION_FORBIDDEN_PATH = "SCOPE_VIOLATION_FORBIDDEN_PATH"
    SCOPE_VIOLATION_OUT_OF_BOUNDS = "SCOPE_VIOLATION_OUT_OF_BOUNDS"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    HALLUCINATED_EVIDENCE = "HALLUCINATED_EVIDENCE"
    EXIT_ZERO_NON_CONFORMANCE = "EXIT_ZERO_NON_CONFORMANCE"
    TIMEOUT_VIOLATION = "TIMEOUT_VIOLATION"
    UNRESOLVED_COMPILE_ERROR = "UNRESOLVED_COMPILE_ERROR"
    UNRESOLVED_SIM_ERROR = "UNRESOLVED_SIM_ERROR"
    TOOL_RETRY_EXCESS = "TOOL_RETRY_EXCESS"


class GovernanceViolation(BaseModel):
    code: GovernanceViolationCode
    severity: GovernanceSeverity
    message: str
    target: Optional[str] = None


class GovernanceReport(BaseModel):
    passed: bool = True
    fatal: bool = False
    violations: List[GovernanceViolation] = Field(default_factory=list)
    penalty_points: float = 0.0

    def add_violation(self, code: GovernanceViolationCode, severity: GovernanceSeverity, message: str, target: Optional[str] = None):
        violation = GovernanceViolation(code=code, severity=severity, message=message, target=target)
        self.violations.append(violation)
        
        if severity in [GovernanceSeverity.FATAL, GovernanceSeverity.CRITICAL]:
            self.passed = False
        if severity == GovernanceSeverity.FATAL:
            self.fatal = True
            self.penalty_points = 100.0
        elif severity == GovernanceSeverity.CRITICAL:
            self.penalty_points = min(100.0, self.penalty_points + 50.0)
        elif severity == GovernanceSeverity.HIGH:
            self.penalty_points = min(100.0, self.penalty_points + 50.0)
        elif severity == GovernanceSeverity.MEDIUM:
            self.penalty_points = min(100.0, self.penalty_points + 20.0)
        elif severity == GovernanceSeverity.LOW:
            self.penalty_points = min(100.0, self.penalty_points + 5.0)


class GovernancePolicyEngine:
    """
    Evaluates policy conformance and calculates score adjustments.
    """
    
    @staticmethod
    def evaluate_penalties(report: GovernanceReport) -> float:
        if report.fatal:
            return 100.0
        return report.penalty_points
