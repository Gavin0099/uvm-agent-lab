from gv100h.spec_qa.contracts.governed_chunk import GovernedChunk
from gv100h.spec_qa.operator_ui.evidence_selection import select_evidence
from gv100h.spec_qa.retrieval.real_corpus_retriever import (
    GovernedChunkRetrievalHit,
)


def _hit(source_id, section, content, index):
    is_usb32 = source_id in {"usb32", "superspeed_hub_lvs"}
    chunk = GovernedChunk.build(
        source_id=source_id,
        document="USB 3.2 Specification" if is_usb32 else "USB 2.0 Specification",
        revision="Rev 1.1" if is_usb32 else "2.0",
        section=section,
        page_or_anchor="p.1",
        authority_level="authoritative",
        chunk_kind="paragraph",
        content=content,
        index=index,
    )
    return GovernedChunkRetrievalHit(
        chunk=chunk,
        score=float(len(content)),
        matched_terms=(),
    )


def test_selector_does_not_equate_bm25_rank_one_with_primary_citation():
    question = (
        "對 USB 2.0 hub，在 A 或 B receptacle 量到的 high-speed 差分 "
        "rise/fall（10% 到 90%）最短時間是多少？"
    )
    answer = "結論：high-speed 差分 rise/fall 最短時間為 500 ps。"
    hits = [
        _hit(
            "usb20_se",
            "7.1.2.1",
            "For low-speed and full-speed, output rise and fall times are measured between 10% and 90%.",
            0,
        ),
        _hit(
            "usb20_se",
            "7.1.2.2",
            "High-speed Signaling Rise and Fall Times. The transition time of a high-speed driver must not be less than the specified minimum allowable differential rise and fall time.",
            1,
        ),
        _hit(
            "usb20_se",
            "7.3.2",
            "Rise Time (10% - 90%) THSR 500 ps. Fall Time (10% - 90%) THSF 500 ps.",
            2,
        ),
    ]

    selection = select_evidence(question, answer, hits)

    assert [hit.chunk.section for hit in selection.selected_hits] == [
        "7.1.2.2",
        "7.3.2",
    ]
    assert [hit.chunk.section for hit in selection.primary_hits] == [
        "7.1.2.2",
        "7.3.2",
    ]


def test_selector_abstains_when_answer_voltage_is_not_in_candidates():
    question = "What is the PORT_POWER value?"
    answer = "PORT_POWER = 99 V."
    candidate = _hit(
        "usb32",
        "10.3.1.1",
        "PORT_POWER feature selector value is 8 V.",
        0,
    )

    selection = select_evidence(question, answer, [candidate])

    assert selection.selected_hits == ()
    assert selection.primary_hits == ()


def test_selector_abstains_when_answer_duration_is_not_in_candidates():
    question = "What is the high-speed rise/fall time?"
    answer = "The minimum high-speed rise/fall time is 600 ps."
    candidate = _hit(
        "usb20_se",
        "7.1.2.2",
        "The minimum high-speed differential rise and fall time is 500 ps.",
        0,
    )

    selection = select_evidence(question, answer, [candidate])

    assert selection.selected_hits == ()
    assert selection.primary_hits == ()


def test_selector_uses_explicit_generation_to_reject_similar_other_generation():
    question = "USB 3.2 configuration descriptor Address state and Configured state"
    answer = (
        "USB 3.2 §9.4.2：Address state 回傳 0；Configured state 回傳目前非零 "
        "bConfigurationValue。"
    )
    usb3 = _hit(
        "usb32",
        "9.4.2",
        "Address state: bConfigurationValue is zero. Configured state: bConfigurationValue is the current non-zero value.",
        0,
    )
    usb2 = _hit(
        "usb20_fw",
        "9.4.2",
        "Address state returns zero. Configured state returns current bConfigurationValue.",
        1,
    )

    selection = select_evidence(question, answer, [usb3, usb2])

    assert [hit.chunk.source_id for hit in selection.selected_hits] == ["usb32"]
    assert [hit.chunk.section for hit in selection.primary_hits] == ["9.4.2"]


def test_selector_preserves_two_load_bearing_document_primaries():
    question = "Compare USB 2.0 and USB 3.2 PORT_POWER requirements"
    answer = (
        "USB 2.0 PORT_POWER 反映目前電源狀態；USB 3.2 PORT_POWER 則定義下游埠的"
        "電源狀態。兩份文件都必須保留。"
    )
    usb3 = _hit(
        "usb32",
        "10.3.1.1",
        "USB 3.2 downstream port PORT_POWER = 0 or 1.",
        0,
    )
    usb2 = _hit(
        "usb20_fw",
        "11.24.2.7.1.6",
        "USB 2.0 PORT_POWER reflects the current power state.",
        1,
    )

    selection = select_evidence(question, answer, [usb3, usb2])

    assert {hit.chunk.source_id for hit in selection.selected_hits} == {
        "usb20_fw",
        "usb32",
    }
    assert {hit.chunk.source_id for hit in selection.primary_hits} == {
        "usb20_fw",
        "usb32",
    }


def test_selector_returns_no_selected_evidence_for_model_abstention():
    hit = _hit("usb32", "7.5", "eSS.Inactive timeout and RxDetect timeout.", 0)

    selection = select_evidence(
        "PM_LC_TIMER 的 x1 與 x2 是多少？",
        "INSUFFICIENT_EVIDENCE\n目前沒有足夠的直接證據。",
        [hit],
    )

    assert selection.selected_hits == ()
    assert selection.primary_hits == ()
