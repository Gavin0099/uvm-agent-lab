import os
from pathlib import Path
from typing import List, Tuple
from .policy import GovernanceViolationCode, GovernanceSeverity, GovernanceReport


class ScopeGuardrail:
    """
    Enforces sandbox scope boundaries.
    Prevents unauthorized reads/writes to forbidden paths (such as RTL source)
    or out-of-scope testbench files.
    """

    def __init__(self, allowed_paths: List[str], forbidden_paths: List[str], base_dir: str = "."):
        self.base_dir = Path(base_dir).resolve()
        self.allowed_paths = [self._normalize(p) for p in allowed_paths]
        self.forbidden_paths = [self._normalize(p) for p in forbidden_paths]

    def _normalize(self, p: str) -> str:
        # Standardize relative paths to forward-slash strings
        clean = p.replace("\\", "/").strip("/")
        return clean

    def check_path_access(self, target_path: str, action: str = "write") -> Tuple[bool, GovernanceReport]:
        report = GovernanceReport()
        clean_target = self._normalize(target_path)

        # 1. Check against forbidden paths
        for forbidden in self.forbidden_paths:
            if clean_target == forbidden or clean_target.startswith(forbidden + "/"):
                report.add_violation(
                    code=GovernanceViolationCode.SCOPE_VIOLATION_FORBIDDEN_PATH,
                    severity=GovernanceSeverity.FATAL,
                    message=f"Access denied: Path '{clean_target}' is inside forbidden directory '{forbidden}'.",
                    target=target_path,
                )
                return False, report

        # 2. Check if within allowed paths
        is_allowed = False
        for allowed in self.allowed_paths:
            if clean_target == allowed or clean_target.startswith(allowed + "/"):
                is_allowed = True
                break

        if not is_allowed:
            report.add_violation(
                code=GovernanceViolationCode.SCOPE_VIOLATION_OUT_OF_BOUNDS,
                severity=GovernanceSeverity.FATAL,
                message=f"Access denied: Path '{clean_target}' is not within any allowed paths {self.allowed_paths}.",
                target=target_path,
            )
            return False, report

        return True, report
