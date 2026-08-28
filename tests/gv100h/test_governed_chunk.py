import hashlib
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gv100h.spec_qa.contracts.evidence_contract import GroundedAnswer
from gv100h.spec_qa.contracts.governed_chunk import GovernedChunk, GovernedChunkError


def _build_chunk(**overrides) -> GovernedChunk:
    kwargs = dict(
        source_id="usb32",
        document="USB 3.2 Specification",
        revision="Rev 1.1",
        section="10.16.2.1",
        page_or_anchor="p.482",
        authority_level="authoritative",
        chunk_kind="paragraph",
        content="PORT_POWER feature selector value is 8 (0x0008).",
        index=0,
    )
    kwargs.update(overrides)
    return GovernedChunk.build(**kwargs)


def test_build_derives_chapter_content_sha256_and_chunk_id():
    chunk = _build_chunk()
    assert chunk.chapter == "10"
    assert chunk.content_sha256 == hashlib.sha256(chunk.content.encode("utf-8")).hexdigest()
    assert chunk.chunk_id.startswith("usb32:10.16.2.1:p.482:0:")


def test_build_is_deterministic_same_input_same_chunk_id():
    a = _build_chunk()
    b = _build_chunk()
    assert a.chunk_id == b.chunk_id
    assert a.content_sha256 == b.content_sha256


def test_build_is_sensitive_to_content_change():
    a = _build_chunk()
    b = _build_chunk(content="A completely different sentence.")
    assert a.chunk_id != b.chunk_id
    assert a.content_sha256 != b.content_sha256


def test_direct_construction_rejects_content_sha256_mismatch():
    chunk = _build_chunk()
    with pytest.raises(GovernedChunkError, match="does not match sha256"):
        GovernedChunk(
            chunk_id=chunk.chunk_id,
            source_id=chunk.source_id,
            document=chunk.document,
            revision=chunk.revision,
            chapter=chunk.chapter,
            section=chunk.section,
            page_or_anchor=chunk.page_or_anchor,
            authority_level=chunk.authority_level,
            chunk_kind=chunk.chunk_kind,
            content=chunk.content,
            content_sha256="0" * 64,
        )


def test_direct_construction_rejects_chapter_section_mismatch():
    chunk = _build_chunk()
    with pytest.raises(GovernedChunkError, match="does not match the leading numeric segment"):
        GovernedChunk(
            chunk_id=chunk.chunk_id,
            source_id=chunk.source_id,
            document=chunk.document,
            revision=chunk.revision,
            chapter="99",
            section=chunk.section,
            page_or_anchor=chunk.page_or_anchor,
            authority_level=chunk.authority_level,
            chunk_kind=chunk.chunk_kind,
            content=chunk.content,
            content_sha256=chunk.content_sha256,
        )


@pytest.mark.parametrize("blank_field", ["document", "revision", "section", "page_or_anchor", "content"])
def test_blank_required_fields_are_rejected(blank_field):
    with pytest.raises(GovernedChunkError):
        _build_chunk(**{blank_field: ""})


def test_section_without_numeric_chapter_prefix_is_rejected():
    with pytest.raises(GovernedChunkError, match="does not start with a numeric chapter segment"):
        _build_chunk(section="Appendix.A.1")


def test_extra_fields_are_forbidden():
    with pytest.raises(GovernedChunkError):
        GovernedChunk(
            chunk_id="x",
            source_id="usb32",
            document="USB 3.2 Specification",
            revision="Rev 1.1",
            chapter="10",
            section="10.16.2.1",
            page_or_anchor="p.482",
            authority_level="authoritative",
            chunk_kind="paragraph",
            content="text",
            content_sha256=hashlib.sha256(b"text").hexdigest(),
            unexpected_field="nope",
        )


def test_to_citation_produces_a_valid_normative_citation_evidence_contract_compatibility():
    """
    Proves a PDF-derived GovernedChunk satisfies the same Answer and
    Evidence Contract (evidence_contract.py) that GovernedQAService already
    enforces for hand-authored GovernedEvidence -- the "GovernedQAService
    can consume real chunks" DONE criterion, without wiring the chunk into
    the live EVIDENCE_REGISTRY/qa_service.py answer path.
    """
    chunk = _build_chunk()
    citation = chunk.to_citation()

    assert citation.evidence_id == chunk.chunk_id
    assert citation.document == chunk.document
    assert citation.revision == chunk.revision
    assert citation.chapter == chunk.chapter
    assert citation.section == chunk.section
    assert citation.page_or_anchor == chunk.page_or_anchor
    assert citation.citation_kind == "normative"

    # A GroundedAnswer built entirely from PDF-derived evidence must satisfy
    # the full contract (status="answer" requires >=1 citation, >=1 claim,
    # boundary=None, and per-claim evidence traceability).
    answer = GroundedAnswer(
        status="answer",
        claims=["PORT_POWER feature selector value is 8."],
        citations=[citation],
        claim_evidence_ids=[[chunk.chunk_id]],
        scope="USB_3_X",
        boundary=None,
        evidence_ids=[chunk.chunk_id],
    )
    assert answer.status == "answer"


def test_to_citation_respects_excerpt_max_len():
    chunk = _build_chunk(content="A" * 500)
    citation = chunk.to_citation(excerpt_max_len=10)
    assert citation.excerpt == "A" * 10
