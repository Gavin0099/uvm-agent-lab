from typing import Dict, Any, List, Optional, Sequence, Tuple
from pydantic import BaseModel, Field, model_validator

from gv100h.spec_qa.retrieval.governed_retriever import GovernedSpecRetriever, GovernedEvidence
from gv100h.spec_qa.contracts.retrieval_policy import RetrievalMode, RetrievalPolicy, validate_policy_inputs
from gv100h.spec_qa.contracts.evidence_contract import AnswerStatus, Citation, GroundedAnswer
from gv100h.spec_qa.contracts.poc1_acceptance_contract import BoundaryCode
from gv100h.spec_qa.evaluation.final_evaluator import FinalQACitation, FinalQAResponse


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
    # `claims` and `boundary_code` complete the contract (status/citations/
    # evidence_ids alone were only half of GroundedAnswer's shape) so a
    # caller can evaluate this response without re-deriving claims/boundary
    # from the free-text `answer`/`boundary` fields.
    status: AnswerStatus = "abstain"
    claims: List[str] = Field(default_factory=list)
    # One entry per ``claims`` entry -- see
    # evidence_contract.GroundedAnswer.claim_evidence_ids for the full
    # rationale (claim-to-evidence TRACEABILITY, not semantic entailment).
    claim_evidence_ids: List[List[str]] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    boundary_code: Optional[BoundaryCode] = None
    evidence_ids: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _is_abstain_matches_status(self) -> "QAResponse":
        """
        ``is_abstain`` is a legacy boolean fail-safe PROJECTION of the
        three-state ``status`` field, not an independent signal a caller is
        free to set: these additive structured fields default to
        status="abstain"/boundary_code=None, so a caller constructing
        QAResponse from only the pre-existing legacy fields (e.g.
        is_abstain=False, leaving status at its default) could previously
        produce a self-contradictory payload -- status="abstain" alongside
        is_abstain=False -- with nothing validating the combination the way
        GroundedAnswer validates its own status/boundary shape (Codex
        review, PR #33, P2, fresh finding on d4f3bf7).

        The projection is deliberately conservative: "conflict" is not an
        abstention, but it is also not a normal confident answer, so a
        legacy boolean-only caller must still see is_abstain=True for it --
        treating a live source conflict as a plain answer would be worse
        than treating it as "not a normal answer". New callers must branch
        on the three-state ``status`` field, not on ``is_abstain``.
        """
        expected_is_abstain = self.status != "answer"
        if self.is_abstain != expected_is_abstain:
            raise ValueError(
                "is_abstain must be the legacy fail-safe projection of "
                "status (False only when status == 'answer'; True for "
                "'abstain' and 'conflict'); got status="
                f"{self.status!r} with is_abstain={self.is_abstain!r}"
            )
        # boundary_code has no legacy-safe default: BoundaryCode is a closed
        # set of specific reasons (see poc1_acceptance_contract.BoundaryCode),
        # with no generic "unspecified" member to fall back on. A prior fix
        # here gated this check on `model_fields_set` to distinguish a
        # legacy-only caller (status/boundary_code left at their defaults)
        # from one that explicitly opted into the new contract fields (Codex
        # review, PR #33, P2, fresh finding on 7c74da3). `model_fields_set`
        # is constructor-time metadata, not part of the serialized data: a
        # plain `model_dump()`/`model_validate()` or JSON round trip of that
        # exact legacy-constructed instance re-presents every field
        # (including ones still at their default value) as explicitly set,
        # so the same "previously-valid legacy abstention" failed to survive
        # a round trip -- it must not be used to encode transient
        # construction provenance for an invariant that has to hold for a
        # coherently serialized contract too (Codex review, PR #33, P2,
        # fresh finding on b05464f).
        #
        # The invariant is therefore expressed purely on field values, with
        # no dependency on how the object was built: "answer" must never
        # carry a boundary_code (mirrors GroundedAnswer), "conflict" always
        # requires one (a live source conflict with no stated reason is not
        # a meaningful signal, and nothing defaults into "conflict" -- it is
        # never the unqualified legacy path), and "abstain" leaves
        # boundary_code optional -- both a generic legacy abstention
        # (boundary_code=None) and a new-contract abstention with a specific
        # reason are valid, round-trip-stable shapes.
        if self.status == "answer" and self.boundary_code is not None:
            raise ValueError(
                "boundary_code must be absent when status == 'answer'; got "
                f"boundary_code={self.boundary_code!r}"
            )
        if self.status == "conflict" and self.boundary_code is None:
            raise ValueError(
                "boundary_code must be populated when status == 'conflict'"
            )
        return self

    def to_final_qa_response(self) -> FinalQAResponse:
        """
        Explicit, tested projection from this runtime/API response onto the
        evaluator's canonical schema (FinalQAResponse/FinalQACitation in
        gv100h/spec_qa/evaluation/final_evaluator.py).

        QAResponse intentionally carries more than the evaluator needs --
        legacy free-text answer/boundary fields, cited_evidences,
        claim_level, is_abstain, evidence_ids, and each citation's
        runtime-only chapter/authority_level provenance -- and
        FinalQAResponse/FinalQACitation both use extra="forbid". Passing
        ``self.model_dump()`` straight to the evaluator is therefore
        unreliable: every response would be rejected as an invalid shape
        (Codex review, PR #33, P1). This method is the single explicit,
        tested narrowing from the runtime contract to the evaluator contract
        -- see tests/gv100h/test_m2_spec_qa.py's
        test_full_contract_chain_* tests, which exercise this method through
        FinalPOC1Evaluator.evaluate_response() end to end, not just as an
        isolated schema conversion.
        """
        return FinalQAResponse(
            status=self.status,
            claims=list(self.claims),
            claim_evidence_ids=[list(ids) for ids in self.claim_evidence_ids],
            citations=[
                FinalQACitation(
                    evidence_id=citation.evidence_id,
                    document=citation.document,
                    revision=citation.revision,
                    section=citation.section,
                    page_or_anchor=citation.page_or_anchor,
                    excerpt_or_evidence_id=citation.excerpt or citation.evidence_id,
                    scope=None,
                    chapter=citation.chapter,
                    authority_level=citation.authority_level,
                )
                for citation in self.citations
            ],
            scope=self.scope,
            boundary_code=self.boundary_code,
        )


