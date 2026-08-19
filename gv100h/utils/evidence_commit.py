import os
import subprocess
from pathlib import Path


EVIDENCE_COMMIT_MESSAGE = "GV100H reconstructed evidence state\n"
EVIDENCE_COMMIT_NAME = "GV100H Evidence"
EVIDENCE_COMMIT_EMAIL = "evidence@localhost"
EVIDENCE_COMMIT_DATE = "2000-01-01T00:00:00+0000"


def compute_reconstructed_head_commit(worktree_path: Path, parent_commit: str) -> str:
    worktree = Path(worktree_path).resolve()
    add_result = subprocess.run(
        ["git", "add", "-A", "-f", "."],
        cwd=str(worktree),
        capture_output=True,
        text=True,
    )
    if add_result.returncode != 0:
        raise RuntimeError(
            f"Could not stage reconstructed evidence state: {add_result.stderr.strip()}"
        )

    tree_result = subprocess.run(
        ["git", "write-tree"],
        cwd=str(worktree),
        capture_output=True,
        text=True,
    )
    if tree_result.returncode != 0:
        raise RuntimeError(
            f"Could not write reconstructed evidence tree: {tree_result.stderr.strip()}"
        )

    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": EVIDENCE_COMMIT_NAME,
            "GIT_AUTHOR_EMAIL": EVIDENCE_COMMIT_EMAIL,
            "GIT_AUTHOR_DATE": EVIDENCE_COMMIT_DATE,
            "GIT_COMMITTER_NAME": EVIDENCE_COMMIT_NAME,
            "GIT_COMMITTER_EMAIL": EVIDENCE_COMMIT_EMAIL,
            "GIT_COMMITTER_DATE": EVIDENCE_COMMIT_DATE,
        }
    )
    commit_result = subprocess.run(
        ["git", "commit-tree", tree_result.stdout.strip(), "-p", parent_commit],
        cwd=str(worktree),
        input=EVIDENCE_COMMIT_MESSAGE,
        capture_output=True,
        text=True,
        env=env,
    )
    if commit_result.returncode != 0:
        raise RuntimeError(
            f"Could not write reconstructed evidence commit: {commit_result.stderr.strip()}"
        )
    return commit_result.stdout.strip()


def list_reconstructed_changed_paths(
    worktree_path: Path,
    parent_commit: str,
    head_commit: str,
) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "--no-renames", "-z", parent_commit, head_commit],
        cwd=str(Path(worktree_path).resolve()),
        capture_output=True,
    )
    if result.returncode != 0:
        error = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Could not enumerate reconstructed changed paths: {error}")

    paths = []
    for raw_path in result.stdout.split(b"\0"):
        if raw_path:
            paths.append(raw_path.decode("utf-8"))
    return list(dict.fromkeys(paths))
