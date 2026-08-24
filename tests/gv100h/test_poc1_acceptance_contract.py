from __future__ import annotations

import json
from pathlib import Path

import pytest

from gv100h.spec_qa.contracts.poc1_acceptance_contract import (
    AcceptanceContractError,
    load_poc1_acceptance_set,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SMOKE_DATASET = PROJECT_ROOT / "gv100h" / "spec_qa" / "golden" / "dataset_30.json"


def _question(index: int, layer: str, category: str) -> dict:
    expected_status = "abstain" if index == 50 else "conflict" if index == 49 else "answer"
    accepted_source_ids = (
        []
        if index == 50
        else ["usb20_fw", "usb32"]
        if index == 49
        else ["usb32"]
    )
    return {
        "question_id": f"QA-{index:03d}",
        "layer": layer,
        "priority": "P0" if layer != "L3" else "P1",
        "category": category,
        "question": f"Independent question {index}",
        "expected_status": expected_status,
        "expected_scope": "USB4_SPEC" if index == 50 else "USB_HUB_COMMON",
        "accepted_source_ids": accepted_source_ids,
        "required_citation_fields": {
            "document": True,
            "revision": True,
            "section": True,
            "page_or_anchor": True,
            "excerpt_or_evidence_id": True,
        },
        "independently_reviewed": True,
        "usb4_negative_control": index == 50,
    }


def _valid_manifest() -> dict:
    questions = []
    for index in range(1, 51):
        if index <= 13:
            layer, category = "L1", "single_spec_fact"
        elif index <= 26:
            layer, category = "L2", "engineering_interpretation"
        elif index <= 38:
            layer, category = "L3", "cross_document"
        else:
            layer, category = "L4", "uncertainty_conflict"
        questions.append(_question(index, layer, category))
    return {
        "schema_name": "poc1_spec_qa_acceptance_set",
        "schema_version": "1.0",
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
        "reviewer_id": "independent-reviewer",
        "reviewed_at": "2026-08-24T00:00:00Z",
        "total_questions": 50,
        "required_layers": {"L1": 10, "L2": 10, "L3": 10, "L4": 10},
        "required_source_ids": [
            "hub_reference",
            "usb20_fw",
            "usb20_se",
            "usb32",
            "superspeed_hub_lvs",
        ],
        "questions": questions,
    }


def _write_manifest(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "acceptance.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_smoke_dataset_is_not_admitted_as_final_acceptance_set(tmp_path: Path):
    smoke = json.loads(SMOKE_DATASET.read_text(encoding="utf-8"))
    smoke.update(
        {
            "schema_name": "poc1_spec_qa_acceptance_set",
            "schema_version": "1.0",
            "corpus_receipt_path": "artifacts/evidence/test-results/corpus.json",
            "corpus_receipt_hash": "a" * 64,
            "benchmark_role": "poc1_acceptance_set",
            "independent_review_complete": True,
            "required_layers": {"L1": 10, "L2": 10, "L3": 10, "L4": 10},
            "required_source_ids": ["usb32"],
        }
    )

    with pytest.raises(AcceptanceContractError, match="50|layer L3"):
        load_poc1_acceptance_set(_write_manifest(tmp_path, smoke))


def test_valid_acceptance_set_contract_loads(tmp_path: Path):
    payload = _valid_manifest()
    for index, source_id in enumerate(
        ["hub_reference", "usb20_fw", "usb20_se", "usb32", "superspeed_hub_lvs"]
    ):
        payload["questions"][index]["accepted_source_ids"] = [source_id]
    manifest = load_poc1_acceptance_set(_write_manifest(tmp_path, payload))

    assert manifest.total_questions == 50
    assert manifest.benchmark_role == "poc1_acceptance_set"
    assert sum(item.usb4_negative_control for item in manifest.questions) == 1


@pytest.mark.parametrize(
    "mutation,expected_message",
    [
        ("duplicate_id", "duplicate question_id"),
        ("foreign_source", "outside required_source_ids"),
        ("extra_source", "exactly match POC-1 sources"),
        ("missing_layer", "layer L4"),
        ("usb4_answer", "must abstain"),
        ("abstain_with_source", "abstain question"),
        ("usb4_layer_mismatch", "must be an L4 uncertainty_conflict question"),
        ("missing_citation_field", "must require all citation fields"),
        ("answer_without_source", "requires an accepted source"),
        ("category_mismatch", "category does not match"),
        ("priority_mismatch", "priority must be P0"),
        ("l3_priority_mismatch", "priority must be P1"),
        ("usb4_scope_mismatch", "must use USB4_SPEC scope"),
        ("conflict_without_competing_source", "at least two competing sources"),
        ("missing_source_coverage", "lacks question coverage for"),
        ("missing_usb4_control", "requires at least one USB4 negative control"),
        ("review_receipt_path", "durable artifacts/ path"),
    ],
)
def test_acceptance_set_rejects_contract_violations(
    tmp_path: Path, mutation: str, expected_message: str
):
    manifest = _valid_manifest()
    if mutation == "duplicate_id":
        manifest["questions"][1]["question_id"] = manifest["questions"][0]["question_id"]
    elif mutation == "foreign_source":
        manifest["questions"][0]["accepted_source_ids"] = ["not_locked"]
    elif mutation == "extra_source":
        manifest["required_source_ids"].append("not_locked")
    elif mutation == "missing_layer":
        for question in manifest["questions"]:
            if question["layer"] == "L4":
                question["layer"] = "L1"
                question["category"] = "single_spec_fact"
                question["priority"] = "P0"
                question["usb4_negative_control"] = False
    elif mutation == "missing_citation_field":
        manifest["questions"][0]["required_citation_fields"]["section"] = False
    elif mutation == "answer_without_source":
        manifest["questions"][0]["accepted_source_ids"] = []
    elif mutation == "category_mismatch":
        manifest["questions"][0]["category"] = "cross_document"
    elif mutation == "priority_mismatch":
        manifest["questions"][0]["priority"] = "P1"
    elif mutation == "l3_priority_mismatch":
        manifest["questions"][26]["priority"] = "P0"
    elif mutation == "usb4_scope_mismatch":
        manifest["questions"][50 - 1]["expected_scope"] = "USB_HUB_COMMON"
    elif mutation == "usb4_layer_mismatch":
        manifest["questions"][49]["layer"] = "L1"
        manifest["questions"][49]["category"] = "single_spec_fact"
        manifest["questions"][49]["priority"] = "P0"
    elif mutation == "abstain_with_source":
        manifest["questions"][49]["accepted_source_ids"] = ["usb32"]
    elif mutation == "conflict_without_competing_source":
        manifest["questions"][48]["accepted_source_ids"] = ["usb32"]
    elif mutation == "missing_source_coverage":
        for question in manifest["questions"]:
            if question["expected_status"] == "answer":
                question["accepted_source_ids"] = ["usb20_fw"]
            elif question["expected_status"] == "conflict":
                question["accepted_source_ids"] = ["usb20_fw", "usb20_se"]
    elif mutation == "missing_usb4_control":
        manifest["questions"][49]["usb4_negative_control"] = False
    elif mutation == "review_receipt_path":
        manifest["review_receipt_path"] = "review/poc1.json"
    else:
        manifest["questions"][49]["accepted_source_ids"] = ["usb32"]
        manifest["questions"][49]["expected_status"] = "answer"

    with pytest.raises(AcceptanceContractError, match=expected_message):
        load_poc1_acceptance_set(_write_manifest(tmp_path, manifest))
