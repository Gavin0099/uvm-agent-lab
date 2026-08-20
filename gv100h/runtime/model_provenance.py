from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Literal

from pydantic import BaseModel, ConfigDict, Field


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
) -> Dict[str, Any]:
    """Verify a receipt against current manifest/artifact bytes and SSOT."""

    manifest_file = Path(manifest_path).resolve()
    artifact_file = Path(artifact_path).resolve()
    receipt_file = Path(receipt_path).resolve()
    manifest = load_model_manifest(manifest_file)
    manifest.validate_ssot(
        model_id=expected_model_id,
        model_artifact=expected_model_artifact,
    )
    receipt = load_model_verification_receipt(receipt_file)
    manifest_hash = sha256_file(manifest_file)
    artifact_hash = manifest.verify_artifact(artifact_file)
    if receipt.manifest_sha256.lower() != manifest_hash.lower():
        raise ValueError("model verification receipt manifest hash does not match manifest bytes")
    if receipt.artifact_sha256.lower() != artifact_hash.lower():
        raise ValueError("model verification receipt artifact hash does not match artifact bytes")
    if receipt.approved_artifact_sha256.lower() != artifact_hash.lower():
        raise ValueError("model verification receipt approved hash does not match artifact bytes")
    if receipt.model_source != manifest.model_source:
        raise ValueError("model verification receipt source does not match manifest")
    if receipt.model_revision != manifest.model_revision:
        raise ValueError("model verification receipt revision does not match manifest")
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
