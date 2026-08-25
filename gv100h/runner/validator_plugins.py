"""Validator plugin boundary for v1 lightweight checks and Phase 2 EDA checks."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Union

from gv100h.runner.verifier import FinalVerificationResult, IndependentVerifier


class ValidatorPlugin(Protocol):
    profile: str

    def verify_task(
        self,
        changed_paths: List[str],
        target_file: Optional[str] = None,
        verification: Optional[Dict[str, Any]] = None,
    ) -> FinalVerificationResult:
        ...


class LightweightValidator:
    """v1 validator for source syntax and test evidence without EDA tools."""

    profile = "lightweight"

    def __init__(self, workspace_root: Union[str, Path], mode: str = "mock"):
        self._verifier = IndependentVerifier(
            Path(workspace_root), mode=mode, validator_profile=self.profile
        )

    def verify_task(
        self,
        changed_paths: List[str],
        target_file: Optional[str] = None,
        verification: Optional[Dict[str, Any]] = None,
    ) -> FinalVerificationResult:
        if not target_file or not target_file.endswith(".py"):
            raise ValueError(
                "lightweight validator requires a Python target; use the eda "
                "profile for SystemVerilog/UVM targets"
            )
        result = self._verifier.verify_task(
            changed_paths=changed_paths,
            target_file=target_file,
            verification=verification,
        )
        return result.model_copy(update={"validator_profile": self.profile})


class EDAValidator:
    """Phase 2 validator for EDA compile/simulation/UVM evidence."""

    profile = "eda"

    def __init__(self, workspace_root: Union[str, Path], mode: str = "mock"):
        self._verifier = IndependentVerifier(
            Path(workspace_root), mode=mode, validator_profile=self.profile
        )

    def verify_task(
        self,
        changed_paths: List[str],
        target_file: Optional[str] = None,
        verification: Optional[Dict[str, Any]] = None,
    ) -> FinalVerificationResult:
        result = self._verifier.verify_task(
            changed_paths=changed_paths,
            target_file=target_file,
            verification=verification,
        )
        return result.model_copy(update={"validator_profile": self.profile})


def create_validator(
    profile: str,
    workspace_root: Union[str, Path],
    mode: str = "mock",
) -> ValidatorPlugin:
    if profile == "lightweight":
        return LightweightValidator(workspace_root, mode=mode)
    if profile == "eda":
        return EDAValidator(workspace_root, mode=mode)
    raise ValueError(f"unknown validator profile: {profile}")