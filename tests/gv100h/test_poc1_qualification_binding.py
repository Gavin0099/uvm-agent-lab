from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from gv100h.coding_eval.governance_ab_runner import ABExperimentSummary
from gv100h.qualification.evaluator import QualificationPolicyEvaluator
from gv100h.spec_qa.contracts.poc1_acceptance_contract import (
    compute_acceptance_set_hash,
    load_poc1_acceptance_set,
)
from gv100h.spec_qa.contracts.poc1_admission import (
    POC1AdmissionError,
    verify_poc1_acceptance_admission,
)
from gv100h.spec_qa.evaluation.deterministic_evaluator import QAEvaluationResult
from gv100h.spec_qa.evaluation.final_evaluator import (
    FinalPOC1EvaluationResult,
    FinalQuestionResult,
)


SOURCE_IDS = ["usb20_fw", "usb20_se", "usb32", "superspeed_hub_lvs"]


def _question(index: int) -> dict:
    if index == 49:
        status = "conflict"
        layer = "L4"
        category = "uncertainty_conflict"
        scope = "USB_HUB_COMMON"
        accepted_sources = ["usb20_fw", "usb32"]
        gold = {
            "accepted_evidence_ids": [],
            "competing_evidence_ids": ["EVIDENCE-49-A", "EVIDENCE-49-B"],
            "boundary_evidence_ids": [],
            "required_claims": [
                {"claim_id": "CLAIM-49-A", "assertion": "claim-a-49"},
                {"claim_id": "CLAIM-49-B", "assertion": "claim-b-49"},
            ],
            "section_anchors": ["section-49-a", "section-49-b"],
            "required_facts": ["claim-a-49", "claim-b-49"],
            "forbidden_claims": [],
            "acceptable_variants": [],
            "boundary_code": "UNRESOLVED_CONFLICT",
        }
        citation = {
            "document": True,
            "revision": True,
            "section": True,
            "page_or_anchor": True,
            "excerpt_or_evidence_id": True,
            "scope": True,
            "boundary_code": True,
            "mode": "competing_sources",
        }
    elif index == 50:
        status = "abstain"
        layer = "L4"
        category = "uncertainty_conflict"
        scope = "USB4_SPEC"
        accepted_sources = []
        gold = {
            "accepted_evidence_ids": [],
            "competing_evidence_ids": [],
            "boundary_evidence_ids": ["BOUNDARY-50"],
            "required_claims": [
                {"claim_id": "CLAIM-50", "assertion": "out-of-scope"},
            ],
            "section_anchors": [],
            "required_facts": [],
            "forbidden_claims": [],
            "acceptable_variants": [],
            "boundary_code": "OUT_OF_SCOPE",
        }
        citation = {
            "document": False,
            "revision": False,
            "section": False,
            "page_or_anchor": False,
            "excerpt_or_evidence_id": True,
            "scope": True,
            "boundary_code": True,
            "mode": "boundary_evidence",
        }
    else:
        status = "answer"
        layer = (
            "L1"
            if index <= 13
            else "L2"
            if index <= 26
            else "L3"
            if index <= 38
            else "L4"
        )
        category = {
            "L1": "single_spec_fact",
            "L2": "engineering_interpretation",
            "L3": "cross_document",
            "L4": "uncertainty_conflict",
        }[layer]
        scope = "USB_HUB_COMMON"
        primary = SOURCE_IDS[(index - 1) % len(SOURCE_IDS)]
        secondary = SOURCE_IDS[index % len(SOURCE_IDS)]
        accepted_sources = (
            [primary, secondary] if layer == "L3" else [primary]
        )
        gold = {
            "accepted_evidence_ids": (
                [f"{primary}:EVIDENCE-{index}-A", f"{secondary}:EVIDENCE-{index}-B"]
                if layer == "L3"
                else [f"EVIDENCE-{index}"]
            ),
            "competing_evidence_ids": [],
            "boundary_evidence_ids": [],
            "required_claims": [
                {"claim_id": f"CLAIM-{index}", "assertion": f"fact-{index}"},
            ],
            "section_anchors": (
                [f"{primary}:section-{index}-a", f"{secondary}:section-{index}-b"]
                if layer == "L3"
                else [f"section-{index}"]
            ),
            "required_facts": [f"fact-{index}"],
            "forbidden_claims": [],
            "acceptable_variants": [],
            "boundary_code": None,
        }
        citation = {
            "document": True,
            "revision": True,
            "section": True,
            "page_or_anchor": True,
            "excerpt_or_evidence_id": True,
            "scope": True,
            "boundary_code": False,
            "mode": "normative_source",
        }

    return {
        "question_id": f"QA-{index:03d}",
        "layer": layer,
        "priority": "P1" if layer == "L3" else "P0",
        "category": category,
        "question": f"Question {index}",
        "expected_status": status,
        "expected_scope": scope,
        "accepted_source_ids": accepted_sources,
        "required_citation_fields": citation,
        "gold": gold,
        "grading": {
            "factual_correctness": 0.40,
            "citation_correctness": 0.25,
            "source_authority": 0.15,
            "scope_control": 0.10,
            "uncertainty_behavior": 0.10,
        },
        "independently_reviewed": True,
        "usb4_negative_control": index == 50,
    }


