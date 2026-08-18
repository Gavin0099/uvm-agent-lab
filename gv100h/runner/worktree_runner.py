import os
import shutil
import hashlib
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from agent.governance.guardrails import ScopeGuardrail
from gv100h.telemetry.schema import FailureClass


class GitWorktreeRunner:
    """
    Executes tasks in disposable Git worktrees or isolated sandboxes.
    Extracts authentic binary git diffs and independently computes verification hashes.
    """

    def __init__(self, repo_root: str, guardrail: Optional[ScopeGuardrail] = None):
        self.repo_root = Path(repo_root).resolve()
        self.guardrail = guardrail

    @staticmethod
    def compute_sha256(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def get_current_commit_sha(self) -> str:
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                check=True
            )
            return res.stdout.strip()
        except Exception:
            return "0000000000000000000000000000000000000000"

    def create_disposable_sandbox(self) -> Path:
        temp_dir = Path(tempfile.mkdtemp(prefix="gv100h_worktree_"))
        return temp_dir

    def extract_git_diff(self, worktree_dir: Path) -> Tuple[bytes, List[str], str]:
        """
        Runs git diff in the worktree directory and returns:
        (raw_diff_bytes, changed_file_paths, diff_sha256)
        """
        try:
            # Get binary diff
            res_diff = subprocess.run(
                ["git", "diff", "--binary", "HEAD"],
                cwd=str(worktree_dir),
                capture_output=True,
                check=False
            )
            raw_diff = res_diff.stdout

            # Get list of changed file names
            res_names = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"],
                cwd=str(worktree_dir),
                capture_output=True,
                text=True,
                check=False
            )
            changed_files = [line.strip() for line in res_names.stdout.splitlines() if line.strip()]
            diff_hash = self.compute_sha256(raw_diff)
            return raw_diff, changed_files, diff_hash
        except Exception as e:
            empty_bytes = b""
            return empty_bytes, [], self.compute_sha256(empty_bytes)

    def verify_changed_paths(self, changed_paths: List[str]) -> Tuple[bool, Optional[str]]:
        if not self.guardrail:
            return True, None

        for path in changed_paths:
            passed, report = self.guardrail.check_path_access(path)
            if not passed or not report.passed:
                return False, f"Scope violation on path: {path}"
        return True, None
