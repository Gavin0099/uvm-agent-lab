"""Vertical-slice TDD: 1 task × 1 repetition × 2 arms.

Production entrypoint: gv100h.coding_eval.single_pair_runner.run_single_ab_pair
This is not the dirty scripts/run_live_eval.py harness and is not a 10×3×2 universe.
"""

from __future__ import annotations

import hashlib
import json
import base64
import subprocess
import sys
from pathlib import Path

import pytest

from gv100h.manifests.validator import ManifestValidationError, ManifestValidator
from agent.governance.guardrails import ScopeGuardrail
from gv100h.runner.verifier import IndependentVerifier
from gv100h.runner.worktree_runner import GitWorktreeRunner
from gv100h.utils.evidence_commit import compute_reconstructed_head_commit
from gv100h.runtime.attestation import sha256_file


REPO_ROOT = Path(__file__).resolve().parents[2]
CASE_PATH = REPO_ROOT / "benchmarks" / "cases" / "UVM-001.yaml"
TARGET_REL = Path("uvm") / "tests" / "usb3_warm_reset_test.sv"
ARMS = ("arm_a_prompt_only", "arm_b_governed_sidecar")
BUNDLE_FILES = (
    "manifest.json",
    "diff.patch",
    "build.log",
    "simulation.log",
    "workspace_tree.json",
    "file_snapshots.json",
    "tool_trace.json",
    "verification.json",
)


def _run_slice(tmp_path: Path, **overrides):
    from gv100h.coding_eval.single_pair_runner import run_single_ab_pair

    kwargs = {
        "task_id": "UVM-001",
        "case_path": CASE_PATH,
        "repetition": 1,
        "mode": "mock",
        "output_dir": tmp_path / "slice_out",
        "repo_root": REPO_ROOT,
        "model_id": "Qwen/Qwen3.8-35B-A3B",
    }
    kwargs.update(overrides)
    return run_single_ab_pair(**kwargs)


def _live_manifest_fixture(result):
    manifest = result["manifests"][0]
    bundle = Path(result["bundle_dirs"][manifest.experiment_arm])
    endpoint_url = "http://127.0.0.1:8000/v1"
    executable = Path(sys.executable).resolve()
    attestation = {
        "schema_version": "1",
        "runtime": "llama.cpp",
        "runtime_commit": "b" * 40,
        "runtime_version": "llama.cpp test",
        "runtime_executable_path": str(executable),
        "runtime_executable_sha256": sha256_file(executable),
        "server_pid": 12345,
        "launch_argv": [str(executable), "--fake-server"],
        "model_id": manifest.model_id,
        "model_path": "fixture/model.gguf",
        "model_sha256": "a" * 64,
        "endpoint_url": endpoint_url,
        "models_endpoint_response": {"data": [{"id": manifest.model_id}]},
        "response_model": manifest.model_id,
        "started_at": "2026-08-20T00:00:00Z",
        "observed_at": "2026-08-20T00:00:01Z",
    }
    attestation_bytes = json.dumps(
        attestation,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    ).encode("utf-8")
    (bundle / "runtime_attestation.json").write_bytes(attestation_bytes)
    live_manifest = manifest.model_copy(update={
        "runtime": "llama.cpp",
        "model_hash": "a" * 64,
        "runtime_commit": "b" * 40,
        "evidence": manifest.evidence.model_copy(update={
            "runtime_attestation_sha256": hashlib.sha256(attestation_bytes).hexdigest(),
            "endpoint_url": endpoint_url,
        }),
    })
    return live_manifest, bundle


def test_single_ab_pair_import_path_is_not_dirty_harness():
    source = Path("gv100h/coding_eval/single_pair_runner.py")
    assert source.exists(), "production entrypoint missing: gv100h/coding_eval/single_pair_runner.py"
    text = source.read_text(encoding="utf-8")
    assert "run_single_ab_pair" in text
    assert "run_live_evaluation" not in text
    cli = Path("scripts/run_single_ab_pair.py")
    assert cli.exists(), "thin CLI missing: scripts/run_single_ab_pair.py"
    assert "run_live_eval" not in cli.read_text(encoding="utf-8")


