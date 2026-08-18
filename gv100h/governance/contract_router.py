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

    def create_guardrail_for_task(self, task_id: Optional[str] = None) -> ScopeGuardrail:
        task_def = self.get_task_contract(task_id)
        allowed = task_def.get("allowed_paths", [])
        forbidden = task_def.get("forbidden_paths", [])
        return ScopeGuardrail(allowed_paths=allowed, forbidden_paths=forbidden, base_dir=str(self.base_dir))
