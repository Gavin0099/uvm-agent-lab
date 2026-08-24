from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class AcceptanceContractError(ValueError):
    pass


REQUIRED_POC1_SOURCE_IDS = frozenset(
    {
        "hub_reference",
        "usb20_fw",
        "usb20_se",
        "usb32",
        "superspeed_hub_lvs",
    }
)


class CitationRequirements(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document: bool
    revision: bool
    section: bool
    page_or_anchor: bool
    excerpt_or_evidence_id: bool


class AcceptanceQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(min_length=1)
    layer: Literal["L1", "L2", "L3", "L4"]
    priority: Literal["P0", "P1"]
    category: Literal[
        "single_spec_fact",
        "engineering_interpretation",
        "cross_document",
        "uncertainty_conflict",
    ]
    question: str = Field(min_length=1)
    expected_status: Literal["answer", "abstain", "conflict"]
    expected_scope: str = Field(min_length=1)
    accepted_source_ids: list[str] = Field(default_factory=list)
    required_citation_fields: CitationRequirements
    independently_reviewed: Literal[True]
    usb4_negative_control: bool = False


class POC1AcceptanceSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_name: Literal["poc1_spec_qa_acceptance_set"]
    schema_version: Literal["1.0"]
    corpus_lock: str = Field(min_length=1)
    corpus_receipt_path: str = Field(min_length=1)
    corpus_receipt_hash: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    dataset_version: str = Field(min_length=1)
    benchmark_role: Literal["poc1_acceptance_set"]
    generated_from_corpus: Literal[False]
    independent_from_corpus: Literal[True]
    independent_review_complete: Literal[True]
    review_receipt_path: str = Field(min_length=1)
    review_receipt_hash: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    reviewer_id: str = Field(min_length=1)
    reviewed_at: str = Field(min_length=1)
    total_questions: int = Field(ge=50, le=100)
    required_layers: Dict[str, int]
    required_source_ids: list[str] = Field(min_length=1)
    questions: list[AcceptanceQuestion] = Field(min_length=50, max_length=100)

    def validate_contract(self) -> None:
        if self.total_questions != len(self.questions):
            raise AcceptanceContractError(
                "total_questions must equal the number of questions"
            )
        if not self.review_receipt_path.startswith("artifacts/"):
            raise AcceptanceContractError(
                "review_receipt_path must point to a durable artifacts/ path"
            )

        required_layers = {"L1", "L2", "L3", "L4"}
        if set(self.required_layers) != required_layers:
            raise AcceptanceContractError(
                "required_layers must declare exactly L1, L2, L3, and L4"
            )
        for layer, minimum in self.required_layers.items():
            if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 1:
                raise AcceptanceContractError(
                    f"required_layers[{layer}] must be a positive integer"
                )

        counts = {layer: 0 for layer in required_layers}
        seen_ids: set[str] = set()
        required_source_ids = set(self.required_source_ids)
        if required_source_ids != REQUIRED_POC1_SOURCE_IDS:
            missing_sources = sorted(REQUIRED_POC1_SOURCE_IDS - required_source_ids)
            extra_sources = sorted(required_source_ids - REQUIRED_POC1_SOURCE_IDS)
            details = []
            if missing_sources:
                details.append("missing: " + ", ".join(missing_sources))
            if extra_sources:
                details.append("extra: " + ", ".join(extra_sources))
            raise AcceptanceContractError(
                "required_source_ids must exactly match POC-1 sources ("
                + "; ".join(details)
                + ")"
            )
        source_coverage = set()
        has_usb4_negative_control = False
        expected_categories = {
            "L1": "single_spec_fact",
            "L2": "engineering_interpretation",
            "L3": "cross_document",
            "L4": "uncertainty_conflict",
        }
        for question in self.questions:
            if question.question_id in seen_ids:
                raise AcceptanceContractError(
                    f"duplicate question_id: {question.question_id}"
                )
            seen_ids.add(question.question_id)
            counts[question.layer] += 1
            if question.category != expected_categories[question.layer]:
                raise AcceptanceContractError(
                    f"question {question.question_id} category does not match "
                    f"layer {question.layer}"
                )
            expected_priority = "P1" if question.layer == "L3" else "P0"
            if question.priority != expected_priority:
                raise AcceptanceContractError(
                    f"question {question.question_id} priority must be "
                    f"{expected_priority} for layer {question.layer}"
                )
            if not set(question.accepted_source_ids).issubset(required_source_ids):
                raise AcceptanceContractError(
                    f"question {question.question_id} cites a source outside required_source_ids"
                )
            if question.expected_status == "answer" and not question.accepted_source_ids:
                raise AcceptanceContractError(
                    f"answer question {question.question_id} requires an accepted source"
                )
            if question.expected_status == "abstain" and question.accepted_source_ids:
                raise AcceptanceContractError(
                    f"abstain question {question.question_id} must not cite accepted sources"
                )
            if question.expected_status == "conflict" and len(
                set(question.accepted_source_ids)
            ) < 2:
                raise AcceptanceContractError(
                    f"conflict question {question.question_id} requires at least two competing sources"
                )
            if not all(
                getattr(question.required_citation_fields, field_name) is True
                for field_name in (
                    "document",
                    "revision",
                    "section",
                    "page_or_anchor",
                    "excerpt_or_evidence_id",
                )
            ):
                raise AcceptanceContractError(
                    f"question {question.question_id} must require all citation fields"
                )
            source_coverage.update(question.accepted_source_ids)
            if question.usb4_negative_control:
                has_usb4_negative_control = True
                if question.layer != "L4" or question.category != "uncertainty_conflict":
                    raise AcceptanceContractError(
                        f"USB4 negative control {question.question_id} must be an L4 uncertainty_conflict question"
                    )
                if question.expected_status != "abstain":
                    raise AcceptanceContractError(
                        f"USB4 negative control {question.question_id} must abstain"
                    )
                if question.expected_scope != "USB4_SPEC":
                    raise AcceptanceContractError(
                        f"USB4 negative control {question.question_id} must use USB4_SPEC scope"
                    )

        for layer, minimum in self.required_layers.items():
            if counts[layer] < minimum:
                raise AcceptanceContractError(
                    f"layer {layer} has {counts[layer]} questions; requires {minimum}"
                )
        if not has_usb4_negative_control:
            raise AcceptanceContractError(
                "acceptance set requires at least one USB4 negative control"
            )
        missing_coverage = sorted(REQUIRED_POC1_SOURCE_IDS - source_coverage)
        if missing_coverage:
            raise AcceptanceContractError(
                "acceptance set lacks question coverage for: "
                + ", ".join(missing_coverage)
            )


def load_poc1_acceptance_set(path: str | Path) -> POC1AcceptanceSet:
    manifest_path = Path(path).resolve()
    try:
        payload: Any = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = POC1AcceptanceSet.model_validate(payload)
        manifest.validate_contract()
        return manifest
    except (OSError, json.JSONDecodeError, ValidationError, AcceptanceContractError) as exc:
        raise AcceptanceContractError(
            f"invalid POC-1 acceptance set {manifest_path}: {exc}"
        ) from exc
