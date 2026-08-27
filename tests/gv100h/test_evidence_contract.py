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
def test_citation_requires_chapter():
    # Codex review (P1): the P0 citation contract requires document,
    # revision, chapter, section, and page-or-anchor. A Citation missing
    # `chapter` cannot represent that shape and must be rejected.
    with pytest.raises(EvidenceContractError):
        Citation(
            evidence_id="USB3-FEAT-PORT_POWER",
            document="usb-if-hub-spec-reference",
            revision="808f23c",
            section="10.16.2.1",
            page_or_anchor="10.16.2.1",
            authority_level="authoritative",
        )


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
def test_grounded_answer_abstain_requires_boundary_and_no_claims():
    with pytest.raises(EvidenceContractError, match="requires a boundary code"):
        GroundedAnswer(
            status="abstain",
            claims=[],
            citations=[],
            evidence_ids=[],
            scope="OUT_OF_SCOPE",
        )

    with pytest.raises(EvidenceContractError, match="must not assert material claims"):
        GroundedAnswer(
            status="abstain",
            claims=["a claim"],
            citations=[],
            evidence_ids=[],
            boundary="MISSING_EVIDENCE",
            scope="OUT_OF_SCOPE",
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
            citations=[
                _citation("USB3-FEAT-PORT_POWER"),
                _citation("USB3-FEAT-PORT_LINK_STATE"),
            ],
            evidence_ids=["USB3-FEAT-PORT_POWER", "USB3-FEAT-PORT_LINK_STATE"],
            boundary="UNRESOLVED_CONFLICT",
            scope="USB_3_X",
        )


@pytest.mark.unit
def test_grounded_answer_conflict_accepts_distinct_provenance_by_revision():
    answer = GroundedAnswer(
        status="conflict",
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
