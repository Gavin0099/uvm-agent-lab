from pathlib import Path

from gv100h.runner.verifier import IndependentVerifier
from scripts.eda.iverilog_adapter import IcarusVerilogAdapter
from scripts.eda.vcs_adapter import SynopsysVCSAdapter
from scripts.eda.router import EDARouter


class _SpyRouter:
    def get_active_backend(self):
        return "stub"


class _WorkspaceReadingRouter:
    def __init__(self, workspace_root):
        self.workspace_root = Path(workspace_root)

    def get_backend_metadata(self):
        return {
            "backend": "vcs",
            "version": "fake-vcs",
            "verification_level": "full_uvm_regression",
            "qualification_admissible": True,
        }

    def compile(self, target_files):
        content = (self.workspace_root / target_files[0]).read_text(encoding="utf-8")
        passed = content == "worktree\n"
        return {
            "status": "pass" if passed else "fail",
            "log": content,
            "command": "fake-vcs compile",
            "cwd": str(self.workspace_root),
            "tool_path": "fake-vcs",
            "version": "fake-vcs",
            "verification_level": "full_uvm_regression",
            "qualification_admissible": True,
        }

    def simulate(self, top_module, seed=1, timeout_sec=60):
        return {
            "status": "pass",
            "log": "--- UVM_TEST_PASSED ---",
            "command": "fake-vcs simulate",
            "cwd": str(self.workspace_root),
            "tool_path": "fake-vcs",
            "version": "fake-vcs",
            "verification_level": "full_uvm_regression",
            "qualification_admissible": True,
        }


def test_verifier_binds_default_router_to_disposable_workspace(tmp_path, monkeypatch):
    captured = {}

    def factory(**kwargs):
        captured.update(kwargs)
        return _SpyRouter()

    monkeypatch.setattr("gv100h.runner.verifier.EDARouter", factory)

    IndependentVerifier(tmp_path, mode="live")

    assert captured["workspace_root"] == Path(tmp_path).resolve()
    assert captured["mode"] == "live"


def test_verifier_uses_worktree_copy_when_repo_and_worktree_disagree(tmp_path):
    repo_root = tmp_path / "repo"
    worktree_root = tmp_path / "worktree"
    repo_root.mkdir()
    worktree_root.mkdir()
    (repo_root / "target.sv").write_text("main\n", encoding="utf-8")
    (worktree_root / "target.sv").write_text("worktree\n", encoding="utf-8")

    result = IndependentVerifier(
        worktree_root,
        mode="live",
        eda_router=_WorkspaceReadingRouter(worktree_root),
    ).verify_task(changed_paths=[], target_file="target.sv")

    assert result.final_pass is True
    assert result.verification_cwd == str(worktree_root.resolve())
    assert result.build_log == "worktree\n"


def test_python_syntax_only_is_not_semantic_qualification(tmp_path):
    target = tmp_path / "target.py"
    target.write_text("value = 1\n", encoding="utf-8")

    result = IndependentVerifier(tmp_path).verify_task(
        changed_paths=[],
        target_file="target.py",
    )

    assert result.build_status == "pass"
    assert result.test_status == "unsupported"
    assert result.final_pass is False
    assert result.qualification_admissible is False


def test_python_verifier_runs_declared_failing_semantic_test(tmp_path):
    target = tmp_path / "target.py"
    target.write_text("value = 1\n", encoding="utf-8")
    test_file = tmp_path / "test_target.py"
    test_file.write_text("assert False, 'semantic failure'\n", encoding="utf-8")

    result = IndependentVerifier(tmp_path).verify_task(
        changed_paths=[],
        target_file="target.py",
        verification={
            "build": {"argv": ["python", "-m", "py_compile", "{target_file}"]},
            "test": {"argv": ["pytest", "-q", "test_target.py"]},
            "timeout_sec": 30,
        },
    )

    assert result.build_status == "pass"
    assert result.test_status == "fail"
    assert result.final_pass is False
    assert result.test_exit_code != 0


