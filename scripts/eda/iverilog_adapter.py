import os
import shutil
import subprocess
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional
from scripts.eda.base_eda import BaseEDAAdapter


class IcarusVerilogAdapter(BaseEDAAdapter):
    """
    Adapter for Icarus Verilog Open-Source Simulator (iverilog + vvp).
    """

    def __init__(self, workspace_root: Optional[Path] = None, build_dir: Optional[str] = None):
        super().__init__("IcarusVerilog", workspace_root)
        self.build_path = self.resolve_workspace_path(build_dir or "build/iverilog")

    def is_available(self) -> bool:
        return (shutil.which("iverilog") is not None) and (shutil.which("vvp") is not None)

    def get_version(self) -> str:
        if not self.is_available():
            return "not_installed"
        try:
            res = subprocess.run(["iverilog", "-V"], capture_output=True, text=True, timeout=5)
            first_line = res.stdout.splitlines()[0] if res.stdout else "unknown"
            return first_line.strip()
        except Exception:
            return "unknown"

    def compile(self, target_files: List[str], extra_flags: Optional[List[str]] = None) -> Dict[str, Any]:
        target_files = self.resolve_target_files(target_files)
        if not self.is_available():
            return {
                "status": "fail",
                "log": "iverilog binary not found in system PATH.",
                "errors_count": 1,
                "log_hash": hashlib.sha256(b"iverilog_not_found").hexdigest(),
                "backend": "iverilog",
                "version": "not_installed",
                "command": "iverilog unavailable",
                "cwd": str(self.workspace_root),
                "tool_path": "",
                "verification_level": "compile_and_simulate",
                "qualification_admissible": False,
            }

        self.build_path.mkdir(parents=True, exist_ok=True)
        out_bin = str(self.build_path / "sim.vvp")

        cmd = ["iverilog", "-g2012", "-o", out_bin]
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
            errors_count = log.lower().count("error")
            return {
                "status": status,
                "log": log if log else "Icarus compilation successful.",
                "errors_count": errors_count,
                "log_hash": hashlib.sha256(log.encode("utf-8")).hexdigest(),
                "backend": "iverilog",
                **self.execution_metadata(
                    cmd,
                    verification_level="compile_and_simulate",
                    qualification_admissible=True,
                ),
            }
        except subprocess.TimeoutExpired:
            return {
                "status": "fail",
                "log": "Icarus compilation timed out.",
                "errors_count": 1,
                "log_hash": hashlib.sha256(b"iverilog_timeout").hexdigest(),
                "backend": "iverilog",
                "version": self.get_version(),
                "command": subprocess.list2cmdline(cmd),
                "cwd": str(self.workspace_root),
                "tool_path": shutil.which("iverilog") or "",
                "verification_level": "compile_and_simulate",
                "qualification_admissible": True,
            }

    def simulate(self, top_module: str, seed: int = 1, timeout_sec: int = 60) -> Dict[str, Any]:
        out_bin = str(self.build_path / "sim.vvp")
        cmd = ["vvp", out_bin]
        if not self.is_available():
            return {
                "status": "fail",
                "log": "vvp binary not found in system PATH.",
                "mismatches": 1,
                "coverage": 0.0,
                "log_hash": hashlib.sha256(b"vvp_not_found").hexdigest(),
                "backend": "iverilog",
                "version": "not_installed",
                "command": "vvp unavailable",
                "cwd": str(self.workspace_root),
                "tool_path": "",
                "verification_level": "compile_and_simulate",
                "qualification_admissible": False,
            }

        if not Path(out_bin).exists():
            return {
                "status": "fail",
                "log": f"Compiled simulation binary '{out_bin}' not found.",
                "mismatches": 1,
                "coverage": 0.0,
                "log_hash": hashlib.sha256(b"sim_vvp_missing").hexdigest(),
                "backend": "iverilog",
                "version": self.get_version(),
                "command": subprocess.list2cmdline(cmd),
                "cwd": str(self.workspace_root),
                "tool_path": shutil.which("vvp") or "",
                "verification_level": "compile_and_simulate",
                "qualification_admissible": False,
            }

        cmd = ["vvp", out_bin]
        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout_sec,
                cwd=str(self.workspace_root)
            )
            log = res.stdout
            status = "pass" if res.returncode == 0 and "error" not in log.lower() else "fail"
            mismatches = log.lower().count("error") + log.lower().count("fatal")
            return {
                "status": status,
                "log": log,
                "mismatches": mismatches,
                "coverage": 100.0 if status == "pass" else 0.0,
                "log_hash": hashlib.sha256(log.encode("utf-8")).hexdigest(),
                "backend": "iverilog",
                "version": self.get_version(),
                "command": subprocess.list2cmdline(cmd),
                "cwd": str(self.workspace_root),
                "tool_path": shutil.which("vvp") or "",
                "verification_level": "compile_and_simulate",
                "qualification_admissible": True,
            }
        except subprocess.TimeoutExpired:
            return {
                "status": "timeout",
                "log": f"Icarus simulation timed out after {timeout_sec}s.",
                "mismatches": 1,
                "coverage": 0.0,
                "log_hash": hashlib.sha256(b"iverilog_sim_timeout").hexdigest(),
                "backend": "iverilog",
                "version": self.get_version(),
                "command": subprocess.list2cmdline(cmd),
                "cwd": str(self.workspace_root),
                "tool_path": shutil.which("vvp") or "",
                "verification_level": "compile_and_simulate",
                "qualification_admissible": True,
            }
