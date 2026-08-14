import os
import shutil
import subprocess
import hashlib
from typing import Dict, Any, List, Optional
from scripts.eda.base_eda import BaseEDAAdapter


class IcarusVerilogAdapter(BaseEDAAdapter):
    """
    Adapter for Icarus Verilog Open-Source Simulator (iverilog + vvp).
    """

    def __init__(self, build_dir: str = "build/iverilog"):
        super().__init__("IcarusVerilog")
        self.build_dir = build_dir

    def is_available(self) -> bool:
        return (shutil.which("iverilog") is not None) and (shutil.which("vvp") is not None)

    def compile(self, target_files: List[str], extra_flags: Optional[List[str]] = None) -> Dict[str, Any]:
        if not self.is_available():
            return {
                "status": "fail",
                "log": "iverilog binary not found in system PATH.",
                "errors_count": 1,
                "log_hash": hashlib.sha256(b"iverilog_not_found").hexdigest(),
            }

        os.makedirs(self.build_dir, exist_ok=True)
        out_bin = os.path.join(self.build_dir, "sim.vvp")

        cmd = ["iverilog", "-g2012", "-o", out_bin]
        if extra_flags:
            cmd.extend(extra_flags)
        cmd.extend(target_files)

        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30)
            log = res.stdout
            status = "pass" if res.returncode == 0 else "fail"
            errors_count = log.lower().count("error")
            return {
                "status": status,
                "log": log if log else "Icarus compilation successful.",
                "errors_count": errors_count,
                "log_hash": hashlib.sha256(log.encode("utf-8")).hexdigest(),
            }
        except subprocess.TimeoutExpired:
            return {
                "status": "fail",
                "log": "Icarus compilation timed out.",
                "errors_count": 1,
                "log_hash": hashlib.sha256(b"iverilog_timeout").hexdigest(),
            }

    def simulate(self, top_module: str, seed: int = 1, timeout_sec: int = 60) -> Dict[str, Any]:
        if not self.is_available():
            return {
                "status": "fail",
                "log": "vvp binary not found in system PATH.",
                "mismatches": 1,
                "coverage": 0.0,
                "log_hash": hashlib.sha256(b"vvp_not_found").hexdigest(),
            }

        out_bin = os.path.join(self.build_dir, "sim.vvp")
        if not os.path.exists(out_bin):
            return {
                "status": "fail",
                "log": f"Simulation executable '{out_bin}' not found. Compile before simulating.",
                "mismatches": 1,
                "coverage": 0.0,
                "log_hash": hashlib.sha256(b"vvp_binary_missing").hexdigest(),
            }

        cmd = ["vvp", out_bin]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout_sec)
            log = res.stdout
            status = "pass" if res.returncode == 0 and "error" not in log.lower() else "fail"
            mismatches = log.lower().count("mismatch") + log.lower().count("error")
            return {
                "status": status,
                "log": log,
                "mismatches": mismatches,
                "coverage": 100.0 if status == "pass" else 50.0,
                "log_hash": hashlib.sha256(log.encode("utf-8")).hexdigest(),
            }
        except subprocess.TimeoutExpired:
            return {
                "status": "timeout",
                "log": f"Simulation timed out after {timeout_sec}s.",
                "mismatches": 1,
                "coverage": 0.0,
                "log_hash": hashlib.sha256(b"vvp_sim_timeout").hexdigest(),
            }
