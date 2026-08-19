from pathlib import Path

from agent.governance.guardrails import ScopeGuardrail
from agent.tools.fs_tools import GovernedFileSystemTools


def test_read_file_enforces_guardrail_and_worktree_containment(tmp_path):
    outside = tmp_path.parent / "outside-secret.txt"
    outside.write_text("secret", encoding="utf-8")
    tools = GovernedFileSystemTools(
        guardrail=ScopeGuardrail(allowed_paths=["uvm/"], forbidden_paths=["rtl/"]),
        root_dir=str(tmp_path),
    )

    denied = tools.read_file("rtl/secret.sv")
    escaped = tools.read_file("../outside-secret.txt")

    assert denied["status"] == "governance_violation"
    assert escaped["status"] == "governance_violation"


def test_read_file_uses_the_same_worktree_root_as_write(tmp_path):
    tools = GovernedFileSystemTools(root_dir=str(tmp_path))
    path = Path("uvm/tests/example.sv")

    assert tools.write_file(str(path), "worktree\n")["status"] == "success"
    result = tools.read_file(str(path))

    assert result["status"] == "success"
    assert result["content"] == "worktree\n"