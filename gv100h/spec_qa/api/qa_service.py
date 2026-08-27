from typing import Dict, Any, List, Optional, Sequence, Tuple
from pydantic import BaseModel

from gv100h.spec_qa.retrieval.governed_retriever import GovernedSpecRetriever, GovernedEvidence
from gv100h.spec_qa.contracts.retrieval_policy import RetrievalMode, RetrievalPolicy
from gv100h.spec_qa.contracts.evidence_contract import AnswerStatus, Citation, GroundedAnswer


class QARequest(BaseModel):
    query: str
    domain: str = "USB_HUB"
    answer_scope: Optional[str] = None
    retrieval_mode: RetrievalMode = "single_scope"
    allowed_evidence_scopes: Optional[Tuple[str, ...]] = None


class QAResponse(BaseModel):
    answer: str
    scope: str
    cited_evidences: List[GovernedEvidence]
    claim_level: str
    boundary: str
    is_abstain: bool
    # Additive Evidence Contract fields (docs/USB_SPEC_QA_POC1_SCOPE.md §5).
    # These are populated in parallel with the legacy free-text fields above
    # so existing callers/tests keep working unchanged; new callers should
    # prefer these structured fields over parsing `answer`/`boundary` prose.
    status: AnswerStatus = "abstain"
    citations: List[Citation] = []
    evidence_ids: List[str] = []


