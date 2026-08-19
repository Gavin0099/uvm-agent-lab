import shutil
import subprocess
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional
from scripts.eda.base_eda import BaseEDAAdapter


class VerilatorAdapter(BaseEDAAdapter):
    """
    Adapter for Verilator Open-Source SystemVerilog Linting and C++ Co-simulation.
    """

    def __init__(self, workspace_root: Optional[Path] = None):
        super().__init__("Verilator", workspace_root)

    def is_available(self) -> bool:
        return shutil.which("verilator") is not None

    def get_version(self) -> str:
        if not self.is_available():
            return "not_installed"
        try:
            res = subprocess.run(["verilator", "--version"], capture_output=True, text=True, timeout=5)
            first_line = res.stdout.splitlines()[0] if res.stdout else "unknown"
            return first_line.strip()
        except Exception:
            return "unknown"

    def compile(self, target_files: List[str], extra_flags: Optional[List[str]] = None) -> Dict[str, Any]:
        target_files = self.resolve_target_files(target_files)
        if not self.is_available():
            return {
                "status": "fail",
                "log": "Verilator binary not found in system PATH.",
                "errors_count": 1,
                "log_hash": hashlib.sha256(b"verilator_not_found").hexdigest(),
                "backend": "verilator",
                "version": "not_installed",
                "verification_level": "lint_only",
                "qualification_admissible": False,
            }

        cmd = ["verilator", "--lint-only", "-Wall"]
        if extra_flags:
            cmd.extend(extra_flags)
        cmd.extend(target_files)

        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=30,
                cwd=str(self.workspace_root)
            )
            log = res.stdout
            status = "pass" if res.returncode == 0 else "fail"
            errors_count = log.count("%Error")
            return {
                "status": status,
                "log": log,
                "errors_count": errors_count,
                "log_hash": hashlib.sha256(log.encode("utf-8")).hexdigest(),
                "backend": "verilator",
                "version": self.get_version(),
                "command": subprocess.list2cmdline(cmd),
                "cwd": str(self.workspace_root),
                "tool_path": shutil.which("verilator") or "",
                "verification_level": "lint_only",
                "qualification_admissible": False,
            }
        except subprocess.TimeoutExpired:
            return {
                "status": "fail",
                "log": "Verilator compilation timed out.",
                "errors_count": 1,
                "log_hash": hashlib.sha256(b"verilator_timeout").hexdigest(),
                "backend": "verilator",
                "version": self.get_version(),
                "verification_level": "lint_only",
                "qualification_admissible": False,
            }
        except Exception as e:
            return {
                "status": "fail",
                "log": f"Verilator execution error: {str(e)}",
                "errors_count": 1,
                "log_hash": hashlib.sha256(str(e).encode("utf-8")).hexdigest(),
                "backend": "verilator",
                "version": self.get_version(),
                "verification_level": "lint_only",
                "qualification_admissible": False,
            }

    def simulate(self, top_module: str, seed: int = 1, timeout_sec: int = 60) -> Dict[str, Any]:
        # Verilator is primarily a compiler/linter; standalone simulation requires C++ testbench compilation
        return {
            "status": "unsupported",
            "log": "Verilator direct simulation unsupported without C++ model binary compilation.",
            "mismatches": 0,
            "coverage": 0.0,
            "log_hash": hashlib.sha256(b"verilator_direct_sim_unsupported").hexdigest(),
            "backend": "verilator",
            "version": self.get_version(),
            "verification_level": "lint_only",
            "qualification_admissible": False,
        }