def _manifest_payload() -> dict:
    return {
        "schema_name": "poc1_spec_qa_acceptance_set",
        "schema_version": "1.1",
        "corpus_lock": "gv100h/spec_qa/contracts/corpus.lock.yaml",
        "corpus_receipt_path": "artifacts/evidence/test-results/corpus.json",
        "corpus_receipt_hash": "a" * 64,
        "dataset_version": "2.0.0",
        "benchmark_role": "poc1_acceptance_set",
        "generated_from_corpus": False,
        "independent_from_corpus": True,
        "independent_review_complete": True,
        "review_receipt_path": "artifacts/reviews/poc1-acceptance-review.json",
        "review_receipt_hash": "0" * 64,
        "reviewer_id": "reviewer-1",
        "reviewed_at": "2026-08-25T00:00:00Z",
        "total_questions": 50,
        "required_layers": {"L1": 10, "L2": 10, "L3": 10, "L4": 10},
        "required_source_ids": SOURCE_IDS,
        "questions": [_question(index) for index in range(1, 51)],
    }


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", *args],
        cwd=repo,
        text=True,
    ).strip()


def _write_json(path: Path, payload: dict) -> bytes:
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    path.write_bytes(encoded)
    return encoded


def _frozen_identity_payload(payload: dict) -> dict:
    return {
        "questions": [
            {
                "question_id": question["question_id"],
                "accepted_source_ids": list(question["accepted_source_ids"]),
            }
            for question in payload["questions"]
        ]
    }


def _build_reviewed_repo(tmp_path: Path, *, frozen_identity_payload: dict | None = None):
    repo = tmp_path / "reviewed-repo"
    manifest_path = repo / "gv100h" / "spec_qa" / "golden" / "poc1_acceptance_set.json"
    receipt_path = repo / "artifacts" / "reviews" / "poc1-acceptance-review.json"
    identity_path = (
        repo
        / "gv100h"
        / "spec_qa"
        / "golden"
        / "poc1_acceptance_set.frozen_source_identity.json"
    )
    manifest_path.parent.mkdir(parents=True)
    receipt_path.parent.mkdir(parents=True)
    payload = _manifest_payload()
    _write_json(manifest_path, payload)
    _write_json(
        identity_path,
        frozen_identity_payload
        if frozen_identity_payload is not None
        else _frozen_identity_payload(payload),
    )

    subprocess.run(["git", "init", "--quiet", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "add",
            str(manifest_path.relative_to(repo)),
            str(identity_path.relative_to(repo)),
        ],
        check=True,
    )
    subprocess.run(["git", "-C", str(repo), "commit", "--quiet", "-m", "review manifest"], check=True)
    reviewed_commit = _git(repo, "rev-parse", "HEAD")

    loaded = load_poc1_acceptance_set(manifest_path)
    manifest_hash = compute_acceptance_set_hash(loaded)
    receipt = {
        "schema_name": "poc1_acceptance_review_receipt",
        "schema_version": "1.0",
        "reviewed_manifest_path": manifest_path.relative_to(repo).as_posix(),
        "reviewed_manifest_hash": manifest_hash,
        "reviewed_commit": reviewed_commit,
        "reviewer_id": loaded.reviewer_id,
        "reviewed_at": loaded.reviewed_at,
        "total_questions": loaded.total_questions,
        "passed_questions": loaded.total_questions,
        "changed_question_ids": [],
        "source_revisions": {source_id: "synthetic-revision" for source_id in SOURCE_IDS},
        "review_status": "approved",
    }
    receipt_bytes = _write_json(receipt_path, receipt)
    payload["review_receipt_hash"] = hashlib.sha256(receipt_bytes).hexdigest()
    _write_json(manifest_path, payload)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "add",
            str(manifest_path.relative_to(repo)),
            str(receipt_path.relative_to(repo)),
        ],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "--quiet", "-m", "bind review receipt"],
        check=True,
    )
    manifest = load_poc1_acceptance_set(manifest_path)
    details = [
        FinalQuestionResult(
            question_id=question.question_id,
            expected_status=question.expected_status,
            observed_status=question.expected_status,
            passed=True,
            retrieval_hit_at_1=True,
            grounded=True,
            citation_valid=True,
            citation_complete=True,
            fabricated_citation=False,
            authority_violation=False,
            scope_correct=True,
            boundary_correct=True,
            required_claims_present=True,
            forbidden_claim_detected=False,
            cited_evidence_ids=[],
        )
        for question in manifest.questions
    ]
    result = FinalPOC1EvaluationResult(
        total_questions=50,
        answer_question_count=48,
        conflict_question_count=1,
        abstain_question_count=1,
        retrieval_recall_at_1=100.0,
        grounded_answer_rate=100.0,
        citation_validity_rate=100.0,
        citation_completeness_rate=100.0,
        conflict_detection_rate=100.0,
        abstention_rate=100.0,
        fabricated_citations_count=0,
        authority_violations_count=0,
        all_gates_passed=True,
        details=details,
        dataset_hash=manifest_hash,
        acceptance_set_hash=manifest_hash,
        acceptance_set_path=str(manifest_path),
        corpus_receipt_path=manifest.corpus_receipt_path,
        corpus_receipt_hash=manifest.corpus_receipt_hash,
        review_receipt_path=manifest.review_receipt_path,
        review_receipt_hash=manifest.review_receipt_hash,
    )
    return repo, manifest_path, result


