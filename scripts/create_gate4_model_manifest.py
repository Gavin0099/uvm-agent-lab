#!/usr/bin/env python3
"""Create an operator-attested Gate 4 model provenance manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from gv100h.runtime.model_provenance import ModelArtifactManifest
from gv100h.runtime.ssot import GV100H_BASELINE


def build_manifest(
    model_path: str | Path,
    *,
    model_source: str,
    model_revision: str,
    output_path: str | Path,
) -> ModelArtifactManifest:
    artifact_path = Path(model_path).resolve()
    if artifact_path.name != GV100H_BASELINE.model_artifact:
        raise ValueError(
            f"model file name {artifact_path.name!r} does not match "
            f"SSOT artifact {GV100H_BASELINE.model_artifact!r}"
        )
    if not artifact_path.is_file():
        raise ValueError(f"model artifact does not exist: {artifact_path}")
    digest = hashlib.sha256()
    with artifact_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    manifest = ModelArtifactManifest(
        model_id=GV100H_BASELINE.model_id,
        model_source=model_source,
        model_revision=model_revision,
        model_artifact=GV100H_BASELINE.model_artifact,
        model_sha256=digest.hexdigest(),
    )
    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest.model_dump(), indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create the operator-attested Gate 4 model manifest"
    )
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--model-source", required=True)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument(
        "--output",
        default="deploy/gate4_model_manifest.json",
    )
    args = parser.parse_args()
    manifest = build_manifest(
        args.model_path,
        model_source=args.model_source,
        model_revision=args.model_revision,
        output_path=args.output,
    )
    print(json.dumps(manifest.model_dump(), indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
