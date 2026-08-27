from __future__ import annotations

import json
from pathlib import Path

import pytest

from gv100h.spec_qa.evaluation.final_evaluator import FinalPOC1Evaluator


PROJECT_ROOT = Path(__file__).resolve().parents[2]
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
            "forbidden_claims": ["forbidden-49"],
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
                {
                    "claim_id": "CLAIM-50-BOUNDARY",
                    "assertion": "out-of-scope-boundary",
                }
            ],
            "section_anchors": [],
            "required_facts": [],
            "forbidden_claims": ["forbidden-50"],
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
                {"claim_id": f"CLAIM-{index}", "assertion": f"fact-{index}"}
            ],
            "section_anchors": (
                [f"{primary}:section-{index}-a", f"{secondary}:section-{index}-b"]
                if layer == "L3"
                else [f"section-{index}"]
            ),
            "required_facts": [f"fact-{index}"],
            "forbidden_claims": [f"forbidden-{index}"],
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
        "question": f"question-{index}",
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
        "question_style": "user_realistic",
    }


def _manifest() -> dict:
    return {
        "schema_name": "poc1_spec_qa_acceptance_set",
        "schema_version": "1.2",
        "corpus_lock": "gv100h/spec_qa/contracts/corpus.lock.yaml",
        "corpus_receipt_path": "artifacts/evidence/test-results/corpus.json",
        "corpus_receipt_hash": "a" * 64,
        "dataset_version": "2.0.0",
        "benchmark_role": "poc1_acceptance_set",
        "generated_from_corpus": False,
        "independent_from_corpus": True,
        "independent_review_complete": True,
        "review_receipt_path": "artifacts/reviews/poc1-acceptance-review.json",
        "review_receipt_hash": "b" * 64,
        "reviewer_id": "synthetic-independent-reviewer",
        "reviewed_at": "2026-08-25T00:00:00Z",
        "total_questions": 50,
        "required_layers": {"L1": 10, "L2": 10, "L3": 10, "L4": 10},
        "required_source_ids": SOURCE_IDS,
        "questions": [_question(index) for index in range(1, 51)],
    }


class SyntheticEvidenceResolver:
    def __init__(self, manifest: dict):
        self._ids = {
            evidence_id
            for question in manifest["questions"]
            for evidence_id in (
                question["gold"]["accepted_evidence_ids"]
                + question["gold"]["competing_evidence_ids"]
                + question["gold"]["boundary_evidence_ids"]
            )
        }

    def get_evidence_by_id(self, evidence_id: str):
        return object() if evidence_id in self._ids else None


def _response(index: int) -> dict:
    question = _question(index)
    status = question["expected_status"]
    if status == "answer":
        return {
            "status": status,
            "claims": [f"fact-{index}"],
            "citations": [
                {
                    "evidence_id": evidence_id,
                    "document": "USB synthetic source",
                    "revision": "synthetic revision",
                    "section": section,
                    "page_or_anchor": section,
                    "excerpt_or_evidence_id": evidence_id,
                    "scope": question["expected_scope"],
                }
                for evidence_id, section in zip(
                    question["gold"]["accepted_evidence_ids"],
                    question["gold"]["section_anchors"],
                )
            ],
            "scope": question["expected_scope"],
            "boundary_code": None,
        }
    if status == "conflict":
        return {
            "status": status,
            "claims": ["claim-a-49", "claim-b-49"],
            "citations": [
                {
                    "evidence_id": evidence_id,
                    "document": "USB synthetic source",
                    "revision": "synthetic revision",
                    "section": section,
                    "page_or_anchor": section,
                    "excerpt_or_evidence_id": evidence_id,
                    "scope": question["expected_scope"],
                }
                for evidence_id, section in (
                    ("EVIDENCE-49-A", "section-49-a"),
                    ("EVIDENCE-49-B", "section-49-b"),
                )
            ],
            "scope": question["expected_scope"],
            "boundary_code": "UNRESOLVED_CONFLICT",
        }
    return {
        "status": status,
        "claims": ["out-of-scope-boundary"],
        "citations": [
            {
                "evidence_id": "BOUNDARY-50",
                "excerpt_or_evidence_id": "BOUNDARY-50",
                "scope": question["expected_scope"],
            }
        ],
        "scope": question["expected_scope"],
        "boundary_code": "OUT_OF_SCOPE",
    }


