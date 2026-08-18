import hashlib
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List

from gv100h.governance.contract_router import TaskContractRouter
from agent.governance.guardrails import ScopeGuardrail


class GovernanceRuntimeBridge:
    """
    Hooks TaskContractRouter into AI Governance lifecycle events
    (session_start, pre_task_check, post_task_check, closeout).
    """

    def __init__(self, contracts_path: Optional[str] = None):
        self.router = TaskContractRouter(contracts_path)

    def pre_task_check(self, task_id: str, repo_root: str) -> Tuple[bool, ScopeGuardrail, Dict[str, Any]]:
        """
        Executes pre-task governance binding.
        Returns: (is_admitted, active_guardrail, runtime_context)
        """
        contract = self.router.get_task_contract(task_id)
        guardrail = self.router.create_guardrail_for_task(task_id, repo_root)

        contract_bytes = str(contract).encode("utf-8")
        contract_hash = hashlib.sha256(contract_bytes).hexdigest()

        context = {
            "task_id": task_id,
            "contract_hash": contract_hash,
            "allowed_paths": contract.get("allowed_paths", []),
            "forbidden_paths": contract.get("forbidden_paths", []),
            "authority_level": contract.get("authority_level", "normative_enforced"),
            "interception_mode": contract.get("interception_mode", "ENFORCED")
        }

        return True, guardrail, context

    def post_task_check(
        self,
        task_id: str,
        changed_paths: List[str],
        guardrail: ScopeGuardrail
    ) -> Tuple[bool, Optional[str]]:
        """
        Executes post-task scope compliance check against active contract.
        """
        for p in changed_paths:
            res = guardrail.check_path_access(p)
            is_allowed = res[0] if isinstance(res, tuple) else res
            if not is_allowed:
                return False, f"Scope violation: path '{p}' forbidden under task contract '{task_id}'"

        return True, None
