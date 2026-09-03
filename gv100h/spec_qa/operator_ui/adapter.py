"""QA adapter for the Operator UI.

Default path: frozen fixtures (no second retriever).
Optional live path: call existing GovernedQAService without changing it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator, Literal, Optional, Sequence

from gv100h.spec_qa.api.qa_service import GovernedQAService, QAResponse
from gv100h.spec_qa.operator_ui.contract import (
    OperatorCitationView,
    OperatorQAView,
    to_operator_view,
)
from gv100h.spec_qa.operator_ui.fixtures import FIXTURES, get_fixture

SourceMode = Literal["fixture", "service", "real_local_rag"]


class OperatorQAAdapter:
    def __init__(
        self,
        *,
        service: Optional[GovernedQAService] = None,
        real_local_rag: Optional[object] = None,
    ) -> None:
        self._service = service
        self._real_local_rag = real_local_rag

    def _get_service(self) -> GovernedQAService:
        if self._service is None:
            self._service = GovernedQAService()
        return self._service

    def _get_real_local_rag(self):
        if self._real_local_rag is None:
            from gv100h.spec_qa.operator_ui.real_local_rag import RealLocalRAG

            project_root = Path(__file__).resolve().parents[3]
            self._real_local_rag = RealLocalRAG.from_environment(
                project_root=project_root
            )
        return self._real_local_rag

    @staticmethod
    def _real_local_rag_view(result) -> OperatorQAView:
        from gv100h.spec_qa.operator_ui.real_local_rag import (
            REAL_LOCAL_RAG_CLAIM_CEILING,
        )

        citations = []
        evidence_ids = []
        for hit in result.hits:
            citation = hit.chunk.to_citation()
            citations.append(
                OperatorCitationView(
                    evidence_id=citation.evidence_id,
                    document=citation.document,
                    revision=citation.revision,
                    chapter=citation.chapter,
                    section=citation.section,
                    page_or_anchor=citation.page_or_anchor,
                    authority_level=citation.authority_level,
                    excerpt=citation.excerpt,
                    citation_kind=citation.citation_kind,
                )
            )
            evidence_ids.append(citation.evidence_id)

        if result.boundary is not None:
            return OperatorQAView(
                status="abstain",
                answer=result.boundary.answer,
                boundary_code=result.boundary.code,
                boundary=result.boundary.boundary,
                boundary_reason=result.boundary.reason,
                scope=result.boundary.scope,
                is_abstain=True,
                claim_ceiling=REAL_LOCAL_RAG_CLAIM_CEILING,
                source="real_local_rag",
                retrieval_kind=result.retriever_kind,
                retrieved_chunk_count=0,
                corpus_sha256=result.corpus_sha256,
            )

        if result.answer is None:
            return OperatorQAView(
                status="abstain",
                answer="目前 real corpus 沒有足夠的 BM25 證據；地端 AI 未被呼叫。",
                boundary_code="MISSING_EVIDENCE",
                boundary="Real PDF BM25 returned no matching evidence.",
                boundary_reason=(
                    "Real PDF BM25 returned no matching evidence; local AI was not called."
                ),
                scope=result.scope,
                is_abstain=True,
                claim_ceiling=REAL_LOCAL_RAG_CLAIM_CEILING,
                source="real_local_rag",
                retrieval_kind=result.retriever_kind,
                retrieved_chunk_count=0,
                corpus_sha256=result.corpus_sha256,
            )

        boundary = (
            "Real PDF BM25 evidence was sent to the configured local AI. "
            "Semantic entailment is not independently verified."
        )
        return OperatorQAView(
            status="answer",
            answer=result.answer,
            claims=[result.answer],
            citations=citations,
            boundary=boundary,
            boundary_reason=boundary,
            scope=result.scope,
            evidence_ids=evidence_ids,
            claim_evidence_ids=[evidence_ids],
            is_abstain=False,
            claim_ceiling=REAL_LOCAL_RAG_CLAIM_CEILING,
            source="real_local_rag",
            retrieval_kind=result.retriever_kind,
            local_model=result.local_model,
            retrieved_chunk_count=len(result.hits),
            corpus_sha256=result.corpus_sha256,
        )

    def ask(
        self,
        question: str,
        *,
        answer_scope: Optional[str] = None,
        retrieval_mode: str = "single_scope",
        allowed_evidence_scopes: Optional[Sequence[str]] = None,
        source: SourceMode = "fixture",
        fixture: str = "answered",
    ) -> OperatorQAView:
        if source == "fixture":
            resp = get_fixture(fixture)
            return to_operator_view(resp, source="fixture")
        if source == "real_local_rag":
            result = self._get_real_local_rag().answer(
                question,
                answer_scope=answer_scope,
                retrieval_mode=retrieval_mode,
                allowed_evidence_scopes=allowed_evidence_scopes,
            )
            return self._real_local_rag_view(result)
        resp = self._get_service().answer_question(
            question,
            answer_scope=answer_scope,
            retrieval_mode=retrieval_mode,  # type: ignore[arg-type]
            allowed_evidence_scopes=allowed_evidence_scopes,
        )
        return to_operator_view(resp, source="service")

    def stream_real_local_rag(
        self,
        question: str,
        *,
        answer_scope: Optional[str] = None,
        retrieval_mode: str = "single_scope",
        allowed_evidence_scopes: Optional[Sequence[str]] = None,
    ) -> Iterator[dict[str, Any]]:
        """Return the bounded real-local-RAG event stream for the web API."""

        def events() -> Iterator[dict[str, Any]]:
            # Keep corpus construction inside the iterator so the HTTP layer
            # can flush this status before the first real-PDF index build.
            yield {
                "type": "status",
                "stage": "loading_corpus",
                "message": "正在載入鎖定 PDF 並建立 BM25 index……",
            }
            yield from self._get_real_local_rag().stream_answer(
                question,
                answer_scope=answer_scope,
                retrieval_mode=retrieval_mode,
                allowed_evidence_scopes=allowed_evidence_scopes,
            )

        return events()

    def ask_service(
        self,
        question: str,
        *,
        answer_scope: Optional[str] = None,
        retrieval_mode: str = "single_scope",
        allowed_evidence_scopes: Optional[Sequence[str]] = None,
    ) -> QAResponse:
        return self._get_service().answer_question(
            question,
            answer_scope=answer_scope,
            retrieval_mode=retrieval_mode,  # type: ignore[arg-type]
            allowed_evidence_scopes=allowed_evidence_scopes,
        )


def fixture_catalog() -> dict[str, str]:
    return {
        name: resp.status
        for name, resp in FIXTURES.items()
    }
