#!/usr/bin/env python3
"""Pre-GV100 software and host preflight; never grants qualification admission."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from gv100h.runtime.ssot import GV100H_BASELINE

EXPERIMENTAL_KV_CACHE_TYPES = frozenset({"q4_0", "q4_1", "q5_0", "q5_1"})


def _normalize_cache_type(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def _selected_cache_types(config_data: Dict[str, Any]) -> tuple[str, str]:
    selected_k = _normalize_cache_type(config_data.get("cache_type_k"))
    selected_v = _normalize_cache_type(config_data.get("cache_type_v"))
    fallback = _normalize_cache_type(config_data.get("kv_cache_type"))
    return selected_k or fallback, selected_v or fallback


def _collect_llama_server_version() -> Optional[str]:
    command = shutil.which("llama-server")
    if not command:
        return None
    for flag in ("--version", "-v"):
        try:
            result = subprocess.run(
                [command, flag], capture_output=True, text=True, timeout=10
            )
        except (OSError, subprocess.SubprocessError):
            continue
        output = (result.stdout or result.stderr).strip()
        if result.returncode == 0 and output:
            return output.splitlines()[0]
    return None


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
        and config_data.get("cache_type_k") == GV100H_BASELINE.kv_cache_type_k
        and config_data.get("cache_type_v") == GV100H_BASELINE.kv_cache_type_v
        and config_data.get("baseline_context_length") == GV100H_BASELINE.baseline_context_length
        and config_data.get("max_model_len") == GV100H_BASELINE.max_model_len
        and config_data.get("profiles", {}).get("mtp_off", {}).get("spec_draft_n_max")
        == GV100H_BASELINE.spec_draft_n_max
        and config_data.get("profiles", {}).get("mtp_n2", {}).get("spec_draft_n_max")
        == 2
    )

    selected_cache_k, selected_cache_v = _selected_cache_types(config_data)
    experimental_kv_selected = (
        selected_cache_k in EXPERIMENTAL_KV_CACHE_TYPES
        or selected_cache_v in EXPERIMENTAL_KV_CACHE_TYPES
    )
    experimental_profile = config_data.get("profiles", {}).get("q4_kv_experimental", {})
    experimental_build_provenance = (
        None
        if not experimental_kv_selected
        else (
            experimental_profile.get("requires_patched_build") is True
            and experimental_profile.get("default_enabled") is False
            and experimental_profile.get("requires_llama_cpp_fix") == GV100H_BASELINE.kv_cache_fix_pr_url
            and experimental_profile.get("issue_reference") == GV100H_BASELINE.kv_cache_issue_url
            and bool(config_data.get("llama_cpp_commit"))
            and bool(config_data.get("llama_server_version"))
            and config_data.get("kv_cache_fix_reference") == GV100H_BASELINE.kv_cache_fix_pr_url
            and config_data.get("kv_cache_fix_verified") is True
        )
    )
    experimental_prefill_validation = (
        None
        if not experimental_kv_selected
        else config_data.get("prefill_benchmark_passed") is True
    )

    commands = {
        "docker": bool(shutil.which("docker")),
        "llama_server": bool(shutil.which("llama-server")),
        "nvidia_smi": bool(shutil.which("nvidia-smi")),
    }
    llama_server_version = _collect_llama_server_version()
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
    if experimental_kv_selected and experimental_build_provenance is not True:
        blockers.append("experimental q4/q5 KV profile requires patched llama.cpp build provenance")
    if experimental_kv_selected and experimental_prefill_validation is not True:
        blockers.append("experimental q4/q5 KV profile requires a passing local prefill benchmark")
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
            "kv_cache_type_k": GV100H_BASELINE.kv_cache_type_k,
            "kv_cache_type_v": GV100H_BASELINE.kv_cache_type_v,
            "baseline_context_length": GV100H_BASELINE.baseline_context_length,
            "context_sweep": list(GV100H_BASELINE.context_sweep),
        },
        "config_path": str(config_file),
        "config_present": config_present,
        "config_matches_ssot": config_matches_ssot,
        "config_error": config_error,
        "selected_kv_cache": {
            "type_k": selected_cache_k,
            "type_v": selected_cache_v,
            "experimental": experimental_kv_selected,
            "build_provenance": experimental_build_provenance,
            "prefill_validation": experimental_prefill_validation,
        },
        "commands": commands,
        "build_provenance": {
            "llama_cpp_commit": config_data.get("llama_cpp_commit"),
            "llama_server_version": config_data.get("llama_server_version") or llama_server_version,
            "issue_reference": GV100H_BASELINE.kv_cache_issue_url,
            "fix_reference": config_data.get("kv_cache_fix_reference"),
            "fix_verified": config_data.get("kv_cache_fix_verified") is True,
        },
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
