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

# A citation's provenance kind, distinguishing three genuinely different
# evidence shapes that GroundedAnswer must not conflate:
#
# - "normative": a USB spec citation (document/revision/chapter/section/
#   page_or_anchor/authority_level all populated) backing an "answer"/
#   "conflict" claim.
# - "boundary": registered boundary evidence (no normative fields) backing
#   an "abstain" claim -- e.g. "USB4 is excluded from the Phase 1 corpus".
# - "governance": a fact about the corpus/governance metadata itself (e.g.
#   corpus.lock.yaml's sources.usb4 entry), used to answer a genuine
#   *corpus-membership* question ("is USB4 included in the Phase 1 corpus?",
#   docs/USB_SPEC_QA_POC1_SCOPE.md lines 86-88) with status="answer" -- it is
#   NOT a normative USB-spec citation and must not be faked as one, but it is
#   also not a boundary citation because the response is a real "answer",
#   not an abstention.
CitationKind = Literal["normative", "boundary", "governance"]

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

# The subset of BoundaryCode reserved for a 'conflict' status, mirroring
# poc1_acceptance_contract.py's own conflict boundary_code whitelist
# ("OUT_OF_SCOPE"/"FICTIONAL_SECTION"/"MISSING_EVIDENCE" describe *why no
# answer was given*, not a conflict between competing sources -- a live
# conflict answer declaring one of those would be contradicting its own
# status) (Codex review, PR #33, P2).
CONFLICT_BOUNDARY_CODES = (
    "AUTHORITY_MISMATCH",
    "VERSION_CONFLICT",
    "UNRESOLVED_CONFLICT",
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
    citation_kind: CitationKind = "normative"

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

    @field_validator("evidence_id", mode="after")
    @classmethod
    def _evidence_id_must_not_be_blank(cls, value: str) -> str:
        # Field(min_length=1) alone accepts "   " -- a whitespace-only
        # evidence_id would still pass GroundedAnswer's cited_ids/evidence_ids
        # match check yet resolve to no real registry entry (Codex review,
        # PR #33, P2).
        if not value.strip():
            raise ValueError("evidence_id must not be blank/whitespace-only")
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
            # A conflict's boundary code must itself describe a conflict
            # (mirrors poc1_acceptance_contract.py's own conflict boundary_code
            # whitelist). "OUT_OF_SCOPE"/"FICTIONAL_SECTION"/"MISSING_EVIDENCE"
            # describe why no answer was given at all, not a disagreement
            # between competing sources -- a live conflict declaring one of
            # those would contradict its own status (Codex review, PR #33, P2).
            if self.boundary not in CONFLICT_BOUNDARY_CODES:
                raise EvidenceContractError(
                    "a 'conflict' status requires a conflict boundary code "
                    f"({CONFLICT_BOUNDARY_CODES!r}); got {self.boundary!r}"
                )
            # A conflict is only real when there are at least two distinct
            # competing claims -- one claim (however many citations back it)
            # is not a conflict, and two identical claim strings are not
            # "competing" either (Codex review, PR #33, P2, mirrors
            # poc1_acceptance_contract.py's >=2 required_claims rule).
            if len(self.claims) < 2 or len(set(self.claims)) < 2:
                raise EvidenceContractError(
                    "a 'conflict' status requires at least two distinct "
                    f"competing claims; got {self.claims!r}"
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
            # The declared boundary code must itself name *which* provenance
            # dimension disagrees -- the generic ">=2 distinct identities"
            # check above let VERSION_CONFLICT pass when only the document or
            # authority_level differed (revisions identical), and let
            # AUTHORITY_MISMATCH pass when only the revision differed
            # (authority_level identical). A conflict declaring the wrong
            # boundary code makes an unsupportable claim about *why* the
            # sources disagree (Codex review, PR #33, P2).
            if self.boundary == "VERSION_CONFLICT":
                revisions = {c.revision for c in self.citations}
                if len(revisions) < 2:
                    raise EvidenceContractError(
                        "a 'VERSION_CONFLICT' status requires citations with at "
                        f"least two distinct revisions; got {sorted(r for r in revisions if r is not None)!r}"
                    )
            elif self.boundary == "AUTHORITY_MISMATCH":
                authority_levels = {c.authority_level for c in self.citations}
                if len(authority_levels) < 2:
                    raise EvidenceContractError(
                        "an 'AUTHORITY_MISMATCH' status requires citations with "
                        "at least two distinct authority levels; got "
                        f"{sorted(a for a in authority_levels if a is not None)!r}"
                    )
            # UNRESOLVED_CONFLICT keeps the generic >=2-distinct-identities
            # check above as its only requirement -- no single field is
            # mandated to differ.
            self._require_normative_citations("conflict")

        return self

    def _require_normative_citations(self, status: str) -> None:
        for citation in self.citations:
            if citation.citation_kind == "boundary":
                # Boundary evidence is registered to explain an *abstention*;
                # reusing it to back an "answer"/"conflict" would let a
                # non-answer fact masquerade as grounding for a real claim
                # (Codex review, PR #33 -- "resolvable != retrievable_as_answer").
                raise EvidenceContractError(
                    f"a {status!r} status must not cite boundary-only evidence "
                    f"(citation {citation.evidence_id!r} has citation_kind='boundary'); "
                    "boundary citations back 'abstain' only"
                )
            if status == "answer" and citation.citation_kind == "governance":
                # A governance-fact citation (e.g. corpus.lock.yaml's usb4
                # membership metadata) answers a real question about the
                # corpus/governance state itself. It must NOT declare
                # normative USB-spec document-identity fields -- it is not a
                # spec citation and must not be dressed up as one -- but it
                # is also not a 'conflict'-eligible shape, so this allowance
                # is answer-only.
                present = [
                    field_name
                    for field_name in NORMATIVE_CITATION_FIELDS
                    if getattr(citation, field_name) is not None
                ]
                if present:
                    raise EvidenceContractError(
                        "a governance-fact citation must not declare normative "
                        f"document-identity fields; citation {citation.evidence_id!r} "
                        f"declares {present}"
                    )
                continue
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
            if citation.citation_kind != "boundary":
                # Absence of normative fields alone is not sufficient: the
                # reciprocal answer/conflict validation explicitly rejects
                # citation_kind="boundary" (_require_normative_citations), but
                # this abstain-side check previously only inspected field
                # presence, so a citation with the default
                # citation_kind="normative" (or a declared "governance") and
                # every normative field left unset would still pass here --
                # certifying a status/kind contradiction and letting callers
                # relabel non-boundary evidence as support for an abstention
                # (Codex review, PR #33, fresh finding on edf8825).
                raise EvidenceContractError(
                    "an 'abstain' status must cite boundary evidence only -- "
                    f"citation {citation.evidence_id!r} declares "
                    f"citation_kind={citation.citation_kind!r}; expected 'boundary'"
                )
