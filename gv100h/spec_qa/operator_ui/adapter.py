"""QA adapter for the Operator UI.

Default path: frozen fixtures (no second retriever).
Optional live path: call existing GovernedQAService without changing it.
"""

from __future__ import annotations

from typing import Literal, Optional, Sequence

from gv100h.spec_qa.api.qa_service import GovernedQAService, QAResponse
from gv100h.spec_qa.operator_ui.contract import OperatorQAView, to_operator_view
from gv100h.spec_qa.operator_ui.fixtures import FIXTURES, get_fixture

SourceMode = Literal["fixture", "service"]


class OperatorQAAdapter:
    def __init__(self, *, service: Optional[GovernedQAService] = None) -> None:
        self._service = service or GovernedQAService()

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
        resp = self._service.answer_question(
            question,
            answer_scope=answer_scope,
            retrieval_mode=retrieval_mode,  # type: ignore[arg-type]
            allowed_evidence_scopes=allowed_evidence_scopes,
        )
        return to_operator_view(resp, source="service")

    def ask_service(
        self,
        question: str,
        *,
        answer_scope: Optional[str] = None,
        retrieval_mode: str = "single_scope",
        allowed_evidence_scopes: Optional[Sequence[str]] = None,
    ) -> QAResponse:
        return self._service.answer_question(
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
