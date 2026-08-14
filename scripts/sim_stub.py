import hashlib
from typing import Dict, Any
from pathlib import Path


class SimStubEngine:
    """
    Deterministic Simulator & Compiler Stub.
    Simulates VCS/Xcelium/Verilator responses deterministically for benchmark verification.
    """

    def __init__(self, fixtures_dir: str = "fixtures"):
        self.fixtures_dir = Path(fixtures_dir).resolve()

    def run_compile(self, target_file: str, extra_flags: str = "") -> Dict[str, Any]:
        """
        Simulates compilation of target SystemVerilog/UVM files.
        """
        # If the target file contains syntax errors or has 'broken' in name, simulate error
        if "broken" in target_file.lower():
            log_path = self.fixtures_dir / "logs" / "compile_error.log"
            log_content = log_path.read_text(encoding="utf-8") if log_path.exists() else "Compile Error: Syntax error."
            return {
                "status": "fail",
                "log": log_content,
                "errors_count": 1,
                "log_hash": hashlib.sha256(log_content.encode("utf-8")).hexdigest(),
            }

        log_path = self.fixtures_dir / "logs" / "compile_pass.log"
        log_content = log_path.read_text(encoding="utf-8") if log_path.exists() else "Compile Pass: 0 Errors, 0 Warnings."
        return {
            "status": "pass",
            "log": log_content,
            "errors_count": 0,
            "log_hash": hashlib.sha256(log_content.encode("utf-8")).hexdigest(),
        }

    def run_simulation(self, test_name: str, seed: int = 1, timeout_sec: int = 60) -> Dict[str, Any]:
        """
        Simulates running a UVM testcase.
        """
        if "fail" in test_name.lower() or "broken" in test_name.lower():
            log_path = self.fixtures_dir / "logs" / "sim_fail.log"
            log_content = log_path.read_text(encoding="utf-8") if log_path.exists() else "UVM_ERROR Scoreboard mismatch."
            return {
                "status": "fail",
                "log": log_content,
                "mismatches": 1,
                "coverage": 45.0,
                "log_hash": hashlib.sha256(log_content.encode("utf-8")).hexdigest(),
            }

        log_path = self.fixtures_dir / "logs" / "sim_pass.log"
        log_content = log_path.read_text(encoding="utf-8") if log_path.exists() else "--- UVM_TEST_PASSED ---"
        return {
            "status": "pass",
            "log": log_content,
            "mismatches": 0,
            "coverage": 100.0,
            "log_hash": hashlib.sha256(log_content.encode("utf-8")).hexdigest(),
        }
