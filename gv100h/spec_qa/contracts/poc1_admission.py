from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any, Dict, Literal

from pydantic import BaseModel, ConfigDict, Field

from gv100h.spec_qa.contracts.poc1_acceptance_contract import (
    REQUIRED_POC1_SOURCE_IDS,
    AcceptanceContractError,
    POC1AcceptanceSet,
    compute_acceptance_set_hash,
    load_frozen_source_sets,
    load_poc1_acceptance_set,
    verify_accepted_source_set_identity,
)


class POC1AdmissionError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        status: Literal["missing", "mismatch", "unverified"] = "mismatch",
    ) -> None:
        super().__init__(message)
        self.status = status


class POC1ReviewReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_name: Literal["poc1_acceptance_review_receipt"]
    schema_version: Literal["1.0"]
    reviewed_manifest_path: str = Field(min_length=1)
    reviewed_manifest_hash: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    reviewed_commit: str = Field(pattern=r"^[0-9a-fA-F]{40,64}$")
    reviewer_id: str = Field(min_length=1)
    reviewed_at: str = Field(min_length=1)
    total_questions: int = Field(ge=50, le=100)
    passed_questions: int = Field(ge=0, le=100)
    changed_question_ids: list[str] = Field(default_factory=list)
    source_revisions: Dict[str, str]
    review_status: Literal["approved"]


def _load_review_receipt(path: Path) -> POC1ReviewReceipt:
    try:
        return POC1ReviewReceipt.model_validate(json.loads(path.read_bytes()))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise POC1AdmissionError(
            f"review receipt is invalid: {exc}",
            status="mismatch",
        ) from exc


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _repo_relative(path: Path, repo_root: Path, label: str) -> str:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise POC1AdmissionError(
            f"{label} must be inside the repository root",
            status="mismatch",
        ) from exc
    return relative.as_posix()


