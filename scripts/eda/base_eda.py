from abc import ABC, abstractmethod
import subprocess
import shutil
from typing import Dict, Any, List, Optional
from pathlib import Path


class BaseEDAAdapter(ABC):
    """
    Abstract Base Class for Electronic Design Automation (EDA) Toolchain Adapters.
    Enforces strict workspace isolation and capability metadata reporting.
    """

    def __init__(self, name: str, workspace_root: Optional[Path] = None):
        self.name = name
        self.workspace_root = Path(workspace_root).resolve() if workspace_root else Path(".").resolve()

    def resolve_workspace_path(self, candidate: str) -> Path:
        path = Path(candidate)
        resolved = (path if path.is_absolute() else self.workspace_root / path).resolve()
        try:
            resolved.relative_to(self.workspace_root)
        except ValueError as exc:
            raise ValueError(
                f"Path '{candidate}' escapes workspace '{self.workspace_root}'"
            ) from exc
        return resolved

    def resolve_target_files(self, target_files: List[str]) -> List[str]:
        return [str(self.resolve_workspace_path(target)) for target in target_files]

    def execution_metadata(
        self,
        command: List[str],
        *,
        verification_level: str,
        qualification_admissible: bool,
    ) -> Dict[str, Any]:
        executable = command[0] if command else ""
        return {
            "command": subprocess.list2cmdline(command),
            "cwd": str(self.workspace_root),
            "tool_path": shutil.which(executable) or "",
            "version": self.get_version(),
            "verification_level": verification_level,
            "qualification_admissible": qualification_admissible,
        }

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the EDA tool binary is installed and executable in PATH."""
        pass
    @abstractmethod
    def get_version(self) -> str:
        """Return tool version string for evidence receipts."""
        pass

    @abstractmethod
    def compile(self, target_files: List[str], extra_flags: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Execute compilation/linting within self.workspace_root.
        Returns: { "status": "pass" | "fail", "log": str, "errors_count": int, "log_hash": str, "backend": str, "qualification_admissible": bool }
        """
        pass

    @abstractmethod
    def simulate(self, top_module: str, seed: int = 1, timeout_sec: int = 60) -> Dict[str, Any]:
        """
        Execute simulation within self.workspace_root.
        Returns: { "status": "pass" | "fail" | "timeout" | "unsupported", "log": str, "mismatches": int, "coverage": float, "log_hash": str, "backend": str, "qualification_admissible": bool }
        """
        pass

