import json
from http.client import HTTPConnection
from http.server import HTTPServer
from pathlib import Path
from threading import Thread

import pytest

from gv100h.spec_qa.contracts.governed_chunk import GovernedChunk
from gv100h.spec_qa.operator_ui.adapter import OperatorQAAdapter
from gv100h.spec_qa.operator_ui.real_local_rag import (
    LocalAIClient,
    LocalAICompletion,
    LocalAIStreamEvent,
    RealLocalRAG,
    classify_real_local_rag_boundary,
)
from gv100h.spec_qa.retrieval.real_corpus_retriever import (
    GovernedChunkRetrievalHit,
)
from gv100h.spec_qa.operator_ui.server import OperatorUIHandler


class FakeRetriever:
    retriever_kind = "governed_chunk_bm25_v1"
    corpus_sha256 = "corpus-digest"

    def __init__(self, hits):
        self.hits = tuple(hits)
        self.chunks = tuple(hit.chunk for hit in self.hits)
        self.calls = []

    def query(self, query, top_k, *, allowed_source_ids):
        self.calls.append(
            {
                "query": query,
                "top_k": top_k,
                "allowed_source_ids": tuple(allowed_source_ids),
            }
        )
        return list(self.hits)[:top_k]


def _hit(*, source_id="usb32", section="10.16.2.10", page="p.483", content="PORT_POWER value is 8"):
    chunk = GovernedChunk.build(
        source_id=source_id,
        document="USB 3.2 Specification",
        revision="Rev 1.1",
        section=section,
        page_or_anchor=page,
        authority_level="authoritative",
        chunk_kind="paragraph",
        content=content,
        index=0,
    )
    return GovernedChunkRetrievalHit(
        chunk=chunk,
        score=4.2,
        matched_terms=("port_power", "value"),
    )


class FakeLocalAI:
    def __init__(self, content="The locked evidence says PORT_POWER is 8."):
        self.content = content
        self.calls = []

    def complete(self, *, system_prompt, user_prompt):
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        return LocalAICompletion(content=self.content, model="fake-local-qwen")


class FakeStreamingLocalAI:
    model = "fake-local-qwen"

    def __init__(self):
        self.calls = []

    def stream_complete(self, *, system_prompt, user_prompt):
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        yield LocalAIStreamEvent(text="PORT_POWER", model=self.model)
        yield LocalAIStreamEvent(text=" 的值為 8。", model=self.model)
        yield LocalAIStreamEvent(
            text="",
            model=self.model,
            finish_reason="stop",
            usage={"prompt_tokens": 42, "completion_tokens": 5, "total_tokens": 47},
            timings={"predicted_per_second": 6.25},
        )


class FakeInsufficientStreamingLocalAI:
    model = "fake-local-qwen"

    def __init__(self):
        self.calls = []

    def stream_complete(self, *, system_prompt, user_prompt):
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        yield LocalAIStreamEvent(text="INSUFFICIENT_", model=self.model)
        yield LocalAIStreamEvent(text="EVIDENCE", model=self.model)
        yield LocalAIStreamEvent(text="：目前沒有足夠的直接證據。", model=self.model)
        yield LocalAIStreamEvent(
            text="",
            model=self.model,
            finish_reason="length",
            usage={"prompt_tokens": 42, "completion_tokens": 7, "total_tokens": 49},
            timings={"predicted_per_second": 6.25},
        )


class FakeWrongLiteralStreamingLocalAI:
    model = "fake-local-qwen"

    def __init__(self):
        self.calls = []

    def stream_complete(self, *, system_prompt, user_prompt):
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        yield LocalAIStreamEvent(text="PORT_POWER = 99 V", model=self.model)
        yield LocalAIStreamEvent(
            text="。",
            model=self.model,
            finish_reason="stop",
            usage={"prompt_tokens": 42, "completion_tokens": 5, "total_tokens": 47},
            timings={"predicted_per_second": 6.25},
        )


def test_real_local_rag_retrieves_by_scope_and_sends_evidence_to_local_ai():
    hit = _hit()
    retriever = FakeRetriever([hit])
    local_ai = FakeLocalAI()
    rag = RealLocalRAG(retriever, local_ai, top_k=5)

    result = rag.answer(
        "PORT_POWER feature selector value",
        answer_scope="USB_3_X",
    )

    assert result.answer == "The locked evidence says PORT_POWER is 8."
    assert result.local_model == "fake-local-qwen"
    assert result.retriever_kind == "governed_chunk_bm25_v1"
    assert result.hits == (hit,)
    assert retriever.calls == [
        {
            "query": "PORT_POWER feature selector value",
            "top_k": 5,
            "allowed_source_ids": ("usb32",),
        }
    ]
    assert "PORT_POWER value is 8" in local_ai.calls[0]["user_prompt"]
    assert hit.chunk.chunk_id in local_ai.calls[0]["user_prompt"]


