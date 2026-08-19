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
                "kv_cache_type": "F16",
                "profiles": {"mtp_n2": {"spec_draft_n_max": 2}},
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