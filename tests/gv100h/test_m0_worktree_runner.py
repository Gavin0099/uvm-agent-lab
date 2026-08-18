import pytest
import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gv100h.runner.worktree_runner import GitWorktreeRunner
from agent.governance.guardrails import ScopeGuardrail


@pytest.mark.contract
def test_git_worktree_runner_compute_sha():
    content = b"sample patch content"
    sha = GitWorktreeRunner.compute_sha256(content)
    assert len(sha) == 64
    assert sha == GitWorktreeRunner.compute_sha256(content)


@pytest.mark.unit
def test_git_worktree_runner_verify_changed_paths():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "uvm" / "tests").mkdir(parents=True)
        (tmp_path / "rtl").mkdir(parents=True)

        guardrail = ScopeGuardrail(
            allowed_paths=["uvm/tests/"],
            forbidden_paths=["rtl/"],
            base_dir=str(tmp_path)
        )
        runner = GitWorktreeRunner(repo_root=str(tmp_path), guardrail=guardrail)

        # Allowed path
        passed_allowed, err_allowed = runner.verify_changed_paths(["uvm/tests/my_test.sv"])
        assert passed_allowed is True
        assert err_allowed is None

        # Forbidden path
        passed_forbidden, err_forbidden = runner.verify_changed_paths(["rtl/core.sv"])
        assert passed_forbidden is False
        assert "Scope violation" in err_forbidden