def test_mock_slice_produces_paired_physical_bundles(tmp_path: Path):
    target_in_repo = REPO_ROOT / TARGET_REL
    before = target_in_repo.read_bytes() if target_in_repo.exists() else None

    result = _run_slice(tmp_path)

    after = target_in_repo.read_bytes() if target_in_repo.exists() else None
    assert before == after, "agent wrote into process CWD / primary repo, not the worktree"

    assert result["task_id"] == "UVM-001"
    assert result["repetition"] == 1
    assert result["universe_complete_claim_allowed"] is False
    assert result["admissible_for_model_qualification"] is False
    assert result["evidence_class"] != "live_inference"
    assert result.get("qualification_decision") == "NO_GO"

    pair_id = result["pair_id"]
    assert isinstance(pair_id, str) and pair_id.startswith("pair-")

    manifests = result["manifests"]
    assert len(manifests) == 2
    assert {m.experiment_arm for m in manifests} == set(ARMS)
    assert {m.pair_id for m in manifests} == {pair_id}
    assert {m.task_id for m in manifests} == {"UVM-001"}
    assert {m.benchmark_task_id for m in manifests} == {"UVM-001"}
    assert {m.repetition for m in manifests} == {1}
    assert {m.base_commit for m in manifests} == {manifests[0].base_commit}
    assert {m.model_id for m in manifests} == {manifests[0].model_id}
    assert {
        m.interception_mode
        for m in manifests
        if m.experiment_arm == "arm_a_prompt_only"
    } == {"POST_HOC"}
    assert {
        m.interception_mode
        for m in manifests
        if m.experiment_arm == "arm_b_governed_sidecar"
    } == {"ENFORCED"}

    validator = ManifestValidator()
    bundle_dirs = result["bundle_dirs"]
    assert set(bundle_dirs) == set(ARMS)
    seen_dirs = set()
    for arm in ARMS:
        bundle = Path(bundle_dirs[arm])
        assert bundle.is_dir()
        assert bundle not in seen_dirs
        seen_dirs.add(bundle)
        assert f"UVM-001" in bundle.as_posix()
        assert pair_id in bundle.as_posix()
        assert arm in bundle.as_posix()
        for name in BUNDLE_FILES:
            assert (bundle / name).is_file(), f"missing {name} in {bundle}"

        manifest = next(m for m in manifests if m.experiment_arm == arm)
        assert manifest.evidence.evidence_schema_version == "2"
        assert manifest.head_commit is not None
        assert len(manifest.head_commit) == 40
        assert manifest.evidence.build_command != "git status"
        assert "git status" not in (manifest.evidence.build_command or "")
        validator.validate_manifest_dict(manifest.model_dump())
        validator.validate_manifest_bundle(
            manifest,
            bundle,
            require_integrity=True,
            repo_root=REPO_ROOT,
        )
        written = (bundle / "diff.patch").read_bytes()
        assert written
        assert str(TARGET_REL).replace("\\", "/").encode("utf-8") in written
        assert hashlib.sha256(written).hexdigest() == manifest.evidence.git_diff_sha256
        assert manifest.evidence.workspace_tree_sha256 == hashlib.sha256(
            (bundle / "workspace_tree.json").read_bytes()
        ).hexdigest()
        snapshots = json.loads((bundle / "file_snapshots.json").read_text(encoding="utf-8"))
        target_snapshot = next(
            item for item in snapshots["files"]
            if item["path"] == str(TARGET_REL).replace("\\", "/")
        )
        assert target_snapshot["sha256"] == manifest.evidence.target_file_sha256

    validator.validate_manifest_set(manifests, require_complete_pairs=True)


