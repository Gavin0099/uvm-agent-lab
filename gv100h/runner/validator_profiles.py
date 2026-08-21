"""Validator profile routing for the v1 harness and Phase 2 EDA plugin.

The profile is intentionally separate from the validator implementation. This
keeps existing EDA adapters reusable while allowing v1 cases to use only
lightweight checks.
"""

from typing import Any, Literal, Mapping

ValidatorProfile = Literal["lightweight", "eda"]


def resolve_validator_profile(case_data: Mapping[str, Any]) -> ValidatorProfile:
    """Resolve explicit validator intent with backward-compatible legacy rules."""

    explicit = case_data.get("validator_profile")
    if explicit in {"lightweight", "eda"}:
        return explicit

    acceptance = case_data.get("acceptance") or {}
    if any(
        acceptance.get(key) in {"pass", "optional"}
        for key in ("compile", "simulation")
    ):
        return "eda"
    if "task_id" in case_data and "id" not in case_data:
        return "eda"
    return "lightweight"


def validator_requires_eda(profile: ValidatorProfile) -> bool:
    """Return whether a case may require the Phase 2 EDA plugin."""

    return profile == "eda"
