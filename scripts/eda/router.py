import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
from scripts.eda.verilator_adapter import VerilatorAdapter
from scripts.eda.iverilog_adapter import IcarusVerilogAdapter
from scripts.eda.vcs_adapter import SynopsysVCSAdapter
from scripts.sim_stub import SimStubEngine


class EDARouter:
    """
    Unified EDA Simulator & Compiler Router.
    Automatically detects available EDA toolchains (VCS, Verilator, Icarus),
    binds to disposable workspace_root, and falls back to deterministic SimStubEngine in mock mode.
    Enforces Fail-Closed rejection for live qualification if real EDA toolchains are unavailable.
    """

    def __init__(
        self,
        preferred_backend: str = "auto",
        workspace_root: Optional[Path] = None,
        mode: str = "mock"
    ):
        self.preferred_backend = preferred_backend
        self.workspace_root = Path(workspace_root).resolve() if workspace_root else Path(".").resolve()
        self.mode = mode

        self.verilator = VerilatorAdapter(self.workspace_root)
        self.iverilog = IcarusVerilogAdapter(self.workspace_root)
        self.vcs = SynopsysVCSAdapter(self.workspace_root)
        self.sim_stub = SimStubEngine()

    def get_active_backend(self) -> str:
        if self.preferred_backend == "vcs" and self.vcs.is_available():
            return "vcs"
        if self.preferred_backend == "verilator" and self.verilator.is_available():
            return "verilator"
        if self.preferred_backend == "iverilog" and self.iverilog.is_available():
            return "iverilog"
        if self.preferred_backend == "stub":
            return "stub"

        # Auto detection order
        if self.vcs.is_available():
            return "vcs"
        if self.iverilog.is_available():
            return "iverilog"
        if self.verilator.is_available():
            return "verilator"
        return "stub"

    def get_backend_metadata(self) -> Dict[str, Any]:
        backend = self.get_active_backend()
        if backend == "vcs":
            return {
                "backend": "vcs",
                "version": self.vcs.get_version(),
                "verification_level": "full_uvm_regression",
                "qualification_admissible": True,
            }
        if backend == "iverilog":
            return {
                "backend": "iverilog",
                "version": self.iverilog.get_version(),
                "verification_level": "compile_and_simulate",
                "qualification_admissible": self.mode != "live",
            }
        if backend == "verilator":
            return {
                "backend": "verilator",
                "version": self.verilator.get_version(),
                "verification_level": "lint_only",
                "qualification_admissible": False,
            }
        return {
            "backend": "stub",
            "version": "synthetic_sim_stub_v1",
            "verification_level": "synthetic",
            "qualification_admissible": False,
        }

    def _decorate_result(
        self,
        result: Dict[str, Any],
        backend: str,
        operation: str,
        arguments: List[str],
    ) -> Dict[str, Any]:
        metadata = self.get_backend_metadata()
        executable = {
            "vcs": "vcs",
            "iverilog": "iverilog",
            "verilator": "verilator",
            "stub": "SimStubEngine",
        }.get(backend, backend)
        result.setdefault(
            "command",
            subprocess.list2cmdline([executable, operation, *arguments]),
        )
        result.setdefault("cwd", str(self.workspace_root))
        result.setdefault("tool_path", shutil.which(executable) or "")
        result.setdefault("version", metadata["version"])
        result.setdefault("verification_level", metadata["verification_level"])
        result["qualification_admissible"] = bool(
            result.get("qualification_admissible", True)
            and metadata["qualification_admissible"]
        )
        return result

    def compile(self, target_files: List[str], extra_flags: Optional[List[str]] = None) -> Dict[str, Any]:
        backend = self.get_active_backend()
        if self.mode == "live" and backend == "stub":
            return self._decorate_result({
                "status": "fail",
                "log": "FAIL-CLOSED: Live qualification requires real installed EDA toolchain (VCS, Icarus, or Verilator). SimStub fallback rejected.",
                "errors_count": 1,
                "log_hash": "stub_fallback_rejected_live_mode",
                "backend": "stub",
                "version": "synthetic_sim_stub_v1",
                "qualification_admissible": False,
            }, backend, "compile", [*target_files, *(extra_flags or [])])

        if backend == "vcs":
            return self._decorate_result(
                self.vcs.compile(target_files, extra_flags),
                backend,
                "compile",
                [*target_files, *(extra_flags or [])],
            )
        if backend == "iverilog":
            return self._decorate_result(
                self.iverilog.compile(target_files, extra_flags),
                backend,
                "compile",
                [*target_files, *(extra_flags or [])],
            )
        if backend == "verilator":
            return self._decorate_result(
                self.verilator.compile(target_files, extra_flags),
                backend,
                "compile",
                [*target_files, *(extra_flags or [])],
            )

        # Stub fallback (mock mode only)
        first_file = target_files[0] if target_files else "top.sv"
        stub_res = self.sim_stub.run_compile(first_file)
        stub_res.update({"backend": "stub", "version": "synthetic_sim_stub_v1", "qualification_admissible": False})
        return self._decorate_result(stub_res, backend, "compile", target_files)

    def simulate(self, top_module: str, seed: int = 1, timeout_sec: int = 60) -> Dict[str, Any]:
        backend = self.get_active_backend()
        if self.mode == "live" and backend == "stub":
            return self._decorate_result({
                "status": "fail",
                "log": "FAIL-CLOSED: Live qualification requires real installed EDA toolchain (VCS or Icarus). SimStub fallback rejected.",
                "mismatches": 1,
                "coverage": 0.0,
                "log_hash": "stub_fallback_rejected_live_mode",
                "backend": "stub",
                "version": "synthetic_sim_stub_v1",
                "qualification_admissible": False,
            }, backend, "simulate", [top_module])

        if backend == "vcs":
            return self._decorate_result(
                self.vcs.simulate(top_module, seed, timeout_sec),
                backend,
                "simulate",
                [top_module, str(seed)],
            )
        if backend == "iverilog":
            return self._decorate_result(
                self.iverilog.simulate(top_module, seed, timeout_sec),
                backend,
                "simulate",
                [top_module, str(seed)],
            )
        if backend == "verilator":
            return self._decorate_result(
                self.verilator.simulate(top_module, seed, timeout_sec),
                backend,
                "simulate",
                [top_module, str(seed)],
            )

        # Stub fallback (mock mode only)
        stub_res = self.sim_stub.run_simulation(top_module, seed, timeout_sec)
        stub_res.update({"backend": "stub", "version": "synthetic_sim_stub_v1", "qualification_admissible": False})
        return self._decorate_result(stub_res, backend, "simulate", [top_module, str(seed)])

