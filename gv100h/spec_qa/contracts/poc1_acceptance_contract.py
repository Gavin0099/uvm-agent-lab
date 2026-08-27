from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any, Dict, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class AcceptanceContractError(ValueError):
    pass


GOLD_EVIDENCE_SOURCE_IDS = frozenset(
    {
        "usb20_fw",
        "usb20_se",
        "usb32",
        "superspeed_hub_lvs",
    }
)
RETRIEVAL_AID_SOURCE_IDS = frozenset({"hub_reference"})
POC1_CORPUS_SOURCE_IDS = GOLD_EVIDENCE_SOURCE_IDS | RETRIEVAL_AID_SOURCE_IDS
REQUIRED_POC1_SOURCE_IDS = GOLD_EVIDENCE_SOURCE_IDS

BoundaryCode = Literal[
    "OUT_OF_SCOPE",
    "FICTIONAL_SECTION",
    "MISSING_EVIDENCE",
    "AUTHORITY_MISMATCH",
    "VERSION_CONFLICT",
    "UNRESOLVED_CONFLICT",
]
BOUNDARY_CODES = get_args(BoundaryCode)
CONFLICT_BOUNDARY_CODES = frozenset(
    {
        "AUTHORITY_MISMATCH",
        "VERSION_CONFLICT",
        "UNRESOLVED_CONFLICT",
    }
)

# A question is "user_realistic" when an engineer could plausibly ask it
# without already knowing which section/table/test-case identifier answers
# it (the agent must locate that itself). "diagnostic" is reserved for
# questions that are only well-posed when a specific excerpt/identifier is
# named up front (e.g. conflict-detection questions that compare two named
# statements). At least this fraction of the acceptance set must be
# user_realistic, or the set over-represents "open-book quiz" phrasing and
# overstates real retrieval+reasoning difficulty.
MIN_USER_REALISTIC_QUESTION_RATIO = 0.7


def _bound_source_ids(values: list[str]) -> set[str]:
    bound: set[str] = set()
    for raw in values:
        text = str(raw).strip()
        if ":" not in text:
            continue
        source_id, rest = text.split(":", 1)
        source_id = source_id.strip()
        rest = rest.strip()
        if source_id and rest:
            bound.add(source_id)
    return bound


# This is a deliberately separate, git-tracked snapshot of "which sources each
# question was approved against" -- NOT the live draft file. Reading the live
# draft here would make the freeze a no-op (every edit silently redefines its
# own baseline). Regenerate it only via freeze_source_set_identity(), never as
# an automatic side effect of loading or editing the draft.
DEFAULT_POC1_SOURCE_SET_IDENTITY_PATH = (
    Path(__file__).resolve().parents[3]
    / "gv100h"
    / "spec_qa"
    / "golden"
    / "poc1_acceptance_set.frozen_source_identity.json"
)


def _question_id(question: Any) -> str:
    if isinstance(question, dict):
        return str(question["question_id"])
    return str(question.question_id)


def _accepted_source_ids(question: Any) -> list[str]:
    if isinstance(question, dict):
        return list(question.get("accepted_source_ids") or [])
    return list(question.accepted_source_ids)


