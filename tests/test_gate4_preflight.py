from pathlib import Path
import hashlib
import json
import subprocess
import pytest

import yaml

from scripts.gate4_preflight import build_preflight_report
from scripts.create_gate4_model_manifest import build_manifest
from scripts.verify_gate4_model_manifest import build_receipt
from gv100h.runtime.model_provenance import verify_model_verification_receipt
from gv100h.runtime.launch_profiles import LaunchProfileError, resolve_launch_command


def _matching_config() -> dict:
    return {
        "model_id": "Qwen3.8-27B",
        "model_artifact": "Qwen3.8-27B-Q4_K_M.gguf",
        "runtime": "llama.cpp",
        "quantization": "Q4_K_M",
        "parallel": 1,
        "kv_cache_type": "Q8_0",
        "cache_type_k": "q8_0",
        "cache_type_v": "q8_0",
        "baseline_context_length": 32768,
        "max_model_len": 262144,
        "profiles": {
            "mtp_off": {
                "spec_type": "none",
                "spec_draft_n_max": 0,
                "launch_args": [
                    "--spec-type",
                    "{spec_type}",
                    "--spec-draft-n-max",
                    "{spec_draft_n_max}",
                ],
            },
            "mtp_n2": {
                "spec_type": "draft-mtp",
                "spec_draft_n_max": 2,
                "launch_args": [
                    "--spec-type",
                    "{spec_type}",
                    "--spec-draft-n-max",
                    "{spec_draft_n_max}",
                ],
            },
        },
        "launch_template": ["llama-server", "-m", "{model_artifact}", "-c", "{context_length}"],
    }


