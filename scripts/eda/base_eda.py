from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pathlib import Path


class BaseEDAAdapter(ABC):
    """
    Abstract Base Class for Electronic Design Automation (EDA) Toolchain Adapters.
    """

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the EDA tool binary is installed and executable in PATH."""
        pass

    @abstractmethod
    def compile(self, target_files: List[str], extra_flags: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Execute compilation/linting.
        Returns: { "status": "pass" | "fail", "log": str, "errors_count": int, "log_hash": str }
        """
        pass

    @abstractmethod
    def simulate(self, top_module: str, seed: int = 1, timeout_sec: int = 60) -> Dict[str, Any]:
        """
        Execute simulation.
        Returns: { "status": "pass" | "fail" | "timeout", "log": str, "mismatches": int, "coverage": float, "log_hash": str }
        """
        pass
