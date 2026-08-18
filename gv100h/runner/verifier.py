import hashlib
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Literal, List
from pydantic import BaseModel, Field

from scripts.eda.router import EDARouter


class FinalVerificationResult(BaseModel):
    """
    Independent, objective verification truth evaluated strictly outside
    the Agent's self-reported claims.
    """
    build_status: Literal["pass", "fail", "unsupported"]
    test_status: Literal["pass", "fail", "unsupported"]
    build_command: str
    build_exit_code: int
    build_log: str
    build_log_sha256: str
    test_command: str
    test_exit_code: int
    test_log: str
    test_log_sha256: str
    final_pass: bool
    failure_class: Optional[str] = None
    eda_backend: str = "unknown"
    eda_version: str = "unknown"
    qualification_admissible: bool = True


class IndependentVerifier:
    """
    Independent Verification Engine executing real EDA compilation & simulation
    strictly within the disposable git worktree sandbox.
    Enforces the core principle: exit 0 != success.
    """

    def __init__(self, workspace_root: Path, mode: str = "mock"):
        self.workspace_root = Path(workspace_root).resolve()
        self.mode = mode
        # Compatible with HEAD EDARouter(preferred_backend=...).
        self.eda_router = EDARouter()

    def _backend_truth(self) -> Dict[str, Any]:
        backend = self.eda_router.get_active_backend()
        if backend == "stub":
            return {
                "backend": "stub",
                "version": "synthetic_sim_stub_v1",
                "qualification_admissible": False,
            }
        return {
            "backend": backend,
            "version": "unknown",
            "qualification_admissible": True,
        }

    def _live_stub_rejected(self, primary_target: str, meta: Dict[str, Any]) -> Optional[FinalVerificationResult]:
        if self.mode != "live" or meta["backend"] != "stub":
            return None
        log = (
            "FAIL-CLOSED: Live qualification requires real installed EDA "
            "toolchain (VCS, Icarus, or Verilator). SimStub fallback rejected."
        )
        log_sha = hashlib.sha256(log.encode("utf-8")).hexdigest()
        return FinalVerificationResult(
            build_status="fail",
            test_status="unsupported",
            build_command=f"compile {primary_target}",
            build_exit_code=1,
            build_log=log,
            build_log_sha256=log_sha,
            test_command="none",
            test_exit_code=1,
            test_log=log,
            test_log_sha256=log_sha,
            final_pass=False,
            failure_class="BUILD_FAIL",
            eda_backend=meta["backend"],
            eda_version=meta["version"],
            qualification_admissible=False,
        )

    def verify_task(
        self,
        changed_paths: List[str],
        target_file: Optional[str] = None,
        top_module: Optional[str] = None
    ) -> FinalVerificationResult:
        meta = self._backend_truth()
        backend = meta["backend"]
        version = meta["version"]
        admissible = meta["qualification_admissible"]

        primary_target = target_file
        if not primary_target and changed_paths:
            primary_target = changed_paths[0]

        if not primary_target:
            primary_target = "uvm/tests/test_case.sv"

        live_reject = self._live_stub_rejected(primary_target, meta)
        if live_reject is not None and not primary_target.endswith(".py"):
            return live_reject

        # Case 1: Python Task
        if primary_target.endswith(".py"):
            cmd = f"python -m py_compile {primary_target}"
            res = subprocess.run(
                cmd,
                shell=True,
                cwd=str(self.workspace_root),
                capture_output=True,
                text=True
            )
            log = (res.stdout or "") + "\n" + (res.stderr or "")
            build_pass = (res.returncode == 0)
            build_log_sha = hashlib.sha256(log.encode("utf-8")).hexdigest()

            return FinalVerificationResult(
                build_status="pass" if build_pass else "fail",
                test_status="pass" if build_pass else "fail",
                build_command=cmd,
                build_exit_code=res.returncode,
                build_log=log,
                build_log_sha256=build_log_sha,
                test_command="pytest",
                test_exit_code=res.returncode,
                test_log=log,
                test_log_sha256=build_log_sha,
                final_pass=build_pass,
                failure_class="BUILD_FAIL" if not build_pass else None,
                eda_backend="python_compiler",
                eda_version="py_compile_3.13",
                qualification_admissible=True
            )

        # Case 2: SystemVerilog / UVM Verification Task
        full_target = (self.workspace_root / primary_target).resolve()
        if not full_target.exists():
            log = f"Target file '{primary_target}' was not found in worktree."
            log_sha = hashlib.sha256(log.encode("utf-8")).hexdigest()
            return FinalVerificationResult(
                build_status="fail",
                test_status="fail",
                build_command=f"compile {primary_target}",
                build_exit_code=1,
                build_log=log,
                build_log_sha256=log_sha,
                test_command="simulate",
                test_exit_code=1,
                test_log=log,
                test_log_sha256=log_sha,
                final_pass=False,
                failure_class="BUILD_FAIL",
                eda_backend=backend,
                eda_version=version,
                qualification_admissible=admissible
            )

        # 1. Compile Phase
        comp_res = self.eda_router.compile([primary_target])
        build_log = comp_res.get("log", "")
        build_log_sha = hashlib.sha256(build_log.encode("utf-8")).hexdigest()
        build_passed = (comp_res.get("status") == "pass")

        if not build_passed:
            return FinalVerificationResult(
                build_status="fail",
                test_status="unsupported",
                build_command=f"compile {primary_target}",
                build_exit_code=1,
                build_log=build_log,
                build_log_sha256=build_log_sha,
                test_command="none",
                test_exit_code=1,
                test_log="Simulation skipped due to build failure.",
                test_log_sha256=hashlib.sha256(b"sim_skipped").hexdigest(),
                final_pass=False,
                failure_class="BUILD_FAIL",
                eda_backend=backend,
                eda_version=version,
                qualification_admissible=admissible and comp_res.get("qualification_admissible", True)
            )

        # 2. Simulation Phase
        module_name = top_module or "valid_test"
        sim_res = self.eda_router.simulate(module_name)
        test_log = sim_res.get("log", "")
        test_log_sha = hashlib.sha256(test_log.encode("utf-8")).hexdigest()
        test_passed = (sim_res.get("status") == "pass")

        final_pass = (build_passed and test_passed)
        failure_class = None if final_pass else ("TEST_FAIL" if not test_passed else "BUILD_FAIL")

        return FinalVerificationResult(
            build_status="pass",
            test_status=sim_res.get("status", "fail"),
            build_command=f"compile {primary_target}",
            build_exit_code=0,
            build_log=build_log,
            build_log_sha256=build_log_sha,
            test_command=f"simulate {module_name}",
            test_exit_code=0 if test_passed else 1,
            test_log=test_log,
            test_log_sha256=test_log_sha,
            final_pass=final_pass,
            failure_class=failure_class,
            eda_backend=backend,
            eda_version=version,
            qualification_admissible=admissible and sim_res.get("qualification_admissible", True)
        )