def test_live_pair_requires_runtime_model_and_build_provenance(tmp_path: Path):
    from gv100h.coding_eval.single_pair_runner import run_single_ab_pair

    with pytest.raises(ValueError, match="explicit provenance"):
        run_single_ab_pair(
            task_id="UVM-001",
            case_path=CASE_PATH,
            repetition=1,
            mode="live",
            output_dir=tmp_path / "live",
            repo_root=REPO_ROOT,
        )


def test_live_pair_rejects_model_hash_mismatch(tmp_path: Path):
    from gv100h.coding_eval.single_pair_runner import run_single_ab_pair

    artifact = tmp_path / "model.gguf"
    artifact.write_bytes(b"model-bytes")

    with pytest.raises(ValueError, match="model_hash does not match"):
        run_single_ab_pair(
            task_id="UVM-001",
            case_path=CASE_PATH,
            repetition=1,
            mode="live",
            output_dir=tmp_path / "live",
            repo_root=REPO_ROOT,
            runtime="llama.cpp",
            quantization="Q4_K_M",
            model_hash="0" * 64,
            model_artifact_path=artifact,
            runtime_commit="b" * 40,
        )


def test_live_pair_requires_runtime_version_for_harness_launcher(tmp_path: Path):
    from gv100h.coding_eval.single_pair_runner import run_single_ab_pair

    artifact = tmp_path / "model.gguf"
    artifact.write_bytes(b"model-bytes")

    with pytest.raises(ValueError, match="runtime_version"):
        run_single_ab_pair(
            task_id="UVM-001",
            case_path=CASE_PATH,
            repetition=1,
            mode="live",
            output_dir=tmp_path / "live",
            repo_root=REPO_ROOT,
            runtime="llama.cpp",
            quantization="Q4_K_M",
            model_hash=hashlib.sha256(b"model-bytes").hexdigest(),
            model_artifact_path=artifact,
            runtime_commit="b" * 40,
            runtime_command=[sys.executable],
        )


def test_live_pair_rejects_external_seed_without_harness_launcher(tmp_path: Path):
    artifact = tmp_path / "model.gguf"
    artifact.write_bytes(b"model-bytes")
    model_hash = hashlib.sha256(b"model-bytes").hexdigest()
    with pytest.raises(ValueError, match="process/endpoint ownership"):
        from gv100h.coding_eval.single_pair_runner import run_single_ab_pair

        run_single_ab_pair(
            task_id="UVM-001",
            case_path=CASE_PATH,
            repetition=1,
            mode="live",
            output_dir=tmp_path / "live",
            repo_root=REPO_ROOT,
            model_id="Qwen/Qwen3.8-35B-A3B",
            runtime="llama.cpp",
            quantization="Q4_K_M",
            model_hash=model_hash,
            model_artifact_path=artifact,
            runtime_commit="b" * 40,
        )


def test_live_pair_stops_runtime_when_arm_fails(tmp_path: Path, monkeypatch):
    from gv100h.coding_eval import single_pair_runner as pair_runner

    artifact = tmp_path / "model.gguf"
    artifact.write_bytes(b"model-bytes")
    model_hash = hashlib.sha256(b"model-bytes").hexdigest()
    instances = []

    class _FakeAttestor:
        def __init__(self, *args, **kwargs):
            self.stopped = False
            instances.append(self)

        def start(self):
            return {"seed": "launched"}

        def stop(self):
            self.stopped = True

    def fail_run_one_arm(**kwargs):
        raise RuntimeError("arm failed")

    monkeypatch.setattr(pair_runner, "RuntimeProcessAttestor", _FakeAttestor)
    monkeypatch.setattr(pair_runner, "_run_one_arm", fail_run_one_arm)

    with pytest.raises(RuntimeError, match="arm failed"):
        pair_runner.run_single_ab_pair(
            task_id="UVM-001",
            case_path=CASE_PATH,
            repetition=1,
            mode="live",
            output_dir=tmp_path / "live",
            repo_root=REPO_ROOT,
            model_id="Qwen/Qwen3.8-35B-A3B",
            runtime="llama.cpp",
            quantization="Q4_K_M",
            model_hash=model_hash,
            model_artifact_path=artifact,
            runtime_commit="b" * 40,
            runtime_command=[sys.executable],
            runtime_version="llama.cpp test",
        )

    assert len(instances) == 1
    assert instances[0].stopped is True