def _write_manifest(tmp_path: Path) -> tuple[dict, Path]:
    manifest = _manifest()
    path = tmp_path / "poc1-acceptance-set.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest, path


def test_final_evaluator_scores_structured_oracles(tmp_path: Path):
    manifest, path = _write_manifest(tmp_path)
    evaluator = FinalPOC1Evaluator(
        str(path),
        evidence_resolver=SyntheticEvidenceResolver(manifest),
    )

    result = evaluator.run_benchmark(
        lambda query, _scope: _response(int(query.split("-")[-1]))
    )

    assert result.total_questions == 50
    assert result.answer_question_count == 48
    assert result.conflict_question_count == 1
    assert result.abstain_question_count == 1
    assert result.retrieval_recall_at_1 == 100.0
    assert result.grounded_answer_rate == 100.0
    assert result.citation_validity_rate == 100.0
    assert result.citation_completeness_rate == 100.0
    assert result.conflict_detection_rate == 100.0
    assert result.abstention_rate == 100.0
    assert result.fabricated_citations_count == 0
    assert result.authority_violations_count == 0
    assert result.all_gates_passed is True
    assert len(result.acceptance_set_hash) == 64
    assert result.dataset_hash == result.acceptance_set_hash
    assert result.review_receipt_path == "artifacts/reviews/poc1-acceptance-review.json"
    assert result.admissible_for_model_qualification is False


def test_final_evaluator_rejects_scope_mismatch_and_invalid_status(tmp_path: Path):
    manifest, path = _write_manifest(tmp_path)
    evaluator = FinalPOC1Evaluator(
        str(path),
        evidence_resolver=SyntheticEvidenceResolver(manifest),
    )

    wrong_scope = _response(1)
    wrong_scope["scope"] = "USB4_SPEC"
    wrong_scope_result = evaluator.evaluate_response(
        evaluator.manifest.questions[0],
        wrong_scope,
    )
    assert wrong_scope_result.passed is False
    assert wrong_scope_result.scope_correct is False
    assert wrong_scope_result.grounded is False

    invalid_status = _response(1)
    invalid_status["status"] = "unknown"
    invalid_result = evaluator.evaluate_response(
        evaluator.manifest.questions[0],
        invalid_status,
    )
    assert invalid_result.passed is False
    assert invalid_result.observed_status == "invalid"
    assert invalid_result.authority_violation is True


def test_final_evaluator_rejects_normative_fields_on_abstain(tmp_path: Path):
    manifest, path = _write_manifest(tmp_path)
    evaluator = FinalPOC1Evaluator(
        str(path),
        evidence_resolver=SyntheticEvidenceResolver(manifest),
    )
    response = _response(50)
    response["citations"][0]["document"] = "USB4 document not in corpus"

    result = evaluator.evaluate_response(
        evaluator.manifest.questions[49],
        response,
    )

    assert result.passed is False
    assert result.citation_complete is False


def test_final_evaluator_rejects_unknown_evidence_and_wrong_status(tmp_path: Path):
    manifest, path = _write_manifest(tmp_path)
    evaluator = FinalPOC1Evaluator(
        str(path),
        evidence_resolver=SyntheticEvidenceResolver(manifest),
    )

    unknown = _response(1)
    unknown["citations"][0]["evidence_id"] = "UNKNOWN-EVIDENCE"
    unknown_result = evaluator.evaluate_response(
        evaluator.manifest.questions[0],
        unknown,
    )
    assert unknown_result.passed is False
    assert unknown_result.fabricated_citation is True
    assert unknown_result.authority_violation is True

    wrong_status = _response(50)
    wrong_status["status"] = "answer"
    wrong_result = evaluator.evaluate_response(
        evaluator.manifest.questions[49],
        wrong_status,
    )
    assert wrong_result.passed is False
    assert wrong_result.observed_status == "answer"
    assert wrong_result.grounded is False


