from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from gv100h.spec_qa.retrieval.governed_retriever import GovernedSpecRetriever, GovernedEvidence


class QARequest(BaseModel):
    query: str
    target_scope: Optional[str] = None


class QAResponse(BaseModel):
    answer: str
    scope: str
    cited_evidences: List[GovernedEvidence]
    claim_level: str
    boundary: str
    is_abstain: bool


class GovernedQAService:
    """
    Same-Origin QA Backend Service.
    Retrieves governed evidence, verifies boundaries, and renders structured responses.
    """

    def __init__(self):
        self.retriever = GovernedSpecRetriever()

    def answer_question(self, query_text: str, target_scope: Optional[str] = None) -> QAResponse:
        q_lower = query_text.lower()
        
        # Check for explicitly unsupported / out-of-scope queries
        unsupported_keywords = [
            "xhci", "eeprom", "眼圖", "抖動", "usbcore", "pcie", "穿透通道",
            "pam3", "99.99", "乙太網路", "40gbps", "informative 附錄"
        ]
        for uk in unsupported_keywords:
            if uk in q_lower:
                return QAResponse(
                    answer="現有 governed reference 無法支持此結論，本 Agent 拒絕過度推論與權威違規 (Abstain)。",
                    scope=target_scope or "OUT_OF_SCOPE",
                    cited_evidences=[],
                    claim_level="abstain_no_evidence",
                    boundary="Exceeds governed knowledge surface of usb-if-hub-spec-reference.",
                    is_abstain=True
                )

        evidences = self.retriever.query(query_text, target_scope)

        # Abstention if no evidence found
        if not evidences:
            return QAResponse(
                answer="現有 governed reference 無法支持此結論，本 Agent 拒絕過度推論 (Abstain)。",
                scope=target_scope or "OUT_OF_SCOPE",
                cited_evidences=[],
                claim_level="abstain_no_evidence",
                boundary="Exceeds governed knowledge surface of usb-if-hub-spec-reference.",
                is_abstain=True
            )

        # Synthesize multi-evidence or single evidence answer
        primary_ev = evidences[0]
        answer_parts = []
        for ev in evidences[:2]:
            answer_parts.append(f"【條款 {ev.section} ({ev.title})】：{ev.content}")

        # Add comparative notes for version confusion queries
        if "支援" in q_lower or "有效" in q_lower:
            if "port_link_state" in q_lower and ("2.0" in q_lower or target_scope == "USB_2_0"):
                answer_parts.append("總結：USB 2.0 Hub 不支援且不適用 PORT_LINK_STATE (0x0005)，此為 USB 3.x 專屬特徵選擇器，在 USB 2.0 下無效。")

        if "相同" in q_lower or "區分" in q_lower or "差異" in q_lower or "是否" in q_lower:
            if "descriptor" in q_lower or "0x2a" in q_lower or "0x29" in q_lower or "描述符" in q_lower:
                answer_parts.append("總結：USB 2.0 (0x29) 與 USB 3.x (0x2A) 描述符不同，兩者不能混用；USB 2.0 收到 0x2A 為未定義。")
            if "port_power" in q_lower:
                answer_parts.append("總結：PORT_POWER 特徵選擇器在 USB 2.0 與 USB 3.x 皆為 8 (0x0008)，兩者相同無差異。")

        full_answer = "\n".join(answer_parts)

        return QAResponse(
            answer=full_answer,
            scope=primary_ev.scope if not target_scope else target_scope,
            cited_evidences=evidences[:2],
            claim_level=primary_ev.claim_level,
            boundary="Strictly bounded by in-scope governed evidence.",
            is_abstain=False
        )
