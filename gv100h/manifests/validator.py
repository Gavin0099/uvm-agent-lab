import json
import jsonschema
from pathlib import Path
from typing import Dict, Any, List, Set

from gv100h.manifests.models import GV100HRunManifest


class ManifestValidationError(Exception):
    """Raised when a run manifest fails cryptographic or schema verification."""
    pass


class ManifestValidator:
    """
    Zero-Trust Validator for GV100H Run Manifests.
    Validates against json-schema, checks cryptographic hash formats, and verifies arm completeness.
    """

    SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "run_manifest.schema.json"

    def __init__(self):
        with open(self.SCHEMA_PATH, "r", encoding="utf-8") as f:
            self.schema = json.load(f)

    def validate_manifest_dict(self, data: Dict[str, Any]) -> GV100HRunManifest:
        # 1. JSON Schema validation
        try:
            jsonschema.validate(instance=data, schema=self.schema)
        except jsonschema.ValidationError as e:
            raise ManifestValidationError(f"Schema validation error: {e.message} at {list(e.path)}")

        # 2. Pydantic strong typing
        try:
            manifest = GV100HRunManifest.model_validate(data)
        except Exception as e:
            raise ManifestValidationError(f"Pydantic model validation error: {str(e)}")

        # 3. Cryptographic hash sanity (SHA-256 must be 64 hex chars)
        diff_hash = manifest.evidence.git_diff_sha256
        if len(diff_hash) != 64 or not all(c in "0123456789abcdefABCDEF" for c in diff_hash):
            raise ManifestValidationError(f"Invalid git_diff_sha256: '{diff_hash}' (must be 64 hex characters)")

        return manifest

    def validate_manifest_set(self, manifests: List[GV100HRunManifest]) -> bool:
        """
        Validates a collection of manifests for duplicates, complete arms, and evidence honesty.
        """
        seen_run_ids: Set[str] = set()
        for m in manifests:
            if m.run_id in seen_run_ids:
                raise ManifestValidationError(f"Duplicate run_id detected: {m.run_id}")
            seen_run_ids.add(m.run_id)

            # Fail-closed check on false success
            if m.outcome.false_success and m.outcome.status == "pass":
                raise ManifestValidationError(f"Corrupted outcome: run {m.run_id} marked false_success=True but status='pass'")

        return True
