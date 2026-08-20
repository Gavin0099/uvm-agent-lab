from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

import yaml


class LaunchProfileError(ValueError):
    """Raised when a Gate 4 runtime profile cannot be rendered safely."""


def _render_argument(argument: Any, values: Dict[str, Any]) -> str:
    if not isinstance(argument, str) or not argument:
        raise LaunchProfileError("launch arguments must be non-empty strings")
    try:
        return argument.format(**values)
    except KeyError as exc:
        raise LaunchProfileError(
            f"launch argument references unknown placeholder: {exc.args[0]}"
        ) from exc


def resolve_launch_command(
    config_path: str | Path,
    *,
    profile_id: str,
    model_artifact: str | Path,
    context_length: int,
) -> Dict[str, Any]:
    """Render one explicit profile command and hash the resolved argv."""

    path = Path(config_path).resolve()
    try:
        config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        template = config["launch_template"]
        profile = config["profiles"][profile_id]
    except (OSError, KeyError, yaml.YAMLError) as exc:
        raise LaunchProfileError(f"invalid launch profile config: {exc}") from exc
    if not isinstance(template, list) or not template:
        raise LaunchProfileError("launch_template must be a non-empty list")
    if not isinstance(profile, dict):
        raise LaunchProfileError(f"profile {profile_id!r} must be a mapping")

    spec_draft_n_max = profile.get("spec_draft_n_max")
    if not isinstance(spec_draft_n_max, int) or spec_draft_n_max < 0:
        raise LaunchProfileError(
            f"profile {profile_id!r} must declare non-negative spec_draft_n_max"
        )
    profile_args = profile.get("launch_args")
    if not isinstance(profile_args, list) or not profile_args:
        raise LaunchProfileError(
            f"profile {profile_id!r} must declare explicit launch_args before bring-up"
        )
    if profile_args is None:
        profile_args = []
    if profile.get("spec_type") is None and any(
        "{spec_type}" in str(argument) for argument in profile_args
    ):
        raise LaunchProfileError(
            f"profile {profile_id!r} uses {{spec_type}} but does not declare spec_type"
        )

    values = {
        "model_artifact": str(model_artifact),
        "context_length": context_length,
        "cache_type_k": profile.get("cache_type_k", config.get("cache_type_k")),
        "cache_type_v": profile.get("cache_type_v", config.get("cache_type_v")),
        "spec_type": profile.get("spec_type"),
        "spec_draft_n_max": spec_draft_n_max,
    }
    resolved = [_render_argument(argument, values) for argument in template]
    resolved.extend(_render_argument(argument, values) for argument in profile_args)
    if resolved[0] != "llama-server":
        raise LaunchProfileError("launch_template must start with llama-server")

    encoded = json.dumps(
        resolved,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "profile_id": profile_id,
        "context_length": context_length,
        "spec_type": profile.get("spec_type"),
        "spec_draft_n_max": spec_draft_n_max,
        "resolved_launch_argv": resolved,
        "launch_argv_sha256": hashlib.sha256(encoded).hexdigest(),
    }