def _qa_result() -> QAEvaluationResult:
    return QAEvaluationResult(
        total_questions=30,
        cat_a_accuracy=100.0,
        cat_b_version_scope_accuracy=100.0,
        cat_c_abstain_rate=100.0,
        cat_d_adversarial_pass_rate=100.0,
        fabricated_citations_count=0,
        authority_violations_count=0,
        all_gates_passed=True,
        details=[],
        evidence_class="live_model_inference",
        admissible_for_model_qualification=True,
        endpoint_observed=True,
    )


def _coding_summary() -> ABExperimentSummary:
    return ABExperimentSummary(
        total_runs_per_arm=30,
        is_synthetic_simulation=True,
        evidence_class="synthetic_offline_scaffold",
        admissible_for_model_qualification=False,
        arm_a_prompt_only={},
        arm_b_governed_sidecar={},
        governance_benefit={},
    )


def test_acceptance_admission_verifies_manifest_receipt_and_reviewed_commit(tmp_path: Path):
    repo, manifest_path, result = _build_reviewed_repo(tmp_path)

    observed = verify_poc1_acceptance_admission(
        manifest_path=manifest_path,
        result=result,
        repo_root=repo,
    )

    assert observed["status"] == "verified"
    assert observed["acceptance_set_hash"] == result.acceptance_set_hash
    assert observed["reviewed_commit"]
    assert observed["reviewer_id"] == "reviewer-1"
    assert observed["passed_questions"] == 50


def test_acceptance_hash_excludes_self_referential_receipt_hash(tmp_path: Path):
    payload = _manifest_payload()
    first = load_poc1_acceptance_set(_write_json(tmp_path / "first.json", payload) and tmp_path / "first.json")
    payload["review_receipt_hash"] = "f" * 64
    second_path = tmp_path / "second.json"
    _write_json(second_path, payload)
    second = load_poc1_acceptance_set(second_path)

    assert compute_acceptance_set_hash(first) == compute_acceptance_set_hash(second)


def test_qualification_requires_verified_final_acceptance_binding(tmp_path: Path):
    repo, manifest_path, result = _build_reviewed_repo(tmp_path)
    decision = QualificationPolicyEvaluator().evaluate(
        _qa_result(),
        _coding_summary(),
        {"total_requests": 0, "corruption_count": 0, "hardware_observed": False},
        final_poc1_result=result,
        acceptance_set_path=manifest_path,
        acceptance_repo_root=repo,
    )

    gate = next(
        gate for gate in decision.gates
        if gate.gate_name == "spec_qa.final_acceptance_set_bound"
    )
    evaluation_gate = next(
        gate for gate in decision.gates
        if gate.gate_name == "spec_qa.final_acceptance_evaluation_passed"
    )
    assert gate.passed is True
    assert evaluation_gate.passed is True
    assert decision.acceptance_set_hash == result.acceptance_set_hash
    assert decision.review_receipt_path == result.review_receipt_path
    assert decision.details["acceptance_admission"]["status"] == "verified"
    assert decision.decision == "NO_GO — synthetic/offline scaffold only"