def _constructed_same_object_conflict_question() -> dict:
    """Artificial X / not-X pair. Not a USB-spec gold item."""
    return {
        "question_id": "FIXTURE-CONFLICT-001",
        "layer": "L4",
        "priority": "P0",
        "category": "uncertainty_conflict",
        "question": (
            "Source A states that object PORT_X in state S under revision R "
            "has property P=true. Source B states that the same object "
            "PORT_X in the same state S under the same revision R has "
            "property P=false. What status should be returned?"
        ),
        "expected_status": "conflict",
        "expected_scope": "USB_HUB_COMMON",
        "accepted_source_ids": ["usb20_fw", "usb32"],
        "required_citation_fields": {
            "document": True,
            "revision": True,
            "section": True,
            "page_or_anchor": True,
            "excerpt_or_evidence_id": True,
            "scope": True,
            "boundary_code": True,
            "mode": "competing_sources",
        },
        "gold": {
            "accepted_evidence_ids": [],
            "competing_evidence_ids": ["EVIDENCE-X", "EVIDENCE-NOT-X"],
            "boundary_evidence_ids": [],
            "required_claims": [
                {
                    "claim_id": "CLAIM-X",
                    "assertion": "Source A asserts P=true for PORT_X in state S at revision R",
                },
                {
                    "claim_id": "CLAIM-NOT-X",
                    "assertion": "Source B asserts P=false for PORT_X in state S at revision R",
                },
            ],
            "section_anchors": ["source-a-same-object", "source-b-same-object"],
            "required_facts": [
                "same object PORT_X",
                "same state S",
                "same revision R",
            ],
            "forbidden_claims": ["scope difference only"],
            "acceptable_variants": [],
            "boundary_code": "UNRESOLVED_CONFLICT",
        },
        "grading": {
            "factual_correctness": 0.40,
            "citation_correctness": 0.25,
            "source_authority": 0.15,
            "scope_control": 0.10,
            "uncertainty_behavior": 0.10,
        },
        "independently_reviewed": True,
        "usb4_negative_control": False,
        "question_style": "diagnostic",
    }


def _constructed_conflict_response() -> dict:
    return {
        "status": "conflict",
        "claims": [
            "Source A asserts P=true for PORT_X in state S at revision R",
            "Source B asserts P=false for PORT_X in state S at revision R",
            "same object PORT_X",
            "same state S",
            "same revision R",
        ],
        "citations": [
            {
                "evidence_id": "EVIDENCE-X",
                "document": "Constructed source A",
                "revision": "R",
                "section": "source-a-same-object",
                "page_or_anchor": "source-a-same-object",
                "excerpt_or_evidence_id": "EVIDENCE-X",
                "scope": "USB_HUB_COMMON",
            },
            {
                "evidence_id": "EVIDENCE-NOT-X",
                "document": "Constructed source B",
                "revision": "R",
                "section": "source-b-same-object",
                "page_or_anchor": "source-b-same-object",
                "excerpt_or_evidence_id": "EVIDENCE-NOT-X",
                "scope": "USB_HUB_COMMON",
            },
        ],
        "scope": "USB_HUB_COMMON",
        "boundary_code": "UNRESOLVED_CONFLICT",
    }


def test_constructed_same_object_conflict_path_is_detected(tmp_path: Path):
    manifest = _manifest()
    manifest["questions"][48] = _constructed_same_object_conflict_question()
    path = tmp_path / "constructed-conflict.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    evaluator = FinalPOC1Evaluator(
        str(path),
        evidence_resolver=SyntheticEvidenceResolver(manifest),
    )
    question = evaluator.manifest.questions[48]

    passed = evaluator.evaluate_response(question, _constructed_conflict_response())
    assert passed.passed is True
    assert passed.expected_status == "conflict"
    assert passed.observed_status == "conflict"
    assert passed.boundary_correct is True

    collapsed = _constructed_conflict_response()
    collapsed["status"] = "answer"
    collapsed["boundary_code"] = None
    collapsed["claims"] = ["scope difference only"]
    collapsed_result = evaluator.evaluate_response(question, collapsed)
    assert collapsed_result.passed is False
    assert collapsed_result.observed_status == "answer"
    assert collapsed_result.forbidden_claim_detected is True