def test_real_local_rag_does_not_call_local_ai_without_retrieval_hits():
    retriever = FakeRetriever([])
    local_ai = FakeLocalAI()
    result = RealLocalRAG(retriever, local_ai).answer(
        "question with no matching evidence",
        answer_scope="USB_3_X",
    )

    assert result.answer is None
    assert result.local_model is None
    assert result.hits == ()
    assert local_ai.calls == []


def test_real_local_rag_rejects_usb4_scope():
    retriever = FakeRetriever([])
    local_ai = FakeLocalAI()
    rag = RealLocalRAG(retriever, local_ai)

    result = rag.answer("USB4 question", answer_scope="USB4_SPEC")

    assert result.boundary is not None
    assert result.boundary.code == "OUT_OF_SCOPE"
    assert result.hits == ()
    assert retriever.calls == []
    assert local_ai.calls == []


def test_boundary_classifier_routes_usb4_before_retrieval():
    boundary = classify_real_local_rag_boundary(
        "What is required by USB4 Router?",
        "USB_HUB_COMMON",
        available_sections=("6.9.3",),
    )

    assert boundary is not None
    assert boundary.code == "OUT_OF_SCOPE"
    assert boundary.scope == "USB4_SPEC"


def test_boundary_classifier_routes_unknown_explicit_section():
    boundary = classify_real_local_rag_boundary(
        "What does section 99.99 require?",
        "USB_2_0",
        available_sections=("7.1.2.2", "11.24.2.2"),
    )

    assert boundary is not None
    assert boundary.code == "FICTIONAL_SECTION"
    assert "99.99" in boundary.reason


def test_boundary_classifier_routes_unlisted_authority():
    boundary = classify_real_local_rag_boundary(
        "Can an unlisted authority be used for this answer?",
        "USB_3_X",
        available_sections=("6.9.3",),
    )

    assert boundary is not None
    assert boundary.code == "AUTHORITY_MISMATCH"
    assert boundary.scope == "USB_3_X"


def test_boundary_classifier_routes_chinese_unlisted_source():
    boundary = classify_real_local_rag_boundary(
        "請使用未列入 Phase 1 corpus 的來源回答。",
        "USB_3_X",
        available_sections=("6.9.3",),
    )

    assert boundary is not None
    assert boundary.code == "AUTHORITY_MISMATCH"
    assert boundary.scope == "USB_3_X"


def test_boundary_classifier_checks_section_only_in_allowed_sources():
    usb2_hit = _hit(source_id="usb20_se", section="6.7", page="p.135")
    usb3_hit = _hit(source_id="usb32", section="6.9.3", page="p.135")
    retriever = FakeRetriever([usb2_hit, usb3_hit])
    local_ai = FakeLocalAI()

    result = RealLocalRAG(retriever, local_ai).answer(
        "What does section 6.7 require?",
        answer_scope="USB_3_X",
    )

    assert result.boundary is not None
    assert result.boundary.code == "FICTIONAL_SECTION"
    assert result.hits == ()
    assert retriever.calls == []
    assert local_ai.calls == []


def test_real_local_rag_stream_checks_section_only_in_allowed_sources():
    usb2_hit = _hit(source_id="usb20_se", section="6.7", page="p.135")
    usb3_hit = _hit(source_id="usb32", section="6.9.3", page="p.135")
    retriever = FakeRetriever([usb2_hit, usb3_hit])
    local_ai = FakeLocalAI()

    events = list(
        RealLocalRAG(retriever, local_ai).stream_answer(
            "What does section 6.7 require?",
            answer_scope="USB_3_X",
        )
    )

    assert events[0]["boundary_code"] == "FICTIONAL_SECTION"
    assert events[0]["citations"] == []
    assert events[-1]["local_model"] is None
    assert not [event for event in events if event["type"] == "token"]
    assert retriever.calls == []
    assert local_ai.calls == []


def test_real_local_rag_stream_routes_section_missing_from_allowed_sources():
    usb2_hit = _hit(source_id="usb20_se", section="6.7", page="p.135")
    usb3_hit = _hit(source_id="usb32", section="6.9.3", page="p.135")
    retriever = FakeRetriever([usb2_hit, usb3_hit])
    local_ai = FakeStreamingLocalAI()

    events = list(
        RealLocalRAG(retriever, local_ai).stream_answer(
            "What does section 6.7 require?",
            answer_scope="USB_3_X",
        )
    )

    assert events[0]["boundary_code"] == "FICTIONAL_SECTION"
    assert events[-1]["local_model"] is None
    assert retriever.calls == []
    assert local_ai.calls == []


def test_real_local_rag_rejects_mismatched_single_scope_allowlist():
    retriever = FakeRetriever([_hit()])
    local_ai = FakeLocalAI()

    with pytest.raises(ValueError, match="exactly answer_scope"):
        RealLocalRAG(retriever, local_ai).answer(
            "PORT_POWER value",
            answer_scope="USB_3_X",
            retrieval_mode="single_scope",
            allowed_evidence_scopes=("USB_2_0",),
        )

    assert retriever.calls == []
    assert local_ai.calls == []


