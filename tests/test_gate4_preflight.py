from pathlib import Path

import yaml

from scripts.gate4_preflight import build_preflight_report


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
                "baseline_context_length": 131072,
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