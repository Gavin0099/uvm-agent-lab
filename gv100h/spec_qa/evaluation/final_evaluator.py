from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Callable, Dict, List, Literal, Optional, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from gv100h.spec_qa.contracts.poc1_acceptance_contract import (
    AcceptanceQuestion,
    BoundaryCode,
    POC1AcceptanceSet,
    _bound_source_ids,
    compute_acceptance_set_hash,
    load_poc1_acceptance_set,
)


class EvidenceResolver(Protocol):
    def get_evidence_by_id(self, evidence_id: str) -> Any:
        ...


class FinalQACitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1)
    document: Optional[str] = None
    revision: Optional[str] = None
    section: Optional[str] = None
    page_or_anchor: Optional[str] = None
    excerpt_or_evidence_id: Optional[str] = None
    scope: Optional[str] = None


class FinalQAResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["answer", "abstain", "conflict"]
    claims: List[str] = Field(default_factory=list)
    citations: List[FinalQACitation] = Field(default_factory=list)
    scope: str = Field(min_length=1)
    boundary_code: Optional[BoundaryCode] = None


class FinalQuestionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    expected_status: str
    observed_status: str
    passed: bool
    retrieval_hit_at_1: bool
    grounded: bool
    citation_valid: bool
    citation_complete: bool
    fabricated_citation: bool
    authority_violation: bool
    scope_correct: bool
    boundary_correct: bool
    required_claims_present: bool
    forbidden_claim_detected: bool
    cited_evidence_ids: List[str]


class FinalPOC1EvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_questions: int
    answer_question_count: int
    conflict_question_count: int
    abstain_question_count: int
    retrieval_recall_at_1: float
    grounded_answer_rate: float
    citation_validity_rate: float
    citation_completeness_rate: float
    conflict_detection_rate: float
    abstention_rate: float
    fabricated_citations_count: int
    authority_violations_count: int
    all_gates_passed: bool
    details: List[FinalQuestionResult]
    dataset_hash: str
    acceptance_set_hash: str
    acceptance_set_path: str
    corpus_receipt_path: str
    corpus_receipt_hash: str
    review_receipt_path: str
    review_receipt_hash: str
    evidence_class: str = "deterministic_final_poc1"
    admissible_for_model_qualification: bool = False
    endpoint_observed: bool = False
    benchmark_role: str = "poc1_acceptance_set"