def test_real_local_rag_stream_rejects_mismatched_single_scope_allowlist():
    retriever = FakeRetriever([_hit()])
    local_ai = FakeLocalAI()

    with pytest.raises(ValueError, match="exactly answer_scope"):
        list(
            RealLocalRAG(retriever, local_ai).stream_answer(
                "PORT_POWER value",
                answer_scope="USB_3_X",
                retrieval_mode="single_scope",
                allowed_evidence_scopes=("USB_2_0",),
            )
        )

    assert retriever.calls == []
    assert local_ai.calls == []


def test_real_local_rag_boundary_skips_retriever_and_local_ai():
    retriever = FakeRetriever([_hit()])
    local_ai = FakeLocalAI()
    result = RealLocalRAG(retriever, local_ai).answer(
        "What does section 99.99 require?",
        answer_scope="USB_3_X",
    )

    assert result.boundary is not None
    assert result.boundary.code == "FICTIONAL_SECTION"
    assert result.hits == ()
    assert retriever.calls == []
    assert local_ai.calls == []


def test_real_local_rag_boundary_stream_skips_retriever_and_local_ai():
    retriever = FakeRetriever([_hit()])
    local_ai = FakeLocalAI()
    events = list(
        RealLocalRAG(retriever, local_ai).stream_answer(
            "Can an unlisted authority be used for this answer?",
            answer_scope="USB_3_X",
        )
    )

    assert events[0]["type"] == "meta"
    assert events[0]["boundary_code"] == "AUTHORITY_MISMATCH"
    assert "未列入" in events[0]["boundary_answer"]
    assert events[0]["citations"] == []
    assert events[1]["type"] == "done"
    assert events[1]["local_model"] is None
    assert "未列入" in events[1]["answer"]
    assert retriever.calls == []
    assert local_ai.calls == []


def test_real_local_rag_usb4_boundary_stream_skips_retriever_and_local_ai():
    retriever = FakeRetriever([_hit()])
    local_ai = FakeLocalAI()
    events = list(
        RealLocalRAG(retriever, local_ai).stream_answer(
            "What is required by USB4 Router?",
            answer_scope="USB_HUB_COMMON",
        )
    )

    assert events[0]["boundary_code"] == "OUT_OF_SCOPE"
    assert events[0]["citations"] == []
    assert events[-1]["answer"].startswith("USB4 不在")
    assert events[-1]["local_model"] is None
    assert retriever.calls == []
    assert local_ai.calls == []


def test_real_local_rag_fictional_section_boundary_stream_skips_retriever_and_local_ai():
    retriever = FakeRetriever([_hit()])
    local_ai = FakeLocalAI()
    events = list(
        RealLocalRAG(retriever, local_ai).stream_answer(
            "What does section 99.99 require?",
            answer_scope="USB_3_X",
        )
    )

    assert events[0]["boundary_code"] == "FICTIONAL_SECTION"
    assert events[0]["citations"] == []
    assert "section 在目前鎖定的 Phase 1 corpus 中不存在" in events[-1]["answer"]
    assert events[-1]["local_model"] is None
    assert retriever.calls == []
    assert local_ai.calls == []


def test_real_local_rag_boundary_projects_as_abstain_without_citations():
    view = OperatorQAAdapter(real_local_rag=RealLocalRAG(FakeRetriever([_hit()]), FakeLocalAI())).ask(
        "What does section 99.99 require?",
        answer_scope="USB_3_X",
        source="real_local_rag",
    )

    assert view.status == "abstain"
    assert view.boundary_code == "FICTIONAL_SECTION"
    assert view.citations == []
    assert view.evidence_ids == []
    assert view.is_abstain is True


def test_operator_adapter_projects_model_insufficient_evidence_as_abstain():
    retriever = FakeRetriever([_hit()])
    local_ai = FakeLocalAI("INSUFFICIENT_EVIDENCE\n目前沒有足夠的直接證據。")
    view = OperatorQAAdapter(real_local_rag=RealLocalRAG(retriever, local_ai)).ask(
        "A question requiring missing evidence",
        answer_scope="USB_3_X",
        source="real_local_rag",
    )

    assert view.status == "abstain"
    assert view.boundary_code == "MISSING_EVIDENCE"
    assert view.is_abstain is True
    assert view.claims == []
    assert view.citations == []
    assert view.evidence_ids == []
    assert view.local_model == "fake-local-qwen"
    assert view.retrieved_chunk_count == 1