def _create_trusted_registry(
    repo_root: Path,
    *,
    artifact_hash: str,
    source: str,
    revision: str,
) -> tuple[Path, str]:
    approval_id = "test-qwen38-27b-q4km-v1"
    registry_path = repo_root / "governance" / "gate4_approved_models.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "approvals": {
                    approval_id: {
                        "model_id": "Qwen3.8-27B",
                        "source": source,
                        "revision": revision,
                        "artifact": "Qwen3.8-27B-Q4_K_M.gguf",
                        "sha256": artifact_hash,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    for command in (
        ["git", "init"],
        ["git", "config", "user.email", "gate4-test@example.invalid"],
        ["git", "config", "user.name", "Gate 4 Test"],
        ["git", "add", "governance/gate4_approved_models.json"],
        ["git", "commit", "-m", "test: add approved model registry"],
    ):
        subprocess.run(
            command,
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    return registry_path, approval_id


def test_preflight_report_matches_mtp_ssot_without_claiming_hardware(tmp_path: Path, monkeypatch):
    config = tmp_path / "llama.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "model_id": "Qwen3.8-27B",
                "model_artifact": "Qwen3.8-27B-Q4_K_M.gguf",
                "runtime": "llama.cpp",
                "quantization": "Q4_K_M",
                "parallel": 1,
                "kv_cache_type": "Q8_0",
                "cache_type_k": "q8_0",
                "cache_type_v": "q8_0",
                    "baseline_context_length": 32768,
                "max_model_len": 262144,
                    "profiles": {
                        "mtp_off": {"spec_draft_n_max": 0},
                        "mtp_n2": {"spec_draft_n_max": 2},
                    },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("shutil.which", lambda name: "tool" if name == "docker" else None)

    report = build_preflight_report(repo_root=tmp_path, config_path=config)

    assert report["config_matches_ssot"] is True
    assert report["software_preflight_passed"] is True
    assert report["hardware_observed"] is False
    assert report["bringup_ready"] is False
    assert report["qualification_admissible"] is False
    assert report["build_provenance"]["llama_server_version"] is None
    assert report["claim_ceiling"] == "pre-hardware-readiness-only"


def test_preflight_rejects_config_drift(tmp_path: Path, monkeypatch):
    config = tmp_path / "llama.yaml"
    config.write_text(
        "model_id: wrong\nmodel_artifact: wrong.gguf\nruntime: llama.cpp\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("shutil.which", lambda name: "tool")

    report = build_preflight_report(repo_root=tmp_path, config_path=config)

    assert report["config_matches_ssot"] is False
    assert report["software_preflight_passed"] is False
    assert report["qualification_admissible"] is False
    assert "baseline config does not match runtime SSOT" in report["blockers"]


def test_preflight_rejects_unproven_q4_kv_selection(tmp_path: Path, monkeypatch):
    config = tmp_path / "q4-llama.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "model_id": "Qwen3.8-27B",
                "model_artifact": "Qwen3.8-27B-Q4_K_M.gguf",
                "runtime": "llama.cpp",
                "quantization": "Q4_K_M",
                "parallel": 1,
                "kv_cache_type": "Q4_0",
                "cache_type_k": "q4_0",
                "cache_type_v": "q4_0",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("shutil.which", lambda name: "tool" if name == "docker" else None)

    report = build_preflight_report(repo_root=tmp_path, config_path=config)

    assert report["config_matches_ssot"] is False
    assert report["selected_kv_cache"]["experimental"] is True
    assert report["selected_kv_cache"]["build_provenance"] is False
    assert report["selected_kv_cache"]["prefill_validation"] is False
    assert "experimental q4/q5 KV profile requires patched llama.cpp build provenance" in report["blockers"]
    assert "experimental q4/q5 KV profile requires a passing local prefill benchmark" in report["blockers"]


def test_preflight_accepts_approved_model_manifest_and_matching_artifact(
    tmp_path: Path, monkeypatch
):
    config = tmp_path / "llama.yaml"
    config.write_text(yaml.safe_dump(_matching_config()), encoding="utf-8")
    artifact = tmp_path / "Qwen3.8-27B-Q4_K_M.gguf"
    artifact.write_bytes(b"approved-model-bytes")
    artifact_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest = tmp_path / "model-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "model_id": "Qwen3.8-27B",
                "model_source": "https://models.example.invalid/qwen38",
                "model_revision": "revision-20260820",
                "model_artifact": "Qwen3.8-27B-Q4_K_M.gguf",
                "model_sha256": artifact_hash,
                "provenance_class": "operator_attested",
                "independent_verification": False,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("shutil.which", lambda _name: "tool")

    report = build_preflight_report(
        repo_root=tmp_path,
        config_path=config,
        model_path=artifact,
        model_manifest_path=manifest,
    )

    assert report["model_provenance"]["ready"] is True
    assert report["model_provenance"]["artifact_hash_matches"] is True
    assert report["model_provenance"]["provenance_class"] == "operator_attested"
    assert report["model_provenance"]["independent_verification"] is False
    assert report["model_provenance"]["claim_ceiling"] == "operator_attested_model_bytes"
    assert report["bringup_ready"] is True
    assert report["qualification_admissible"] is False


def test_preflight_rejects_artifact_with_unapproved_hash(tmp_path: Path, monkeypatch):
    config = tmp_path / "llama.yaml"
    config.write_text(yaml.safe_dump(_matching_config()), encoding="utf-8")
    artifact = tmp_path / "Qwen3.8-27B-Q4_K_M.gguf"
    artifact.write_bytes(b"unapproved-model-bytes")
    manifest = tmp_path / "model-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "model_id": "Qwen3.8-27B",
                "model_source": "https://models.example.invalid/qwen38",
                "model_revision": "revision-20260820",
                "model_artifact": "Qwen3.8-27B-Q4_K_M.gguf",
                "model_sha256": "0" * 64,
                "provenance_class": "operator_attested",
                "independent_verification": False,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("shutil.which", lambda _name: "tool")

    report = build_preflight_report(
        repo_root=tmp_path,
        config_path=config,
        model_path=artifact,
        model_manifest_path=manifest,
    )

    assert report["model_artifact_present"] is True
    assert report["model_provenance"]["ready"] is False
    assert report["bringup_ready"] is False
    assert any("SHA-256" in blocker for blocker in report["blockers"])


def test_independent_model_verification_receipt_binds_manifest_and_artifact(
    tmp_path: Path,
):
    artifact = tmp_path / "Qwen3.8-27B-Q4_K_M.gguf"
    artifact.write_bytes(b"approved-model-bytes")
    artifact_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
    registry_path, approval_id = _create_trusted_registry(
        tmp_path,
        artifact_hash=artifact_hash,
        source="https://models.example.invalid/qwen38",
        revision="revision-20260820",
    )
    manifest_path = tmp_path / "model-manifest.json"
    receipt_path = tmp_path / "verification-receipt.json"
    build_manifest(
        artifact,
        model_source="https://models.example.invalid/qwen38",
        model_revision="revision-20260820",
        output_path=manifest_path,
    )
    build_receipt(
        manifest_path,
        artifact,
        approval_id=approval_id,
        approval_registry_path=registry_path,
        verifier_id="release-checksum-verifier",
        verification_basis="vendor-release-checksum",
        output_path=receipt_path,
        repo_root=tmp_path,
    )

    receipt = verify_model_verification_receipt(
        manifest_path,
        artifact,
        receipt_path,
        expected_model_id="Qwen3.8-27B",
        expected_model_artifact="Qwen3.8-27B-Q4_K_M.gguf",
        approval_registry_path=registry_path,
        repo_root=tmp_path,
    )

    assert receipt["independent_verification"] is True
    assert receipt["approved_artifact_sha256"] == artifact_hash


def test_preflight_reports_independent_model_receipt(tmp_path: Path, monkeypatch):
    config = tmp_path / "llama.yaml"
    config.write_text(yaml.safe_dump(_matching_config()), encoding="utf-8")
    artifact = tmp_path / "Qwen3.8-27B-Q4_K_M.gguf"
    artifact.write_bytes(b"approved-model-bytes")
    artifact_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
    registry_path, approval_id = _create_trusted_registry(
        tmp_path,
        artifact_hash=artifact_hash,
        source="https://models.example.invalid/qwen38",
        revision="revision-20260820",
    )
    manifest_path = tmp_path / "model-manifest.json"
    receipt_path = tmp_path / "verification-receipt.json"
    build_manifest(
        artifact,
        model_source="https://models.example.invalid/qwen38",
        model_revision="revision-20260820",
        output_path=manifest_path,
    )
    build_receipt(
        manifest_path,
        artifact,
        approval_id=approval_id,
        approval_registry_path=registry_path,
        verifier_id="release-checksum-verifier",
        verification_basis="vendor-release-checksum",
        output_path=receipt_path,
        repo_root=tmp_path,
    )
    monkeypatch.setattr("shutil.which", lambda _name: "tool")

    report = build_preflight_report(
        repo_root=tmp_path,
        config_path=config,
        model_path=artifact,
        model_manifest_path=manifest_path,
        model_verification_receipt_path=receipt_path,
        model_approval_registry_path=registry_path,
    )

    assert report["model_provenance"]["independent_verification"] is True
    assert report["model_provenance"]["approval_id"] == approval_id
    assert len(report["model_provenance"]["approval_registry_sha256"]) == 64
    assert len(report["model_provenance"]["approval_registry_blob_oid"]) == 40
    assert report["model_provenance"]["approval_registry_last_change_commit"]
    assert report["qualification_blockers"] == []


def test_preflight_exit_code_can_require_full_bringup():
    from scripts.gate4_preflight import preflight_exit_code

    report = {
        "software_preflight_passed": True,
        "bringup_ready": False,
    }

    assert preflight_exit_code(report, require_bringup=False) == 0
    assert preflight_exit_code(report, require_bringup=True) == 1


def test_launch_profile_renders_control_command_and_hash(tmp_path: Path):
    config = tmp_path / "llama.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "cache_type_k": "q8_0",
                "cache_type_v": "q8_0",
                "launch_template": [
                    "llama-server",
                    "-m",
                    "{model_artifact}",
                    "-c",
                    "{context_length}",
                ],
                "profiles": {
                    "mtp_off": {"spec_draft_n_max": 0, "launch_args": []},
                    "mtp_n2": {
                        "spec_type": "draft-mtp",
                        "spec_draft_n_max": 2,
                        "launch_args": [
                            "--spec-type",
                            "{spec_type}",
                            "--spec-draft-n-max",
                            "{spec_draft_n_max}",
                        ],
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    resolved = resolve_launch_command(
        config,
        profile_id="mtp_n2",
        model_artifact="Qwen3.8-27B-Q4_K_M.gguf",
        context_length=32768,
    )

    assert resolved["resolved_launch_argv"][-4:] == [
        "--spec-type",
        "draft-mtp",
        "--spec-draft-n-max",
        "2",
    ]
    assert len(resolved["launch_argv_sha256"]) == 64


def test_launch_profile_rejects_mtp_without_explicit_args(tmp_path: Path):
    config = tmp_path / "llama.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "launch_template": ["llama-server", "-m", "{model_artifact}"],
                "profiles": {
                    "mtp_n2": {"spec_type": "draft-mtp", "spec_draft_n_max": 2}
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(LaunchProfileError, match="launch_args"):
        resolve_launch_command(
            config,
            profile_id="mtp_n2",
            model_artifact="Qwen3.8-27B-Q4_K_M.gguf",
            context_length=32768,
        )