def _run_git_bytes(repo_root: Path, *arguments: str) -> bytes:
    result = subprocess.run(
        ["git", *arguments],
        cwd=str(repo_root),
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise POC1AdmissionError(
            "reviewed manifest commit could not be verified",
            status="unverified",
        )
    return result.stdout


def _review_path(repo_root: Path, relative_path: str) -> Path:
    candidate = Path(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise POC1AdmissionError(
            "review receipt path must be a safe repository-relative path",
            status="mismatch",
        )
    return (repo_root / candidate).resolve()


def _detail_value(detail: Any, field_name: str) -> Any:
    if isinstance(detail, dict):
        return detail.get(field_name)
    return getattr(detail, field_name, None)


def _rate(numerator: int, denominator: int) -> float:
    return round((numerator / denominator) * 100.0, 2) if denominator else 0.0


def _verify_result_consistency(
    manifest: POC1AcceptanceSet,
    result: Any,
) -> None:
    details = getattr(result, "details", None)
    if not isinstance(details, list) or len(details) != manifest.total_questions:
        raise POC1AdmissionError(
            "final POC-1 result details must cover every manifest question",
            status="mismatch",
        )
    questions_by_id = {question.question_id: question for question in manifest.questions}
    seen_ids: set[str] = set()
    for detail in details:
        question_id = _detail_value(detail, "question_id")
        if question_id not in questions_by_id or question_id in seen_ids:
            raise POC1AdmissionError(
                "final POC-1 result details have invalid or duplicate question IDs",
                status="mismatch",
            )
        seen_ids.add(question_id)
        question = questions_by_id[question_id]
        if _detail_value(detail, "expected_status") != question.expected_status:
            raise POC1AdmissionError(
                f"final POC-1 result status binding mismatch for {question_id}",
                status="mismatch",
            )
    if seen_ids != set(questions_by_id):
        raise POC1AdmissionError(
            "final POC-1 result details do not match manifest question IDs",
            status="mismatch",
        )

    counts = {
        status: sum(
            question.expected_status == status for question in manifest.questions
        )
        for status in ("answer", "conflict", "abstain")
    }
    if any(
        getattr(result, f"{status}_question_count", None) != counts[status]
        for status in counts
    ):
        raise POC1AdmissionError(
            "final POC-1 result question counts do not match manifest",
            status="mismatch",
        )

    def count_true(field_name: str, status: str | None = None) -> int:
        return sum(
            bool(_detail_value(detail, field_name))
            for detail in details
            if status is None or _detail_value(detail, "expected_status") == status
        )

    total = manifest.total_questions
    expected_rates = {
        "retrieval_recall_at_1": _rate(count_true("retrieval_hit_at_1"), total),
        "grounded_answer_rate": _rate(
            count_true("passed", "answer"), counts["answer"]
        ),
        "citation_validity_rate": _rate(count_true("citation_valid"), total),
        "citation_completeness_rate": _rate(
            count_true("citation_complete"), total
        ),
        "conflict_detection_rate": _rate(
            count_true("passed", "conflict"), counts["conflict"]
        ),
        "abstention_rate": _rate(
            count_true("passed", "abstain"), counts["abstain"]
        ),
    }
    for field_name, expected in expected_rates.items():
        observed = getattr(result, field_name, None)
        if not isinstance(observed, (int, float)) or not math.isclose(
            float(observed), expected, abs_tol=0.01
        ):
            raise POC1AdmissionError(
                f"final POC-1 result metric {field_name} does not match details",
                status="mismatch",
            )
    expected_counts = {
        "fabricated_citations_count": count_true("fabricated_citation"),
        "authority_violations_count": count_true("authority_violation"),
    }
    for field_name, expected in expected_counts.items():
        if getattr(result, field_name, None) != expected:
            raise POC1AdmissionError(
                f"final POC-1 result count {field_name} does not match details",
                status="mismatch",
            )
    if getattr(result, "all_gates_passed", None) != all(
        bool(_detail_value(detail, "passed")) for detail in details
    ):
        raise POC1AdmissionError(
            "final POC-1 result all_gates_passed does not match details",
            status="mismatch",
        )


def verify_poc1_acceptance_admission(
    *,
    manifest_path: str | Path,
    result: Any,
    repo_root: str | Path,
) -> Dict[str, Any]:
    root = Path(repo_root).resolve()
    manifest_file = Path(manifest_path).resolve()
    if not manifest_file.is_file():
        raise POC1AdmissionError(
            f"acceptance manifest does not exist: {manifest_file}",
            status="missing",
        )

    manifest = load_poc1_acceptance_set(manifest_file)
    # Resolve the frozen source-set identity relative to the caller-supplied
    # repo_root (not this module's own checkout location), so admission
    # always verifies against the specific repository being admitted.
    frozen_identity_path = (
        root
        / "gv100h"
        / "spec_qa"
        / "golden"
        / "poc1_acceptance_set.frozen_source_identity.json"
    )
    try:
        frozen_source_sets = load_frozen_source_sets(frozen_identity_path)
        verify_accepted_source_set_identity(
            manifest.questions, frozen_source_sets=frozen_source_sets
        )
    except AcceptanceContractError as exc:
        raise POC1AdmissionError(
            f"accepted source-set identity mismatch: {exc}",
            status="mismatch",
        ) from exc
    _verify_result_consistency(manifest, result)
    manifest_relative = _repo_relative(manifest_file, root, "acceptance manifest")
    if not result or getattr(result, "acceptance_set_path", None) is None:
        raise POC1AdmissionError(
            "final POC-1 result does not carry acceptance_set_path",
            status="missing",
        )
    result_manifest = Path(result.acceptance_set_path).resolve()
    if result_manifest != manifest_file:
        raise POC1AdmissionError(
            "final POC-1 result acceptance_set_path does not match manifest",
            status="mismatch",
        )

    manifest_hash = compute_acceptance_set_hash(manifest)
    manifest_fields = {
        "acceptance_set_hash": manifest_hash,
        "dataset_hash": manifest_hash,
        "corpus_receipt_path": manifest.corpus_receipt_path,
        "corpus_receipt_hash": manifest.corpus_receipt_hash,
        "review_receipt_path": manifest.review_receipt_path,
        "review_receipt_hash": manifest.review_receipt_hash,
        "benchmark_role": manifest.benchmark_role,
        "total_questions": manifest.total_questions,
    }
    for field_name, expected in manifest_fields.items():
        if getattr(result, field_name, None) != expected:
            raise POC1AdmissionError(
                f"final POC-1 result field {field_name} does not match manifest",
                status="mismatch",
            )

    receipt_file = _review_path(root, manifest.review_receipt_path)
    if not receipt_file.is_file():
        raise POC1AdmissionError(
            f"review receipt does not exist: {receipt_file}",
            status="missing",
        )
    receipt_bytes = receipt_file.read_bytes()
    actual_receipt_hash = _sha256_bytes(receipt_bytes)
    if actual_receipt_hash.lower() != manifest.review_receipt_hash.lower():
        raise POC1AdmissionError(
            "review receipt hash does not match manifest",
            status="mismatch",
        )
    receipt = _load_review_receipt(receipt_file)

    if receipt.reviewed_manifest_path != manifest_relative:
        raise POC1AdmissionError(
            "review receipt manifest path does not match acceptance manifest",
            status="mismatch",
        )
    if receipt.reviewed_manifest_hash.lower() != manifest_hash.lower():
        raise POC1AdmissionError(
            "review receipt manifest hash does not match acceptance manifest",
            status="mismatch",
        )
    if receipt.reviewer_id != manifest.reviewer_id:
        raise POC1AdmissionError(
            "review receipt reviewer does not match acceptance manifest",
            status="mismatch",
        )
    if receipt.reviewed_at != manifest.reviewed_at:
        raise POC1AdmissionError(
            "review receipt timestamp does not match acceptance manifest",
            status="mismatch",
        )
    if receipt.total_questions != manifest.total_questions:
        raise POC1AdmissionError(
            "review receipt question count does not match acceptance manifest",
            status="mismatch",
        )
    if receipt.passed_questions != receipt.total_questions:
        raise POC1AdmissionError(
            "approved review receipt must pass every question",
            status="mismatch",
        )
    if len(receipt.changed_question_ids) != len(set(receipt.changed_question_ids)):
        raise POC1AdmissionError(
            "review receipt changed_question_ids must be unique",
            status="mismatch",
        )
    question_ids = {question.question_id for question in manifest.questions}
    if not set(receipt.changed_question_ids).issubset(question_ids):
        raise POC1AdmissionError(
            "review receipt changed_question_ids must reference manifest questions",
            status="mismatch",
        )
    if set(receipt.source_revisions) != REQUIRED_POC1_SOURCE_IDS:
        raise POC1AdmissionError(
            "review receipt source_revisions must cover exactly POC-1 sources",
            status="mismatch",
        )
    if any(not revision.strip() for revision in receipt.source_revisions.values()):
        raise POC1AdmissionError(
            "review receipt source_revisions must be non-empty",
            status="mismatch",
        )

    _run_git_bytes(root, "ls-files", "--error-unmatch", "--", manifest_relative)
    committed_bytes = _run_git_bytes(
        root,
        "show",
        f"{receipt.reviewed_commit}:{manifest_relative}",
    )
    try:
        committed_payload = json.loads(committed_bytes)
        committed_manifest = POC1AcceptanceSet.model_validate(committed_payload)
        committed_manifest.validate_contract()
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise POC1AdmissionError(
            f"reviewed commit does not contain a valid acceptance manifest: {exc}",
            status="unverified",
        ) from exc
    if compute_acceptance_set_hash(committed_manifest).lower() != manifest_hash.lower():
        raise POC1AdmissionError(
            "reviewed commit manifest hash does not match current acceptance manifest",
            status="mismatch",
        )

    return {
        "status": "verified",
        "acceptance_set_hash": manifest_hash,
        "manifest_path": manifest_relative,
        "review_receipt_path": manifest.review_receipt_path,
        "review_receipt_hash": manifest.review_receipt_hash,
        "reviewed_commit": receipt.reviewed_commit,
        "reviewer_id": receipt.reviewer_id,
        "reviewed_at": receipt.reviewed_at,
        "total_questions": receipt.total_questions,
        "passed_questions": receipt.passed_questions,
        "source_revisions": receipt.source_revisions,
    }