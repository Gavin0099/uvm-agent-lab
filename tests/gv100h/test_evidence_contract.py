import pytest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gv100h.spec_qa.contracts.evidence_contract import (
    Citation,
    EvidenceContractError,
    GroundedAnswer,
)


def _citation(
    evidence_id: str = "USB3-FEAT-PORT_POWER",
    *,
    document: str = "usb-if-hub-spec-reference",
    revision: str = "808f23c",
    authority_level: str = "authoritative",
) -> Citation:
    return Citation(
        evidence_id=evidence_id,
        document=document,
        revision=revision,
        chapter="10",
        section="10.16.2.1",
        page_or_anchor="10.16.2.1",
        authority_level=authority_level,
        excerpt="PORT_POWER feature selector value is 8 (0x0008).",
    )


def _boundary_citation(
    evidence_id: str = "USB4-OUT-OF-SCOPE",
    *,
    excerpt: str = "Phase 1 corpus does not include the USB4 specification.",
) -> Citation:
    # A boundary citation backs an 'abstain' claim: it must NOT declare any
    # normative document-identity field (document/revision/chapter/section/
    # page_or_anchor/authority_level), per poc1_acceptance_contract.py's
    # "boundary_evidence" citation mode. It must also declare
    # citation_kind="boundary" explicitly -- the default "normative" is
    # rejected by GroundedAnswer._require_boundary_citations() (Codex
    # review, PR #33, fresh finding on edf8825).
    return Citation(evidence_id=evidence_id, excerpt=excerpt, citation_kind="boundary")


@pytest.mark.unit
def test_citation_rejects_empty_required_fields():
    with pytest.raises(EvidenceContractError):
        Citation(
            evidence_id="",
            document="usb-if-hub-spec-reference",
            revision="808f23c",
            chapter="10",
            section="10.16.2.1",
            page_or_anchor="10.16.2.1",
            authority_level="authoritative",
        )


@pytest.mark.unit
def test_citation_permits_omitting_normative_fields():
    # Codex review follow-up (PR #33): normative document-identity fields are
    # now conditional on the answer's status (enforced by GroundedAnswer, not
    # Citation itself), so a boundary citation with only evidence_id/excerpt
    # must construct successfully.
    citation = Citation(evidence_id="USB4-OUT-OF-SCOPE", excerpt="out of scope")
    assert citation.document is None
    assert citation.chapter is None
    assert citation.authority_level is None


@pytest.mark.unit
def test_citation_rejects_blank_normative_field_when_provided():
    with pytest.raises(EvidenceContractError):
        Citation(
            evidence_id="USB3-FEAT-PORT_POWER",
            document="   ",
            revision="808f23c",
            chapter="10",
            section="10.16.2.1",
            page_or_anchor="10.16.2.1",
            authority_level="authoritative",
        )


@pytest.mark.unit
def test_citation_rejects_whitespace_only_evidence_id():
    # Codex review follow-up (PR #33, P2): Field(min_length=1) alone accepts
    # "   ", which would still satisfy GroundedAnswer's cited_ids/evidence_ids
    # match check yet resolve to no real registry entry.
    with pytest.raises(EvidenceContractError, match="evidence_id must not be blank"):
        Citation(evidence_id="   ", excerpt="boundary citation")


@pytest.mark.unit
def test_grounded_answer_answer_status_requires_citation_and_claim():
    with pytest.raises(EvidenceContractError, match="requires at least one supporting citation"):
        GroundedAnswer(
            status="answer",
            claims=["some claim"],
            citations=[],
            evidence_ids=[],
            scope="USB_3_X",
        )

    with pytest.raises(EvidenceContractError, match="requires at least one material claim"):
        GroundedAnswer(
            status="answer",
            claims=[],
            citations=[_citation()],
            evidence_ids=["USB3-FEAT-PORT_POWER"],
            scope="USB_3_X",
        )


@pytest.mark.unit
def test_grounded_answer_answer_status_rejects_boundary_code():
    with pytest.raises(EvidenceContractError, match="must not declare a boundary code"):
        GroundedAnswer(
            status="answer",
            claims=["some claim"],
            citations=[_citation()],
            evidence_ids=["USB3-FEAT-PORT_POWER"],
            boundary="MISSING_EVIDENCE",
            scope="USB_3_X",
        )


