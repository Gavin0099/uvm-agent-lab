from __future__ import annotations

import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DRAFT_PATH = (
    PROJECT_ROOT
    / "gv100h"
    / "spec_qa"
    / "golden"
    / "poc1_acceptance_set.draft.json"
)
ADMITTED_MANIFEST_PATH = DRAFT_PATH.with_name("poc1_acceptance_set.json")
REQUIRED_SOURCE_IDS = [
    "hub_reference",
    "usb20_fw",
    "usb20_se",
    "usb32",
    "superspeed_hub_lvs",
]
EXPECTED_CATEGORY_BY_LAYER = {
    "L1": "single_spec_fact",
    "L2": "engineering_interpretation",
    "L3": "cross_document",
    "L4": "uncertainty_conflict",
}
GENERIC_CONTEXT_PATTERN = re.compile(
    r"Chapter N|declared|selected|this query|the declared Chapter",
    re.IGNORECASE,
)


def test_poc1_authoring_draft_is_consistent_and_not_admitted():
    payload = json.loads(DRAFT_PATH.read_text(encoding="utf-8"))
    questions = payload["questions"]

    layer_counts = {
        layer: sum(question["layer"] == layer for question in questions)
        for layer in ("L1", "L2", "L3", "L4")
    }
    conflict_count = sum(
        question["expected_status"] == "conflict" for question in questions
    )
    abstain_count = sum(
        question["expected_status"] == "abstain" for question in questions
    )
    usb4_control_count = sum(
        question["usb4_negative_control"] for question in questions
    )

    assert payload["status"] == "draft_not_admitted"
    assert payload["benchmark_role"] == "acceptance_authoring_draft"
    assert payload["generated_from_corpus"] is False
    assert payload["total_questions"] == len(questions) == 50
    assert payload["required_source_ids"] == REQUIRED_SOURCE_IDS
    assert layer_counts == payload["coverage_status"]["layer_counts"]
    assert all(
        layer_counts[layer] >= minimum
        for layer, minimum in payload["required_layers"].items()
    )
    assert conflict_count == payload["coverage_status"]["conflict_question_count"] == 5
    assert abstain_count == payload["coverage_status"]["abstain_question_count"] == 7
    assert (
        usb4_control_count
        == payload["coverage_status"]["usb4_negative_control_count"]
        == 2
    )
    assert all(
        payload["coverage_status"]["source_question_coverage"][source_id]
        for source_id in REQUIRED_SOURCE_IDS
    )
    assert all(
        question["category"] == EXPECTED_CATEGORY_BY_LAYER[question["layer"]]
        and question["priority"] == ("P1" if question["layer"] == "L3" else "P0")
        for question in questions
    )
    assert all(
        set(question["accepted_source_ids"]).issubset(REQUIRED_SOURCE_IDS)
        for question in questions
    )
    assert all(
        (
            question["expected_status"] == "answer"
            and question["accepted_source_ids"]
        )
        or (
            question["expected_status"] == "abstain"
            and not question["accepted_source_ids"]
        )
        or (
            question["expected_status"] == "conflict"
            and len(question["accepted_source_ids"]) >= 2
        )
        for question in questions
    )
    assert all(
        all(question["required_citation_fields"].values()) for question in questions
    )
    assert all(
        not question["usb4_negative_control"]
        or (
            question["layer"] == "L4"
            and question["category"] == "uncertainty_conflict"
            and question["expected_status"] == "abstain"
            and question["expected_scope"] == "USB4_SPEC"
        )
        for question in questions
    )

    question_ids = [question["question_id"] for question in questions]
    assert len(question_ids) == len(set(question_ids))
    assert all(
        not GENERIC_CONTEXT_PATTERN.search(question["question"])
        for question in questions
    )
    assert all(question["independently_reviewed"] is False for question in questions)
    assert payload["independent_review_complete"] is False
    assert payload["review_status"] == "required"
    assert all(
        payload[field] is None
        for field in (
            "review_receipt_path",
            "review_receipt_hash",
            "reviewer_id",
            "reviewed_at",
        )
    )
    assert not ADMITTED_MANIFEST_PATH.exists()