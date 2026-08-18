"""Vertical-slice TDD: 1 task × 1 repetition × 2 arms.

Production entrypoint: gv100h.coding_eval.single_pair_runner.run_single_ab_pair
This is not the dirty scripts/run_live_eval.py harness and is not a 10×3×2 universe.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from gv100h.manifests.validator import ManifestValidator
from gv100h.runner.verifier import IndependentVerifier


REPO_ROOT = Path(__file__).resolve().parents[2]
CASE_PATH = REPO_ROOT / "benchmarks" / "cases" / "UVM-001.yaml"
TARGET_REL = Path("uvm") / "tests" / "usb3_warm_reset_test.sv"
ARMS = ("arm_a_prompt_only", "arm_b_governed_sidecar")
BUNDLE_FILES = ("manifest.json", "diff.patch", "build.log", "simulation.log")


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
        assert manifest.evidence.build_command != "git status"
        assert "git status" not in (manifest.evidence.build_command or "")
        validator.validate_manifest_dict(manifest.model_dump())
        validator.validate_manifest_bundle(manifest, bundle)

        written = (bundle / "diff.patch").read_bytes()
        assert hashlib.sha256(written).hexdigest() == manifest.evidence.git_diff_sha256

    validator.validate_manifest_set(manifests, require_complete_pairs=True)


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
