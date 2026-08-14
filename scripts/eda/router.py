from typing import Dict, Any, List, Optional
from scripts.eda.verilator_adapter import VerilatorAdapter
from scripts.eda.iverilog_adapter import IcarusVerilogAdapter
from scripts.eda.vcs_adapter import SynopsysVCSAdapter
from scripts.sim_stub import SimStubEngine


class EDARouter:
    """
    Unified EDA Simulator & Compiler Router.
    Automatically detects available EDA toolchains (VCS, Verilator, Icarus),
    and falls back to deterministic SimStubEngine when hardware licenses/tools are not present.
    """

    def __init__(self, preferred_backend: str = "auto"):
        self.preferred_backend = preferred_backend
        self.verilator = VerilatorAdapter()
        self.iverilog = IcarusVerilogAdapter()
        self.vcs = SynopsysVCSAdapter()
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
        if self.verilator.is_available():
            return "verilator"
        if self.iverilog.is_available():
            return "iverilog"
        return "stub"

    def compile(self, target_files: List[str], extra_flags: Optional[List[str]] = None) -> Dict[str, Any]:
        backend = self.get_active_backend()
        if backend == "vcs":
            return self.vcs.compile(target_files, extra_flags)
        if backend == "verilator":
            return self.verilator.compile(target_files, extra_flags)
        if backend == "iverilog":
            return self.iverilog.compile(target_files, extra_flags)
        
        # Stub fallback
        first_file = target_files[0] if target_files else "top.sv"
        return self.sim_stub.run_compile(first_file)

    def simulate(self, top_module: str, seed: int = 1, timeout_sec: int = 60) -> Dict[str, Any]:
        backend = self.get_active_backend()
        if backend == "vcs":
            return self.vcs.simulate(top_module, seed, timeout_sec)
        if backend == "verilator":
            return self.verilator.simulate(top_module, seed, timeout_sec)
        if backend == "iverilog":
            return self.iverilog.simulate(top_module, seed, timeout_sec)

        # Stub fallback
        return self.sim_stub.run_simulation(top_module, seed, timeout_sec)
