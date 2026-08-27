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

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from gv100h.spec_qa.contracts.poc1_acceptance_contract import BoundaryCode

AnswerStatus = Literal["answer", "abstain", "conflict"]

AuthorityLevel = Literal["authoritative", "informative", "derived"]


class EvidenceContractError(ValueError):
    """Raised when a Citation or GroundedAnswer violates the Evidence Contract."""


class Citation(BaseModel):
    """
    A single piece of cited evidence, traceable to document, revision,
    section, and page-or-anchor per docs/USB_SPEC_QA_POC1_SCOPE.md Section 5.
    """

    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1)
    document: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    section: str = Field(min_length=1)
    page_or_anchor: str = Field(min_length=1)
    authority_level: AuthorityLevel
    excerpt: Optional[str] = None

    def __init__(self, **data):
        # See GroundedAnswer.__init__ for why this re-raises as a plain
        # EvidenceContractError instead of leaking pydantic_core.ValidationError.
        try:
            super().__init__(**data)
        except ValidationError as exc:
            messages = "; ".join(error["msg"] for error in exc.errors())
            raise EvidenceContractError(messages) from exc


class GroundedAnswer(BaseModel):
    """
    Structured Answer and Evidence Contract
    (docs/USB_SPEC_QA_POC1_SCOPE.md Section 5).
    """

    model_config = ConfigDict(extra="forbid")

    status: AnswerStatus
    claims: List[str] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    scope: Optional[str] = None
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

        elif self.status == "abstain":
            if self.boundary is None:
                raise EvidenceContractError(
                    "an 'abstain' status requires a boundary code explaining why "
                    "no answer was given"
                )
            if self.claims:
                raise EvidenceContractError(
                    "an 'abstain' status must not assert material claims"
                )

        elif self.status == "conflict":
            if self.boundary is None:
                raise EvidenceContractError(
                    "a 'conflict' status requires a boundary code"
                )
            if len(self.citations) < 2:
                raise EvidenceContractError(
                    "a 'conflict' status requires citations from at least two "
                    "competing sources; got "
                    f"{len(self.citations)}"
                )

        return self