def load_frozen_source_sets(
    draft_path: str | Path | None = None,
) -> Dict[str, frozenset[str]]:
    identity_path = (
        Path(draft_path)
        if draft_path is not None
        else DEFAULT_POC1_SOURCE_SET_IDENTITY_PATH
    )
    try:
        payload: Any = json.loads(identity_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AcceptanceContractError(
            f"preregistered source-set identity is missing or invalid: {identity_path}"
        ) from exc
    questions = payload.get("questions") if isinstance(payload, dict) else None
    if not isinstance(questions, list) or not questions:
        raise AcceptanceContractError(
            "preregistered source-set identity must declare questions"
        )
    frozen: Dict[str, frozenset[str]] = {}
    for question in questions:
        if not isinstance(question, dict):
            raise AcceptanceContractError(
                "preregistered source-set identity has an invalid question"
            )
        question_id = str(question.get("question_id") or "").strip()
        if not question_id:
            raise AcceptanceContractError(
                "preregistered source-set identity requires question_id"
            )
        if question_id in frozen:
            raise AcceptanceContractError(
                f"preregistered source-set identity has duplicate question_id: {question_id}"
            )
        frozen[question_id] = frozenset(_accepted_source_ids(question))
    return frozen


def freeze_source_set_identity(
    source_path: str | Path,
    output_path: str | Path | None = None,
) -> Dict[str, frozenset[str]]:
    """Deliberately (re-)generate the pinned source-set identity snapshot.

    This must only be invoked as an explicit, reviewed action (e.g. when a
    question's accepted_source_ids are re-approved after review) -- never
    automatically as a side effect of loading or editing the draft. Reading
    ``source_path`` (typically the live draft) and writing the same content
    right back out as the "frozen" baseline on every edit would make the
    freeze a tautology that can never detect drift.
    """
    source = Path(source_path)
    try:
        payload: Any = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AcceptanceContractError(
            f"source-set identity source is missing or invalid: {source}"
        ) from exc
    questions = payload.get("questions") if isinstance(payload, dict) else None
    if not isinstance(questions, list) or not questions:
        raise AcceptanceContractError(
            "source-set identity source must declare questions"
        )
    frozen_payload = {
        "questions": [
            {
                "question_id": _question_id(question),
                "accepted_source_ids": _accepted_source_ids(question),
            }
            for question in questions
        ]
    }
    destination = (
        Path(output_path)
        if output_path is not None
        else DEFAULT_POC1_SOURCE_SET_IDENTITY_PATH
    )
    destination.write_text(
        json.dumps(frozen_payload, ensure_ascii=True, sort_keys=True, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return load_frozen_source_sets(destination)


def verify_accepted_source_set_identity(
    questions: Any,
    frozen_source_sets: Dict[str, frozenset[str]] | None = None,
    *,
    draft_path: str | Path | None = None,
) -> None:
    identity = (
        frozen_source_sets
        if frozen_source_sets is not None
        else load_frozen_source_sets(draft_path)
    )
    admitted_ids = {_question_id(question) for question in questions}
    if admitted_ids != set(identity):
        missing = sorted(set(identity) - admitted_ids)
        extra = sorted(admitted_ids - set(identity))
        details = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if extra:
            details.append("extra: " + ", ".join(extra))
        raise AcceptanceContractError(
            "admitted question IDs must exactly match the preregistered "
            "source-set identity (" + "; ".join(details) + ")"
        )
    for question in questions:
        question_id = _question_id(question)
        if question_id not in identity:
            continue
        accepted = set(_accepted_source_ids(question))
        required = set(identity[question_id])
        if accepted != required:
            raise AcceptanceContractError(
                f"question {question_id} accepted_source_ids must exactly match "
                "the preregistered source set"
            )


class CitationRequirements(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document: bool = False
    revision: bool = False
    section: bool = False
    page_or_anchor: bool = False
    excerpt_or_evidence_id: bool = False
    scope: bool = False
    boundary_code: bool = False
    mode: Literal[
        "normative_source",
        "competing_sources",
        "boundary_evidence",
    ] = "normative_source"


class GoldClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(min_length=1)
    assertion: str = Field(min_length=1)
    required: bool = True


class GoldOracle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted_evidence_ids: list[str] = Field(default_factory=list)
    competing_evidence_ids: list[str] = Field(default_factory=list)
    boundary_evidence_ids: list[str] = Field(default_factory=list)
    required_claims: list[GoldClaim] = Field(default_factory=list)
    section_anchors: list[str] = Field(default_factory=list)
    required_facts: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(default_factory=list)
    acceptable_variants: list[str] = Field(default_factory=list)
    boundary_code: BoundaryCode | None = None


class GradingWeights(BaseModel):
    model_config = ConfigDict(extra="forbid")

    factual_correctness: float = Field(ge=0.0, le=1.0)
    citation_correctness: float = Field(ge=0.0, le=1.0)
    source_authority: float = Field(ge=0.0, le=1.0)
    scope_control: float = Field(ge=0.0, le=1.0)
    uncertainty_behavior: float = Field(ge=0.0, le=1.0)


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
    gold: GoldOracle
    grading: GradingWeights
    independently_reviewed: Literal[True]
    usb4_negative_control: bool = False
    question_style: Literal["user_realistic", "diagnostic"]


class POC1AcceptanceSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_name: Literal["poc1_spec_qa_acceptance_set"]
    schema_version: Literal["1.2"]
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
            retrieval_aids = sorted(
                set(question.accepted_source_ids) & RETRIEVAL_AID_SOURCE_IDS
            )
            if retrieval_aids:
                raise AcceptanceContractError(
                    f"question {question.question_id} accepted_source_ids must not "
                    "include retrieval-aid sources: " + ", ".join(retrieval_aids)
                )
            if not set(question.accepted_source_ids).issubset(required_source_ids):
                raise AcceptanceContractError(
                    f"question {question.question_id} cites a source outside required_source_ids"
                )
            if question.category == "cross_document" and len(
                set(question.accepted_source_ids)
            ) < 2:
                raise AcceptanceContractError(
                    f"cross_document question {question.question_id} requires at least two sources"
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
            citation = question.required_citation_fields
            gold = question.gold
            evidence_ids = (
                gold.accepted_evidence_ids
                + gold.competing_evidence_ids
                + gold.boundary_evidence_ids
            )
            if any(not evidence_id.strip() for evidence_id in evidence_ids):
                raise AcceptanceContractError(
                    f"question {question.question_id} gold evidence IDs must be non-empty"
                )
            if len(evidence_ids) != len(set(evidence_ids)):
                raise AcceptanceContractError(
                    f"question {question.question_id} gold evidence IDs must be unique"
                )
            claim_ids = [claim.claim_id for claim in gold.required_claims]
            if any(not claim_id.strip() for claim_id in claim_ids):
                raise AcceptanceContractError(
                    f"question {question.question_id} gold claim IDs must be non-empty"
                )
            if len(claim_ids) != len(set(claim_ids)):
                raise AcceptanceContractError(
                    f"question {question.question_id} gold claim IDs must be unique"
                )
            if any(not fact.strip() for fact in gold.required_facts):
                raise AcceptanceContractError(
                    f"question {question.question_id} gold facts must be non-empty"
                )
            if any(not anchor.strip() for anchor in gold.section_anchors):
                raise AcceptanceContractError(
                    f"question {question.question_id} gold section anchors must be non-empty"
                )
            if any(not claim.assertion.strip() for claim in gold.required_claims):
                raise AcceptanceContractError(
                    f"question {question.question_id} gold claim assertions must be non-empty"
                )
            weight_total = sum(
                (
                    question.grading.factual_correctness,
                    question.grading.citation_correctness,
                    question.grading.source_authority,
                    question.grading.scope_control,
                    question.grading.uncertainty_behavior,
                )
            )
            if abs(weight_total - 1.0) > 1e-6:
                raise AcceptanceContractError(
                    f"question {question.question_id} grading weights must sum to 1.0"
                )
            normative_fields = (
                "document",
                "revision",
                "section",
                "page_or_anchor",
                "excerpt_or_evidence_id",
            )
            if question.usb4_negative_control and question.expected_status != "abstain":
                raise AcceptanceContractError(
                    f"USB4 negative control {question.question_id} must abstain"
                )
            if question.expected_status == "answer":
                if not gold.accepted_evidence_ids:
                    raise AcceptanceContractError(
                        f"answer question {question.question_id} requires gold accepted evidence"
                    )
                if gold.competing_evidence_ids or gold.boundary_evidence_ids:
                    raise AcceptanceContractError(
                        f"answer question {question.question_id} cannot use competing or boundary evidence"
                    )
                if (
                    not gold.required_claims
                    or not any(claim.required for claim in gold.required_claims)
                    or not gold.required_facts
                    or not gold.section_anchors
                ):
                    raise AcceptanceContractError(
                        f"answer question {question.question_id} requires gold claims, facts, and section anchors"
                    )
                if gold.boundary_code is not None:
                    raise AcceptanceContractError(
                        f"answer question {question.question_id} must not declare a boundary code"
                    )
                if len(question.accepted_source_ids) >= 2:
                    bound_evidence = _bound_source_ids(gold.accepted_evidence_ids)
                    bound_anchors = _bound_source_ids(gold.section_anchors)
                    missing_sources = [
                        source_id
                        for source_id in question.accepted_source_ids
                        if source_id not in bound_evidence or source_id not in bound_anchors
                    ]
                    if missing_sources:
                        raise AcceptanceContractError(
                            f"answer question {question.question_id} requires each "
                            "accepted_source_id to have gold accepted evidence and "
                            "section anchors"
                        )
                if citation.mode != "normative_source" or not citation.scope or citation.boundary_code or not all(
                    getattr(citation, field_name) is True for field_name in normative_fields
                ):
                    raise AcceptanceContractError(
                        f"question {question.question_id} must require normative source citation fields"
                    )
            elif question.expected_status == "conflict":
                if gold.accepted_evidence_ids or gold.boundary_evidence_ids:
                    raise AcceptanceContractError(
                        f"conflict question {question.question_id} must use competing evidence only"
                    )
                if len(set(gold.competing_evidence_ids)) < 2:
                    raise AcceptanceContractError(
                        f"conflict question {question.question_id} requires at least two gold competing evidence IDs"
                    )
                if (
                    len(gold.required_claims) < 2
                    or sum(1 for claim in gold.required_claims if claim.required) < 2
                    or len(gold.section_anchors) < 2
                ):
                    raise AcceptanceContractError(
                        f"conflict question {question.question_id} requires two gold claims and section anchors"
                    )
                if gold.boundary_code not in CONFLICT_BOUNDARY_CODES:
                    raise AcceptanceContractError(
                        f"conflict question {question.question_id} requires a conflict boundary code"
                    )
                if citation.mode != "competing_sources" or not citation.scope or not citation.boundary_code or not all(
                    getattr(citation, field_name) is True for field_name in normative_fields
                ):
                    raise AcceptanceContractError(
                        f"conflict question {question.question_id} requires competing-source citation fields"
                    )
            else:
                if gold.accepted_evidence_ids or gold.competing_evidence_ids:
                    raise AcceptanceContractError(
                        f"abstain question {question.question_id} must not use answer or competing evidence"
                    )
                if (
                    not gold.boundary_evidence_ids
                    or not gold.required_claims
                    or not any(claim.required for claim in gold.required_claims)
                ):
                    raise AcceptanceContractError(
                        f"abstain question {question.question_id} requires boundary evidence and a boundary claim"
                    )
                if gold.section_anchors:
                    raise AcceptanceContractError(
                        f"abstain question {question.question_id} must not declare normative section anchors"
                    )
                if gold.boundary_code is None:
                    raise AcceptanceContractError(
                        f"abstain question {question.question_id} requires a boundary code"
                    )
                if citation.mode != "boundary_evidence" or not citation.scope or not citation.boundary_code or not citation.excerpt_or_evidence_id:
                    raise AcceptanceContractError(
                        f"abstain question {question.question_id} requires boundary citation fields"
                    )
                if any(getattr(citation, field_name) for field_name in normative_fields[:-1]):
                    raise AcceptanceContractError(
                        f"abstain question {question.question_id} must not require normative citation fields"
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
        realistic_count = sum(
            question.question_style == "user_realistic" for question in self.questions
        )
        realistic_ratio = realistic_count / len(self.questions)
        if realistic_ratio < MIN_USER_REALISTIC_QUESTION_RATIO:
            raise AcceptanceContractError(
                f"user_realistic question ratio {realistic_ratio:.2f} is below "
                f"the required minimum {MIN_USER_REALISTIC_QUESTION_RATIO:.2f}; "
                "questions must not lean on diagnostic-only phrasing that "
                "leaks target section/table/test-case identifiers"
            )
        # NOTE: frozen source-set identity is deliberately NOT checked here.
        # This method validates structural/schema correctness for any
        # manifest (including ad hoc test fixtures) and has no repo_root
        # context to resolve a frozen baseline against. The identity/freeze
        # check is an admission-time concern with a resolvable trust
        # boundary; it is enforced by
        # poc1_admission.verify_poc1_acceptance_admission(), which receives
        # an explicit repo_root and threads it into
        # verify_accepted_source_set_identity(..., frozen_source_sets=...).
        missing_coverage = sorted(REQUIRED_POC1_SOURCE_IDS - source_coverage)
        if missing_coverage:
            raise AcceptanceContractError(
                "acceptance set lacks question coverage for: "
                + ", ".join(missing_coverage)
            )


def compute_acceptance_set_hash(manifest: POC1AcceptanceSet) -> str:
    """Hash acceptance content while excluding the self-referential receipt hash."""

    payload = manifest.model_dump(mode="json")
    payload.pop("review_receipt_hash", None)
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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