@pytest.mark.unit
def test_grounded_answer_answer_status_requires_normative_citation_fields():
    # Codex review follow-up (PR #33, P1): a citation missing its normative
    # document-identity fields (e.g. one built for boundary use) must not be
    # silently accepted as evidence for an "answer". Uses citation_kind
    # left at its default "normative" (not _boundary_citation(), which now
    # declares citation_kind="boundary" and would instead trip the earlier
    # "must not cite boundary-only evidence" check) to isolate the
    # missing-normative-fields branch this test targets.
    with pytest.raises(EvidenceContractError, match="requires normative citation fields"):
        GroundedAnswer(
            status="answer",
            claims=["some claim"],
            citations=[Citation(evidence_id="USB3-FEAT-PORT_POWER", excerpt="x")],
            evidence_ids=["USB3-FEAT-PORT_POWER"],
            scope="USB_3_X",
        )


@pytest.mark.unit
def test_grounded_answer_answer_status_valid_case_passes():
    answer = GroundedAnswer(
        status="answer",
        claims=["PORT_POWER is 8 (0x0008)."],
        citations=[_citation()],
        scope="USB_3_X",
        evidence_ids=["USB3-FEAT-PORT_POWER"],
    )
    assert answer.status == "answer"
    assert answer.evidence_ids == ["USB3-FEAT-PORT_POWER"]


@pytest.mark.unit
def test_grounded_answer_requires_nonempty_scope():
    # Codex review (P1): scope is part of the Wrong-Version/Wrong-Scope
    # defense and must be required and nonempty for every evaluated answer,
    # not just "answer" status responses.
    with pytest.raises(EvidenceContractError):
        GroundedAnswer(
            status="answer",
            claims=["PORT_POWER is 8 (0x0008)."],
            citations=[_citation()],
            evidence_ids=["USB3-FEAT-PORT_POWER"],
        )

    with pytest.raises(EvidenceContractError):
        GroundedAnswer(
            status="abstain",
            claims=[],
            citations=[],
            evidence_ids=[],
            boundary="OUT_OF_SCOPE",
            scope="",
        )


@pytest.mark.unit
def test_grounded_answer_rejects_whitespace_only_scope():
    # Codex review follow-up (PR #33, P2): Field(min_length=1) alone accepts
    # "   ", which identifies no real corpus scope but would still be
    # certified, defeating the wrong-scope defense.
    with pytest.raises(EvidenceContractError):
        GroundedAnswer(
            status="abstain",
            claims=[],
            citations=[],
            evidence_ids=[],
            boundary="OUT_OF_SCOPE",
            scope="   ",
        )


@pytest.mark.unit
def test_grounded_answer_rejects_whitespace_only_claims():
    with pytest.raises(EvidenceContractError):
        GroundedAnswer(
            status="answer",
            claims=["   "],
            citations=[_citation()],
            evidence_ids=["USB3-FEAT-PORT_POWER"],
            scope="USB_3_X",
        )


@pytest.mark.unit
def test_grounded_answer_abstain_requires_boundary_code():
    with pytest.raises(EvidenceContractError, match="requires a boundary code"):
        GroundedAnswer(
            status="abstain",
            claims=[],
            citations=[],
            evidence_ids=[],
            scope="OUT_OF_SCOPE",
        )


@pytest.mark.unit
def test_grounded_answer_abstain_allows_boundary_claim_with_boundary_citation():
    # Codex review follow-up (PR #33, P1): a formal acceptance-manifest
    # abstain requires boundary_evidence_ids AND a required boundary claim
    # (poc1_acceptance_contract.py) -- the previous rule ("abstain must not
    # assert material claims") made that shape impossible to represent.
    answer = GroundedAnswer(
        status="abstain",
        claims=["Phase 1 corpus does not include the USB4 specification."],
        citations=[_boundary_citation()],
        evidence_ids=["USB4-OUT-OF-SCOPE"],
        boundary="OUT_OF_SCOPE",
        scope="USB4_SPEC",
    )
    assert answer.claims == ["Phase 1 corpus does not include the USB4 specification."]


@pytest.mark.unit
def test_grounded_answer_abstain_rejects_claim_without_boundary_citation():
    with pytest.raises(EvidenceContractError, match="requires at least one supporting boundary citation"):
        GroundedAnswer(
            status="abstain",
            claims=["Phase 1 corpus does not include the USB4 specification."],
            citations=[],
            evidence_ids=[],
            boundary="OUT_OF_SCOPE",
            scope="USB4_SPEC",
        )