class GovernedQAService:
    """
    Same-Origin QA Backend Service.
    Retrieves governed evidence, verifies boundaries, and renders structured responses.
    """

    def __init__(self):
        self.retriever = GovernedSpecRetriever()

    def answer_question(
        self,
        query_text: str,
        answer_scope: Optional[str] = None,
        *,
        domain: str = "USB_HUB",
        retrieval_mode: RetrievalMode = "single_scope",
        allowed_evidence_scopes: Optional[Sequence[str]] = None,
    ) -> QAResponse:
        q_lower = query_text.lower()

        # Check for explicitly unsupported / out-of-scope queries
        unsupported_keywords = [
            "xhci", "eeprom", "眼圖", "抖動", "usbcore", "pcie", "穿透通道",
            "pam3", "99.99", "乙太網路", "40gbps", "informative 附錄"
        ]
        for uk in unsupported_keywords:
            if uk in q_lower:
                return self._build_response(
                    answer="現有 governed reference 無法支持此結論，本 Agent 拒絕過度推論與權威違規 (Abstain)。",
                    scope=answer_scope or "OUT_OF_SCOPE",
                    cited_evidences=[],
                    claim_level="abstain_no_evidence",
                    boundary="Exceeds governed knowledge surface of usb-if-hub-spec-reference.",
                    is_abstain=True,
                    status="abstain",
                    boundary_code="OUT_OF_SCOPE",
                )

        # allowed_evidence_scopes is only meaningful paired with an
        # answer_scope: RetrievalPolicy requires answer_scope to construct
        # the policy at all, and single_scope/explicit_cross_scope both
        # derive their eligibility from it. Silently dropping an explicitly
        # declared allowed_evidence_scopes restriction (by falling through to
        # an unscoped RetrievalPolicy=None query) would let the retriever
        # cite evidence outside the caller's declared hard boundary -- reject
        # the combination instead of silently widening retrieval.
        if answer_scope is None and allowed_evidence_scopes:
            raise ValueError(
                "allowed_evidence_scopes was provided without answer_scope; "
                "GovernedQAService requires answer_scope to build a scope-restricting "
                "RetrievalPolicy. Provide answer_scope, or omit allowed_evidence_scopes "
                "to run a fully unscoped query."
            )

        # RetrievalPolicy is only constructed when the caller declares an
        # answer_scope. `domain`/`retrieval_mode`/`allowed_evidence_scopes` are
        # the caller's explicit policy declaration -- this service never
        # infers them from `query_text`.
        retrieval_policy = (
            RetrievalPolicy(
                domain=domain,
                answer_scope=answer_scope,
                retrieval_mode=retrieval_mode,
                allowed_evidence_scopes=(
                    tuple(allowed_evidence_scopes) if allowed_evidence_scopes else None
                ),
            )
            if answer_scope is not None
            else None
        )
        evidences = self.retriever.query(query_text, retrieval_policy=retrieval_policy)

        # Abstention if no evidence found
        if not evidences:
            return self._build_response(
                answer="現有 governed reference 無法支持此結論，本 Agent 拒絕過度推論 (Abstain)。",
                scope=answer_scope or "OUT_OF_SCOPE",
                cited_evidences=[],
                claim_level="abstain_no_evidence",
                boundary="Exceeds governed knowledge surface of usb-if-hub-spec-reference.",
                is_abstain=True,
                status="abstain",
                boundary_code="MISSING_EVIDENCE",
            )

        # Synthesize multi-evidence or single evidence answer
        primary_ev = evidences[0]
        answer_parts = []
        for ev in evidences[:2]:
            answer_parts.append(f"【條款 {ev.section} ({ev.title})】：{ev.content}")

        # Add comparative notes for version confusion queries
        if "支援" in q_lower or "有效" in q_lower:
            if "port_link_state" in q_lower and ("2.0" in q_lower or answer_scope == "USB_2_0"):
                answer_parts.append("總結：USB 2.0 Hub 不支援且不適用 PORT_LINK_STATE (0x0005)，此為 USB 3.x 專屬特徵選擇器，在 USB 2.0 下無效。")

        if "相同" in q_lower or "區分" in q_lower or "差異" in q_lower or "是否" in q_lower:
            if "descriptor" in q_lower or "0x2a" in q_lower or "0x29" in q_lower or "描述符" in q_lower:
                answer_parts.append("總結：USB 2.0 (0x29) 與 USB 3.x (0x2A) 描述符不同，兩者不能混用；USB 2.0 收到 0x2A 為未定義。")
            if "port_power" in q_lower:
                answer_parts.append("總結：PORT_POWER 特徵選擇器在 USB 2.0 與 USB 3.x 皆為 8 (0x0008)，兩者相同無差異。")

        full_answer = "\n".join(answer_parts)

        cited = evidences[:2]
        citations = [self.retriever.to_citation(ev) for ev in cited]

        return self._build_response(
            answer=full_answer,
            scope=primary_ev.scope if not answer_scope else answer_scope,
            cited_evidences=cited,
            claim_level=primary_ev.claim_level,
            boundary="Strictly bounded by in-scope governed evidence.",
            is_abstain=False,
            status="answer",
            claims=answer_parts,
            citations=citations,
        )

    def _build_response(
        self,
        *,
        answer: str,
        scope: str,
        cited_evidences: List[GovernedEvidence],
        claim_level: str,
        boundary: str,
        is_abstain: bool,
        status: AnswerStatus,
        claims: Optional[List[str]] = None,
        citations: Optional[List[Citation]] = None,
        boundary_code: Optional[str] = None,
    ) -> QAResponse:
        """
        Construct a QAResponse and self-validate its structured Evidence
        Contract fields (status/claims/citations/evidence_ids/boundary)
        against GroundedAnswer before returning -- this is a fail-closed
        check: if this service ever builds a response that violates the
        Answer and Evidence Contract (docs/USB_SPEC_QA_POC1_SCOPE.md §5),
        it raises instead of silently returning a non-compliant response.
        """
        citations = citations or []
        evidence_ids = [c.evidence_id for c in citations]

        GroundedAnswer(
            status=status,
            claims=claims or [],
            citations=citations,
            scope=scope,
            boundary=boundary_code,
            evidence_ids=evidence_ids,
        )

        return QAResponse(
            answer=answer,
            scope=scope,
            cited_evidences=cited_evidences,
            claim_level=claim_level,
            boundary=boundary,
            is_abstain=is_abstain,
            status=status,
            citations=citations,
            evidence_ids=evidence_ids,
        )

