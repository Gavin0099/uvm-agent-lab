"""Frozen QAResponse fixtures for the Operator UI.

Presentation fixtures only. They must remain valid GroundedAnswer /
QAResponse shapes, must not reconstruct a second evidence registry, and
must not reuse production evidence IDs or provenance.
"""

from __future__ import annotations

from typing import Dict, List

from gv100h.spec_qa.api.qa_service import QAResponse
from gv100h.spec_qa.contracts.evidence_contract import Citation

FIXTURE_DOCUMENT = "operator-ui-fixture"
FIXTURE_REVISION = "synthetic-v1"
FIXTURE_ID_PREFIX = "FIXTURE-"

FIXTURE_ANSWER_ID = "FIXTURE-ANSWER-USB3-PORT-POWER"
FIXTURE_ABSTAIN_ID = "FIXTURE-ABSTAIN-USB4"
FIXTURE_CONFLICT_A_ID = "FIXTURE-CONFLICT-USB3"
FIXTURE_CONFLICT_B_ID = "FIXTURE-CONFLICT-USB2"


def _citation(
    *,
    evidence_id: str,
    excerpt: str,
    section: str = "",
    authority_level: str = "authoritative",
    document: str = FIXTURE_DOCUMENT,
    revision: str = FIXTURE_REVISION,
    citation_kind: str = "normative",
) -> Citation:
    if citation_kind == "boundary":
        return Citation(
            evidence_id=evidence_id,
            excerpt=excerpt,
            citation_kind="boundary",
        )
    chapter = section.split(".", 1)[0]
    return Citation(
        evidence_id=evidence_id,
        document=document,
        revision=revision,
        chapter=chapter,
        section=section,
        page_or_anchor=section,
        authority_level=authority_level,  # type: ignore[arg-type]
        excerpt=excerpt,
        citation_kind="normative",
    )


def answered_port_power() -> QAResponse:
    citation = _citation(
        evidence_id=FIXTURE_ANSWER_ID,
        section="10.16.2.1",
        excerpt="Synthetic fixture: USB 3.x Hub Class PORT_POWER selector value is presented as 8 (0x0008).",
    )
    return QAResponse(
        answer="Synthetic fixture answer: USB 3.x Hub Class PORT_POWER feature selector value is 8 (0x0008).",
        scope="USB_3_X",
        cited_evidences=[],
        claim_level="normative_requirement",
        boundary="Strictly bounded by in-scope governed evidence.",
        is_abstain=False,
        status="answer",
        claims=["Synthetic fixture: PORT_POWER feature selector value is 8 (0x0008)."],
        claim_evidence_ids=[[FIXTURE_ANSWER_ID]],
        citations=[citation],
        boundary_code=None,
        evidence_ids=[FIXTURE_ANSWER_ID],
        contract_mode="structured",
    )


def abstained_usb4() -> QAResponse:
    citation = _citation(
        evidence_id=FIXTURE_ABSTAIN_ID,
        excerpt="Synthetic fixture: Phase 1 corpus does not include the USB4 specification.",
        citation_kind="boundary",
    )
    return QAResponse(
        answer="現有 governed reference 無法支持此結論，本 Agent 拒絕過度推論 (Abstain)。",
        scope="USB4_SPEC",
        cited_evidences=[],
        claim_level="abstain_no_evidence",
        boundary="Exceeds governed knowledge surface of usb-if-hub-spec-reference.",
        is_abstain=True,
        status="abstain",
        claims=["Synthetic fixture: Phase 1 corpus does not include the USB4 specification."],
        claim_evidence_ids=[[FIXTURE_ABSTAIN_ID]],
        citations=[citation],
        boundary_code="OUT_OF_SCOPE",
        evidence_ids=[FIXTURE_ABSTAIN_ID],
        contract_mode="structured",
    )


def conflict_port_power_authority() -> QAResponse:
    usb3 = _citation(
        evidence_id=FIXTURE_CONFLICT_A_ID,
        section="10.16.2.1",
        excerpt="Synthetic fixture A treats PORT_POWER as an authoritative Hub Class selector value 8.",
        authority_level="authoritative",
    )
    usb2 = _citation(
        evidence_id=FIXTURE_CONFLICT_B_ID,
        section="11.24.2.1",
        excerpt="Synthetic fixture B treats PORT_POWER as informative-only.",
        authority_level="informative",
    )
    return QAResponse(
        answer="Synthetic fixture conflict: competing canned sources disagree on PORT_POWER authority.",
        scope="USB_HUB_COMMON",
        cited_evidences=[],
        claim_level="normative_requirement",
        boundary="Competing provenance identities prevent a single certified answer.",
        is_abstain=True,
        status="conflict",
        claims=[
            "Synthetic fixture A treats PORT_POWER as an authoritative Hub Class selector value 8.",
            "Synthetic fixture B treats PORT_POWER as informative-only.",
        ],
        claim_evidence_ids=[[FIXTURE_CONFLICT_A_ID], [FIXTURE_CONFLICT_B_ID]],
        citations=[usb3, usb2],
        boundary_code="AUTHORITY_MISMATCH",
        evidence_ids=[FIXTURE_CONFLICT_A_ID, FIXTURE_CONFLICT_B_ID],
        contract_mode="structured",
    )


FIXTURES: Dict[str, QAResponse] = {
    "answered": answered_port_power(),
    "abstain": abstained_usb4(),
    "conflict": conflict_port_power_authority(),
}


def fixture_names() -> List[str]:
    return list(FIXTURES.keys())


def get_fixture(name: str) -> QAResponse:
    try:
        return FIXTURES[name]
    except KeyError as err:
        raise KeyError(f"unknown operator UI fixture: {name!r}") from err