@pytest.mark.parametrize(
    "mutation",
    ["missing_result", "result_hash", "result_metric", "receipt"],
)
def test_qualification_rejects_missing_or_tampered_acceptance_binding(
    tmp_path: Path,
    mutation: str,
):
    repo, manifest_path, result = _build_reviewed_repo(tmp_path)
    if mutation == "missing_result":
        result = None
    elif mutation == "result_hash":
        result = result.model_copy(update={"acceptance_set_hash": "0" * 64})
    elif mutation == "result_metric":
        result = result.model_copy(update={"retrieval_recall_at_1": 0.0})
    else:
        receipt_path = repo / "artifacts" / "reviews" / "poc1-acceptance-review.json"
        receipt_path.write_text("{}", encoding="utf-8")

    decision = QualificationPolicyEvaluator().evaluate(
        _qa_result(),
        _coding_summary(),
        {"total_requests": 0, "corruption_count": 0, "hardware_observed": False},
        final_poc1_result=result,
        acceptance_set_path=manifest_path,
        acceptance_repo_root=repo,
    )
    gate = next(
        gate for gate in decision.gates
        if gate.gate_name == "spec_qa.final_acceptance_set_bound"
    )
    evaluation_gate = next(
        gate for gate in decision.gates
        if gate.gate_name == "spec_qa.final_acceptance_evaluation_passed"
    )
    assert gate.passed is False
    assert evaluation_gate.passed is False
    assert decision.decision_boundary_state == "acceptance_not_bound"


def test_admission_rejects_reviewed_commit_with_wrong_manifest(tmp_path: Path):
    repo, manifest_path, result = _build_reviewed_repo(tmp_path)
    tampered = result.model_copy(update={"review_receipt_hash": "0" * 64})

    with pytest.raises(POC1AdmissionError, match="review_receipt_hash"):
        verify_poc1_acceptance_admission(
            manifest_path=manifest_path,
            result=tampered,
            repo_root=repo,
        )


@pytest.mark.parametrize("mutation", ["empty_revision", "unknown_question"])
def test_admission_rejects_invalid_review_receipt_metadata(
    tmp_path: Path,
    mutation: str,
):
    repo, manifest_path, result = _build_reviewed_repo(tmp_path)
    receipt_path = repo / "artifacts" / "reviews" / "poc1-acceptance-review.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if mutation == "empty_revision":
        receipt["source_revisions"]["usb32"] = ""
    else:
        receipt["changed_question_ids"] = ["QA-UNKNOWN"]
    receipt_bytes = json.dumps(
        receipt,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    receipt_path.write_bytes(receipt_bytes)

    with pytest.raises(POC1AdmissionError):
        verify_poc1_acceptance_admission(
            manifest_path=manifest_path,
            result=result,
            repo_root=repo,
        )


def test_admission_rejects_disjoint_source_set_identity(tmp_path: Path):
    """A manifest whose admitted question IDs have zero overlap with the
    frozen source-set identity must be rejected outright, not silently
    treated as an unrelated/unchecked question set."""
    payload = _manifest_payload()
    disjoint_identity = {
        "questions": [
            {
                "question_id": "SOMETHING-ELSE-ENTIRELY",
                "accepted_source_ids": ["usb20_fw"],
            }
        ]
    }
    repo, manifest_path, result = _build_reviewed_repo(
        tmp_path, frozen_identity_payload=disjoint_identity
    )

    with pytest.raises(POC1AdmissionError, match="source-set identity"):
        verify_poc1_acceptance_admission(
            manifest_path=manifest_path,
            result=result,
            repo_root=repo,
        )


def test_admission_rejects_tampered_source_set_identity(tmp_path: Path):
    """Once frozen, silently narrowing/widening an already-approved
    question's accepted_source_ids must be rejected even though the question
    IDs still overlap the frozen identity."""
    payload = _manifest_payload()
    frozen = _frozen_identity_payload(payload)
    frozen["questions"][0] = dict(frozen["questions"][0])
    frozen["questions"][0]["accepted_source_ids"] = ["usb20_fw", "usb32"]
    repo, manifest_path, result = _build_reviewed_repo(
        tmp_path, frozen_identity_payload=frozen
    )

    with pytest.raises(POC1AdmissionError, match="source-set identity"):
        verify_poc1_acceptance_admission(
            manifest_path=manifest_path,
            result=result,
            repo_root=repo,
        )


def test_admission_requires_frozen_source_set_identity_artifact(tmp_path: Path):
    """The frozen identity must be a real, git-tracked artifact under
    repo_root -- if it is missing, admission must fail closed rather than
    silently skip the identity check."""
    repo, manifest_path, result = _build_reviewed_repo(tmp_path)
    identity_path = (
        repo
        / "gv100h"
        / "spec_qa"
        / "golden"
        / "poc1_acceptance_set.frozen_source_identity.json"
    )
    identity_path.unlink()

    with pytest.raises(POC1AdmissionError, match="missing or invalid"):
        verify_poc1_acceptance_admission(
            manifest_path=manifest_path,
            result=result,
            repo_root=repo,
        )