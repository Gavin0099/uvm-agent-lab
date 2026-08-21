#!/usr/bin/env python3
"""Verify a Gate 4 model manifest against a committed approval registry."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gv100h.runtime.model_provenance import (
    ModelVerificationReceipt,
    load_approved_model_registry,
    load_model_manifest,
    sha256_file,
)
from gv100h.runtime.ssot import GV100H_BASELINE


def build_receipt(
    manifest_path: str | Path,
    artifact_path: str | Path,
    *,
    approval_id: str,
    approval_registry_path: str | Path,
    verifier_id: str,
    verification_basis: str,
    output_path: str | Path,
    repo_root: str | Path | None = None,
) -> ModelVerificationReceipt:
    manifest_file = Path(manifest_path).resolve()
    artifact_file = Path(artifact_path).resolve()
    manifest = load_model_manifest(manifest_file)
    manifest.validate_ssot(
        model_id=GV100H_BASELINE.model_id,
        model_artifact=GV100H_BASELINE.model_artifact,
    )
    registry, registry_identity = load_approved_model_registry(
        approval_registry_path,
        repo_root=repo_root,
    )
    approval = registry.approvals.get(approval_id)
    if approval is None:
        raise ValueError(f"approval_id {approval_id!r} is not in the approval registry")
    if manifest.model_id != approval.model_id:
        raise ValueError("model manifest model_id does not match approval registry")
    if manifest.model_source != approval.source:
        raise ValueError("model manifest source does not match approval registry")
    if manifest.model_revision != approval.revision:
        raise ValueError("model manifest revision does not match approval registry")
    if manifest.model_artifact != approval.artifact:
        raise ValueError("model manifest artifact does not match approval registry")
    artifact_sha256 = manifest.verify_artifact(artifact_file)
    if artifact_sha256.lower() != approval.sha256.lower():
        raise ValueError("artifact bytes do not match committed approval registry")
    receipt = ModelVerificationReceipt(
        verification_status="verified",
        independent_verification=True,
        approval_id=approval_id,
        approval_registry_path=registry_identity["relative_path"],
        approval_registry_sha256=registry_identity["sha256"],
        approval_registry_commit=registry_identity["commit"],
        verifier_id=verifier_id,
        verified_at=datetime.now(timezone.utc).isoformat(),
        verification_basis=verification_basis,
        manifest_sha256=sha256_file(manifest_file),
        artifact_sha256=artifact_sha256,
        approved_artifact_sha256=approval.sha256,
        model_source=approval.source,
        model_revision=approval.revision,
    )
    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(receipt.model_dump(), indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a Gate 4 model manifest")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--approval-id", required=True)
    parser.add_argument(
        "--approval-registry",
        default="governance/gate4_approved_models.json",
    )
    parser.add_argument("--verifier-id", required=True)
    parser.add_argument("--verification-basis", required=True)
    parser.add_argument("--output", default="deploy/gate4_model_verification_receipt.json")
    args = parser.parse_args()
    receipt = build_receipt(
        args.manifest,
        args.artifact,
        approval_id=args.approval_id,
        approval_registry_path=args.approval_registry,
        verifier_id=args.verifier_id,
        verification_basis=args.verification_basis,
        output_path=args.output,
        repo_root=args.repo_root,
    )
    print(json.dumps(receipt.model_dump(), indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
