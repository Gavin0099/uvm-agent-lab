import hashlib
import json
import base64
import binascii
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import jsonschema

from agent.governance.guardrails import ScopeGuardrail
from gv100h.governance.contract_router import TaskContractRouter
from gv100h.manifests.models import GV100HRunManifest
from gv100h.runner.worktree_runner import FatalWorktreeError, GitWorktreeRunner
from gv100h.utils.case_contract import resolve_benchmark_case
from gv100h.utils.evidence_commit import compute_reconstructed_head_commit


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
        for field_name in (
            "workspace_tree_sha256",
            "target_file_sha256",
            "file_snapshots_sha256",
            "tool_trace_sha256",
            "verification_sha256",
        ):
            field_value = getattr(manifest.evidence, field_name)
            if field_value is not None and (
                len(field_value) != 64
                or not all(c in "0123456789abcdefABCDEF" for c in field_value)
            ):
                raise ManifestValidationError(
                    f"Invalid {field_name}: '{field_value}' (must be 64 hex characters)"
                )
        if manifest.benchmark_case_hash is not None and (
            len(manifest.benchmark_case_hash) != 64
            or not all(c in "0123456789abcdefABCDEF" for c in manifest.benchmark_case_hash)
        ):
            raise ManifestValidationError(
                f"Invalid benchmark_case_hash: '{manifest.benchmark_case_hash}'"
            )

        return manifest

    def validate_manifest_bundle(
        self,
        manifest: GV100HRunManifest,
        bundle_dir: Path,
        *,
        require_integrity: bool = False,
        repo_root: Optional[Path] = None,
        guardrail: Optional[ScopeGuardrail] = None,
    ) -> bool:
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
        diff_bytes = diff_file.read_bytes()
        if not diff_bytes:
            raise ManifestValidationError("Evidence 'diff.patch' must be non-empty")
        real_diff_sha = hashlib.sha256(diff_bytes).hexdigest()
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

        bound_fields = {
            "workspace_tree_sha256": manifest.evidence.workspace_tree_sha256,
            "target_file": manifest.evidence.target_file,
            "target_file_sha256": manifest.evidence.target_file_sha256,
            "file_snapshots_sha256": manifest.evidence.file_snapshots_sha256,
            "tool_trace_sha256": manifest.evidence.tool_trace_sha256,
            "verification_sha256": manifest.evidence.verification_sha256,
            "endpoint_observed": manifest.evidence.endpoint_observed,
            "eda_backend": manifest.evidence.eda_backend,
            "qualification_admissible": manifest.evidence.qualification_admissible,
            "benchmark_case_hash": manifest.benchmark_case_hash,
        }
        binding_requested = (
            require_integrity
            or manifest.evidence.evidence_schema_version is not None
            or any(value is not None for value in bound_fields.values())
        )
        if binding_requested:
            if manifest.evidence.evidence_schema_version != "2":
                raise ManifestValidationError(
                    "Strict evidence binding requires evidence_schema_version='2'"
                )
            missing = [name for name, value in bound_fields.items() if value is None]
            if missing:
                raise ManifestValidationError(
                    f"Incomplete evidence binding fields: {', '.join(missing)}"
                )
            if manifest.hardware.hardware_observed is None:
                raise ManifestValidationError(
                    "Strict evidence binding requires hardware_observed"
                )
            if manifest.head_commit is None or len(manifest.head_commit) != 40:
                raise ManifestValidationError(
                    "Strict evidence binding requires a 40-character head_commit"
                )

            artifact_hashes = {
                "workspace_tree.json": manifest.evidence.workspace_tree_sha256,
                "file_snapshots.json": manifest.evidence.file_snapshots_sha256,
                "tool_trace.json": manifest.evidence.tool_trace_sha256,
                "verification.json": manifest.evidence.verification_sha256,
            }
            artifact_bytes = {}
            for name, expected_sha in artifact_hashes.items():
                artifact = bundle_path / name
                if not artifact.exists():
                    raise ManifestValidationError(
                        f"Physical evidence '{name}' missing in {bundle_path}"
                    )
                payload = artifact.read_bytes()
                actual_sha = hashlib.sha256(payload).hexdigest()
                if actual_sha != expected_sha:
                    raise ManifestValidationError(
                        f"Tamper detected: {name} hash mismatch! Manifest claims {expected_sha}, physical file is {actual_sha}"
                    )
                artifact_bytes[name] = payload

            try:
                workspace_tree = json.loads(artifact_bytes["workspace_tree.json"])
                file_snapshots = json.loads(artifact_bytes["file_snapshots.json"])
                tool_trace = json.loads(artifact_bytes["tool_trace.json"])
                verification = json.loads(artifact_bytes["verification.json"])
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ManifestValidationError(f"Evidence JSON is invalid: {exc}") from exc
            if tool_trace.get("endpoint_observed") != manifest.evidence.endpoint_observed:
                raise ManifestValidationError(
                    "Tool trace endpoint observation is not bound to manifest"
                )
            if verification.get("endpoint_observed") != manifest.evidence.endpoint_observed:
                raise ManifestValidationError(
                    "Verification endpoint observation is not bound to manifest"
                )
            if verification.get("eda_backend") != manifest.evidence.eda_backend:
                raise ManifestValidationError(
                    "Verification EDA backend is not bound to manifest"
                )
            if verification.get("qualification_admissible") != manifest.evidence.qualification_admissible:
                raise ManifestValidationError(
                    "Verification qualification status is not bound to manifest"
                )

            snapshot_entries = file_snapshots.get("files")
            tree_entries = workspace_tree.get("files")
            if not isinstance(snapshot_entries, list) or not isinstance(tree_entries, list):
                raise ManifestValidationError("Evidence snapshots must contain a 'files' list")

            canonical_tree_entries = []
            snapshot_contents: Dict[str, bytes] = {}
            target_snapshot = None
            for entry in snapshot_entries:
                if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                    raise ManifestValidationError("Invalid file snapshot entry")
                kind = entry.get("kind")
                if kind == "file":
                    try:
                        content = base64.b64decode(entry["content_b64"], validate=True)
                    except (KeyError, ValueError, binascii.Error) as exc:
                        raise ManifestValidationError("Invalid file snapshot content") from exc
                    actual_file_sha = hashlib.sha256(content).hexdigest()
                    if actual_file_sha != entry.get("sha256") or len(content) != entry.get("size"):
                        raise ManifestValidationError(
                            f"File snapshot hash mismatch for {entry['path']}"
                        )
                    snapshot_contents[entry["path"]] = content
                    tree_entry = {
                        "kind": "file",
                        "path": entry["path"],
                        "sha256": entry["sha256"],
                        "size": entry["size"],
                    }
                    if entry["path"] == manifest.evidence.target_file:
                        target_snapshot = content
                elif kind == "symlink":
                    tree_entry = {
                        "kind": "symlink",
                        "path": entry["path"],
                        "target": entry.get("target"),
                    }
                elif kind == "missing":
                    tree_entry = {"kind": "missing", "path": entry["path"]}
                else:
                    raise ManifestValidationError(f"Unknown file snapshot kind: {kind}")
                canonical_tree_entries.append(tree_entry)

            if tree_entries != canonical_tree_entries:
                raise ManifestValidationError("Workspace tree does not match file snapshots")
            if sorted(entry["path"] for entry in snapshot_entries) != sorted(manifest.evidence.changed_paths):
                raise ManifestValidationError("File snapshots do not match changed_paths")
            if target_snapshot is None:
                raise ManifestValidationError(
                    f"Target file snapshot missing: {manifest.evidence.target_file}"
                )
            if hashlib.sha256(target_snapshot).hexdigest() != manifest.evidence.target_file_sha256:
                raise ManifestValidationError("Target file snapshot hash is not bound to manifest")

            if repo_root is None:
                raise ManifestValidationError(
                    "Strict evidence binding requires repo_root for patch reconstruction"
                )
            reconstructed_files, reconstructed_head_commit, reconstructed_paths = (
                self._reconstruct_files_from_patch(
                    manifest=manifest,
                    diff_bytes=diff_bytes,
                    repo_root=repo_root,
                    paths=[entry["path"] for entry in snapshot_entries],
                )
            )
            if reconstructed_head_commit != manifest.head_commit:
                raise ManifestValidationError(
                    "Patch reconstruction head_commit does not match manifest"
                )
            declared_paths = set(manifest.evidence.changed_paths)
            snapshot_paths = {entry["path"] for entry in snapshot_entries}
            actual_paths = set(reconstructed_paths)
            if actual_paths != declared_paths or actual_paths != snapshot_paths:
                raise ManifestValidationError(
                    "Reconstructed Git changed-path set does not match changed_paths/snapshots"
                )
            if guardrail is None:
                try:
                    case_id = manifest.benchmark_task_id or manifest.task_id
                    case_data = resolve_benchmark_case(
                        Path(repo_root),
                        case_id,
                        manifest.benchmark_case_hash,
                    )
                    guardrail = TaskContractRouter(
                        base_dir=str(repo_root)
                    ).create_guardrail_for_benchmark_execution(
                        case_id,
                        base_dir=str(repo_root),
                        case_data=case_data,
                    )
                except (FileNotFoundError, KeyError, ValueError) as exc:
                    raise ManifestValidationError(
                        f"Strict evidence binding could not load benchmark case contract: {exc}"
                    ) from exc
            for changed_path in sorted(actual_paths):
                allowed, _report = guardrail.check_path_access(changed_path)
                if not allowed:
                    raise ManifestValidationError(
                        f"Reconstructed patch path violates benchmark guardrail: {changed_path}"
                    )
            for entry in snapshot_entries:
                path = entry["path"]
                reconstructed = reconstructed_files[path]
                if entry["kind"] == "file":
                    if reconstructed.get("kind") != "file" or reconstructed.get("content") != snapshot_contents[path]:
                        raise ManifestValidationError(
                            f"Patch reconstruction does not match file snapshot: {path}"
                        )
                elif entry["kind"] == "symlink":
                    if reconstructed != {"kind": "symlink", "target": entry.get("target")}:
                        raise ManifestValidationError(
                            f"Patch reconstruction does not match symlink snapshot: {path}"
                        )
                elif reconstructed.get("kind") != "missing":
                    raise ManifestValidationError(
                        f"Patch reconstruction does not match missing snapshot: {path}"
                    )

            reconstructed_target = reconstructed_files.get(manifest.evidence.target_file, {})
            if reconstructed_target.get("kind") != "file":
                raise ManifestValidationError(
                    f"Patch did not reconstruct target file: {manifest.evidence.target_file}"
                )
            if hashlib.sha256(reconstructed_target["content"]).hexdigest() != manifest.evidence.target_file_sha256:
                raise ManifestValidationError(
                    "Patch reconstruction target hash does not match target_file_sha256"
                )
            if reconstructed_target["content"] != target_snapshot:
                raise ManifestValidationError(
                    "Patch reconstruction target does not match file snapshot"
                )

        return True

    @staticmethod
    def _reconstruct_files_from_patch(
        *,
        manifest: GV100HRunManifest,
        diff_bytes: bytes,
        repo_root: Path,
        paths: List[str],
    ) -> tuple[Dict[str, Dict[str, Any]], str, List[str]]:
        root = Path(repo_root).resolve()
        if not (root / ".git").exists():
            raise ManifestValidationError(f"Git repository not found for patch reconstruction: {root}")

        temp_dir = Path(tempfile.mkdtemp(prefix="gv100h_patch_verify_"))
        try:
            add_result = subprocess.run(
                ["git", "worktree", "add", "--detach", str(temp_dir), manifest.base_commit],
                cwd=str(root),
                capture_output=True,
                text=True,
            )
            if add_result.returncode != 0:
                raise ManifestValidationError(
                    f"Could not create clean base worktree: {add_result.stderr.strip()}"
                )

            check_result = subprocess.run(
                ["git", "apply", "--check"],
                cwd=str(temp_dir),
                input=diff_bytes,
                capture_output=True,
            )
            if check_result.returncode != 0:
                error = check_result.stderr.decode("utf-8", errors="replace").strip()
                raise ManifestValidationError(f"Patch does not apply cleanly: {error}")

            apply_result = subprocess.run(
                ["git", "apply"],
                cwd=str(temp_dir),
                input=diff_bytes,
                capture_output=True,
            )
            if apply_result.returncode != 0:
                error = apply_result.stderr.decode("utf-8", errors="replace").strip()
                raise ManifestValidationError(f"Patch application failed: {error}")

            try:
                reconstructed_paths = GitWorktreeRunner.list_worktree_changed_paths(temp_dir)
            except FatalWorktreeError as exc:
                raise ManifestValidationError(
                    f"Could not enumerate reconstructed Git changed paths: {exc}"
                ) from exc
            inventory_paths = list(dict.fromkeys([*paths, *reconstructed_paths]))
            reconstructed: Dict[str, Dict[str, Any]] = {}
            for path in inventory_paths:
                relative = Path(str(path).replace("\\", "/"))
                if relative.is_absolute() or ".." in relative.parts:
                    raise ManifestValidationError(
                        f"Invalid changed path for patch reconstruction: {path}"
                    )
                candidate = (temp_dir / relative).resolve()
                try:
                    candidate.relative_to(temp_dir.resolve())
                except ValueError as exc:
                    raise ManifestValidationError(
                        f"Reconstructed path escaped clean base worktree: {path}"
                    ) from exc
                if candidate.is_symlink():
                    reconstructed[path] = {
                        "kind": "symlink",
                        "target": os.readlink(candidate),
                    }
                elif candidate.is_file():
                    reconstructed[path] = {
                        "kind": "file",
                        "content": candidate.read_bytes(),
                    }
                else:
                    reconstructed[path] = {"kind": "missing"}
            reconstructed_head_commit = compute_reconstructed_head_commit(
                temp_dir,
                manifest.base_commit,
            )
            return reconstructed, reconstructed_head_commit, reconstructed_paths
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(temp_dir)],
                cwd=str(root),
                capture_output=True,
            )
            shutil.rmtree(temp_dir, ignore_errors=True)

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