def test_pair_validator_rejects_duplicate_pair_arm(tmp_path: Path):
    result = _run_slice(tmp_path)
    manifests = list(result["manifests"])
    duplicate = manifests[0].model_copy(update={"run_id": "duplicate-arm-run"})

    with pytest.raises(ManifestValidationError, match="Duplicate manifest"):
        ManifestValidator().validate_manifest_set(
            manifests + [duplicate], require_complete_pairs=True
        )


def test_pair_validator_rejects_tampered_pair_id(tmp_path: Path):
    result = _run_slice(tmp_path)
    manifests = [
        manifest.model_copy(update={"pair_id": "pair-tampered"})
        for manifest in result["manifests"]
    ]

    with pytest.raises(ManifestValidationError, match="Pair ID does not match"):
        ManifestValidator().validate_manifest_set(
            manifests, require_complete_pairs=True
        )


def test_independent_replay_rejects_self_consistent_forged_verification(tmp_path: Path):
    result = _run_slice(tmp_path)
    manifest = result["manifests"][0]
    bundle = Path(result["bundle_dirs"][manifest.experiment_arm])
    verification_path = bundle / "verification.json"
    forged = json.loads(verification_path.read_text(encoding="utf-8"))
    forged["final_pass"] = False
    forged_bytes = json.dumps(
        forged, ensure_ascii=True, indent=2, sort_keys=True
    ).encode("utf-8")
    verification_path.write_bytes(forged_bytes)
    forged_manifest = manifest.model_copy(update={
        "evidence": manifest.evidence.model_copy(update={
            "verification_sha256": hashlib.sha256(forged_bytes).hexdigest(),
        })
    })

    with pytest.raises(ManifestValidationError, match="Independent replay mismatch"):
        ManifestValidator().validate_manifest_bundle(
            forged_manifest,
            bundle,
            require_integrity=True,
            repo_root=REPO_ROOT,
            replay_verification=True,
        )
def test_pinned_case_hash_mismatch_is_rejected():
    base_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    with pytest.raises(ManifestValidationError, match="Pinned benchmark case hash mismatch"):
        ManifestValidator._load_pinned_case(
            REPO_ROOT,
            base_commit,
            "UVM-001",
            "0" * 64,
        )


def test_independent_replay_rejects_forged_logs_with_refreshed_hashes(tmp_path: Path):
    result = _run_slice(tmp_path)
    manifest = result["manifests"][0]
    bundle = Path(result["bundle_dirs"][manifest.experiment_arm])
    verification_path = bundle / "verification.json"
    build_path = bundle / "build.log"
    forged_build = b"forged build pass\n"
    build_path.write_bytes(forged_build)
    forged_verification = json.loads(verification_path.read_text(encoding="utf-8"))
    forged_verification["build_log_sha256"] = hashlib.sha256(forged_build).hexdigest()
    forged_verification_bytes = json.dumps(
        forged_verification, ensure_ascii=True, indent=2, sort_keys=True
    ).encode("utf-8")
    verification_path.write_bytes(forged_verification_bytes)
    forged_manifest = manifest.model_copy(update={
        "evidence": manifest.evidence.model_copy(update={
            "build_log_sha256": hashlib.sha256(forged_build).hexdigest(),
            "verification_sha256": hashlib.sha256(forged_verification_bytes).hexdigest(),
        })
    })

    with pytest.raises(ManifestValidationError, match="Independent replay mismatch"):
        ManifestValidator().validate_manifest_bundle(
            forged_manifest,
            bundle,
            require_integrity=True,
            repo_root=REPO_ROOT,
            replay_verification=True,
        )


