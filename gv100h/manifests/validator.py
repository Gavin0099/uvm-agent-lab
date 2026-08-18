import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Set

import jsonschema

from gv100h.manifests.models import GV100HRunManifest


class ManifestValidationError(Exception):
    """Raised when a run manifest fails cryptographic or schema verification."""
    pass


class ManifestValidator:
    """
    Zero-Trust Tamper-Evident Validator for GV100H Run Manifests.
    Validates against json-schema, verifies cryptographic hash integrity against physical bundle files,
    and enforces strict pair matching between experiment arms.
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

    def validate_manifest_bundle(self, manifest: GV100HRunManifest, bundle_dir: Path) -> bool:
        """
        Tamper-Evident Re-Verification:
        Re-computes SHA-256 hashes directly from physical artifact files in bundle_dir
        and compares bit-for-bit against manifest claims.
        """
        bundle_path = Path(bundle_dir).resolve()
        if not bundle_path.exists():
            raise ManifestValidationError(f"Evidence bundle directory not found: {bundle_path}")

        # 1. Verify diff.patch
        diff_file = bundle_path / "diff.patch"
        if not diff_file.exists():
            raise ManifestValidationError(f"Physical evidence 'diff.patch' missing in {bundle_path}")
        real_diff_sha = hashlib.sha256(diff_file.read_bytes()).hexdigest()
        if real_diff_sha != manifest.evidence.git_diff_sha256:
            raise ManifestValidationError(
                f"Tamper detected: git_diff_sha256 mismatch! "
                f"Manifest claims {manifest.evidence.git_diff_sha256}, physical file is {real_diff_sha}"
            )

        # 2. Verify build.log (if recorded)
        if manifest.evidence.build_log_sha256:
            build_file = bundle_path / "build.log"
            if not build_file.exists():
                raise ManifestValidationError(f"Physical evidence 'build.log' missing in {bundle_path}")
            real_build_sha = hashlib.sha256(build_file.read_bytes()).hexdigest()
            if real_build_sha != manifest.evidence.build_log_sha256:
                raise ManifestValidationError(
                    f"Tamper detected: build_log_sha256 mismatch! "
                    f"Manifest claims {manifest.evidence.build_log_sha256}, physical file is {real_build_sha}"
                )

        # 3. Verify simulation.log (if recorded)
        if manifest.evidence.test_log_sha256:
            sim_file = bundle_path / "simulation.log"
            if not sim_file.exists():
                raise ManifestValidationError(f"Physical evidence 'simulation.log' missing in {bundle_path}")
            real_sim_sha = hashlib.sha256(sim_file.read_bytes()).hexdigest()
            if real_sim_sha != manifest.evidence.test_log_sha256:
                raise ManifestValidationError(
                    f"Tamper detected: test_log_sha256 mismatch! "
                    f"Manifest claims {manifest.evidence.test_log_sha256}, physical file is {real_sim_sha}"
                )

        return True

    def validate_manifest_set(
        self,
        manifests: List[GV100HRunManifest],
        require_complete_pairs: bool = False
    ) -> bool:
        """
        Validates a collection of manifests for duplicates, complete arms, and evidence honesty.
        """
        seen_run_ids: Set[str] = set()
        arm_a_by_pair: Dict[str, GV100HRunManifest] = {}
        arm_b_by_pair: Dict[str, GV100HRunManifest] = {}

        for m in manifests:
            if m.run_id in seen_run_ids:
                raise ManifestValidationError(f"Duplicate run_id detected: {m.run_id}")
            seen_run_ids.add(m.run_id)

            # Fail-closed check on false success
            if m.outcome.false_success and m.outcome.status == "pass":
                raise ManifestValidationError(f"Corrupted outcome: run {m.run_id} marked false_success=True but status='pass'")

            if m.pair_id:
                if m.experiment_arm == "arm_a_prompt_only":
                    arm_a_by_pair[m.pair_id] = m
                elif m.experiment_arm == "arm_b_governed_sidecar":
                    arm_b_by_pair[m.pair_id] = m

        if require_complete_pairs:
            all_pairs = set(arm_a_by_pair.keys()).union(set(arm_b_by_pair.keys()))
            if not all_pairs:
                raise ManifestValidationError("No paired runs found in manifest set.")

            for pid in all_pairs:
                if pid not in arm_a_by_pair:
                    raise ManifestValidationError(f"Incomplete pair '{pid}': Arm A run is missing.")
                if pid not in arm_b_by_pair:
                    raise ManifestValidationError(f"Incomplete pair '{pid}': Arm B run is missing.")

                # Validate invariant fields between Arm A and Arm B
                ma = arm_a_by_pair[pid]
                mb = arm_b_by_pair[pid]
                if ma.task_id != mb.task_id or ma.base_commit != mb.base_commit or ma.model_id != mb.model_id:
                    raise ManifestValidationError(
                        f"Invariant drift detected in pair '{pid}': "
                        f"Arm A ({ma.task_id}, {ma.base_commit[:7]}, {ma.model_id}) != "
                        f"Arm B ({mb.task_id}, {mb.base_commit[:7]}, {mb.model_id})"
                    )

        return True

