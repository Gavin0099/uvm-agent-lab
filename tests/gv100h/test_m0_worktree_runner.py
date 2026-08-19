import pytest
import os
import sys
import tempfile
import subprocess
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


@pytest.mark.contract
def test_porcelain_v2_parser_handles_spaces_unicode_rename_and_copy():
    rename_record = (
        b"2 R. N... 100644 100644 100644 "
        + b"0" * 40
        + b" "
        + b"0" * 40
        + b" R100 new file.sv\0old file.sv\0"
    )
    copy_record = (
        b"2 C. N... 100644 100644 100644 "
        + b"0" * 40
        + b" "
        + b"0" * 40
        + " C100 copied 測試.sv\0source file.sv\0".encode("utf-8")
    )
    untracked_record = "? unicode 測試.sv\0".encode("utf-8")

    paths = GitWorktreeRunner._parse_porcelain_v2_paths(
        rename_record + copy_record + untracked_record
    )

    assert paths == [
        "new file.sv",
        "old file.sv",
        "copied 測試.sv",
        "source file.sv",
        "unicode 測試.sv",
    ]


@pytest.mark.contract
def test_porcelain_v2_parser_handles_real_git_rename_and_unicode_fixture(tmp_path: Path):
    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=str(tmp_path), check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")
    (tmp_path / "old file.sv").write_text("old\n", encoding="utf-8")
    (tmp_path / "unicode 測試.sv").write_text("unicode\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-qm", "base")

    (tmp_path / "old file.sv").rename(tmp_path / "new file.sv")
    (tmp_path / "unicode 測試.sv").write_text("changed\n", encoding="utf-8")
    git("add", "-A")
    status = subprocess.run(
        ["git", "status", "--porcelain=v2", "-z", "--untracked-files=all"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )

    paths = GitWorktreeRunner._parse_porcelain_v2_paths(status.stdout)
    assert "new file.sv" in paths
    assert "old file.sv" in paths
    assert "unicode 測試.sv" in paths
