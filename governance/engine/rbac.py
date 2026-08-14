from pathlib import Path
from typing import Dict, Any, List, Optional
import yaml
from governance.engine.violations import (
    GovernanceViolationCode,
    GovernanceSeverity,
    GovernanceReport,
)


class RoleBasedAccessController:
    """
    Enforces Agent Role-Based Access Control (RBAC) per the AGENTS.md contract.
    """

    def __init__(self, policy_path: str = "governance/policies/rbac_policy.yaml"):
        self.policy_path = Path(policy_path).resolve()
        self.roles_config = self._load_policy()

    def _load_policy(self) -> Dict[str, Any]:
        if not self.policy_path.exists():
            return {}
        try:
            with open(self.policy_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data.get("roles", {})
        except Exception:
            return {}

    def get_role_spec(self, role_name: str) -> Optional[Dict[str, Any]]:
        return self.roles_config.get(role_name)

    def validate_action(
        self,
        role_name: str,
        tool_name: str,
        target_path: Optional[str] = None
    ) -> GovernanceReport:
        report = GovernanceReport()
        role_spec = self.get_role_spec(role_name)
        if not role_spec:
            # Unknown role - issue warning but proceed if basic permissions allow
            return report

        # 1. Check Tool Permission
        allowed_tools = role_spec.get("allowed_tools", [])
        if tool_name not in allowed_tools:
            report.add_violation(
                code=GovernanceViolationCode.RBAC_UNAUTHORIZED_TOOL,
                severity=GovernanceSeverity.CRITICAL,
                message=f"Agent role '{role_name}' is not permitted to invoke tool '{tool_name}'. Allowed: {allowed_tools}",
                target=tool_name,
                policy="agent_rbac_policy"
            )
            return report

        # 2. Check Path Permission (if target_path is specified)
        if target_path:
            clean_path = target_path.replace("\\", "/").strip("/")
            
            # Check forbidden paths
            for forbidden in role_spec.get("forbidden_paths", []):
                clean_forbid = forbidden.replace("\\", "/").strip("/")
                if clean_path == clean_forbid or clean_path.startswith(clean_forbid + "/"):
                    report.add_violation(
                        code=GovernanceViolationCode.SCOPE_VIOLATION_FORBIDDEN_PATH,
                        severity=GovernanceSeverity.FATAL,
                        message=f"Agent role '{role_name}' attempted to access forbidden path '{clean_path}' (forbidden: '{clean_forbid}').",
                        target=target_path,
                        policy="agent_rbac_policy"
                    )
                    return report

            # Check allowed paths
            is_allowed = False
            for allowed in role_spec.get("allowed_paths", []):
                clean_allow = allowed.replace("\\", "/").strip("/")
                if clean_path == clean_allow or clean_path.startswith(clean_allow + "/"):
                    is_allowed = True
                    break

            if not is_allowed:
                report.add_violation(
                    code=GovernanceViolationCode.SCOPE_VIOLATION_OUT_OF_BOUNDS,
                    severity=GovernanceSeverity.FATAL,
                    message=f"Path '{clean_path}' is outside allowed paths for role '{role_name}' ({role_spec.get('allowed_paths')}).",
                    target=target_path,
                    policy="agent_rbac_policy"
                )

        return report