def test_independent_replay_does_not_treat_scope_outcome_as_verifier_failure(tmp_path: Path):
    result = _run_slice(tmp_path)
    manifest = result["manifests"][0].model_copy(update={
        "outcome": result["manifests"][0].outcome.model_copy(
            update={"status": "scope_violation", "failure_class": "SCOPE_VIOLATION"}
        )
    })
    bundle = Path(result["bundle_dirs"][manifest.experiment_arm])

    assert ManifestValidator().validate_manifest_bundle(
        manifest,
        bundle,
        require_integrity=True,
        repo_root=REPO_ROOT,
        replay_verification=False,
    ) is True


def test_live_bundle_requires_runtime_attestation_file(tmp_path: Path):
    result = _run_slice(tmp_path)
    manifest = result["manifests"][0].model_copy(update={
        "runtime": "llama.cpp",
        "model_hash": "a" * 64,
        "runtime_commit": "b" * 40,
    })
    bundle = Path(result["bundle_dirs"][manifest.experiment_arm])

    with pytest.raises(ManifestValidationError, match="runtime_attestation"):
        ManifestValidator().validate_manifest_bundle(
            manifest,
            bundle,
            require_integrity=True,
            repo_root=REPO_ROOT,
            replay_verification=True,
        )


def test_live_bundle_validates_runtime_attestation_identity(tmp_path: Path):
    result = _run_slice(tmp_path)
    manifest, bundle = _live_manifest_fixture(result)
    validator = ManifestValidator()

    validator.validate_manifest_dict(manifest.model_dump())
    assert validator.validate_manifest_bundle(
        manifest,
        bundle,
        require_integrity=True,
        repo_root=REPO_ROOT,
        replay_verification=False,
    ) is True


@pytest.mark.parametrize("mutation", ["endpoint", "runtime_commit", "model_id"])
def test_live_bundle_rejects_runtime_attestation_identity_mismatch(
    tmp_path: Path,
    mutation: str,
):
    result = _run_slice(tmp_path)
    manifest, bundle = _live_manifest_fixture(result)
    if mutation == "endpoint":
        mutated = manifest.model_copy(update={
            "evidence": manifest.evidence.model_copy(
                update={"endpoint_url": "http://127.0.0.1:9000/v1"}
            )
        })
    elif mutation == "runtime_commit":
        mutated = manifest.model_copy(update={"runtime_commit": "c" * 40})
    else:
        mutated = manifest.model_copy(update={"model_id": "different-model"})

    with pytest.raises(ManifestValidationError, match="Runtime attestation identity"):
        ManifestValidator().validate_manifest_bundle(
            mutated,
            bundle,
            require_integrity=True,
            repo_root=REPO_ROOT,
            replay_verification=True,
        )


def test_live_bundle_rejects_attestation_models_response_mismatch(tmp_path: Path):
    result = _run_slice(tmp_path)
    manifest, bundle = _live_manifest_fixture(result)
    attestation_path = bundle / "runtime_attestation.json"
    attestation = json.loads(attestation_path.read_text(encoding="utf-8"))
    attestation["models_endpoint_response"] = {
        "data": [{"id": "different-model"}]
    }
    attestation_bytes = json.dumps(
        attestation,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    ).encode("utf-8")
    attestation_path.write_bytes(attestation_bytes)
    mutated = manifest.model_copy(update={
        "evidence": manifest.evidence.model_copy(update={
            "runtime_attestation_sha256": hashlib.sha256(attestation_bytes).hexdigest(),
        })
    })

    with pytest.raises(ManifestValidationError, match="Runtime attestation identity"):
        ManifestValidator().validate_manifest_bundle(
            mutated,
            bundle,
            require_integrity=True,
            repo_root=REPO_ROOT,
            replay_verification=False,
        )

