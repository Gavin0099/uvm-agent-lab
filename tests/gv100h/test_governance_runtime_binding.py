import pytest
import sys
import tempfile
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gv100h.governance.runtime_bridge import GovernanceRuntimeBridge
from gv100h.runner.worktree_runner import GitWorktreeRunner


@pytest.mark.contract
def test_governance_runtime_bridge_lifecycle():
    bridge = GovernanceRuntimeBridge()

    # Create real temp git repo
    with tempfile.TemporaryDirectory() as tmp_repo:
        r_path = Path(tmp_repo)
        subprocess.run(["git", "init"], cwd=str(r_path), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "TestUser"], cwd=str(r_path), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(r_path), check=True, capture_output=True)

        (r_path / "README.md").write_text("Init", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=str(r_path), check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(r_path), check=True, capture_output=True)

        # 1. Pre-task check with GV100H-M0
        admitted, guardrail, ctx = bridge.pre_task_check("GV100H-M0", str(r_path))
        assert admitted is True
        assert ctx["task_id"] == "GV100H-M0"
        assert len(ctx["contract_hash"]) == 64
        assert "gv100h/gateway/" in ctx["allowed_paths"]
        assert "rtl/" in ctx["forbidden_paths"]

        # 2. Post-task check on allowed path
        valid_paths = ["gv100h/gateway/server.py"]
        passed, err = bridge.post_task_check("GV100H-M0", valid_paths, guardrail)
        assert passed is True
        assert err is None

        # 3. Post-task check on forbidden path
        forbidden_paths = ["rtl/core.sv"]
        passed_f, err_f = bridge.post_task_check("GV100H-M0", forbidden_paths, guardrail)
        assert passed_f is False
        assert "Scope violation" in err_f