def _constructed_multi_source_answer_question() -> dict:
    """L3-shaped gold with two required sources and two interchangeable
    evidence alternates for one of them. Regression fixture for the
    per-required-source citation coverage check."""
    return {
        "question_id": "FIXTURE-MULTISRC-001",
        "layer": "L3",
        "priority": "P1",
        "category": "cross_document",
        "question": "Constructed cross-document coverage question.",
        "expected_status": "answer",
        "expected_scope": "USB_HUB_COMMON",
        "accepted_source_ids": ["usb20_fw", "usb32"],
        "required_citation_fields": {
            "document": True,
            "revision": True,
            "section": True,
            "page_or_anchor": True,
            "excerpt_or_evidence_id": True,
            "scope": True,
            "boundary_code": False,
            "mode": "normative_source",
        },
        "gold": {
            "accepted_evidence_ids": [
                "usb20_fw:E1",
                "usb20_fw:E2",
                "usb32:E3",
            ],
            "competing_evidence_ids": [],
            "boundary_evidence_ids": [],
            "required_claims": [
                {
                    "claim_id": "CLAIM-MULTISRC",
                    "assertion": "multi-source fact",
                }
            ],
            "section_anchors": [
                "usb20_fw:section-e1",
                "usb20_fw:section-e2",
                "usb32:section-e3",
            ],
            "required_facts": ["multi-source fact"],
            "forbidden_claims": ["unsupported-multisrc"],
            "acceptable_variants": [],
            "boundary_code": None,
        },
        "grading": {
            "factual_correctness": 0.40,
            "citation_correctness": 0.25,
            "source_authority": 0.15,
            "scope_control": 0.10,
            "uncertainty_behavior": 0.10,
        },
        "independently_reviewed": True,
        "usb4_negative_control": False,
        "question_style": "user_realistic",
    }


def _multi_source_response(evidence_ids: list[str]) -> dict:
    return {
        "status": "answer",
        "claims": ["multi-source fact"],
        "citations": [
            {
                "evidence_id": evidence_id,
                "document": "USB synthetic source",
                "revision": "synthetic revision",
                "section": evidence_id,
                "page_or_anchor": evidence_id,
                "excerpt_or_evidence_id": evidence_id,
                "scope": "USB_HUB_COMMON",
            }
            for evidence_id in evidence_ids
        ],
        "scope": "USB_HUB_COMMON",
        "boundary_code": None,
    }


def test_multi_source_answer_citing_only_one_required_source_fails(tmp_path: Path):
    """L3 gold requires usb20_fw + usb32 coverage. Citing only usb20_fw's
    evidence must not pass, even though that one citation is individually
    legitimate (closes the P1 gap: subset-only checks let a model answer
    a multi-source question from a single source)."""
    manifest = _manifest()
    manifest["questions"][26] = _constructed_multi_source_answer_question()
    path = tmp_path / "constructed-multisource.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    evaluator = FinalPOC1Evaluator(
        str(path),
        evidence_resolver=SyntheticEvidenceResolver(manifest),
    )
    question = evaluator.manifest.questions[26]

    result = evaluator.evaluate_response(
        question, _multi_source_response(["usb20_fw:E1"])
    )

    assert result.citation_valid is False
    assert result.grounded is False
    assert result.passed is False


def test_multi_source_answer_accepts_alternate_evidence_per_source(tmp_path: Path):
    """Citing a different, still-valid evidence id for one of the required
    sources (an alternate, not the first-listed gold id) must still pass,
    as long as every required source is covered by at least one citation."""
    manifest = _manifest()
    manifest["questions"][26] = _constructed_multi_source_answer_question()
    path = tmp_path / "constructed-multisource.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    evaluator = FinalPOC1Evaluator(
        str(path),
        evidence_resolver=SyntheticEvidenceResolver(manifest),
    )
    question = evaluator.manifest.questions[26]

    result = evaluator.evaluate_response(
        question, _multi_source_response(["usb20_fw:E2", "usb32:E3"])
    )

    assert result.citation_valid is True
    assert result.grounded is True
    assert result.passed is True