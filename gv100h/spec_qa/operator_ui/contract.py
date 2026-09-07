"""Frozen presentation mapping for QAResponse.

Machine A (PDF/RAG) may ADD citation richness (page, chunk_id,
source_revision) later. This module must not rename or delete the
frozen fields, must not reimplement retrieval, and must not fabricate
PDF anchors when they are absent.
"""

from __future__ import annotations

from typing import Any, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from gv100h.spec_qa.api.qa_service import QAResponse
from gv100h.spec_qa.contracts.evidence_contract import Citation

CLAIM_CEILING = (
    "Operator UI / development shell only; not POC-1 qualification, "
    "not Gate 4, and not a complete Spec Bot."
)

ABSTAIN_EXPLAINER = (
    "系統不是不知道答案，而是目前證據不足以在治理規則下回答。"
)

# Frozen consumer surface. Additive citation fields are optional display
# only; absence must never be filled with a fake PDF/chunk link.
FROZEN_QA_RESPONSE_FIELDS = (
    "status",
    "answer",
    "claims",
    "citations",
    "boundary_code",
    "scope",
    "claim_evidence_ids",
    "evidence_ids",
    "is_abstain",
)

FROZEN_CITATION_FIELDS = (
    "evidence_id",
    "document",
    "revision",
    "chapter",
    "section",
    "page_or_anchor",
    "authority_level",
    "excerpt",
    "citation_kind",
)

OperatorStatus = Literal["answer", "abstain", "conflict"]
OperatorSource = Literal["fixture", "service", "real_local_rag"]


class OperatorCitationView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    document: Optional[str] = None
    revision: Optional[str] = None
    chapter: Optional[str] = None
    section: Optional[str] = None
    page_or_anchor: Optional[str] = None
    authority_level: Optional[str] = None
    excerpt: Optional[str] = None
    citation_kind: str = "normative"
    has_pdf_anchor: bool = False
    pdf_href: Optional[str] = None
    # Retrieval-only metadata. These fields make candidate evidence useful
    # for diagnosis without changing the frozen citation fields above.
    retrieval_rank: Optional[int] = None
    retrieval_score: Optional[float] = None
    matched_terms: List[str] = Field(default_factory=list)


class OperatorQAView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: OperatorStatus
    answer: str
    claims: List[str] = Field(default_factory=list)
    citations: List[OperatorCitationView] = Field(default_factory=list)
    # Real-local-RAG keeps BM25 candidate evidence separate from the smaller
    # selected evidence set used for citation projection. The selector does
    # not observe model-internal evidence use; these additive fields remain a
    # deterministic traceability projection and leave frozen fields unchanged.
    candidate_citations: List[OperatorCitationView] = Field(default_factory=list)
    selected_evidence_ids: List[str] = Field(default_factory=list)
    primary_evidence_ids: List[str] = Field(default_factory=list)
    evidence_selection_method: Optional[str] = None
    boundary_code: Optional[str] = None
    boundary: str
    boundary_reason: str
    scope: str
    evidence_ids: List[str] = Field(default_factory=list)
    claim_evidence_ids: List[List[str]] = Field(default_factory=list)
    is_abstain: bool
    claim_ceiling: str = CLAIM_CEILING
    source: OperatorSource = "fixture"
    retrieval_kind: Optional[str] = None
    local_model: Optional[str] = None
    retrieved_chunk_count: Optional[int] = None
    corpus_sha256: Optional[str] = None


def citation_to_view(citation: Citation) -> OperatorCitationView:
    """Project a frozen Citation. Never invent a PDF href."""
    return OperatorCitationView(
        evidence_id=citation.evidence_id,
        document=citation.document,
        revision=citation.revision,
        chapter=citation.chapter,
        section=citation.section,
        page_or_anchor=citation.page_or_anchor,
        authority_level=citation.authority_level,
        excerpt=citation.excerpt,
        citation_kind=citation.citation_kind,
        has_pdf_anchor=False,
        pdf_href=None,
    )


def _boundary_reason(resp: QAResponse) -> str:
    if resp.status == "answer":
        return resp.boundary or ""
    parts = [ABSTAIN_EXPLAINER]
    if resp.boundary_code:
        parts.append(f"boundary_code={resp.boundary_code}")
    if resp.boundary:
        parts.append(resp.boundary)
    return " ".join(part for part in parts if part)


def to_operator_view(resp: QAResponse, *, source: Literal["fixture", "service"] = "fixture") -> OperatorQAView:
    return OperatorQAView(
        status=resp.status,
        answer=resp.answer,
        claims=list(resp.claims),
        citations=[citation_to_view(citation) for citation in resp.citations],
        boundary_code=resp.boundary_code,
        boundary=resp.boundary,
        boundary_reason=_boundary_reason(resp),
        scope=resp.scope,
        evidence_ids=list(resp.evidence_ids),
        claim_evidence_ids=[list(ids) for ids in resp.claim_evidence_ids],
        is_abstain=resp.is_abstain,
        source=source,
    )


def frozen_fields_present(payload: dict[str, Any]) -> bool:
    return all(field in payload for field in FROZEN_QA_RESPONSE_FIELDS)
