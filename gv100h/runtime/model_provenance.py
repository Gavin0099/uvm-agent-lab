from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field


DEFAULT_APPROVAL_REGISTRY_RELATIVE_PATH = Path(
    "governance/gate4_approved_models.json"
)


class ModelArtifactManifest(BaseModel):
    """Approved model provenance required before Gate 4 bring-up."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1", pattern=r"^1$")
    model_id: str = Field(min_length=1)
    model_source: str = Field(min_length=1)
    model_revision: str = Field(min_length=1)
    model_artifact: str = Field(min_length=1)
    model_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    provenance_class: Literal["operator_attested"]
    independent_verification: Literal[False]

    def validate_ssot(self, *, model_id: str, model_artifact: str) -> None:
        if self.model_id != model_id:
            raise ValueError(
                f"model manifest model_id {self.model_id!r} does not match SSOT {model_id!r}"
            )
        if self.model_artifact != model_artifact:
            raise ValueError(
                "model manifest model_artifact "
                f"{self.model_artifact!r} does not match SSOT {model_artifact!r}"
            )
        if Path(self.model_artifact).name != self.model_artifact:
            raise ValueError("model manifest model_artifact must be a file name, not a path")

    def verify_artifact(self, path: str | Path) -> str:
        artifact_path = Path(path).resolve()
        if not artifact_path.is_file():
            raise ValueError(f"model artifact does not exist: {artifact_path}")
        if artifact_path.name != self.model_artifact:
            raise ValueError(
                f"model artifact file name {artifact_path.name!r} does not match "
                f"approved artifact {self.model_artifact!r}"
            )
        digest = hashlib.sha256()
        with artifact_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        actual_hash = digest.hexdigest()
        if actual_hash.lower() != self.model_sha256.lower():
            raise ValueError(
                "model artifact SHA-256 does not match approved manifest: "
                f"expected {self.model_sha256}, got {actual_hash}"
            )
        return actual_hash


class ApprovedModelRecord(BaseModel):
    """One externally approved model identity from the tracked registry."""

    model_config = ConfigDict(extra="forbid")

    model_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    artifact: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")


class ApprovedModelRegistry(BaseModel):
    """Versioned approval trust anchor reviewed as repository content."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"]
    approvals: Dict[str, ApprovedModelRecord] = Field(default_factory=dict)


