"""
Answer and Evidence Contract for the USB Hub Spec QA service.

This formalizes docs/USB_SPEC_QA_POC1_SCOPE.md Section 5 ("Answer and Evidence
Contract") as an enforceable pydantic schema, the same way
``retrieval_policy.py`` formalized the retrieval eligibility contract.

Every evaluated answer must expose this structured shape, even when the
user-facing rendering is natural language prose:

- ``status``: ``answer``, ``abstain``, or ``conflict``.
- ``claims``: material claims made by the answer.
- ``citations``: document, revision, section, page-or-anchor, authority
  level, and evidence ID for every piece of cited evidence.
- ``scope``: the corpus scope used for the answer.
- ``boundary``: a registered boundary code when evidence is missing,
  out of scope, or in conflict (reuses ``poc1_acceptance_contract.BoundaryCode``
  so both the acceptance-set expectations and the live answer contract share
  one vocabulary).
- ``evidence_ids``: IDs that can be resolved against the governed knowledge
  layer -- this must exactly match the evidence IDs referenced by
  ``citations``; it exists as a separate field because the source document
  requires it to be independently resolvable, not merely inferred from
  ``citations``.

Design principle (do not violate elsewhere in this codebase): this module is
a pure schema/validation layer. It must not import from ``retrieval/`` or
``api/`` -- callers (``governed_retriever.py``, ``qa_service.py``) depend on
this contract, not the other way around, the same layering already used by
``retrieval_policy.py``.
"""
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from gv100h.spec_qa.contracts.poc1_acceptance_contract import BoundaryCode

AnswerStatus = Literal["answer", "abstain", "conflict"]

AuthorityLevel = Literal["authoritative", "informative", "derived"]

# Fields that identify a *normative* citation (backing an "answer"/"conflict"
# claim against a specific document/revision/section). A *boundary* citation
# (backing an "abstain") must not declare any of these -- per
# poc1_acceptance_contract.py's CitationRequirements, boundary_evidence mode
# explicitly forbids normative document/section identity fields. GroundedAnswer
# ._check_contract() is the single place that enforces which shape (all
# present vs. all absent) applies, based on ``status`` -- Citation itself only
# enforces "non-blank if provided" so one class can represent both shapes.
NORMATIVE_CITATION_FIELDS = (
    "document",
    "revision",
    "chapter",
    "section",
    "page_or_anchor",
    "authority_level",
)


class EvidenceContractError(ValueError):
    """Raised when a Citation or GroundedAnswer violates the Evidence Contract."""


