import os
import shutil
import hashlib
import tempfile
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional
from agent.governance.guardrails import ScopeGuardrail


class FatalWorktreeError(Exception):
    """Raised when Git worktree creation, status, or diff extraction fails."""
    pass


class GitWorktreeRunner:
    """
    Manages ephemeral Git worktrees for zero-trust sandbox execution.
    Enforces real worktree isolation, captures untracked files, and extracts binary diffs.
    """

    def __init__(self, repo_root: Optional[str] = None, guardrail: Optional[ScopeGuardrail] = None):
        self.repo_root = Path(repo_root).resolve() if repo_root else Path(__file__).resolve().parent.parent.parent
        self.guardrail = guardrail
        if not (self.repo_root / ".git").exists():
            # Allow fallback for isolated mock testdirs if initialized
            pass

    @staticmethod
    def compute_sha256(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def verify_changed_paths(self, changed_paths: List[str]) -> Tuple[bool, Optional[str]]:
        if not self.guardrail:
            return True, None
        for p in changed_paths:
            res = self.guardrail.check_path_access(p)
            is_allowed = res[0] if isinstance(res, tuple) else res
            if not is_allowed:
                return False, f"Scope violation: Forbidden or out-of-scope path access: {p}"
        return True, None

    def create_worktree(self, base_sha: str = "HEAD") -> Tuple[Path, str]:
        """
        Creates a real disposable detached Git worktree.
        Returns: (worktree_path, resolved_base_sha)
        """
        try:
            rev_res = subprocess.run(
                ["git", "rev-parse", base_sha],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                check=True
            )
            resolved_sha = rev_res.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise FatalWorktreeError(f"Failed to resolve base SHA '{base_sha}': {e.stderr.strip()}")

        temp_dir = Path(tempfile.mkdtemp(prefix="gv100h_worktree_"))
        
        try:
            subprocess.run(
                ["git", "worktree", "add", "--detach", str(temp_dir), resolved_sha],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise FatalWorktreeError(f"git worktree add failed for SHA '{resolved_sha}': {e.stderr.strip()}")

        return temp_dir, resolved_sha

    def extract_worktree_diff(self, worktree_path: Path, base_sha: str) -> Tuple[bytes, List[str], str]:
        """
        Extracts raw binary diff and lists ALL changed + untracked files in the worktree.
        Returns: (diff_bytes, changed_paths, diff_sha256)
        """
        w_path = Path(worktree_path)
        if not w_path.exists():
            raise FatalWorktreeError(f"Worktree path '{worktree_path}' does not exist.")

        try:
            status_res = subprocess.run(
                ["git", "status", "--porcelain=v2", "--untracked-files=all"],
                cwd=str(w_path),
                capture_output=True,
                text=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            raise FatalWorktreeError(f"git status failed in worktree: {e.stderr.strip()}")

        changed_paths = []
        for line in status_res.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) >= 2:
                changed_path = parts[-1]
                changed_paths.append(changed_path)

        try:
            diff_res = subprocess.run(
                ["git", "diff", "--binary", base_sha],
                cwd=str(w_path),
                capture_output=True,
                check=True
            )
            diff_bytes = diff_res.stdout
        except subprocess.CalledProcessError as e:
            raise FatalWorktreeError(f"git diff failed in worktree: {e.stderr.decode('utf-8', errors='replace').strip()}")

        hasher = hashlib.sha256(diff_bytes)
        for cp in sorted(changed_paths):
            target_f = w_path / cp
            if target_f.is_file():
                hasher.update(cp.encode("utf-8"))
                hasher.update(target_f.read_bytes())

        diff_sha256 = hasher.hexdigest()
        return diff_bytes, sorted(changed_paths), diff_sha256

    def cleanup_worktree(self, worktree_path: Path):
        w_path = Path(worktree_path)
        if w_path.exists():
            try:
                subprocess.run(
                    ["git", "worktree", "remove", "--force", str(w_path)],
                    cwd=str(self.repo_root),
                    capture_output=True,
                    check=False
                )
            except Exception:
                pass
            shutil.rmtree(w_path, ignore_errors=True)