class FinalPOC1Evaluator:
    """Evaluate structured model responses against a reviewed POC-1 manifest."""

    _STATUS_TO_GOLD_IDS = {
        "answer": "accepted_evidence_ids",
        "conflict": "competing_evidence_ids",
        "abstain": "boundary_evidence_ids",
    }

    def __init__(
        self,
        manifest_path: str,
        evidence_resolver: EvidenceResolver,
    ):
        self.manifest: POC1AcceptanceSet = load_poc1_acceptance_set(manifest_path)
        self.manifest_path = str(manifest_path)
        self.evidence_resolver = evidence_resolver
        self.acceptance_set_hash = self._hash_manifest(self.manifest)
        self.dataset_hash = self.acceptance_set_hash

    @staticmethod
    def _hash_manifest(manifest: POC1AcceptanceSet) -> str:
        return compute_acceptance_set_hash(manifest)

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value.strip().casefold())

    @classmethod
    def _contains_expected(cls, values: List[str], expected: str, variants: List[str]) -> bool:
        haystack = cls._normalize(" ".join(values))
        candidates = [expected, *variants]
        return any(cls._normalize(candidate) in haystack for candidate in candidates)

    @staticmethod
    def _required_citation_fields_present(
        response: FinalQAResponse,
        question: AcceptanceQuestion,
    ) -> bool:
        requirements = question.required_citation_fields
        fields = (
            "document",
            "revision",
            "section",
            "page_or_anchor",
            "excerpt_or_evidence_id",
        )
        if not response.citations:
            return False
        for citation in response.citations:
            for field_name in fields:
                if getattr(requirements, field_name) and not getattr(citation, field_name):
                    return False
                if (
                    not getattr(requirements, field_name)
                    and getattr(citation, field_name)
                ):
                    return False
        if requirements.scope and not response.scope:
            return False
        if requirements.boundary_code and not response.boundary_code:
            return False
        if not requirements.boundary_code and response.boundary_code is not None:
            return False
        return True

    def _coerce_response(self, raw_response: Any) -> Optional[FinalQAResponse]:
        if isinstance(raw_response, FinalQAResponse):
            return raw_response
        try:
            return FinalQAResponse.model_validate(raw_response)
        except ValidationError:
            return None

    def evaluate_response(
        self,
        question: AcceptanceQuestion,
        raw_response: Any,
    ) -> FinalQuestionResult:
        response = self._coerce_response(raw_response)
        if response is None:
            return FinalQuestionResult(
                question_id=question.question_id,
                expected_status=question.expected_status,
                observed_status="invalid",
                passed=False,
                retrieval_hit_at_1=False,
                grounded=False,
                citation_valid=False,
                citation_complete=False,
                fabricated_citation=True,
                authority_violation=True,
                scope_correct=False,
                boundary_correct=False,
                required_claims_present=False,
                forbidden_claim_detected=False,
                cited_evidence_ids=[],
            )

        cited_ids = [citation.evidence_id for citation in response.citations]
        expected_ids = set(
            getattr(question.gold, self._STATUS_TO_GOLD_IDS[question.expected_status])
        )
        resolved_ids = {
            evidence_id
            for evidence_id in cited_ids
            if self.evidence_resolver.get_evidence_by_id(evidence_id) is not None
        }
        fabricated = resolved_ids != set(cited_ids)
        authority_violation = not set(cited_ids).issubset(expected_ids)
        scope_correct = response.scope == question.expected_scope and all(
            citation.scope in {None, question.expected_scope}
            for citation in response.citations
        )
        retrieval_hit_at_1 = bool(cited_ids and cited_ids[0] in expected_ids)

        required_claims_present = all(
            not claim.required
            or self._contains_expected(
                response.claims,
                claim.assertion,
                question.gold.acceptable_variants,
            )
            for claim in question.gold.required_claims
        ) and all(
            self._contains_expected(
                response.claims,
                required_fact,
                question.gold.acceptable_variants,
            )
            for required_fact in question.gold.required_facts
        )
        forbidden_claim_detected = any(
            self._contains_expected(response.claims, forbidden, [])
            for forbidden in question.gold.forbidden_claims
        )
        boundary_correct = response.boundary_code == question.gold.boundary_code
        status_correct = response.status == question.expected_status
        citation_complete = self._required_citation_fields_present(response, question)

        if question.expected_status == "answer":
            base_evidence_shape_correct = bool(cited_ids) and set(cited_ids).issubset(
                expected_ids
            )
            if base_evidence_shape_correct and len(question.accepted_source_ids) >= 2:
                # Multi-source (e.g. cross_document) gold: citing a subset of
                # the allowed evidence pool is not enough on its own -- a
                # response that only cites evidence bound to one required
                # source must not pass. Require at least one cited,
                # `source_id:`-bound evidence item per accepted_source_id,
                # not that every expected_evidence_id be cited (alternates
                # for the same source are allowed).
                cited_source_coverage = _bound_source_ids(cited_ids)
                evidence_shape_correct = set(
                    question.accepted_source_ids
                ).issubset(cited_source_coverage)
            else:
                evidence_shape_correct = base_evidence_shape_correct
        elif question.expected_status == "conflict":
            evidence_shape_correct = expected_ids.issubset(set(cited_ids))
        else:
            evidence_shape_correct = bool(cited_ids) and set(cited_ids).issubset(expected_ids)
        citation_valid = (
            evidence_shape_correct
            and not fabricated
            and not authority_violation
        )
        grounded = (
            status_correct
            and citation_valid
            and required_claims_present
            and not forbidden_claim_detected
            and boundary_correct
            and scope_correct
        )
        passed = grounded and citation_complete
        return FinalQuestionResult(
            question_id=question.question_id,
            expected_status=question.expected_status,
            observed_status=response.status,
            passed=passed,
            retrieval_hit_at_1=retrieval_hit_at_1,
            grounded=grounded,
            citation_valid=citation_valid,
            citation_complete=citation_complete,
            fabricated_citation=fabricated,
            authority_violation=authority_violation,
            scope_correct=scope_correct,
            boundary_correct=boundary_correct,
            required_claims_present=required_claims_present,
            forbidden_claim_detected=forbidden_claim_detected,
            cited_evidence_ids=cited_ids,
        )

    def run_benchmark(
        self,
        agent_fn: Callable[[str, str], Any],
    ) -> FinalPOC1EvaluationResult:
        details = [
            self.evaluate_response(
                question,
                agent_fn(question.question, question.expected_scope),
            )
            for question in self.manifest.questions
        ]
        counts = {
            status: sum(
                question.expected_status == status for question in self.manifest.questions
            )
            for status in ("answer", "conflict", "abstain")
        }

        def rate(numerator: int, denominator: int) -> float:
            return round((numerator / denominator) * 100.0, 2) if denominator else 0.0

        passed_answers = sum(
            detail.passed
            for detail in details
            if detail.expected_status == "answer"
        )
        passed_conflicts = sum(
            detail.passed
            for detail in details
            if detail.expected_status == "conflict"
        )
        passed_abstains = sum(
            detail.passed
            for detail in details
            if detail.expected_status == "abstain"
        )
        return FinalPOC1EvaluationResult(
            total_questions=len(details),
            answer_question_count=counts["answer"],
            conflict_question_count=counts["conflict"],
            abstain_question_count=counts["abstain"],
            retrieval_recall_at_1=rate(
                sum(detail.retrieval_hit_at_1 for detail in details),
                len(details),
            ),
            grounded_answer_rate=rate(passed_answers, counts["answer"]),
            citation_validity_rate=rate(
                sum(detail.citation_valid for detail in details),
                len(details),
            ),
            citation_completeness_rate=rate(
                sum(detail.citation_complete for detail in details),
                len(details),
            ),
            conflict_detection_rate=rate(passed_conflicts, counts["conflict"]),
            abstention_rate=rate(passed_abstains, counts["abstain"]),
            fabricated_citations_count=sum(
                detail.fabricated_citation for detail in details
            ),
            authority_violations_count=sum(
                detail.authority_violation for detail in details
            ),
            all_gates_passed=all(detail.passed for detail in details),
            details=details,
            dataset_hash=self.dataset_hash,
            acceptance_set_hash=self.acceptance_set_hash,
            acceptance_set_path=self.manifest_path,
            corpus_receipt_path=self.manifest.corpus_receipt_path,
            corpus_receipt_hash=self.manifest.corpus_receipt_hash,
            review_receipt_path=self.manifest.review_receipt_path,
            review_receipt_hash=self.manifest.review_receipt_hash,
        )