def test_legacy_bundle_is_rejected_at_strict_integrity_boundary(tmp_path: Path):
    bundle = tmp_path / "legacy"
    bundle.mkdir()
    diff = b"diff --git a/legacy.sv b/legacy.sv\n+legacy\n"
    (bundle / "diff.patch").write_bytes(diff)
    manifest = {
        "run_id": "legacy-run",
        "task_id": "UVM-001",
        "experiment_arm": "arm_a_prompt_only",
        "target_repo": "test",
        "base_commit": "a" * 40,
        "model_id": "model",
        "runtime": "mock_replay",
        "framework_commit": "b" * 40,
        "contract_id": "contract",
        "hardware": {"gpu_count": 0, "gpu_model": "mock"},
        "evidence": {"git_diff_sha256": hashlib.sha256(diff).hexdigest()},
        "outcome": {"status": "fail", "false_success": False},
    }
    parsed = ManifestValidator().validate_manifest_dict(manifest)
    with pytest.raises(ManifestValidationError, match="evidence_schema_version"):
        ManifestValidator().validate_manifest_bundle(parsed, bundle, require_integrity=True)


def test_semantic_forgery_is_rejected_after_patch_hash_update(tmp_path: Path):
    result = _run_slice(tmp_path)
    manifest = result["manifests"][0]
    bundle = Path(result["bundle_dirs"][manifest.experiment_arm])
    patch_file = bundle / "diff.patch"
    original_patch = patch_file.read_bytes()
    forged_patch = original_patch.replace(
        b"Verified UVM generation",
        b"Forged UVM generation",
        1,
    )
    assert forged_patch != original_patch
    patch_file.write_bytes(forged_patch)
    forged_manifest = manifest.model_copy(update={
        "evidence": manifest.evidence.model_copy(update={
            "git_diff_sha256": hashlib.sha256(forged_patch).hexdigest(),
        })
    })

    with pytest.raises(
        ManifestValidationError,
        match="Patch reconstruction (does not match file snapshot|target hash does not match|head_commit does not match)",
    ):
        ManifestValidator().validate_manifest_bundle(
            forged_manifest,
            bundle,
            require_integrity=True,
            repo_root=REPO_ROOT,
        )


def test_reconstructed_head_commit_mismatch_is_rejected(tmp_path: Path):
    result = _run_slice(tmp_path)
    manifest = result["manifests"][0]
    bundle = Path(result["bundle_dirs"][manifest.experiment_arm])
    forged_manifest = manifest.model_copy(update={"head_commit": "0" * 40})

    with pytest.raises(
        ManifestValidationError,
        match="head_commit",
    ):
        ManifestValidator().validate_manifest_bundle(
            forged_manifest,
            bundle,
            require_integrity=True,
            repo_root=REPO_ROOT,
        )


def test_reconstructed_paths_are_rechecked_against_guardrail(tmp_path: Path):
    result = _run_slice(tmp_path)
    manifest = result["manifests"][0]
    bundle = Path(result["bundle_dirs"][manifest.experiment_arm])
    deny_target = ScopeGuardrail(
        allowed_paths=["rtl/"],
        forbidden_paths=["uvm/tests/"],
        base_dir=str(REPO_ROOT),
    )

    with pytest.raises(ManifestValidationError, match="benchmark guardrail"):
        ManifestValidator().validate_manifest_bundle(
            manifest,
            bundle,
            require_integrity=True,
            repo_root=REPO_ROOT,
            guardrail=deny_target,
        )