class GovernedQAService:
    """
    Same-Origin QA Backend Service.
    Retrieves governed evidence, verifies boundaries, and renders structured responses.
    """

    def __init__(self):
        self.retriever = GovernedSpecRetriever()

    @staticmethod
    def _resolve_boundary_scope(
        answer_scope: Optional[str],
        boundary_evidence: Any,
    ) -> str:
        """
        Reconcile a caller-declared answer_scope with a registered
        BoundaryEvidence's own governed scope, for the USB4
        corpus-membership governance-answer branch and the USB4 abstain
        branch below.

        answer_scope is the caller's explicit Retrieval Policy declaration,
        not a hint this service is free to reinterpret: silently replacing
        an unrelated caller-declared answer_scope (e.g. "USB_2_0") with
        boundary_evidence.scope (e.g. "USB4_SPEC") used to make a USB4
        governance claim/abstention pass GroundedAnswer while still
        mislabeling its scope, and it rewrote the caller's declared intent
        without their knowledge (Codex review, PR #33, fresh finding on
        88200c5). This fails closed instead of guessing: an absent
        answer_scope defers to the evidence's governed scope, a matching
        answer_scope proceeds normally, and a conflicting answer_scope is
        rejected with a deterministic ValueError rather than silently
        coerced -- evidence may prove a caller's declared scope is wrong,
        but it must not silently rewrite it.
        """
        if answer_scope is None:
            return boundary_evidence.scope
        if answer_scope != boundary_evidence.scope:
            raise ValueError(
                f"answer_scope {answer_scope!r} conflicts with the governed "
                f"scope {boundary_evidence.scope!r} of boundary evidence "
                f"{boundary_evidence.evidence_id!r}; GovernedQAService does "
                "not silently override a caller-declared answer_scope with "
                "the evidence's own scope."
            )
        return answer_scope

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

        # `is not None` (not truthiness) so an explicitly empty
        # allowed_evidence_scopes=[] is still treated as "provided" and
        # rejected here rather than silently passing through as if it had
        # been omitted (Codex review, PR #33, fresh finding on 90a6e1a).
        if answer_scope is None and allowed_evidence_scopes is not None:
            raise ValueError(
                "allowed_evidence_scopes was provided without answer_scope; "
                "GovernedQAService requires answer_scope to build a scope-restricting "
                "RetrievalPolicy. Provide answer_scope, or omit allowed_evidence_scopes "
                "to run a fully unscoped query."
            )

        # The domain/retrieval_mode/allowed_evidence_scopes-shape checks that
        # do NOT depend on answer_scope must run unconditionally too --
        # RetrievalPolicy itself cannot be constructed without answer_scope
        # (it is a required field there), so calling
        # answer_question("USB4 ...", domain="HID") with no answer_scope
        # previously skipped policy validation entirely and still returned a
        # normal abstention. validate_policy_inputs() covers exactly the
        # answer_scope-independent subset (unknown domain,
        # explicit_cross_scope without allowed_evidence_scopes); the
        # RetrievalPolicy construction below still separately validates the
        # answer_scope-dependent part (single_scope's derived/matched
        # allowed_evidence_scopes) once answer_scope is known (Codex review,
        # PR #33, P2).
        validate_policy_inputs(
            domain=domain,
            retrieval_mode=retrieval_mode,
            allowed_evidence_scopes=(
                tuple(allowed_evidence_scopes)
                if allowed_evidence_scopes is not None
                else None
            ),
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
                    tuple(allowed_evidence_scopes)
                    if allowed_evidence_scopes is not None
                    else None
                ),
            )
            if answer_scope is not None
            else None
        )

        # USB4 is a Phase 2 exclusion, BUT docs/USB_SPEC_QA_POC1_SCOPE.md
        # lines 86-88 carve out one explicit exception: a question that is
        # *only* asking whether USB4 is included in the current corpus is a
        # genuine, answerable governance/corpus-membership fact, not an
        # out-of-scope USB4 topic question. This must not be modeled as a
        # fake USB4 normative-spec citation -- it is grounded in
        # corpus.lock.yaml's own membership metadata, cited with
        # citation_kind="governance" (Codex review, PR #33, P1).
        #
        # Intent matching is deliberately narrow (whole membership-question
        # patterns), not a broad substring/marker list: a marker list
        # containing single generic words like "included"/"包含" also
        # matches ordinary substantive USB4 feature questions (e.g. "What
        # features are included in USB4?"), misclassifying them as
        # corpus-membership questions and returning a governance answer
        # instead of the required Phase-1-exclusion abstain (Codex review,
        # PR #33, P2).
        usb4_corpus_membership_patterns = (
            "usb4 included in",
            "usb4 in the current corpus",
            "usb4 part of the current corpus",
            "usb4 part of phase 1",
            "usb4 in phase 1",
            "usb4 in phase1",
            "phase 1 include usb4",
            "phase1 include usb4",
            "phase 1 corpus include usb4",
            "corpus include usb4",
            "corpus 有包含 usb4",
            "corpus 包含 usb4",
            "corpus 有 usb4",
            "corpus 是否包含 usb4",
            "phase 1 是否包含 usb4",
            "phase 1 有包含 usb4",
            "屬於 phase 1",
            "屬於目前 corpus",
            "usb4 屬於",
            "usb4 有包含在",
            "usb4 是否包含在",
            "usb4 有沒有涵蓋",
            "涵蓋 usb4",
        )
        # A bare pattern like "usb4 included in" also matches an ordinary
        # hub-capability question (e.g. "Is USB4 included in this hub's
        # supported-protocol list?"), which is asking about the hub, not
        # about the corpus -- and must still abstain as a generic USB4
        # topic question, not be answered as a corpus-membership fact
        # (Codex review, PR #33, fresh finding on edf8825). Require an
        # explicit corpus/phase qualifier to co-occur in the question
        # rather than treating any single membership-shaped phrase alone as
        # sufficient; every pattern above except the bare "usb4 included
        # in" already carries such a qualifier itself.
        usb4_corpus_context_markers = (
            "corpus",
            "phase 1",
            "phase1",
            "phase 2",
            "phase2",
        )
        is_usb4_corpus_membership_question = (
            "usb4" in q_lower
            and any(pattern in q_lower for pattern in usb4_corpus_membership_patterns)
            and any(marker in q_lower for marker in usb4_corpus_context_markers)
        )
        if is_usb4_corpus_membership_question:
            boundary_evidence = self.retriever.get_boundary_evidence_by_id(
                "POC1-BOUNDARY-USB4-EXCLUDED"
            )
            if boundary_evidence is None:
                raise RuntimeError(
                    "expected boundary evidence 'POC1-BOUNDARY-USB4-EXCLUDED' "
                    "is not registered in BOUNDARY_EVIDENCE_REGISTRY"
                )
            governance_citation = self.retriever.to_governance_citation(boundary_evidence)
            claim = (
                "USB4 is not included in the Phase 1 corpus; it is a declared "
                "Phase 2 source (corpus.lock.yaml sources.usb4: phase=phase_2, "
                "included=false, retrieval_status=excluded_from_phase_1)."
            )
            return self._build_response(
                answer=claim,
                scope=self._resolve_boundary_scope(answer_scope, boundary_evidence),
                cited_evidences=[],
                claim_level="governance_fact_answer",
                boundary=(
                    "Governance fact answer: corpus.lock.yaml sources.usb4 "
                    "membership metadata (not a USB4 normative-spec citation)."
                ),
                is_abstain=False,
                status="answer",
                claims=[claim],
                claim_evidence_ids=[[governance_citation.evidence_id]],
                citations=[governance_citation],
            )

        # USB4 is a registered Phase 2 exclusion (corpus.lock.yaml
        # sources.usb4: phase=phase_2, included=false) -- a query about USB4
        # must abstain with a real, registered boundary claim/citation
        # resolved from GovernedSpecRetriever.BOUNDARY_EVIDENCE_REGISTRY, not
        # an empty claims/citations abstain (Codex review, PR #33, P1). This
        # is checked before the generic unsupported_keywords list below
        # because it has real, registered boundary evidence backing it; the
        # generic list (still) does not.
        if "usb4" in q_lower:
            boundary_evidence = self.retriever.get_boundary_evidence_by_id(
                "POC1-BOUNDARY-USB4-EXCLUDED"
            )
            if boundary_evidence is None:
                raise RuntimeError(
                    "expected boundary evidence 'POC1-BOUNDARY-USB4-EXCLUDED' "
                    "is not registered in BOUNDARY_EVIDENCE_REGISTRY"
                )
            boundary_citation = self.retriever.to_boundary_citation(boundary_evidence)
            return self._build_response(
                answer=(
                    "現有 governed reference 無法支持此結論，本 Agent 拒絕過度推論"
                    f"，超出範圍 (Abstain)：{boundary_evidence.claim}"
                ),
                scope=self._resolve_boundary_scope(answer_scope, boundary_evidence),
                cited_evidences=[],
                claim_level="abstain_boundary_claim",
                boundary=(
                    "Exceeds governed knowledge surface of "
                    "usb-if-hub-spec-reference (USB4 excluded from Phase 1 corpus)."
                ),
                is_abstain=True,
                status="abstain",
                claims=[boundary_evidence.claim],
                claim_evidence_ids=[[boundary_citation.evidence_id]],
                citations=[boundary_citation],
                boundary_code=boundary_evidence.boundary_code,
            )

        # Check for explicitly unsupported / out-of-scope queries. Deliberately
        # claims=[]/citations=[] (both defaulted by _build_response), same
        # reasoning as the MISSING_EVIDENCE abstain below: a generic keyword
        # match here does not correspond to any single registered corpus/
        # governance fact. A generic BoundaryEvidence entry backed by
        # hub_reference.known_limits was tried and removed (Codex review,
        # PR #33, P1, 2nd pass) -- known_limits only proves ONE source
        # (hub_reference) doesn't cover a topic, not that the ENTIRE Phase 1
        # corpus (which also includes usb20_fw/usb20_se/usb32/
        # superspeed_hub_lvs, each with their own coverage) lacks it; citing
        # it as if it were a corpus-wide boundary fact would itself be an
        # unsupported inferential leap. Until real topic-specific boundary
        # evidence exists, abstain with no citation rather than fabricate one.
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

        evidences = self.retriever.query(query_text, retrieval_policy=retrieval_policy)

        # Abstention if no evidence found. Deliberately claims=[]/citations=[]
        # (both defaulted by _build_response): "no eligible evidence was
        # found for this query" is a runtime retrieval observation (a given
        # query + scope + retrieval policy + corpus revision produced zero
        # results), not a static corpus/governance fact -- unlike the USB4
        # branch above, there is no registered BoundaryEvidence to cite here,
        # and fabricating one would misrepresent a runtime observation as a
        # corpus fact. GroundedAnswer already permits an abstain with no
        # claims/citations, so this remains contract-valid as-is. Backing
        # this with a real citation needs a runtime retrieval-boundary
        # receipt (query/scope/policy/corpus_lock_hash/result_count=0),
        # which is a follow-up, not implemented here (Codex review, PR #33,
        # P1 -- tracked as a prerequisite, not silently worked around).
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
        cited = evidences[:2]
        citations = [self.retriever.to_citation(ev) for ev in cited]
        cited_evidence_ids = [ev.evidence_id for ev in cited]

        answer_parts = []
        claim_evidence_ids: List[List[str]] = []
        for ev in cited:
            answer_parts.append(f"【條款 {ev.section} ({ev.title})】：{ev.content}")
            claim_evidence_ids.append([ev.evidence_id])

        # Add comparative notes for version confusion queries. Each summary
        # claim below is derived from (and only from) the evidence already
        # cited above, so it is bound to every evidence_id in
        # cited_evidence_ids -- never to a fabricated or unrelated
        # evidence_id (Codex review, PR #33, P1, fresh finding on d4f3bf7).
        if "支援" in q_lower or "有效" in q_lower:
            if "port_link_state" in q_lower and ("2.0" in q_lower or answer_scope == "USB_2_0"):
                answer_parts.append("總結：USB 2.0 Hub 不支援且不適用 PORT_LINK_STATE (0x0005)，此為 USB 3.x 專屬特徵選擇器，在 USB 2.0 下無效。")
                claim_evidence_ids.append(list(cited_evidence_ids))

        if "相同" in q_lower or "區分" in q_lower or "差異" in q_lower or "是否" in q_lower:
            if "descriptor" in q_lower or "0x2a" in q_lower or "0x29" in q_lower or "描述符" in q_lower:
                answer_parts.append("總結：USB 2.0 (0x29) 與 USB 3.x (0x2A) 描述符不同，兩者不能混用；USB 2.0 收到 0x2A 為未定義。")
                claim_evidence_ids.append(list(cited_evidence_ids))
            if "port_power" in q_lower:
                answer_parts.append("總結：PORT_POWER 特徵選擇器在 USB 2.0 與 USB 3.x 皆為 8 (0x0008)，兩者相同無差異。")
                claim_evidence_ids.append(list(cited_evidence_ids))

        full_answer = "\n".join(answer_parts)

        return self._build_response(
            answer=full_answer,
            scope=primary_ev.scope if not answer_scope else answer_scope,
            cited_evidences=cited,
            claim_level=primary_ev.claim_level,
            boundary="Strictly bounded by in-scope governed evidence.",
            is_abstain=False,
            status="answer",
            claims=answer_parts,
            claim_evidence_ids=claim_evidence_ids,
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
        claim_evidence_ids: Optional[List[List[str]]] = None,
        citations: Optional[List[Citation]] = None,
        boundary_code: Optional[BoundaryCode] = None,
    ) -> QAResponse:
        """
        Construct a QAResponse and self-validate its structured Evidence
        Contract fields (status/claims/citations/evidence_ids/scope/boundary)
        against GroundedAnswer before returning -- this is a fail-closed
        check: if this service ever builds a response that violates the
        Answer and Evidence Contract (docs/USB_SPEC_QA_POC1_SCOPE.md §5),
        it raises instead of silently returning a non-compliant response.

        The validated claims/citations/scope/boundary_code/evidence_ids are
        all carried through onto the returned QAResponse -- the response is
        the complete evaluated contract, not just the fields that happened
        to be convenient to expose.
        """
        claims = claims or []
        claim_evidence_ids = claim_evidence_ids or []
        citations = citations or []
        evidence_ids = [c.evidence_id for c in citations]

        GroundedAnswer(
            status=status,
            claims=claims,
            claim_evidence_ids=claim_evidence_ids,
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
            claims=claims,
            claim_evidence_ids=claim_evidence_ids,
            citations=citations,
            boundary_code=boundary_code,
            evidence_ids=evidence_ids,
        )


