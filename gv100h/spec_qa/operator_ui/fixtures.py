"""Frozen QAResponse fixtures for the Operator UI.

Presentation fixtures only. They must remain valid GroundedAnswer /
QAResponse shapes and must not reconstruct a second evidence registry.
"""

from __future__ import annotations

from typing import Dict, List

from gv100h.spec_qa.api.qa_service import QAResponse
from gv100h.spec_qa.contracts.evidence_contract import Citation


def _citation(
    *,
    evidence_id: str,
    excerpt: str,
    section: str = "",
    authority_level: str = "authoritative",
    document: str = "usb-if-hub-spec-reference",
    revision: str = "808f23c",
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
        evidence_id="USB3-FEAT-PORT_POWER",
        section="10.16.2.1",
        excerpt="In USB 3.x Hub specifications, PORT_POWER feature selector value is 8 (0x0008).",
    )
    return QAResponse(
        answer="USB 3.x Hub Class PORT_POWER feature selector value is 8 (0x0008).",
        scope="USB_3_X",
        cited_evidences=[],
        claim_level="normative_requirement",
        boundary="Strictly bounded by in-scope governed evidence.",
        is_abstain=False,
        status="answer",
        claims=["PORT_POWER feature selector value is 8 (0x0008)."],
        claim_evidence_ids=[["USB3-FEAT-PORT_POWER"]],
        citations=[citation],
        boundary_code=None,
        evidence_ids=["USB3-FEAT-PORT_POWER"],
        contract_mode="structured",
    )


def abstained_usb4() -> QAResponse:
    citation = _citation(
        evidence_id="USB4-OUT-OF-SCOPE",
        excerpt="Phase 1 corpus does not include the USB4 specification.",
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
        claims=["Phase 1 corpus does not include the USB4 specification."],
        claim_evidence_ids=[["USB4-OUT-OF-SCOPE"]],
        citations=[citation],
        boundary_code="OUT_OF_SCOPE",
        evidence_ids=["USB4-OUT-OF-SCOPE"],
        contract_mode="structured",
    )


def conflict_port_power_authority() -> QAResponse:
    usb3 = _citation(
        evidence_id="USB3-FEAT-PORT_POWER",
        section="10.16.2.1",
        excerpt="USB 3.x treats PORT_POWER as an authoritative Hub Class selector value 8.",
        revision="usb32-1.1",
    )
    usb2 = _citation(
        evidence_id="USB2-FEAT-PORT_POWER",
        section="11.24.2.1",
        excerpt="A competing record treats PORT_POWER as informative-only for USB 2.0.",
        document="usb-2.0",
        revision="usb20-2.0",
        authority_level="informative",
    )
    return QAResponse(
        answer="Competing sources disagree on PORT_POWER authority; no single governed answer is certified.",
        scope="USB_HUB_COMMON",
        cited_evidences=[],
        claim_level="normative_requirement",
        boundary="Competing provenance identities prevent a single certified answer.",
        is_abstain=True,
        status="conflict",
        claims=[
            "USB 3.x treats PORT_POWER as an authoritative Hub Class selector value 8.",
            "A competing record treats PORT_POWER as informative-only for USB 2.0.",
        ],
        claim_evidence_ids=[["USB3-FEAT-PORT_POWER"], ["USB2-FEAT-PORT_POWER"]],
        citations=[usb3, usb2],
        boundary_code="AUTHORITY_MISMATCH",
        evidence_ids=["USB3-FEAT-PORT_POWER", "USB2-FEAT-PORT_POWER"],
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
