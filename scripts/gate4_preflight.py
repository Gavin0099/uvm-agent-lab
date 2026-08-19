#!/usr/bin/env python3
"""Pre-GV100 software and host preflight; never grants qualification admission."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from gv100h.runtime.ssot import GV100H_BASELINE


def build_preflight_report(
    *,
    repo_root: Path,
    config_path: Optional[Path] = None,
    model_path: Optional[Path] = None,
) -> Dict[str, Any]:
    root = Path(repo_root).resolve()
    config_file = (config_path or root / "deploy" / "llama_cpp_gv100.yaml").resolve()
    config_present = config_file.is_file()
    config_data: Dict[str, Any] = {}
    config_error = None
    if config_present:
        try:
            config_data = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            config_error = str(exc)

    config_matches_ssot = (
        config_present
        and config_error is None
        and config_data.get("model_id") == GV100H_BASELINE.model_id
        and config_data.get("model_artifact") == GV100H_BASELINE.model_artifact
        and config_data.get("runtime") == GV100H_BASELINE.runtime_type
        and config_data.get("quantization") == GV100H_BASELINE.quantization
        and config_data.get("parallel") == GV100H_BASELINE.parallel
        and config_data.get("kv_cache_type") == GV100H_BASELINE.kv_cache_type
        and config_data.get("profiles", {}).get("mtp_n2", {}).get("spec_draft_n_max")
        == GV100H_BASELINE.spec_draft_n_max
    )

    commands = {
        "docker": bool(shutil.which("docker")),
        "llama_server": bool(shutil.which("llama-server")),
        "nvidia_smi": bool(shutil.which("nvidia-smi")),
    }
    artifact_path = Path(model_path).resolve() if model_path else None
    model_artifact_present = bool(artifact_path and artifact_path.is_file())
    software_preflight_passed = config_matches_ssot and commands["docker"]
    hardware_observed = commands["nvidia_smi"]
    bringup_ready = (
        software_preflight_passed
        and commands["llama_server"]
        and model_artifact_present
        and hardware_observed
    )

    blockers = []
    if not config_present:
        blockers.append("llama.cpp baseline config is missing")
    elif config_error:
        blockers.append(f"baseline config is invalid: {config_error}")
    elif not config_matches_ssot:
        blockers.append("baseline config does not match runtime SSOT")
    if not commands["docker"]:
        blockers.append("docker command is unavailable")
    if not commands["llama_server"]:
        blockers.append("llama-server command is unavailable")
    if not model_artifact_present:
        blockers.append("Qwen3.8-27B GGUF model artifact was not supplied")
    if not hardware_observed:
        blockers.append("nvidia-smi is unavailable; hardware is not observed")

    return {
        "baseline": {
            "candidate_name": GV100H_BASELINE.candidate_name,
            "model_id": GV100H_BASELINE.model_id,
            "model_artifact": GV100H_BASELINE.model_artifact,
            "runtime": GV100H_BASELINE.runtime_type,
            "quantization": GV100H_BASELINE.quantization,
            "mtp_enabled": GV100H_BASELINE.mtp_enabled,
            "spec_draft_n_max": GV100H_BASELINE.spec_draft_n_max,
            "context_sweep": list(GV100H_BASELINE.context_sweep),
        },
        "config_path": str(config_file),
        "config_present": config_present,
        "config_matches_ssot": config_matches_ssot,
        "config_error": config_error,
        "commands": commands,
        "model_artifact_path": str(artifact_path) if artifact_path else None,
        "model_artifact_present": model_artifact_present,
        "software_preflight_passed": software_preflight_passed,
        "hardware_observed": hardware_observed,
        "bringup_ready": bringup_ready,
        "qualification_admissible": False,
        "claim_ceiling": "pre-hardware-readiness-only",
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check pre-GV100 llama.cpp readiness")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--config", default=None)
    parser.add_argument("--model-path", default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    report = build_preflight_report(
        repo_root=Path(args.repo_root),
        config_path=Path(args.config) if args.config else None,
        model_path=Path(args.model_path) if args.model_path else None,
    )
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    print(rendered)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["software_preflight_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
