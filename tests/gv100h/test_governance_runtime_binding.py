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


def _init_repo_with_manifests(r_path: Path, requirements_text: str) -> None:
    subprocess.run(["git", "init"], cwd=str(r_path), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "TestUser"], cwd=str(r_path), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(r_path), check=True, capture_output=True)

    (r_path / "requirements.txt").write_text(requirements_text, encoding="utf-8")
    (r_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\ndependencies = []\n', encoding="utf-8"
    )
    governance_dir = r_path / "governance"
    governance_dir.mkdir(parents=True, exist_ok=True)
    (governance_dir / "approved_dependency_additions.json").write_text(
        '{"tasks": {"GV100H-M2-DEPS": {"allowed_packages": ["pdfplumber", "fpdf2"]}}}',
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=str(r_path), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=str(r_path), check=True, capture_output=True)


@pytest.mark.contract
def test_governance_runtime_bridge_enforces_dependency_manifest_content():
    """Declared `validators:` entries are executed when post_task_check()
    is invoked. This is library-level dispatch, not evidence of a production
    session orchestrator. GV100H-M2-DEPS declares
    dependency_manifest_diff_validator.py; an unapproved requirements.txt
    change must be rejected by post_task_check() itself when that method
    is called with repo_root/base_ref.
    """
    bridge = GovernanceRuntimeBridge()

    with tempfile.TemporaryDirectory() as tmp_repo:
        r_path = Path(tmp_repo)
        _init_repo_with_manifests(r_path, "pyyaml>=6.0.1\n")

        admitted, guardrail, ctx = bridge.pre_task_check("GV100H-M2-DEPS", str(r_path))
        assert admitted is True
        assert "validators/dependency_manifest_diff_validator.py" in ctx["validators"]

        # Additive, allowlisted change: passes.
        (r_path / "requirements.txt").write_text(
            "pyyaml>=6.0.1\npdfplumber>=0.10\n", encoding="utf-8"
        )
        passed, err = bridge.post_task_check(
            "GV100H-M2-DEPS",
            ["requirements.txt"],
            guardrail,
            repo_root=str(r_path),
            base_ref="HEAD",
        )
        assert passed is True, err

        # Unapproved change: rejected by content validation, not just path
        # membership (requirements.txt is in allowed_paths either way).
        (r_path / "requirements.txt").write_text(
            "pyyaml>=6.0.1\nrequests>=2.31.0\n", encoding="utf-8"
        )
        passed_bad, err_bad = bridge.post_task_check(
            "GV100H-M2-DEPS",
            ["requirements.txt"],
            guardrail,
            repo_root=str(r_path),
            base_ref="HEAD",
        )
        assert passed_bad is False
        assert "Dependency manifest content violation" in err_bad
        assert "requests" in err_bad


@pytest.mark.contract
def test_governance_runtime_bridge_content_validator_survives_path_normalization():
    """Regression for the P1 Codex finding: _run_declared_content_validators()
    must normalize changed_paths the same way ScopeGuardrail.check_path_access()
    does before comparing against the guarded manifest filename set. A
    differently-formatted equivalent path ('./requirements.txt', an absolute
    path, or a backslash-separated path) must not silently skip content
    validation just because it doesn't exact-string-match "requirements.txt".
    """
    bridge = GovernanceRuntimeBridge()

    with tempfile.TemporaryDirectory() as tmp_repo:
        r_path = Path(tmp_repo)
        _init_repo_with_manifests(r_path, "pyyaml>=6.0.1\n")

        _admitted, guardrail, _ctx = bridge.pre_task_check("GV100H-M2-DEPS", str(r_path))

        (r_path / "requirements.txt").write_text(
            "pyyaml>=6.0.1\nrequests>=2.31.0\n", encoding="utf-8"
        )

        for differently_formatted_path in (
            "./requirements.txt",
            str(r_path / "requirements.txt"),
            "requirements.txt".replace("/", "\\"),
        ):
            passed_bad, err_bad = bridge.post_task_check(
                "GV100H-M2-DEPS",
                [differently_formatted_path],
                guardrail,
                repo_root=str(r_path),
                base_ref="HEAD",
            )
            assert passed_bad is False, (
                f"expected content validation to still trigger for "
                f"{differently_formatted_path!r}, but it was skipped"
            )
            assert "Dependency manifest content violation" in err_bad



@pytest.mark.contract
def test_governance_runtime_bridge_fails_closed_without_repo_context():
    """If a caller invokes post_task_check() for a manifest-guarded task
    without repo_root/base_ref, it must fail closed, not silently skip
    content validation."""
    bridge = GovernanceRuntimeBridge()

    with tempfile.TemporaryDirectory() as tmp_repo:
        r_path = Path(tmp_repo)
        _init_repo_with_manifests(r_path, "pyyaml>=6.0.1\n")

        _admitted, guardrail, _ctx = bridge.pre_task_check("GV100H-M2-DEPS", str(r_path))
        passed, err = bridge.post_task_check(
            "GV100H-M2-DEPS", ["requirements.txt"], guardrail
        )
        assert passed is False
        assert "not given repo_root/base_ref" in err
