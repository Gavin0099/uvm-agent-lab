#!/usr/bin/env python3
"""Verify a Gate 4 model manifest against an independent approved checksum."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from gv100h.runtime.model_provenance import (
    ModelVerificationReceipt,
    load_model_manifest,
    sha256_file,
)
from gv100h.runtime.ssot import GV100H_BASELINE


def build_receipt(
    manifest_path: str | Path,
    artifact_path: str | Path,
    *,
    approved_sha256: str,
    approved_source: str,
    approved_revision: str,
    verifier_id: str,
    verification_basis: str,
    output_path: str | Path,
) -> ModelVerificationReceipt:
    manifest_file = Path(manifest_path).resolve()
    artifact_file = Path(artifact_path).resolve()
    manifest = load_model_manifest(manifest_file)
    manifest.validate_ssot(
        model_id=GV100H_BASELINE.model_id,
        model_artifact=GV100H_BASELINE.model_artifact,
    )
    if manifest.model_source != approved_source:
        raise ValueError("approved source does not match model manifest")
    if manifest.model_revision != approved_revision:
        raise ValueError("approved revision does not match model manifest")
    artifact_sha256 = manifest.verify_artifact(artifact_file)
    if artifact_sha256.lower() != approved_sha256.lower():
        raise ValueError("artifact bytes do not match independently approved SHA-256")
    if artifact_sha256.lower() != manifest.model_sha256.lower():
        raise ValueError("artifact bytes do not match model manifest SHA-256")
    receipt = ModelVerificationReceipt(
        verification_status="verified",
        independent_verification=True,
        verifier_id=verifier_id,
        verified_at=datetime.now(timezone.utc).isoformat(),
        verification_basis=verification_basis,
        manifest_sha256=sha256_file(manifest_file),
        artifact_sha256=artifact_sha256,
        approved_artifact_sha256=approved_sha256,
        model_source=approved_source,
        model_revision=approved_revision,
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
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--approved-sha256", required=True)
    parser.add_argument("--approved-source", required=True)
    parser.add_argument("--approved-revision", required=True)
    parser.add_argument("--verifier-id", required=True)
    parser.add_argument("--verification-basis", required=True)
    parser.add_argument("--output", default="deploy/gate4_model_verification_receipt.json")
    args = parser.parse_args()
    receipt = build_receipt(
        args.manifest,
        args.artifact,
        approved_sha256=args.approved_sha256,
        approved_source=args.approved_source,
        approved_revision=args.approved_revision,
        verifier_id=args.verifier_id,
        verification_basis=args.verification_basis,
        output_path=args.output,
    )
    print(json.dumps(receipt.model_dump(), indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