@pytest.mark.unit
def test_grounded_answer_abstain_rejects_normative_shaped_citation():
    # A boundary claim must be backed by *boundary* evidence, not a
    # normative-shaped citation -- that would misrepresent an abstain as if
    # it were grounded in a specific document/section like an "answer".
    with pytest.raises(EvidenceContractError, match="must cite boundary evidence only"):
        GroundedAnswer(
            status="abstain",
            claims=["a boundary claim"],
            citations=[_citation()],
            evidence_ids=["USB3-FEAT-PORT_POWER"],
            boundary="OUT_OF_SCOPE",
            scope="USB_3_X",
        )


@pytest.mark.unit
def test_grounded_answer_abstain_rejects_citation_kind_not_boundary():
    # Codex review, PR #33, fresh finding on edf8825: leaving every
    # normative field unset is not sufficient on its own -- a citation
    # declaring citation_kind="normative" (the default) or "governance"
    # with no normative fields set previously still passed
    # _require_boundary_citations(), certifying a status/kind contradiction
    # and letting non-boundary evidence be relabeled as support for an
    # abstention, even though the reciprocal answer/conflict validation
    # explicitly rejects citation_kind="boundary" citations.
    with pytest.raises(EvidenceContractError, match="expected 'boundary'"):
        GroundedAnswer(
            status="abstain",
            claims=["a boundary claim"],
            citations=[Citation(evidence_id="USB4-OUT-OF-SCOPE", excerpt="x")],
            evidence_ids=["USB4-OUT-OF-SCOPE"],
            boundary="OUT_OF_SCOPE",
            scope="USB4_SPEC",
        )
    with pytest.raises(EvidenceContractError, match="expected 'boundary'"):
        GroundedAnswer(
            status="abstain",
            claims=["a boundary claim"],
            citations=[
                Citation(
                    evidence_id="USB4-OUT-OF-SCOPE",
                    excerpt="x",
                    citation_kind="governance",
                )
            ],
            evidence_ids=["USB4-OUT-OF-SCOPE"],
            boundary="OUT_OF_SCOPE",
            scope="USB4_SPEC",
        )


@pytest.mark.unit
def test_grounded_answer_abstain_valid_case_passes():
    answer = GroundedAnswer(
        status="abstain",
        claims=[],
        citations=[],
        evidence_ids=[],
        boundary="OUT_OF_SCOPE",
        scope="OUT_OF_SCOPE",
    )
    assert answer.boundary == "OUT_OF_SCOPE"


@pytest.mark.unit
def test_grounded_answer_conflict_requires_boundary_and_two_distinct_sources():
    with pytest.raises(EvidenceContractError, match="requires a boundary code"):
        GroundedAnswer(
            status="conflict",
            citations=[
                _citation("USB3-FEAT-PORT_POWER", document="usb32-rev1.1"),
                _citation("USB2-FEAT-PORT_POWER", document="usb32-rev1.2"),
            ],
            evidence_ids=["USB3-FEAT-PORT_POWER", "USB2-FEAT-PORT_POWER"],
            scope="USB_3_X",
        )

    with pytest.raises(EvidenceContractError, match="distinct competing provenance identities"):
        GroundedAnswer(
            status="conflict",
            claims=["claim A", "claim B"],
            citations=[_citation()],
            evidence_ids=["USB3-FEAT-PORT_POWER"],
            boundary="VERSION_CONFLICT",
            scope="USB_3_X",
        )


@pytest.mark.unit
def test_grounded_answer_conflict_rejects_same_source_citations():
    # Codex review (P2): two citations from the same (document, revision,
    # authority_level) are not "competing sources" -- they are the same
    # source cited twice, e.g. two unrelated sections of one document.
    with pytest.raises(EvidenceContractError, match="distinct competing provenance identities"):
        GroundedAnswer(
            status="conflict",
            claims=["claim A", "claim B"],
            citations=[
                _citation("USB3-FEAT-PORT_POWER"),
                _citation("USB3-FEAT-PORT_LINK_STATE"),
            ],
            evidence_ids=["USB3-FEAT-PORT_POWER", "USB3-FEAT-PORT_LINK_STATE"],
            boundary="UNRESOLVED_CONFLICT",
            scope="USB_3_X",
        )


