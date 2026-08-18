import os
from pathlib import Path
from typing import Dict, Any, Optional, List
import yaml

from agent.governance.guardrails import ScopeGuardrail


class TaskContractRouter:
    """
    Dynamically routes and binds task-specific governance contracts
    defined in contracts/gv100h-poc.yaml.
    """

    DEFAULT_CONTRACT_FILE = "contracts/gv100h-poc.yaml"

    def __init__(self, contract_path: Optional[str] = None, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir or ".").resolve()
        if contract_path:
            self.contract_file = Path(contract_path).resolve()
        else:
            self.contract_file = self.base_dir / self.DEFAULT_CONTRACT_FILE

        self._contract_data: Dict[str, Any] = self._load_contract_file()

    def _load_contract_file(self) -> Dict[str, Any]:
        if not self.contract_file.exists():
            raise FileNotFoundError(f"Governance contract file not found: {self.contract_file}")
        with open(self.contract_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data

    @property
    def version(self) -> str:
        return self._contract_data.get("version", "unknown")

    @property
    def domain(self) -> str:
        return self._contract_data.get("domain", "unknown")

    def list_tasks(self) -> List[str]:
        return list(self._contract_data.get("tasks", {}).keys())

    def get_task_contract(self, task_id: Optional[str] = None) -> Dict[str, Any]:
        effective_task_id = task_id or os.getenv("GV100H_TASK_ID")
        if not effective_task_id:
            raise ValueError("Task ID must be provided directly or via GV100H_TASK_ID environment variable.")

        tasks = self._contract_data.get("tasks", {})
        if effective_task_id not in tasks:
            raise KeyError(f"Task '{effective_task_id}' not defined in {self.contract_file}. Available: {list(tasks.keys())}")

        task_def = dict(tasks[effective_task_id])
        task_def["task_id"] = effective_task_id
        return task_def

    def get_development_contract(self, milestone_id: str) -> Dict[str, Any]:
        """Returns the Development Governance Contract for a given engineering milestone (e.g. GV100H-M0.5)."""
        return self.get_task_contract(milestone_id)

    def get_benchmark_execution_contract(
        self,
        benchmark_task_id: str,
        case_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Returns the Benchmark Execution Governance Contract for an evaluated agent running a testcase
        in a disposable worktree (e.g. UVM-001, USB3-WR-001).
        """
        defaults = self._contract_data.get("benchmark_execution_defaults", {})
        allowed = defaults.get("allowed_paths", ["uvm/tests/", "uvm/sequences/", "uvm/env/"])
        forbidden = defaults.get("forbidden_paths", ["rtl/", "additional/", ".git/"])

        if case_data:
            allowed = case_data.get("allowed_paths", allowed)
            forbidden = case_data.get("forbidden_paths", forbidden)

        return {
            "task_id": benchmark_task_id,
            "contract_id": f"EXEC-CONTRACT-{benchmark_task_id}",
            "allowed_paths": allowed,
            "forbidden_paths": forbidden,
            "authority_level": "normative_enforced",
            "interception_mode": "ENFORCED"
        }

    def create_guardrail_for_task(self, task_id: Optional[str] = None, base_dir: Optional[str] = None) -> ScopeGuardrail:
        task_def = self.get_task_contract(task_id)
        allowed = task_def.get("allowed_paths", [])
        forbidden = task_def.get("forbidden_paths", [])
        effective_base_dir = base_dir or str(self.base_dir)
        return ScopeGuardrail(allowed_paths=allowed, forbidden_paths=forbidden, base_dir=effective_base_dir)

    def create_guardrail_for_benchmark_execution(
        self,
        benchmark_task_id: str,
        base_dir: Optional[str] = None,
        case_data: Optional[Dict[str, Any]] = None
    ) -> ScopeGuardrail:
        contract = self.get_benchmark_execution_contract(benchmark_task_id, case_data)
        allowed = contract.get("allowed_paths", [])
        forbidden = contract.get("forbidden_paths", [])
        effective_base_dir = base_dir or str(self.base_dir)
        return ScopeGuardrail(allowed_paths=allowed, forbidden_paths=forbidden, base_dir=effective_base_dir)