class Citation(BaseModel):
    """
    A single piece of cited evidence.

    Two shapes share this one class, distinguished by whether the normative
    identity fields are populated:

    - a *normative* citation (used by "answer"/"conflict"): document,
      revision, chapter, section, page_or_anchor, and authority_level must
      ALL be populated, per docs/USB_SPEC_QA_POC1_SCOPE.md Section 5.
    - a *boundary* citation (used by "abstain"): none of those fields may be
      populated -- a boundary citation only needs evidence_id (and,
      optionally, excerpt) to explain why no answer was given, per
      poc1_acceptance_contract.py's "boundary_evidence" citation mode.

    GroundedAnswer._check_contract() enforces which shape applies for a
    given ``status``; this class only guarantees that any provided field is
    non-blank.
    """

    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1)
    document: Optional[str] = Field(default=None, min_length=1)
    revision: Optional[str] = Field(default=None, min_length=1)
    chapter: Optional[str] = Field(default=None, min_length=1)
    section: Optional[str] = Field(default=None, min_length=1)
    page_or_anchor: Optional[str] = Field(default=None, min_length=1)
    authority_level: Optional[AuthorityLevel] = None
    excerpt: Optional[str] = None

    def __init__(self, **data):
        # See GroundedAnswer.__init__ for why this re-raises as a plain
        # EvidenceContractError instead of leaking pydantic_core.ValidationError.
        try:
            super().__init__(**data)
        except ValidationError as exc:
            messages = "; ".join(error["msg"] for error in exc.errors())
            raise EvidenceContractError(messages) from exc

    @field_validator("document", "revision", "chapter", "section", "page_or_anchor", mode="after")
    @classmethod
    def _normative_field_not_blank_if_present(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("must not be blank/whitespace-only when provided")
        return value


class GroundedAnswer(BaseModel):
    """
    Structured Answer and Evidence Contract
    (docs/USB_SPEC_QA_POC1_SCOPE.md Section 5).
    """

    model_config = ConfigDict(extra="forbid")

    status: AnswerStatus
    claims: List[str] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    # Required and nonempty: every evaluated answer -- including abstain and
    # conflict -- must expose which corpus scope it was evaluated under
    # (docs/USB_SPEC_QA_POC1_SCOPE.md §5). This is part of the Wrong-Version/
    # Wrong-Scope defense, not a cosmetic field.
    scope: str = Field(min_length=1)
    boundary: Optional[BoundaryCode] = None
    evidence_ids: List[str] = Field(default_factory=list)

    def __init__(self, **data):
        # pydantic v2 wraps every exception raised inside a model_validator
        # (including our own EvidenceContractError) into a generic
        # pydantic_core.ValidationError. GroundedAnswer is meant to be a
        # simple caller-facing value contract (mirroring RetrievalPolicy), so
        # re-surface a plain EvidenceContractError instead of leaking a
        # pydantic-specific exception shape to every call site.
        try:
            super().__init__(**data)
        except ValidationError as exc:
            messages = "; ".join(error["msg"] for error in exc.errors())
            raise EvidenceContractError(messages) from exc

    @field_validator("scope")
    @classmethod
    def _scope_must_not_be_blank(cls, value: str) -> str:
        # Field(min_length=1) alone accepts "   " -- a whitespace-only scope
        # identifies no real corpus scope but would still be certified,
        # defeating the wrong-scope defense (Codex review, PR #33, P2).
        if not value.strip():
            raise ValueError("scope must not be blank/whitespace-only")
        return value

    @field_validator("claims")
    @classmethod
    def _claims_must_not_contain_blank_entries(cls, value: List[str]) -> List[str]:
        if any(not claim.strip() for claim in value):
            raise ValueError("claims must not contain blank/whitespace-only entries")
        return value

    @model_validator(mode="after")
    def _check_contract(self) -> "GroundedAnswer":
        cited_ids = [citation.evidence_id for citation in self.citations]

        if set(cited_ids) != set(self.evidence_ids):
            raise EvidenceContractError(
                "evidence_ids must exactly match the evidence_id set referenced "
                f"by citations; citations declared {sorted(set(cited_ids))!r}, "
                f"evidence_ids declared {sorted(set(self.evidence_ids))!r}"
            )
        if len(cited_ids) != len(set(cited_ids)):
            raise EvidenceContractError(
                "citations must not cite the same evidence_id more than once"
            )

        if self.status == "answer":
            if not self.citations:
                raise EvidenceContractError(
                    "an 'answer' status requires at least one supporting citation "
                    "(P0 grounding/citation gate)"
                )
            if not self.claims:
                raise EvidenceContractError(
                    "an 'answer' status requires at least one material claim"
                )
            if self.boundary is not None:
                raise EvidenceContractError(
                    "an 'answer' status must not declare a boundary code; "
                    "boundary is reserved for abstain/conflict"
                )
            self._require_normative_citations("answer")

        elif self.status == "abstain":
            if self.boundary is None:
                raise EvidenceContractError(
                    "an 'abstain' status requires a boundary code explaining why "
                    "no answer was given"
                )
            # An abstain response is allowed (and, per a formal acceptance
            # manifest's boundary_evidence_ids + required_claims, sometimes
            # required) to assert a *boundary* claim -- e.g. "Phase 1 corpus
            # does not include the USB4 specification" is a material claim,
            # but not an "answer" to the question. What it must never do is
            # assert an unsupported claim: if it asserts any claim at all, it
            # must cite at least one boundary citation backing it (Codex
            # review, PR #33, P1 -- previously this status forbade claims
            # entirely, which made a conforming acceptance-manifest abstain
            # impossible to represent).
            if self.claims and not self.citations:
                raise EvidenceContractError(
                    "an 'abstain' status that asserts a boundary claim requires "
                    "at least one supporting boundary citation"
                )
            self._require_boundary_citations()

        elif self.status == "conflict":
            if self.boundary is None:
                raise EvidenceContractError(
                    "a 'conflict' status requires a boundary code"
                )
            # A conflict is only real when the citations come from distinct
            # competing provenance -- two citations that happen to share the
            # same (document, revision, authority_level) are not "competing
            # sources or authority levels", they are the same source cited
            # twice. Counting citations alone (the previous rule) let two
            # unrelated sections of the SAME source falsely qualify as a
            # conflict.
            provenance_identities = {
                (c.document, c.revision, c.authority_level) for c in self.citations
            }
            if len(provenance_identities) < 2:
                raise EvidenceContractError(
                    "a 'conflict' status requires citations from at least two "
                    "distinct competing provenance identities (document, "
                    "revision, authority_level); got "
                    f"{len(provenance_identities)} distinct identity(ies) across "
                    f"{len(self.citations)} citation(s)"
                )
            self._require_normative_citations("conflict")

        return self

    def _require_normative_citations(self, status: str) -> None:
        for citation in self.citations:
            missing = [
                field_name
                for field_name in NORMATIVE_CITATION_FIELDS
                if getattr(citation, field_name) is None
            ]
            if missing:
                raise EvidenceContractError(
                    f"a {status!r} status requires normative citation fields "
                    f"{NORMATIVE_CITATION_FIELDS} on every citation; citation "
                    f"{citation.evidence_id!r} is missing {missing}"
                )

    def _require_boundary_citations(self) -> None:
        for citation in self.citations:
            present = [
                field_name
                for field_name in NORMATIVE_CITATION_FIELDS
                if getattr(citation, field_name) is not None
            ]
            if present:
                raise EvidenceContractError(
                    "an 'abstain' status must cite boundary evidence only -- "
                    "citations must not declare normative document-identity "
                    f"fields; citation {citation.evidence_id!r} declares {present}"
                )
