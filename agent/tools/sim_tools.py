from pathlib import Path
from typing import Dict, Any, List, Optional
from scripts.eda.router import EDARouter


class GovernedSimTools:
    """
    Governed EDA Simulator & Compiler invocation tool wrapper.
    Routes requests through EDARouter (supporting VCS, Verilator, Icarus, and deterministic SimStub).
    """

    def __init__(
        self,
        eda_router: Optional[EDARouter] = None,
        workspace_root: Optional[Path] = None,
        mode: str = "mock"
    ):
        self.workspace_root = Path(workspace_root).resolve() if workspace_root else Path(".").resolve()
        self.mode = mode
        self.eda_router = eda_router or EDARouter(
            workspace_root=self.workspace_root,
            mode=self.mode,
        )

    def compile(self, target_file: str, extra_flags: str = "") -> Dict[str, Any]:
        flags = [f for f in extra_flags.split() if f] if extra_flags else None
        target_list = [target_file]
        return self.eda_router.compile(target_files=target_list, extra_flags=flags)

    def simulate(self, test_name: str, seed: int = 1, timeout_sec: int = 60) -> Dict[str, Any]:
        return self.eda_router.simulate(top_module=test_name, seed=seed, timeout_sec=timeout_sec)

