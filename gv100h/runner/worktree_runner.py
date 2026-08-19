import os
import shutil
import hashlib
import json
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

    @staticmethod
    def build_workspace_tree_snapshot(worktree_path: Path, changed_paths: List[str]) -> bytes:
        worktree = Path(worktree_path)
        files = []
        for changed_path in sorted(changed_paths):
            target = worktree / changed_path
            if target.is_symlink():
                files.append({
                    "kind": "symlink",
                    "path": changed_path,
                    "target": os.readlink(target),
                })
            elif target.is_file():
                content = target.read_bytes()
                files.append({
                    "kind": "file",
                    "path": changed_path,
                    "sha256": GitWorktreeRunner.compute_sha256(content),
                    "size": len(content),
                })
            else:
                files.append({"kind": "missing", "path": changed_path})
        return json.dumps(
            {"files": files},
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    @staticmethod
    def list_worktree_changed_paths(worktree_path: Path) -> List[str]:
        w_path = Path(worktree_path)
        if not w_path.exists():
            raise FatalWorktreeError(f"Worktree path '{worktree_path}' does not exist.")
        try:
            subprocess.run(
                ["git", "add", "-N", "-f", "."],
                cwd=str(w_path),
                capture_output=True,
                check=True,
            )
            status_after_add = subprocess.run(
                ["git", "status", "--porcelain=v2", "-z", "--untracked-files=all"],
                cwd=str(w_path),
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            error = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else str(exc)
            raise FatalWorktreeError(
                f"git status failed in worktree: {error.strip()}"
            ) from exc
        return GitWorktreeRunner._parse_porcelain_v2_paths(status_after_add.stdout)

    @staticmethod
    def _parse_porcelain_v2_paths(payload: bytes) -> List[str]:
        paths: List[str] = []
        records = payload.split(b"\0")
        index = 0
        while index < len(records):
            record = records[index]
            index += 1
            if not record:
                continue

            record_type = record[:1]
            if record_type in {b"?", b"!"}:
                if len(record) < 3 or record[1:2] != b" ":
                    raise FatalWorktreeError(f"Malformed porcelain-v2 path record: {record!r}")
                raw_paths = [record[2:]]
            elif record_type in {b"1", b"u"}:
                fields = record.split(b" ", 8 if record_type == b"1" else 10)
                expected_fields = 9 if record_type == b"1" else 11
                if len(fields) != expected_fields:
                    raise FatalWorktreeError(f"Malformed porcelain-v2 path record: {record!r}")
                raw_paths = [fields[-1]]
            elif record_type == b"2":
                fields = record.split(b" ", 8)
                if len(fields) != 9:
                    raise FatalWorktreeError(f"Malformed porcelain-v2 rename record: {record!r}")
                score_and_path = fields[-1].split(b" ", 1)
                if len(score_and_path) != 2 or index >= len(records):
                    raise FatalWorktreeError(f"Malformed porcelain-v2 rename record: {record!r}")
                raw_paths = [score_and_path[1], records[index]]
                index += 1
            elif record_type == b"#":
                continue
            else:
                raise FatalWorktreeError(f"Unsupported porcelain-v2 record: {record!r}")

            try:
                paths.extend(raw_path.decode("utf-8") for raw_path in raw_paths)
            except UnicodeDecodeError as exc:
                raise FatalWorktreeError("Porcelain-v2 path is not valid UTF-8") from exc

        return list(dict.fromkeys(paths))

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
            changed_paths = self.list_worktree_changed_paths(w_path)
            diff_res = subprocess.run(
                ["git", "diff", "--binary", base_sha],
                cwd=str(w_path),
                capture_output=True,
                check=True,
            )
            diff_bytes = diff_res.stdout
        except subprocess.CalledProcessError as e:
            error = e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e)
            raise FatalWorktreeError(f"git diff failed in worktree: {error.strip()}")

        sorted_paths = sorted(changed_paths)
        workspace_tree = self.build_workspace_tree_snapshot(w_path, sorted_paths)
        workspace_tree_sha256 = self.compute_sha256(workspace_tree)
        return diff_bytes, sorted_paths, workspace_tree_sha256

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