@pytest.mark.unit
def test_grounded_answer_conflict_rejects_invalid_boundary_code():
    # Codex review (PR #33, P2): OUT_OF_SCOPE/FICTIONAL_SECTION/MISSING_EVIDENCE
    # describe why no answer was given at all, not a disagreement between
    # competing sources -- a live conflict declaring one of those would
    # contradict its own status. Mirrors poc1_acceptance_contract.py's own
    # conflict boundary_code whitelist.
    with pytest.raises(EvidenceContractError, match="requires a conflict boundary code"):
        GroundedAnswer(
            status="conflict",
            claims=["claim A", "claim B"],
            citations=[
                _citation("USB3-FEAT-PORT_POWER", revision="1.0"),
                _citation("USB2-FEAT-PORT_POWER", revision="1.1"),
            ],
            evidence_ids=["USB3-FEAT-PORT_POWER", "USB2-FEAT-PORT_POWER"],
            boundary="OUT_OF_SCOPE",
            scope="USB_3_X",
        )


@pytest.mark.unit
def test_grounded_answer_conflict_requires_two_distinct_competing_claims():
    # Codex review (PR #33, P2): a single claim (however many citations back
    # it) is not a "conflict", and two identical claim strings are not
    # "competing" either. Mirrors poc1_acceptance_contract.py's >=2
    # required_claims rule for conflict questions.
    with pytest.raises(EvidenceContractError, match="at least two distinct competing claims"):
        GroundedAnswer(
            status="conflict",
            claims=["only one claim"],
            citations=[
                _citation("USB3-FEAT-PORT_POWER", revision="1.0"),
                _citation("USB2-FEAT-PORT_POWER", revision="1.1"),
            ],
            evidence_ids=["USB3-FEAT-PORT_POWER", "USB2-FEAT-PORT_POWER"],
            boundary="VERSION_CONFLICT",
            scope="USB_3_X",
        )

    with pytest.raises(EvidenceContractError, match="at least two distinct competing claims"):
        GroundedAnswer(
            status="conflict",
            claims=["the same claim", "the same claim"],
            citations=[
                _citation("USB3-FEAT-PORT_POWER", revision="1.0"),
                _citation("USB2-FEAT-PORT_POWER", revision="1.1"),
            ],
            evidence_ids=["USB3-FEAT-PORT_POWER", "USB2-FEAT-PORT_POWER"],
            boundary="VERSION_CONFLICT",
            scope="USB_3_X",
        )


@pytest.mark.unit
def test_grounded_answer_conflict_accepts_distinct_provenance_by_revision():
    answer = GroundedAnswer(
        status="conflict",
        claims=["USB 3.x revision 1.0 says X", "USB 3.x revision 1.1 says Y"],
        citations=[
            _citation("USB3-FEAT-PORT_POWER", revision="1.0"),
            _citation("USB2-FEAT-PORT_POWER", revision="1.1"),
        ],
        evidence_ids=["USB3-FEAT-PORT_POWER", "USB2-FEAT-PORT_POWER"],
        boundary="VERSION_CONFLICT",
        scope="USB_3_X",
    )
    assert answer.status == "conflict"


@pytest.mark.unit
def test_grounded_answer_conflict_accepts_distinct_provenance_by_authority_level():
    answer = GroundedAnswer(
        status="conflict",
        claims=["the authoritative source says X", "the derived source says Y"],
        citations=[
            _citation("USB3-FEAT-PORT_POWER", authority_level="authoritative"),
            _citation("USB2-FEAT-PORT_POWER", authority_level="derived"),
        ],
        evidence_ids=["USB3-FEAT-PORT_POWER", "USB2-FEAT-PORT_POWER"],
        boundary="AUTHORITY_MISMATCH",
        scope="USB_3_X",
    )
    assert answer.status == "conflict"


@pytest.mark.unit
def test_grounded_answer_evidence_ids_must_match_citations():
    with pytest.raises(EvidenceContractError, match="evidence_ids must exactly match"):
        GroundedAnswer(
            status="answer",
            claims=["a claim"],
            citations=[_citation()],
            evidence_ids=["SOME-OTHER-ID"],
            scope="USB_3_X",
        )


@pytest.mark.unit
def test_grounded_answer_rejects_duplicate_citation_evidence_ids():
    with pytest.raises(EvidenceContractError, match="must not cite the same evidence_id"):
        GroundedAnswer(
            status="conflict",
            citations=[_citation(), _citation()],
            evidence_ids=["USB3-FEAT-PORT_POWER"],
            boundary="VERSION_CONFLICT",
            scope="USB_3_X",
        )