def test_hidden_forbidden_path_is_rejected_after_hash_and_head_update(tmp_path: Path):
    result = _run_slice(tmp_path)
    manifest = result["manifests"][0]
    bundle = Path(result["bundle_dirs"][manifest.experiment_arm])
    hidden_path = "rtl/hidden.sv"
    hidden_content = b"module hidden; endmodule\n"
    hidden_patch = (
        b"diff --git a/rtl/hidden.sv b/rtl/hidden.sv\n"
        b"new file mode 100644\n"
        b"index 0000000..0000000\n"
        b"--- /dev/null\n"
        b"+++ b/rtl/hidden.sv\n"
        b"@@ -0,0 +1 @@\n"
        b"+module hidden; endmodule\n"
    )
    patch_file = bundle / "diff.patch"
    forged_patch = patch_file.read_bytes() + hidden_patch
    patch_file.write_bytes(forged_patch)

    worktree_mgr = GitWorktreeRunner(str(REPO_ROOT))
    worktree, _base = worktree_mgr.create_worktree(manifest.base_commit)
    try:
        subprocess.run(
            ["git", "apply"],
            cwd=str(worktree),
            input=forged_patch,
            capture_output=True,
            check=True,
        )
        forged_head = compute_reconstructed_head_commit(worktree, manifest.base_commit)
    finally:
        worktree_mgr.cleanup_worktree(worktree)

    forged_manifest = manifest.model_copy(update={
        "head_commit": forged_head,
        "evidence": manifest.evidence.model_copy(update={
            "git_diff_sha256": hashlib.sha256(forged_patch).hexdigest(),
        }),
    })
    with pytest.raises(ManifestValidationError, match="changed-path set"):
        ManifestValidator().validate_manifest_bundle(
            forged_manifest,
            bundle,
            require_integrity=True,
            repo_root=REPO_ROOT,
        )


