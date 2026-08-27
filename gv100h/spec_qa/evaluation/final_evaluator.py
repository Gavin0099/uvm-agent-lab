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
    compute_acceptance_set_hash,
    load_poc1_acceptance_set,
)


class EvidenceResolver(Protocol):
    def get_evidence_by_id(self, evidence_id: str) -> Any:
        ...

    def get_canonical_citation_by_id(self, evidence_id: str) -> Optional[Any]:
        """
        Resolve evidence_id to its canonical, source-of-truth citation shape
        (an object exposing document/revision/chapter/section/page_or_anchor/
        authority_level attributes, e.g. evidence_contract.Citation), or
        None if not registered. Used by FinalPOC1Evaluator to verify
        submitted citation *correctness* against real provenance, not just
        *completeness* (fields merely present) -- without this, a response
        could submit a plausible-looking but false value (e.g. the wrong
        chapter) for a resolvable evidence_id and still be scored
        citation_complete (Codex review, PR #33, P1).

        The evaluator looks this method up with getattr() rather than
        assuming every EvidenceResolver implements it, so a resolver that
        only implements get_evidence_by_id() does not raise AttributeError.
        However, a resolver lacking this method is NOT a free pass: EVERY
        submitted citation -- normative or non-normative/boundary-shaped --
        whose canonical evidence-shape cannot be verified this way is scored
        as invalid (fail closed), because "the check was skipped" and "the
        citation is correct" are not the same thing (Codex review, PR #33,
        P1). Non-normative citations are no longer exempt: an acceptance
        manifest can mistakenly list an ordinary normative evidence_id under
        boundary_evidence_ids, and only resolving the canonical record can
        catch a boundary-shaped submission for what is actually normative
        evidence, or vice versa (Codex review, PR #33, fresh finding on
        ad0542c).
        """
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
    # Additive P0 provenance fields (docs/USB_SPEC_QA_POC1_SCOPE.md Section 5
    # lists chapter and authority_level as mandatory citation fields
    # alongside document/revision/section/page_or_anchor). qa_service.py's
    # runtime Citation already carries both; previously
    # QAResponse.to_final_qa_response() silently dropped them when
    # projecting onto this schema (Codex review, PR #33, P1).
    chapter: Optional[str] = None
    authority_level: Optional[str] = None


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
        # Symmetric presence check for every normative identity field,
        # including chapter/authority_level: this is what keeps a
        # *boundary* citation shape from posing as a *normative* one (all
        # required fields present) and, just as important, keeps a
        # normative-looking field from leaking onto a citation whose
        # question never required it -- e.g. an abstention citation must
        # not smuggle in a chapter/authority_level value under a
        # boundary_evidence-mode question (Codex review, PR #33, P1).
        # chapter/authority_level used to be checked one-directionally only
        # (required -> must be present) to stay lenient with older ad-hoc
        # fixtures that predate these fields being mandatory for
        # answer/conflict questions; POC1AcceptanceSet.validate_contract()
        # now enforces chapter=True/authority_level=True for every real,
        # reviewed answer/conflict question, so that leniency is no longer
        # needed and was itself a gap Codex flagged.
        fields = (
            "document",
            "revision",
            "chapter",
            "section",
            "page_or_anchor",
            "authority_level",
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

    _CANONICAL_PROVENANCE_FIELDS = (
        "document",
        "revision",
        "chapter",
        "section",
        "page_or_anchor",
        "authority_level",
    )

    def _canonical_field_mismatches(
        self,
        citation: FinalQACitation,
    ) -> Optional[frozenset]:
        """
        Verify a submitted citation's evidence-shape (normative vs
        boundary/non-normative) and, when normative, its
        document/revision/chapter/section/page_or_anchor/authority_level
        fields against the resolver's own canonical record for that
        evidence_id.

        Canonical verification fails closed uniformly for every citation,
        normative or not (Codex review, PR #33, fresh finding on ad0542c).
        The previous version treated any non-normative (`document is None`)
        citation as automatically valid without ever consulting the
        canonical record, so an acceptance manifest that mistakenly listed
        an ordinary normative evidence_id under boundary_evidence_ids could
        be "satisfied" by a boundary-shaped response citing that same
        evidence_id: the ID resolves, it's in the expected set, and the
        absent normative fields satisfy boundary-shape completeness --
        nothing ever checked whether that evidence_id is genuinely
        boundary-shaped in the canonical registry. Symmetrically, a
        normative-looking citation for an evidence_id whose canonical
        record is actually boundary-shaped must also be rejected. Treating
        boundary citations as exempt from canonical verification (while
        normative ones fail closed) would itself reintroduce the
        "unverifiable == correct" gap already closed for normative
        provenance (Codex review, PR #33, P1).

        "excerpt_or_evidence_id" is verified for *every* citation,
        normative or boundary, independent of the document/revision/etc.
        comparison above: QAResponse.to_final_qa_response() only ever
        populates this field with either the resolver's own canonical
        excerpt (Citation.excerpt, e.g. from to_citation()/
        to_boundary_citation()) or a fallback to the citation's own
        evidence_id, so those are the only two values a genuine response
        can produce. Accepting anything else means a response could pair a
        real, correctly-provenanced evidence_id with a fabricated quote and
        still pass both citation_complete and citation_valid, letting
        unsupported evidence text through the grounding gate (Codex
        review, PR #33, fresh finding on 88200c5). This is a precise
        equality check against the canonical excerpt or the evidence_id --
        deliberately not fuzzy/substring/similarity matching, since the
        canonical excerpt is already a well-defined, deterministic value.

        Returns:
        - a frozenset containing "citation_kind" when the submitted
          citation's normative/non-normative shape does not match the
          canonical record's shape (e.g. a boundary-shaped citation for an
          evidence_id whose canonical record is normative, or vice versa);
        - a frozenset containing "excerpt_or_evidence_id" (alone, or
          alongside other mismatched field names) when the submitted value
          is neither the citation's own evidence_id nor the canonical
          record's excerpt;
        - a non-empty frozenset of the field names that disagree, when both
          the submitted citation and its canonical record are normative but
          some field was submitted incorrectly (e.g. chapter="999" for an
          evidence_id whose real chapter is "10");
        - an empty frozenset() only when the submitted citation and its
          canonical record agree on evidence-shape, the excerpt/evidence_id
          identity check passes, and (for normative citations) every
          compared field matches;
        - None when evidence-shape could not be verified at all -- the
          resolver has no get_canonical_citation_by_id(), or the
          evidence_id does not resolve to any canonical record. Callers
          must treat None as "fail closed", not as "no mismatch", for every
          citation regardless of its submitted shape (Codex review, PR #33,
          fresh finding on ad0542c).
        """
        get_canonical = getattr(self.evidence_resolver, "get_canonical_citation_by_id", None)
        if get_canonical is None:
            return None
        canonical = get_canonical(citation.evidence_id)
        if canonical is None:
            return None

        submitted_normative = citation.document is not None
        canonical_normative = getattr(canonical, "document", None) is not None
        if submitted_normative != canonical_normative:
            return frozenset({"citation_kind"})

        mismatches = set()
        canonical_excerpt = getattr(canonical, "excerpt", None)
        if citation.excerpt_or_evidence_id not in (citation.evidence_id, canonical_excerpt):
            mismatches.add("excerpt_or_evidence_id")

        if not submitted_normative:
            return frozenset(mismatches)

        mismatches.update(
            field_name
            for field_name in self._CANONICAL_PROVENANCE_FIELDS
            if getattr(citation, field_name) != getattr(canonical, field_name)
        )
        return frozenset(mismatches)

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
        citation_mismatches = [
            self._canonical_field_mismatches(citation) for citation in response.citations
        ]
        canonical_provenance_ok = all(
            mismatches is not None and not mismatches for mismatches in citation_mismatches
        )
        # authority_violation is True either when the cited evidence set
        # falls outside what the question accepts (source-eligibility), OR
        # when a citation's authority_level disagrees with the resolver's
        # canonical record for that evidence_id -- e.g. a response citing
        # the accepted evidence_id but reporting the wrong authority_level
        # must still be counted against authority_violations_count, not
        # just flagged via the separate citation_valid/grounded outcome
        # (Codex review, PR #33, P2).
        canonical_authority_mismatch = any(
            mismatches is not None and "authority_level" in mismatches
            for mismatches in citation_mismatches
        )
        authority_violation = (
            not set(cited_ids).issubset(expected_ids) or canonical_authority_mismatch
        )
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
            evidence_shape_correct = bool(cited_ids) and set(cited_ids).issubset(expected_ids)
        elif question.expected_status == "conflict":
            evidence_shape_correct = expected_ids.issubset(set(cited_ids))
        else:
            evidence_shape_correct = bool(cited_ids) and set(cited_ids).issubset(expected_ids)
        citation_valid = (
            evidence_shape_correct
            and not fabricated
            and not authority_violation
            and canonical_provenance_ok
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