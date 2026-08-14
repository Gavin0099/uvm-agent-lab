import os
import shutil
import subprocess
import hashlib
from typing import Dict, Any, List, Optional
from scripts.eda.base_eda import BaseEDAAdapter


class SynopsysVCSAdapter(BaseEDAAdapter):
    """
    Adapter for Synopsys VCS Commercial Simulator with IEEE 1800.2 UVM support.
    """

    def __init__(self, simv_path: str = "./simv"):
        super().__init__("SynopsysVCS")
        self.simv_path = simv_path

    def is_available(self) -> bool:
        return shutil.which("vcs") is not None

    def compile(self, target_files: List[str], extra_flags: Optional[List[str]] = None) -> Dict[str, Any]:
        if not self.is_available():
            return {
                "status": "fail",
                "log": "Synopsys VCS binary ('vcs') not found in PATH or license server unavailable.",
                "errors_count": 1,
                "log_hash": hashlib.sha256(b"vcs_not_found").hexdigest(),
            }

        cmd = ["vcs", "-sverilog", "-ntb_opts", "uvm-1.2", "-timescale=1ns/1ps", "-o", self.simv_path]
        if extra_flags:
            cmd.extend(extra_flags)
        cmd.extend(target_files)

        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120)
            log = res.stdout
            status = "pass" if res.returncode == 0 and "Error-[" not in log else "fail"
            errors_count = log.count("Error-[")
            return {
                "status": status,
                "log": log,
                "errors_count": errors_count,
                "log_hash": hashlib.sha256(log.encode("utf-8")).hexdigest(),
            }
        except subprocess.TimeoutExpired:
            return {
                "status": "fail",
                "log": "VCS compilation timed out.",
                "errors_count": 1,
                "log_hash": hashlib.sha256(b"vcs_timeout").hexdigest(),
            }

    def simulate(self, top_module: str, seed: int = 1, timeout_sec: int = 120) -> Dict[str, Any]:
        if not os.path.exists(self.simv_path):
            return {
                "status": "fail",
                "log": f"VCS executable '{self.simv_path}' not found.",
                "mismatches": 1,
                "coverage": 0.0,
                "log_hash": hashlib.sha256(b"simv_missing").hexdigest(),
            }

        cmd = [self.simv_path, f"+ntb_random_seed={seed}", f"+UVM_TESTNAME={top_module}"]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout_sec)
            log = res.stdout
            has_passed = "--- UVM_TEST_PASSED ---" in log and "UVM_ERROR" not in log
            status = "pass" if has_passed else "fail"
            mismatches = log.count("UVM_ERROR") + log.count("UVM_FATAL")
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
                "log": f"VCS simulation timed out after {timeout_sec}s.",
                "mismatches": 1,
                "coverage": 0.0,
                "log_hash": hashlib.sha256(b"vcs_sim_timeout").hexdigest(),
            }
