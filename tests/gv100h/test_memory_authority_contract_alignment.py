import subprocess
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _commit_object_exists(commit: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(PROJECT_ROOT), "cat-file", "-e", f"{commit}^{{commit}}"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


@pytest.mark.contract
def test_memory_authority_contract_matches_git_binding_semantics():
    contract_text = (
        PROJECT_ROOT / "governance" / "MEMORY_AUTHORITY_CONTRACT.md"
    ).read_text(encoding="utf-8")
    assert "resolves to a local Git commit object" in contract_text
    assert "matches a hash-like regex" not in contract_text

    current_commit = subprocess.check_output(
        ["git", "-C", str(PROJECT_ROOT), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    nonexistent_commit = "0123456789abcdef0123456789abcdef01234567"

    assert _commit_object_exists(current_commit) is True
    assert _commit_object_exists(nonexistent_commit) is False