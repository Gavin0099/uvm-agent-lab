from typing import Dict, Any
from scripts.sim_stub import SimStubEngine


class GovernedSimTools:
    """
    EDA Simulator invocation tool wrapper (interfacing with SimStub / VCS / Verilator).
    """

    def __init__(self, sim_engine: SimStubEngine = None):
        self.sim_engine = sim_engine or SimStubEngine()

    def compile(self, target_file: str, extra_flags: str = "") -> Dict[str, Any]:
        result = self.sim_engine.run_compile(target_file=target_file, extra_flags=extra_flags)
        return result

    def simulate(self, test_name: str, seed: int = 1, timeout_sec: int = 60) -> Dict[str, Any]:
        result = self.sim_engine.run_simulation(test_name=test_name, seed=seed, timeout_sec=timeout_sec)
        return result