def test_python_verifier_does_not_execute_shell_metacharacters(tmp_path):
    marker = tmp_path / "shell-marker.txt"
    malicious_target = f"valid.py; echo injected > {marker.name}.py"

    result = IndependentVerifier(tmp_path).verify_task(
        changed_paths=[],
        target_file=malicious_target,
    )

    assert result.final_pass is False
    assert not marker.exists()
    assert not (tmp_path / f"{marker.name}.py").exists()


def test_verilator_backend_is_lint_only_and_not_admissible(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.eda.router.VerilatorAdapter.is_available", lambda self: True)
    monkeypatch.setattr("scripts.eda.router.VerilatorAdapter.get_version", lambda self: "Verilator test")

    metadata = EDARouter(
        preferred_backend="verilator",
        workspace_root=tmp_path,
        mode="live",
    ).get_backend_metadata()

    assert metadata["backend"] == "verilator"
    assert metadata["verification_level"] == "lint_only"
    assert metadata["qualification_admissible"] is False


def test_verilator_result_records_lint_command_and_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.eda.router.VerilatorAdapter.is_available", lambda self: True)
    monkeypatch.setattr("scripts.eda.router.VerilatorAdapter.get_version", lambda self: "Verilator test")

    def fake_run(command, **kwargs):
        assert command[:3] == ["verilator", "--lint-only", "-Wall"]
        assert kwargs["cwd"] == str(Path(tmp_path).resolve())

        class Result:
            returncode = 0
            stdout = "lint ok"

        return Result()

    monkeypatch.setattr("scripts.eda.verilator_adapter.subprocess.run", fake_run)
    result = EDARouter(
        preferred_backend="verilator",
        workspace_root=tmp_path,
        mode="live",
    ).compile(["fixture.sv"])

    assert result["status"] == "pass"
    assert "--lint-only" in result["command"]
    assert result["cwd"] == str(Path(tmp_path).resolve())
    assert result["tool_path"] == ""
    assert result["verification_level"] == "lint_only"
    assert result["qualification_admissible"] is False


def test_verifier_rejects_target_outside_disposable_worktree(tmp_path):
    outside_target = tmp_path.parent / "outside.py"
    outside_target.write_text("print('outside')\n", encoding="utf-8")

    result = IndependentVerifier(tmp_path).verify_task(
        changed_paths=[],
        target_file=str(outside_target),
    )

    assert result.final_pass is False
    assert "escapes disposable worktree" in result.build_log
    assert result.qualification_admissible is False


def test_adapters_reject_targets_and_outputs_outside_workspace(tmp_path):
    outside_target = tmp_path.parent / "outside.sv"
    outside_target.write_text("module outside; endmodule\n", encoding="utf-8")

    iverilog = IcarusVerilogAdapter(tmp_path)
    try:
        iverilog.compile([str(outside_target)])
    except ValueError as exc:
        assert "escapes workspace" in str(exc)
    else:
        raise AssertionError("Icarus must reject a target outside the worktree")

    try:
        SynopsysVCSAdapter(tmp_path, simv_rel_path="../outside/simv")
    except ValueError as exc:
        assert "escapes workspace" in str(exc)
    else:
        raise AssertionError("VCS must reject an output path outside the worktree")


def test_live_stub_router_is_not_admissible(tmp_path):
    router = EDARouter(preferred_backend="stub", workspace_root=tmp_path, mode="live")

    compile_result = router.compile(["missing.sv"])
    simulate_result = router.simulate("missing_test")

    assert compile_result["qualification_admissible"] is False
    assert simulate_result["qualification_admissible"] is False


def test_live_iverilog_is_execution_capable_but_not_qualification_admissible(
    tmp_path, monkeypatch
):
    monkeypatch.setattr("scripts.eda.router.IcarusVerilogAdapter.is_available", lambda self: True)
    monkeypatch.setattr("scripts.eda.router.IcarusVerilogAdapter.get_version", lambda self: "Icarus test")

    metadata = EDARouter(
        preferred_backend="iverilog",
        workspace_root=tmp_path,
        mode="live",
    ).get_backend_metadata()

    assert metadata["backend"] == "iverilog"
    assert metadata["verification_level"] == "compile_and_simulate"
    assert metadata["qualification_admissible"] is False