def test_case_specific_forbidden_path_is_rejected_even_when_declared(tmp_path: Path):
    result = _run_slice(tmp_path)
    manifest = result["manifests"][0]
    bundle = Path(result["bundle_dirs"][manifest.experiment_arm])
    hidden_path = "uvm/env/hidden.sv"
    hidden_content = b"module hidden; endmodule\n"
    hidden_patch = (
        b"diff --git a/uvm/env/hidden.sv b/uvm/env/hidden.sv\n"
        b"new file mode 100644\n"
        b"index 0000000..0000000\n"
        b"--- /dev/null\n"
        b"+++ b/uvm/env/hidden.sv\n"
        b"@@ -0,0 +1 @@\n"
        b"+module hidden; endmodule\n"
    )
    patch_file = bundle / "diff.patch"
    forged_patch = patch_file.read_bytes() + hidden_patch
    patch_file.write_bytes(forged_patch)

    snapshots_file = bundle / "file_snapshots.json"
    snapshots = json.loads(snapshots_file.read_text(encoding="utf-8"))
    snapshots["files"].append({
        "content_b64": base64.b64encode(hidden_content).decode("ascii"),
        "kind": "file",
        "path": hidden_path,
        "sha256": hashlib.sha256(hidden_content).hexdigest(),
        "size": len(hidden_content),
    })
    snapshots["files"] = sorted(snapshots["files"], key=lambda item: item["path"])
    snapshots_file.write_text(
        json.dumps(snapshots, ensure_ascii=True, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )

    tree_file = bundle / "workspace_tree.json"
    tree = json.loads(tree_file.read_text(encoding="utf-8"))
    tree["files"].append({
        "kind": "file",
        "path": hidden_path,
        "sha256": hashlib.sha256(hidden_content).hexdigest(),
        "size": len(hidden_content),
    })
    tree["files"] = sorted(tree["files"], key=lambda item: item["path"])
    tree_file.write_text(
        json.dumps(tree, ensure_ascii=True, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )

    worktree_mgr = GitWorktreeRunner(str(REPO_ROOT))
    worktree, _base = worktree_mgr.create_worktree(manifest.base_commit)
    try:
        subprocess.run(
            ["git", "apply"],
            cwd=str(worktree),
            input=forged_patch,
            capture_output=True,
            check=True,
        )
        forged_head = compute_reconstructed_head_commit(worktree, manifest.base_commit)
    finally:
        worktree_mgr.cleanup_worktree(worktree)

    changed_paths = sorted([*manifest.evidence.changed_paths, hidden_path])
    forged_manifest = manifest.model_copy(update={
        "head_commit": forged_head,
        "evidence": manifest.evidence.model_copy(update={
            "git_diff_sha256": hashlib.sha256(forged_patch).hexdigest(),
            "changed_paths": changed_paths,
            "workspace_tree_sha256": hashlib.sha256(tree_file.read_bytes()).hexdigest(),
            "file_snapshots_sha256": hashlib.sha256(snapshots_file.read_bytes()).hexdigest(),
        }),
    })
    with pytest.raises(ManifestValidationError, match="benchmark guardrail"):
        ManifestValidator().validate_manifest_bundle(
            forged_manifest,
            bundle,
            require_integrity=True,
            repo_root=REPO_ROOT,
        )


def test_slice_evidence_binding_rejects_empty_and_tampered_artifacts(tmp_path: Path):
    result = _run_slice(tmp_path)
    manifest = result["manifests"][0]
    bundle = Path(result["bundle_dirs"][manifest.experiment_arm])
    validator = ManifestValidator()

    diff_file = bundle / "diff.patch"
    original_diff = diff_file.read_bytes()
    diff_file.write_bytes(b"")
    with pytest.raises(ManifestValidationError, match="non-empty"):
        validator.validate_manifest_bundle(manifest, bundle)
    diff_file.write_bytes(original_diff)

    trace_file = bundle / "tool_trace.json"
    original_trace = trace_file.read_bytes()
    trace_file.write_bytes(original_trace + b" tampered")
    with pytest.raises(ManifestValidationError, match="tool_trace.json hash mismatch"):
        validator.validate_manifest_bundle(manifest, bundle)
    trace_file.write_bytes(original_trace)

    verification_file = bundle / "verification.json"
    original_verification = verification_file.read_bytes()
    verification_file.unlink()
    with pytest.raises(ManifestValidationError, match=r"verification\.json.*missing"):
        validator.validate_manifest_bundle(manifest, bundle)
    verification_file.write_bytes(original_verification)

    snapshots_file = bundle / "file_snapshots.json"
    original_snapshots = snapshots_file.read_bytes()
    snapshots_file.write_bytes(original_snapshots.replace(b"content_b64", b"tampered_b64", 1))
    with pytest.raises(ManifestValidationError, match="file_snapshots.json hash mismatch"):
        validator.validate_manifest_bundle(manifest, bundle)
    snapshots_file.write_bytes(original_snapshots)


def test_slice_feeds_ab_aggregator_without_claiming_go(tmp_path: Path):
    result = _run_slice(tmp_path)
    from gv100h.coding_eval.governance_ab_runner import GovernanceABRunner

    summary = GovernanceABRunner().run_ab_benchmark(
        runs_per_task=3,
        manifest_dir=str(result["output_dir"]),
    )
    assert summary.admissible_for_model_qualification is False
    assert summary.is_synthetic_simulation is True
    assert summary.evidence_class != "live_inference"


def test_single_pair_require_live_rejects_incomplete_universe(tmp_path: Path):
    result = _run_slice(tmp_path)
    from gv100h.coding_eval.governance_ab_runner import (
        GovernanceABRunner,
        GovernanceAdmissionError,
    )

    with pytest.raises(GovernanceAdmissionError, match="non-admissible"):
        GovernanceABRunner().run_ab_benchmark(
            runs_per_task=3,
            manifest_dir=str(result["output_dir"]),
            require_live=True,
        )


def test_live_eda_fail_closed_is_not_stub_pass(tmp_path: Path):
    sv = tmp_path / "uvm" / "tests" / "usb3_warm_reset_test.sv"
    sv.parent.mkdir(parents=True, exist_ok=True)
    sv.write_text("module usb3_warm_reset_test; endmodule\n", encoding="utf-8")

    res = IndependentVerifier(workspace_root=tmp_path, mode="live").verify_task(
        changed_paths=["uvm/tests/usb3_warm_reset_test.sv"],
        target_file="uvm/tests/usb3_warm_reset_test.sv",
    )
    if res.eda_backend == "stub" or res.qualification_admissible is False:
        assert res.final_pass is False
        assert res.qualification_admissible is False
        assert "FAIL-CLOSED" in res.build_log or res.build_status in {"fail", "unsupported"}
    else:
        pytest.skip("real EDA toolchain present; live stub-rejection path not exercised")