def _run_git(*arguments: str, cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError("approval registry git identity could not be verified") from exc
    return result.stdout.strip()


def _approval_registry_identity(
    path: str | Path,
    *,
    repo_root: Optional[str | Path] = None,
) -> Dict[str, str]:
    registry_file = Path(path)
    if not registry_file.is_absolute() and repo_root is not None:
        registry_file = Path(repo_root) / registry_file
    registry_file = registry_file.resolve()
    if not registry_file.is_file():
        raise ValueError(f"approval registry does not exist: {registry_file}")

    git_root = Path(
        _run_git("rev-parse", "--show-toplevel", cwd=registry_file.parent)
    ).resolve()
    if repo_root is not None and git_root != Path(repo_root).resolve():
        raise ValueError("approval registry is outside the requested repository")
    try:
        relative_path = registry_file.relative_to(git_root).as_posix()
    except ValueError as exc:
        raise ValueError("approval registry is outside its git repository") from exc
    expected_path = DEFAULT_APPROVAL_REGISTRY_RELATIVE_PATH.as_posix()
    if relative_path != expected_path:
        raise ValueError(
            f"approval registry must be {expected_path}, got {relative_path}"
        )

    try:
        _run_git("ls-files", "--error-unmatch", "--", relative_path, cwd=git_root)
    except ValueError as exc:
        raise ValueError("approval registry must be tracked and committed") from exc
    if _run_git("status", "--porcelain", "--", relative_path, cwd=git_root):
        raise ValueError("approval registry must be clean and committed")

    return {
        "path": str(registry_file),
        "relative_path": relative_path,
        "sha256": sha256_file(registry_file),
        "commit": _run_git("rev-parse", "HEAD", cwd=git_root),
    }


def load_approved_model_registry(
    path: str | Path,
    *,
    repo_root: Optional[str | Path] = None,
) -> Tuple[ApprovedModelRegistry, Dict[str, str]]:
    registry_file = Path(path)
    if not registry_file.is_absolute() and repo_root is not None:
        registry_file = Path(repo_root) / registry_file
    registry_file = registry_file.resolve()
    try:
        raw: Dict[str, Any] = json.loads(registry_file.read_text(encoding="utf-8"))
        registry = ApprovedModelRegistry.model_validate(raw)
    except Exception as exc:
        raise ValueError(f"invalid Gate 4 approval registry: {exc}") from exc
    return registry, _approval_registry_identity(registry_file, repo_root=repo_root)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    file_path = Path(path).resolve()
    if not file_path.is_file():
        raise ValueError(f"file does not exist: {file_path}")
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ModelVerificationReceipt(BaseModel):
    """Independent verification receipt bound to manifest and artifact bytes."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1", pattern=r"^1$")
    verification_status: Literal["verified"]
    independent_verification: Literal[True]
    approval_id: str = Field(min_length=1)
    approval_registry_path: str = Field(min_length=1)
    approval_registry_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    approval_registry_commit: str = Field(pattern=r"^[0-9a-fA-F]{40,64}$")
    verifier_id: str = Field(min_length=1)
    verified_at: str = Field(min_length=1)
    verification_basis: str = Field(min_length=1)
    manifest_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    artifact_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    approved_artifact_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    model_source: str = Field(min_length=1)
    model_revision: str = Field(min_length=1)


def verify_model_verification_receipt(
    manifest_path: str | Path,
    artifact_path: str | Path,
    receipt_path: str | Path,
    *,
    expected_model_id: str,
    expected_model_artifact: str,
    approval_registry_path: str | Path,
    repo_root: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Verify a receipt against SSOT, artifact bytes, and the committed registry."""

    manifest_file = Path(manifest_path).resolve()
    artifact_file = Path(artifact_path).resolve()
    receipt_file = Path(receipt_path).resolve()
    manifest = load_model_manifest(manifest_file)
    manifest.validate_ssot(
        model_id=expected_model_id,
        model_artifact=expected_model_artifact,
    )
    receipt = load_model_verification_receipt(receipt_file)
    registry, registry_identity = load_approved_model_registry(
        approval_registry_path,
        repo_root=repo_root,
    )
    if receipt.approval_registry_path != registry_identity["relative_path"]:
        raise ValueError("model verification receipt registry path does not match")
    if receipt.approval_registry_sha256.lower() != registry_identity["sha256"].lower():
        raise ValueError("model verification receipt registry hash does not match registry bytes")
    if receipt.approval_registry_commit != registry_identity["commit"]:
        raise ValueError("model verification receipt registry commit does not match HEAD")
    approval = registry.approvals.get(receipt.approval_id)
    if approval is None:
        raise ValueError("model verification receipt approval_id is not in the registry")
    if approval.model_id != manifest.model_id:
        raise ValueError("approval registry model_id does not match manifest")
    if approval.source != manifest.model_source:
        raise ValueError("approval registry source does not match manifest")
    if approval.revision != manifest.model_revision:
        raise ValueError("approval registry revision does not match manifest")
    if approval.artifact != manifest.model_artifact:
        raise ValueError("approval registry artifact does not match manifest")
    manifest_hash = sha256_file(manifest_file)
    artifact_hash = manifest.verify_artifact(artifact_file)
    if receipt.manifest_sha256.lower() != manifest_hash.lower():
        raise ValueError("model verification receipt manifest hash does not match manifest bytes")
    if receipt.artifact_sha256.lower() != artifact_hash.lower():
        raise ValueError("model verification receipt artifact hash does not match artifact bytes")
    if receipt.approved_artifact_sha256.lower() != artifact_hash.lower():
        raise ValueError("model verification receipt approved hash does not match artifact bytes")
    if approval.sha256.lower() != artifact_hash.lower():
        raise ValueError("artifact bytes do not match committed approval registry")
    if receipt.approved_artifact_sha256.lower() != approval.sha256.lower():
        raise ValueError("model verification receipt approved hash does not match registry")
    if receipt.model_source != approval.source:
        raise ValueError("model verification receipt source does not match registry")
    if receipt.model_revision != approval.revision:
        raise ValueError("model verification receipt revision does not match registry")
    return receipt.model_dump()


def load_model_manifest(path: str | Path) -> ModelArtifactManifest:
    manifest_path = Path(path).resolve()
    try:
        raw: Dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
        return ModelArtifactManifest.model_validate(raw)
    except Exception as exc:
        raise ValueError(f"invalid model provenance manifest: {exc}") from exc


def load_model_verification_receipt(path: str | Path) -> ModelVerificationReceipt:
    receipt_path = Path(path).resolve()
    try:
        raw: Dict[str, Any] = json.loads(receipt_path.read_text(encoding="utf-8"))
        return ModelVerificationReceipt.model_validate(raw)
    except Exception as exc:
        raise ValueError(f"invalid model verification receipt: {exc}") from exc
