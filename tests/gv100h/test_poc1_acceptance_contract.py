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
    if expected_status == "answer":
        gold = {
            "accepted_evidence_ids": [f"EVIDENCE-{index}-A"],
            "competing_evidence_ids": [],
            "boundary_evidence_ids": [],
            "required_claims": [
                {
                    "claim_id": f"CLAIM-{index}-A",
                    "assertion": f"Required answer fact {index}",
                }
            ],
            "section_anchors": [f"section-{index}"],
            "required_facts": [f"fact-{index}"],
            "forbidden_claims": [f"unsupported-{index}"],
            "acceptable_variants": [f"variant-{index}"],
            "boundary_code": None,
        }
        citation = {
            "document": True,
            "revision": True,
            "chapter": True,
            "section": True,
            "page_or_anchor": True,
            "excerpt_or_evidence_id": True,
            "authority_level": True,
            "scope": True,
            "boundary_code": False,
            "mode": "normative_source",
        }
    elif expected_status == "conflict":
        gold = {
            "accepted_evidence_ids": [],
            "competing_evidence_ids": [
                f"EVIDENCE-{index}-A",
                f"EVIDENCE-{index}-B",
            ],
            "boundary_evidence_ids": [],
            "required_claims": [
                {
                    "claim_id": f"CLAIM-{index}-A",
                    "assertion": f"Competing claim A for {index}",
                },
                {
                    "claim_id": f"CLAIM-{index}-B",
                    "assertion": f"Competing claim B for {index}",
                },
            ],
            "section_anchors": [f"section-{index}-a", f"section-{index}-b"],
            "required_facts": [f"fact-{index}-a", f"fact-{index}-b"],
            "forbidden_claims": [f"unresolved-{index}"],
            "acceptable_variants": [],
            "boundary_code": "UNRESOLVED_CONFLICT",
        }
        citation = {
            "document": True,
            "revision": True,
            "chapter": True,
            "section": True,
            "page_or_anchor": True,
            "excerpt_or_evidence_id": True,
            "authority_level": True,
            "scope": True,
            "boundary_code": True,
            "mode": "competing_sources",
        }
    else:
        gold = {
            "accepted_evidence_ids": [],
            "competing_evidence_ids": [],
            "boundary_evidence_ids": [f"BOUNDARY-{index}"],
            "required_claims": [
                {
                    "claim_id": f"CLAIM-{index}-BOUNDARY",
                    "assertion": f"Return the declared boundary for {index}",
                }
            ],
            "section_anchors": [],
            "required_facts": [],
            "forbidden_claims": [f"unsupported-{index}"],
            "acceptable_variants": [],
            "boundary_code": "OUT_OF_SCOPE" if index == 50 else "MISSING_EVIDENCE",
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
    return {
        "question_id": f"QA-{index:03d}",
        "layer": layer,
        "priority": "P0" if layer != "L3" else "P1",
        "category": category,
        "question": f"Independent question {index}",
        "expected_status": expected_status,
        "expected_scope": "USB4_SPEC" if index == 50 else "USB_HUB_COMMON",
        "accepted_source_ids": accepted_source_ids,
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
            "schema_version": "1.1",
            "corpus_receipt_path": "artifacts/evidence/test-results/corpus.json",
            "corpus_receipt_hash": "a" * 64,
            "benchmark_role": "poc1_acceptance_set",
            "independent_review_complete": True,
            "required_layers": {"L1": 10, "L2": 10, "L3": 10, "L4": 10},
            "required_source_ids": ["usb32"],
        }
    )

    with pytest.raises(AcceptanceContractError, match="gold|50|layer L3"):
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
        ("missing_citation_field", "must require normative source citation fields"),
        ("missing_gold_evidence", "requires gold accepted evidence"),
        ("empty_gold_evidence", "gold evidence IDs must be non-empty"),
        ("missing_required_claim", "requires gold claims, facts, and section anchors"),
        ("blank_gold_fact", "gold facts must be non-empty"),
        ("blank_section_anchor", "gold section anchors must be non-empty"),
        ("conflict_optional_claims", "requires two gold claims and section anchors"),
        ("abstain_optional_claim", "requires boundary evidence and a boundary claim"),
        ("conflict_gold_single", "at least two gold competing evidence IDs"),
        ("abstain_normative_citation", "must not require normative citation fields"),
        ("missing_boundary_evidence", "requires boundary evidence"),
        ("answer_boundary_citation", "must require normative source citation fields"),
        ("conflict_missing_scope", "requires competing-source citation fields"),
        ("grading_drift", "grading weights must sum to 1.0"),
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
    elif mutation == "missing_gold_evidence":
        manifest["questions"][0]["gold"]["accepted_evidence_ids"] = []
    elif mutation == "blank_gold_fact":
        manifest["questions"][0]["gold"]["required_facts"] = [" "]
    elif mutation == "blank_section_anchor":
        manifest["questions"][0]["gold"]["section_anchors"] = ["\t"]
    elif mutation == "conflict_optional_claims":
        for claim in manifest["questions"][48]["gold"]["required_claims"]:
            claim["required"] = False
    elif mutation == "abstain_optional_claim":
        manifest["questions"][49]["gold"]["required_claims"][0]["required"] = False
    elif mutation == "empty_gold_evidence":
        manifest["questions"][0]["gold"]["accepted_evidence_ids"] = [""]
    elif mutation == "missing_required_claim":
        manifest["questions"][0]["gold"]["required_claims"][0]["required"] = False
    elif mutation == "conflict_gold_single":
        manifest["questions"][48]["gold"]["competing_evidence_ids"] = [
            "EVIDENCE-49-A"
        ]
    elif mutation == "abstain_normative_citation":
        manifest["questions"][49]["required_citation_fields"]["document"] = True
    elif mutation == "missing_boundary_evidence":
        manifest["questions"][49]["gold"]["boundary_evidence_ids"] = []
    elif mutation == "answer_boundary_citation":
        manifest["questions"][0]["required_citation_fields"]["boundary_code"] = True
    elif mutation == "conflict_missing_scope":
        manifest["questions"][48]["required_citation_fields"]["scope"] = False
    elif mutation == "grading_drift":
        manifest["questions"][0]["grading"]["factual_correctness"] = 0.50
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