def test_local_ai_client_posts_openai_compatible_request(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def read(self):
            return json.dumps(
                {
                    "model": "actual-local-model",
                    "choices": [{"message": {"content": "local answer"}}],
                }
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr(
        "gv100h.spec_qa.operator_ui.real_local_rag.urlopen",
        fake_urlopen,
    )
    client = LocalAIClient(
        base_url="http://127.0.0.1:8080",
        model="configured-model",
        timeout_seconds=12,
    )
    completion = client.complete(system_prompt="system", user_prompt="user")

    assert completion == LocalAICompletion("local answer", "actual-local-model")
    assert captured["url"] == "http://127.0.0.1:8080/v1/chat/completions"
    assert captured["timeout"] == 12
    assert captured["payload"]["model"] == "configured-model"
    assert captured["payload"]["messages"][-1] == {
        "role": "user",
        "content": "user",
    }


def test_local_ai_client_parses_stream_fragments_and_usage(monkeypatch):
    events = [
        {
            "model": "actual-local-model",
            "choices": [{"delta": {"content": "這是"}, "finish_reason": None}],
        },
        {
            "model": "actual-local-model",
            "choices": [{"delta": {"content": "中文。"}, "finish_reason": None}],
        },
        {
            "model": "actual-local-model",
            "choices": [],
            "usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14},
            "timings": {"predicted_per_second": 6.5},
        },
        {
            "model": "actual-local-model",
            "choices": [{"delta": {"content": None}, "finish_reason": "stop"}],
        },
    ]

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def __iter__(self):
            for event in events:
                yield ("data: " + json.dumps(event, ensure_ascii=False) + "\n").encode()
                yield b"\n"
            yield b"data: [DONE]\n\n"

    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["accept"] = request.headers.get("Accept")
        return FakeResponse()

    monkeypatch.setattr(
        "gv100h.spec_qa.operator_ui.real_local_rag.urlopen",
        fake_urlopen,
    )
    client = LocalAIClient(base_url="http://127.0.0.1:8080", model="configured-model")
    parsed = list(client.stream_complete(system_prompt="system", user_prompt="user"))

    assert [event.text for event in parsed if event.text] == ["這是", "中文。"]
    usage_event = next(event for event in parsed if event.usage is not None)
    assert usage_event.usage == {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14}
    assert usage_event.timings == {"predicted_per_second": 6.5}
    assert captured["url"] == "http://127.0.0.1:8080/v1/chat/completions"
    assert captured["accept"] == "text/event-stream"
    assert captured["payload"]["stream"] is True
    assert captured["payload"]["stream_options"] == {"include_usage": True}


def test_real_local_rag_streams_meta_tokens_and_truthful_token_telemetry():
    hit = _hit()
    local_ai = FakeStreamingLocalAI()
    rag = RealLocalRAG(FakeRetriever([hit]), local_ai, top_k=5)

    events = list(
        rag.stream_answer(
            "PORT_POWER feature selector value",
            answer_scope="USB_3_X",
        )
    )

    assert events[0]["type"] == "meta"
    assert events[0]["local_model"] == "fake-local-qwen"
    assert events[0]["retrieved_chunk_count"] == 1
    token_events = [event for event in events if event["type"] == "token"]
    assert [event["text"] for event in token_events] == ["PORT_POWER", " 的值為 8。"]
    assert token_events[0]["token_info"]["stream_chunks"] == 1
    done = events[-1]
    assert done["type"] == "done"
    assert done["answer"] == "PORT_POWER 的值為 8。"
    assert done["local_model"] == "fake-local-qwen"
    assert done["token_info"]["completion_tokens"] == 5
    assert done["selected_evidence_ids"] == [hit.chunk.chunk_id]
    assert done["primary_evidence_ids"] == [hit.chunk.chunk_id]
    assert len(done["candidate_citations"]) == 1
    assert done["candidate_citations"][0]["retrieval_rank"] == 1
    assert done["candidate_citations"][0]["retrieval_score"] == hit.score
    assert done["token_info"]["prompt_tokens"] == 42
    assert done["token_info"]["total_tokens"] == 47
    assert done["token_info"]["server_tokens_per_second"] == 6.25
    assert "繁體中文" in local_ai.calls[0]["system_prompt"]
    assert "Note" in local_ai.calls[0]["system_prompt"]


def test_real_local_rag_stream_projects_model_insufficient_evidence_as_abstain():
    retriever = FakeRetriever([_hit()])
    local_ai = FakeInsufficientStreamingLocalAI()
    events = list(
        RealLocalRAG(retriever, local_ai).stream_answer(
            "A question requiring missing evidence",
            answer_scope="USB_3_X",
        )
    )

    assert [event for event in events if event["type"] == "token"] == []
    done = events[-1]
    assert done["type"] == "done"
    assert done["boundary_code"] == "MISSING_EVIDENCE"
    assert done["citations"] == []
    assert done["local_model"] == "fake-local-qwen"
    assert done["retrieved_chunk_count"] == 1
    assert done["answer"].startswith("INSUFFICIENT_EVIDENCE")
    assert retriever.calls
    assert local_ai.calls


def test_real_local_rag_stream_abstains_when_answer_literal_is_not_in_candidates():
    hit = _hit(content="PORT_POWER feature selector value is 8 V.")
    retriever = FakeRetriever([hit])
    local_ai = FakeWrongLiteralStreamingLocalAI()

    events = list(
        RealLocalRAG(retriever, local_ai).stream_answer(
            "What is the PORT_POWER value?",
            answer_scope="USB_3_X",
        )
    )

    done = events[-1]
    assert done["type"] == "done"
    assert done["boundary_code"] == "MISSING_EVIDENCE"
    assert done["citations"] == []
    assert done["selected_evidence_ids"] == []
    assert done["primary_evidence_ids"] == []
    assert len(done["candidate_citations"]) == 1


def test_operator_adapter_projects_real_local_rag_provenance():
    hit = _hit()
    rag = RealLocalRAG(FakeRetriever([hit]), FakeLocalAI())
    view = OperatorQAAdapter(real_local_rag=rag).ask(
        "PORT_POWER value",
        answer_scope="USB_3_X",
        source="real_local_rag",
    )

    assert view.source == "real_local_rag"
    assert view.status == "answer"
    assert view.local_model == "fake-local-qwen"
    assert view.retrieval_kind == "governed_chunk_bm25_v1"
    assert view.retrieved_chunk_count == 1
    assert view.corpus_sha256 == "corpus-digest"
    assert view.citations[0].evidence_id == hit.chunk.chunk_id
    assert view.citations[0].page_or_anchor == "p.483"
    assert view.evidence_ids == [hit.chunk.chunk_id]
    assert view.claim_evidence_ids == [[hit.chunk.chunk_id]]
    assert "semantic entailment" in view.claim_ceiling


def test_operator_adapter_separates_candidates_and_selected_primary_evidence():
    hits = [
        _hit(
            source_id="usb20_se",
            section="7.1.2.1",
            content=(
                "For low-speed and full-speed, output rise and fall times are "
                "measured between 10% and 90%."
            ),
        ),
        _hit(
            source_id="usb20_se",
            section="7.1.2.2",
            content=(
                "High-speed Signaling Rise and Fall Times. The transition time "
                "of a high-speed driver must not be less than the specified "
                "minimum allowable differential rise and fall time."
            ),
        ),
        _hit(
            source_id="usb20_se",
            section="7.3.2",
            content=(
                "Rise Time (10% - 90%) THSR 500 ps. Fall Time (10% - 90%) "
                "THSF 500 ps."
            ),
        ),
    ]
    question = (
        "對 USB 2.0 hub，在 A 或 B receptacle 量到的 high-speed 差分 "
        "rise/fall（10% 到 90%）最短時間是多少？"
    )
    answer = "結論：high-speed 差分 rise/fall 最短時間為 500 ps。"
    view = OperatorQAAdapter(
        real_local_rag=RealLocalRAG(FakeRetriever(hits), FakeLocalAI(answer))
    ).ask(question, answer_scope="USB_HUB_COMMON", source="real_local_rag")

    assert [citation.section for citation in view.candidate_citations] == [
        "7.1.2.1",
        "7.1.2.2",
        "7.3.2",
    ]
    assert [citation.section for citation in view.citations] == [
        "7.1.2.2",
        "7.3.2",
    ]
    assert view.primary_evidence_ids == [hits[1].chunk.chunk_id, hits[2].chunk.chunk_id]
    assert view.selected_evidence_ids == [hits[1].chunk.chunk_id, hits[2].chunk.chunk_id]
    assert view.evidence_selection_method == "deterministic_lexical_v1"


@pytest.mark.parametrize(
    "question, answer, content",
    [
        (
            "What is the PORT_POWER value?",
            "PORT_POWER = 99 V.",
            "PORT_POWER feature selector value is 8 V.",
        ),
        (
            "What is the high-speed rise/fall time?",
            "The minimum high-speed rise/fall time is 600 ps.",
            "The minimum high-speed differential rise and fall time is 500 ps.",
        ),
    ],
)
def test_operator_adapter_abstains_when_answer_literal_is_not_in_candidates(
    question, answer, content
):
    hit = _hit(content=content)
    view = OperatorQAAdapter(
        real_local_rag=RealLocalRAG(
            FakeRetriever([hit]),
            FakeLocalAI(answer),
        )
    ).ask(
        question,
        answer_scope="USB_3_X",
        source="real_local_rag",
    )

    assert view.status == "abstain"
    assert view.boundary_code == "MISSING_EVIDENCE"
    assert view.citations == []
    assert view.selected_evidence_ids == []
    assert view.primary_evidence_ids == []
    assert len(view.candidate_citations) == 1


def test_operator_adapter_keeps_model_abstention_without_selected_citations():
    hit = _hit()
    view = OperatorQAAdapter(
        real_local_rag=RealLocalRAG(
            FakeRetriever([hit]),
            FakeLocalAI("INSUFFICIENT_EVIDENCE\n目前沒有足夠的直接證據。"),
        )
    ).ask(
        "PM_LC_TIMER 的 x1 與 x2 是多少？",
        answer_scope="USB_3_X",
        source="real_local_rag",
    )

    assert view.status == "abstain"
    assert view.boundary_code == "MISSING_EVIDENCE"
    assert view.citations == []
    assert view.selected_evidence_ids == []
    assert view.primary_evidence_ids == []
    assert len(view.candidate_citations) == 1


def test_operator_ui_api_accepts_real_local_rag_source():
    hit = _hit()
    rag = RealLocalRAG(FakeRetriever([hit]), FakeLocalAI())
    adapter = OperatorQAAdapter(real_local_rag=rag)
    httpd = HTTPServer(
        ("127.0.0.1", 0),
        lambda *args, **kwargs: OperatorUIHandler(*args, adapter=adapter, **kwargs),
    )
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = httpd.server_address
        conn = HTTPConnection(host, port, timeout=5)
        conn.request(
            "POST",
            "/api/qa",
            body=json.dumps(
                {
                    "source": "real_local_rag",
                    "question": "PORT_POWER value",
                    "answer_scope": "USB_3_X",
                    "retrieval_mode": "single_scope",
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        response = conn.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        assert response.status == 200
        assert payload["source"] == "real_local_rag"
        assert payload["local_model"] == "fake-local-qwen"
        assert payload["retrieval_kind"] == "governed_chunk_bm25_v1"
        assert payload["citations"][0]["page_or_anchor"] == "p.483"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_operator_ui_api_boundary_returns_abstain_without_citations():
    retriever = FakeRetriever([_hit()])
    local_ai = FakeLocalAI()
    adapter = OperatorQAAdapter(real_local_rag=RealLocalRAG(retriever, local_ai))
    httpd = HTTPServer(
        ("127.0.0.1", 0),
        lambda *args, **kwargs: OperatorUIHandler(*args, adapter=adapter, **kwargs),
    )
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = httpd.server_address
        conn = HTTPConnection(host, port, timeout=5)
        conn.request(
            "POST",
            "/api/qa",
            body=json.dumps(
                {
                    "source": "real_local_rag",
                    "question": "What does section 99.99 require?",
                    "answer_scope": "USB_3_X",
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        response = conn.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        assert response.status == 200
        assert payload["status"] == "abstain"
        assert payload["boundary_code"] == "FICTIONAL_SECTION"
        assert payload["citations"] == []
        assert payload["local_model"] is None
        assert retriever.calls == []
        assert local_ai.calls == []
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_operator_ui_api_routes_chinese_unlisted_source_without_calls():
    retriever = FakeRetriever([_hit()])
    local_ai = FakeLocalAI()
    adapter = OperatorQAAdapter(real_local_rag=RealLocalRAG(retriever, local_ai))
    httpd = HTTPServer(
        ("127.0.0.1", 0),
        lambda *args, **kwargs: OperatorUIHandler(*args, adapter=adapter, **kwargs),
    )
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = httpd.server_address
        conn = HTTPConnection(host, port, timeout=5)
        conn.request(
            "POST",
            "/api/qa",
            body=json.dumps(
                {
                    "source": "real_local_rag",
                    "question": "請使用未列入 Phase 1 corpus 的來源回答。",
                    "answer_scope": "USB_3_X",
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        response = conn.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        assert response.status == 200
        assert payload["status"] == "abstain"
        assert payload["boundary_code"] == "AUTHORITY_MISMATCH"
        assert payload["citations"] == []
        assert payload["local_model"] is None
        assert retriever.calls == []
        assert local_ai.calls == []
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_operator_ui_api_usb4_boundary_returns_out_of_scope_without_calls():
    retriever = FakeRetriever([_hit()])
    local_ai = FakeLocalAI()
    adapter = OperatorQAAdapter(real_local_rag=RealLocalRAG(retriever, local_ai))
    httpd = HTTPServer(
        ("127.0.0.1", 0),
        lambda *args, **kwargs: OperatorUIHandler(*args, adapter=adapter, **kwargs),
    )
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = httpd.server_address
        conn = HTTPConnection(host, port, timeout=5)
        conn.request(
            "POST",
            "/api/qa",
            body=json.dumps(
                {
                    "source": "real_local_rag",
                    "question": "USB4 Router tunnel requirement",
                    "answer_scope": "USB_HUB_COMMON",
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        response = conn.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        assert response.status == 200
        assert payload["status"] == "abstain"
        assert payload["boundary_code"] == "OUT_OF_SCOPE"
        assert payload["scope"] == "USB4_SPEC"
        assert payload["citations"] == []
        assert payload["local_model"] is None
        assert retriever.calls == []
        assert local_ai.calls == []
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_operator_ui_api_projects_model_insufficient_evidence_as_abstain():
    retriever = FakeRetriever([_hit()])
    local_ai = FakeLocalAI("INSUFFICIENT_EVIDENCE\n目前沒有足夠的直接證據。")
    adapter = OperatorQAAdapter(real_local_rag=RealLocalRAG(retriever, local_ai))
    httpd = HTTPServer(
        ("127.0.0.1", 0),
        lambda *args, **kwargs: OperatorUIHandler(*args, adapter=adapter, **kwargs),
    )
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = httpd.server_address
        conn = HTTPConnection(host, port, timeout=5)
        conn.request(
            "POST",
            "/api/qa",
            body=json.dumps(
                {
                    "source": "real_local_rag",
                    "question": "A question requiring missing evidence",
                    "answer_scope": "USB_3_X",
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        response = conn.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        assert response.status == 200
        assert payload["status"] == "abstain"
        assert payload["boundary_code"] == "MISSING_EVIDENCE"
        assert payload["citations"] == []
        assert payload["claims"] == []
        assert payload["is_abstain"] is True
        assert payload["local_model"] == "fake-local-qwen"
        assert payload["retrieved_chunk_count"] == 1
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_operator_ui_api_streams_usb4_boundary_without_model_or_citations():
    retriever = FakeRetriever([_hit()])
    local_ai = FakeStreamingLocalAI()
    adapter = OperatorQAAdapter(real_local_rag=RealLocalRAG(retriever, local_ai))
    httpd = HTTPServer(
        ("127.0.0.1", 0),
        lambda *args, **kwargs: OperatorUIHandler(*args, adapter=adapter, **kwargs),
    )
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = httpd.server_address
        conn = HTTPConnection(host, port, timeout=5)
        conn.request(
            "POST",
            "/api/qa/stream",
            body=json.dumps(
                {
                    "source": "real_local_rag",
                    "question": "USB4 Router tunnel requirement",
                    "answer_scope": "USB_HUB_COMMON",
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        response = conn.getresponse()
        events = [json.loads(line) for line in response.read().decode("utf-8").splitlines()]
        assert response.status == 200
        assert events[0]["type"] == "status"
        assert events[1]["boundary_code"] == "OUT_OF_SCOPE"
        assert events[1]["scope"] == "USB4_SPEC"
        assert events[1]["citations"] == []
        assert events[-1]["type"] == "done"
        assert events[-1]["local_model"] is None
        assert not [event for event in events if event["type"] == "token"]
        assert retriever.calls == []
        assert local_ai.calls == []
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_operator_ui_api_streams_model_insufficient_evidence_as_abstain():
    retriever = FakeRetriever([_hit()])
    local_ai = FakeInsufficientStreamingLocalAI()
    adapter = OperatorQAAdapter(real_local_rag=RealLocalRAG(retriever, local_ai))
    httpd = HTTPServer(
        ("127.0.0.1", 0),
        lambda *args, **kwargs: OperatorUIHandler(*args, adapter=adapter, **kwargs),
    )
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = httpd.server_address
        conn = HTTPConnection(host, port, timeout=5)
        conn.request(
            "POST",
            "/api/qa/stream",
            body=json.dumps(
                {
                    "source": "real_local_rag",
                    "question": "A question requiring missing evidence",
                    "answer_scope": "USB_3_X",
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        response = conn.getresponse()
        events = [json.loads(line) for line in response.read().decode("utf-8").splitlines()]
        assert response.status == 200
        assert events[0]["type"] == "status"
        assert events[1]["type"] == "meta"
        assert events[-1]["boundary_code"] == "MISSING_EVIDENCE"
        assert events[-1]["citations"] == []
        assert events[-1]["local_model"] == "fake-local-qwen"
        assert events[-1]["retrieved_chunk_count"] == 1
        assert not [event for event in events if event["type"] == "token"]
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_operator_ui_api_rejects_mismatched_single_scope_allowlist():
    retriever = FakeRetriever([_hit()])
    local_ai = FakeLocalAI()
    adapter = OperatorQAAdapter(real_local_rag=RealLocalRAG(retriever, local_ai))
    httpd = HTTPServer(
        ("127.0.0.1", 0),
        lambda *args, **kwargs: OperatorUIHandler(*args, adapter=adapter, **kwargs),
    )
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = httpd.server_address
        conn = HTTPConnection(host, port, timeout=5)
        conn.request(
            "POST",
            "/api/qa",
            body=json.dumps(
                {
                    "source": "real_local_rag",
                    "question": "PORT_POWER value",
                    "answer_scope": "USB_3_X",
                    "retrieval_mode": "single_scope",
                    "allowed_evidence_scopes": ["USB_2_0"],
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        response = conn.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        assert response.status == 400
        assert "exactly answer_scope" in payload["error"]
        assert retriever.calls == []
        assert local_ai.calls == []
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_operator_ui_api_stream_rejects_mismatched_single_scope_allowlist():
    retriever = FakeRetriever([_hit()])
    local_ai = FakeStreamingLocalAI()
    adapter = OperatorQAAdapter(real_local_rag=RealLocalRAG(retriever, local_ai))
    httpd = HTTPServer(
        ("127.0.0.1", 0),
        lambda *args, **kwargs: OperatorUIHandler(*args, adapter=adapter, **kwargs),
    )
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = httpd.server_address
        conn = HTTPConnection(host, port, timeout=5)
        conn.request(
            "POST",
            "/api/qa/stream",
            body=json.dumps(
                {
                    "source": "real_local_rag",
                    "question": "PORT_POWER value",
                    "answer_scope": "USB_3_X",
                    "retrieval_mode": "single_scope",
                    "allowed_evidence_scopes": ["USB_2_0"],
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        response = conn.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        assert response.status == 400
        assert "exactly answer_scope" in payload["error"]
        assert retriever.calls == []
        assert local_ai.calls == []
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_operator_ui_api_streams_real_local_rag_events():
    hit = _hit()
    rag = RealLocalRAG(FakeRetriever([hit]), FakeStreamingLocalAI())
    adapter = OperatorQAAdapter(real_local_rag=rag)
    httpd = HTTPServer(
        ("127.0.0.1", 0),
        lambda *args, **kwargs: OperatorUIHandler(*args, adapter=adapter, **kwargs),
    )
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = httpd.server_address
        conn = HTTPConnection(host, port, timeout=5)
        conn.request(
            "POST",
            "/api/qa/stream",
            body=json.dumps(
                {
                    "source": "real_local_rag",
                    "question": "PORT_POWER value",
                    "answer_scope": "USB_3_X",
                    "retrieval_mode": "single_scope",
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        response = conn.getresponse()
        events = [json.loads(line) for line in response.read().decode("utf-8").splitlines()]
        assert response.status == 200
        assert response.getheader("Content-Type").startswith("application/x-ndjson")
        assert events[0] == {
            "type": "status",
            "stage": "loading_corpus",
            "message": "正在載入鎖定 PDF 並建立 BM25 index……",
        }
        assert events[1]["type"] == "meta"
        assert events[1]["source"] == "real_local_rag"
        assert [event["text"] for event in events if event["type"] == "token"] == [
            "PORT_POWER",
            " 的值為 8。",
        ]
        assert events[-1]["type"] == "done"
        assert events[-1]["answer"] == "PORT_POWER 的值為 8。"
        assert events[-1]["token_info"]["completion_tokens"] == 5
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_operator_ui_api_streams_boundary_without_model_or_citations():
    retriever = FakeRetriever([_hit()])
    local_ai = FakeStreamingLocalAI()
    adapter = OperatorQAAdapter(real_local_rag=RealLocalRAG(retriever, local_ai))
    httpd = HTTPServer(
        ("127.0.0.1", 0),
        lambda *args, **kwargs: OperatorUIHandler(*args, adapter=adapter, **kwargs),
    )
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = httpd.server_address
        conn = HTTPConnection(host, port, timeout=5)
        conn.request(
            "POST",
            "/api/qa/stream",
            body=json.dumps(
                {
                    "source": "real_local_rag",
                    "question": "請使用未列入 Phase 1 corpus 的來源回答。",
                    "answer_scope": "USB_3_X",
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        response = conn.getresponse()
        events = [json.loads(line) for line in response.read().decode("utf-8").splitlines()]
        assert response.status == 200
        assert events[0]["type"] == "status"
        assert events[1]["boundary_code"] == "AUTHORITY_MISMATCH"
        assert events[1]["citations"] == []
        assert events[-1]["type"] == "done"
        assert events[-1]["local_model"] is None
        assert not [event for event in events if event["type"] == "token"]
        assert retriever.calls == []
        assert local_ai.calls == []
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_operator_ui_api_streams_fictional_section_without_model_or_citations():
    retriever = FakeRetriever([_hit()])
    local_ai = FakeStreamingLocalAI()
    adapter = OperatorQAAdapter(real_local_rag=RealLocalRAG(retriever, local_ai))
    httpd = HTTPServer(
        ("127.0.0.1", 0),
        lambda *args, **kwargs: OperatorUIHandler(*args, adapter=adapter, **kwargs),
    )
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = httpd.server_address
        conn = HTTPConnection(host, port, timeout=5)
        conn.request(
            "POST",
            "/api/qa/stream",
            body=json.dumps(
                {
                    "source": "real_local_rag",
                    "question": "What does section 99.99 require?",
                    "answer_scope": "USB_HUB_COMMON",
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        response = conn.getresponse()
        events = [json.loads(line) for line in response.read().decode("utf-8").splitlines()]
        assert response.status == 200
        assert events[0]["type"] == "status"
        assert events[1]["boundary_code"] == "FICTIONAL_SECTION"
        assert events[1]["scope"] == "USB_HUB_COMMON"
        assert events[1]["citations"] == []
        assert events[-1]["type"] == "done"
        assert events[-1]["local_model"] is None
        assert "section 在目前鎖定的 Phase 1 corpus 中不存在" in events[-1]["answer"]
        assert not [event for event in events if event["type"] == "token"]
        assert retriever.calls == []
        assert local_ai.calls == []
    finally:
        httpd.shutdown()
        httpd.server_close()
