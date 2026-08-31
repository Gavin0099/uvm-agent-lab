import hashlib
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List

from gv100h.governance.contract_router import TaskContractRouter
from agent.governance.guardrails import ScopeGuardrail

# Declared-validator entries that this bridge knows how to actually execute
# against real changed paths, keyed by the `validators:` entry in
# contracts/gv100h-poc.yaml. A task can declare a validator in the contract
# for documentation purposes without it being wired here; only entries in
# this map are executed when post_task_check() is invoked. There is no
# production session orchestrator that currently calls post_task_check();
# CI still runs the validator independently in --lenient mode.
_DEPENDENCY_MANIFEST_VALIDATOR_ENTRY = "validators/dependency_manifest_diff_validator.py"
_DEPENDENCY_MANIFEST_GUARDED_FILES = {"pyproject.toml", "requirements.txt"}


class GovernanceRuntimeBridge:
    """
    Library hooks for TaskContractRouter into governance lifecycle events
    (pre_task_check, post_task_check, and the separate benchmark-execution
    path).

    Claim ceiling: ``post_task_check()`` is the dispatch point for declared
    content validators *when a caller invokes it*. There is currently no
    production session/task orchestrator that calls ``pre_task_check`` /
    ``post_task_check``; the only in-repo caller is
    ``tests/gv100h/test_governance_runtime_binding.py``. The production
    coding-eval runner uses ``pre_benchmark_execution_check`` /
    ``post_benchmark_execution_check``, which does not run the dependency
    manifest validator. CI enforces that validator in ``--lenient`` mode.
    Do not claim runtime-wide strict closeout is in effect.
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
            "interception_mode": contract.get("interception_mode", "ENFORCED"),
            "validators": contract.get("validators", []),
        }

        return True, guardrail, context

    def post_task_check(
        self,
        task_id: str,
        changed_paths: List[str],
        guardrail: ScopeGuardrail,
        *,
        repo_root: Optional[str] = None,
        base_ref: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        for p in changed_paths:
            res = guardrail.check_path_access(p)
            is_allowed = res[0] if isinstance(res, tuple) else res
            if not is_allowed:
                return False, f"Scope violation: path '{p}' forbidden under task contract '{task_id}'"

        content_ok, content_err = self._run_declared_content_validators(
            task_id, changed_paths, guardrail, repo_root=repo_root, base_ref=base_ref
        )
        if not content_ok:
            return False, content_err

        return True, None

    def _run_declared_content_validators(
        self,
        task_id: str,
        changed_paths: List[str],
        guardrail: ScopeGuardrail,
        *,
        repo_root: Optional[str],
        base_ref: Optional[str],
    ) -> Tuple[bool, Optional[str]]:
        """Executes declared content-level validators when post_task_check() is called.

        A `validators:` entry in contracts/gv100h-poc.yaml is otherwise inert
        prose unless a real dispatch exists here. This is that dispatch
        point. Claim ceiling: it runs only if a caller invokes
        post_task_check(); no production orchestrator currently does.
        """
        declared_validators = self.router.get_task_contract(task_id).get("validators", [])
        if _DEPENDENCY_MANIFEST_VALIDATOR_ENTRY not in declared_validators:
            return True, None

        # Normalize each changed path the same way ScopeGuardrail.check_path_access()
        # does before comparing against the guarded filename set: a raw string
        # intersection would miss './requirements.txt', an absolute path inside
        # repo_root, or a backslash-separated equivalent, silently skipping
        # content validation for a guarded manifest that was actually touched.
        touched = set()
        for p in changed_paths:
            normalized = guardrail.normalize_relative_path(p)
            if normalized is not None and normalized in _DEPENDENCY_MANIFEST_GUARDED_FILES:
                touched.add(normalized)
        if not touched:
            return True, None

        if repo_root is None or base_ref is None:
            return False, (
                f"task '{task_id}' declares {_DEPENDENCY_MANIFEST_VALIDATOR_ENTRY} and changed "
                f"{sorted(touched)}, but post_task_check() was not given repo_root/base_ref to "
                "validate the diff content against"
            )

        from validators.dependency_manifest_diff_validator import (
            validate_manifests_against_ref,
        )

        allowlist_path = Path(repo_root) / "governance" / "approved_dependency_additions.json"
        result = validate_manifests_against_ref(
            base_ref, allowlist_path, task_id=task_id, repo_root=Path(repo_root)
        )
        if not result.is_valid:
            return False, (
                f"Dependency manifest content violation under task contract '{task_id}': "
                + "; ".join(result.violations)
            )
        return True, None


    def pre_benchmark_execution_check(
        self,
        benchmark_task_id: str,
        worktree_root: str,
        case_data: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, ScopeGuardrail, Dict[str, Any]]:
        """
        Executes pre-task governance binding specifically for benchmark cases in disposable worktrees.
        Returns: (is_admitted, active_guardrail, runtime_context)
        """
        contract = self.router.get_benchmark_execution_contract(benchmark_task_id, case_data)
        guardrail = self.router.create_guardrail_for_benchmark_execution(benchmark_task_id, worktree_root, case_data)

        # Canonical JSON string for deterministic contract hash
        contract_str = f"{contract['contract_id']}:{sorted(contract['allowed_paths'])}:{sorted(contract['forbidden_paths'])}"
        contract_hash = hashlib.sha256(contract_str.encode("utf-8")).hexdigest()

        context = {
            "benchmark_task_id": benchmark_task_id,
            "execution_contract_id": contract["contract_id"],
            "execution_contract_hash": contract_hash,
            "allowed_paths": contract.get("allowed_paths", []),
            "forbidden_paths": contract.get("forbidden_paths", []),
            "authority_level": contract.get("authority_level", "normative_enforced"),
            "interception_mode": contract.get("interception_mode", "ENFORCED")
        }

        return True, guardrail, context

    def post_benchmark_execution_check(
        self,
        benchmark_task_id: str,
        changed_paths: List[str],
        guardrail: ScopeGuardrail
    ) -> Tuple[bool, Optional[str]]:
        """
        Executes post-task scope compliance check against active benchmark execution contract.
        """
        for p in changed_paths:
            res = guardrail.check_path_access(p)
            is_allowed = res[0] if isinstance(res, tuple) else res
            if not is_allowed:
                return False, f"Scope violation: path '{p}' forbidden under benchmark contract '{benchmark_task_id}'"

        return True, None

