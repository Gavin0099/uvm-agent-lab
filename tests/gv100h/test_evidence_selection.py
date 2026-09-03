import pytest

from gv100h.spec_qa.contracts.governed_chunk import GovernedChunk
from gv100h.spec_qa.operator_ui.evidence_selection import (
    _unitless_numeric_anchors,
    select_evidence,
)
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


def test_selector_abstains_when_answer_unitless_count_is_not_in_candidates():
    candidate = _hit(
        "usb32",
        "10.1",
        "The hub supports 8 downstream ports.",
        0,
    )

    selection = select_evidence(
        "How many downstream ports are supported?",
        "The hub supports 4 downstream ports.",
        [candidate],
    )

    assert selection.selected_hits == ()
    assert selection.primary_hits == ()


def test_selector_accepts_matching_unitless_count():
    candidate = _hit(
        "usb32",
        "10.1",
        "The hub supports 8 downstream ports.",
        0,
    )

    selection = select_evidence(
        "How many downstream ports are supported?",
        "The hub supports 8 downstream ports.",
        [candidate],
    )

    assert [hit.chunk.chunk_id for hit in selection.selected_hits] == [
        candidate.chunk.chunk_id
    ]
    assert [hit.chunk.chunk_id for hit in selection.primary_hits] == [
        candidate.chunk.chunk_id
    ]


def test_selector_preserves_numeric_sign_in_material_anchor():
    candidate = _hit(
        "usb32",
        "7.1",
        "The voltage is -5 V.",
        0,
    )

    wrong_sign = select_evidence(
        "What is the voltage?",
        "The voltage is +5 V.",
        [candidate],
    )
    matching_sign = select_evidence(
        "What is the voltage?",
        "The voltage is -5 V.",
        [candidate],
    )

    assert wrong_sign.selected_hits == ()
    assert wrong_sign.primary_hits == ()
    assert matching_sign.selected_hits == (candidate,)
    assert matching_sign.primary_hits == (candidate,)


@pytest.mark.parametrize(
    ("answer", "candidate"),
    [
        ("The threshold is 500 uA.", "The threshold is 100 uA."),
        ("The voltage is 2 uV.", "The voltage is 1 uV."),
        ("The clock rate is 45 kHz.", "The clock rate is 90 kHz."),
        ("The resistance is 45 ohms.", "The resistance is 90 ohms."),
        ("The resistance is 45 Ω.", "The resistance is 90 Ω."),
        ("The payload width is 32 bits.", "The payload width is 16 bits."),
        ("The voltage is 5 volts.", "The voltage is 3 volts."),
    ],
)
def test_selector_rejects_mismatched_pdf_measurement_units(answer, candidate):
    selection = select_evidence(
        "What is the measurement?",
        answer,
        [_hit("usb32", "10.1", candidate, 0)],
    )

    assert selection.selected_hits == ()
    assert selection.primary_hits == ()


@pytest.mark.parametrize(
    "answer",
    [
        "The threshold is 500 uA.",
        "The voltage is 2 uV.",
        "The clock rate is 45 kHz.",
        "The resistance is 45 ohms.",
        "The resistance is 45 Ω.",
        "The payload width is 32 bits.",
        "The voltage is 5 volts.",
    ],
)
def test_selector_accepts_matching_pdf_measurement_units(answer):
    candidate = _hit("usb32", "10.1", answer, 0)
    selection = select_evidence(
        "What is the measurement?",
        answer,
        [candidate],
    )

    assert selection.selected_hits == (candidate,)
    assert selection.primary_hits == (candidate,)


@pytest.mark.parametrize(
    ("answer", "candidate"),
    [
        ("PORT_POWER is enabled.", "PORT_POWER is disabled."),
        ("PORT_POWER is set.", "PORT_POWER is clear."),
        ("PORT_POWER is on.", "PORT_POWER is off."),
        ("PORT_POWER is ACTIVE.", "PORT_POWER is INACTIVE."),
    ],
)
def test_selector_rejects_mismatched_closed_state_values(answer, candidate):
    selection = select_evidence(
        "What is PORT_POWER?",
        answer,
        [_hit("usb32", "10.1", candidate, 0)],
    )

    assert selection.selected_hits == ()
    assert selection.primary_hits == ()


@pytest.mark.parametrize("state", ["enabled", "set", "on", "active"])
def test_selector_accepts_matching_closed_state_value(state):
    candidate = _hit("usb32", "10.1", f"PORT_POWER is {state}.", 0)
    selection = select_evidence(
        "What is PORT_POWER?",
        f"PORT_POWER is {state}.",
        [candidate],
    )

    assert selection.selected_hits == (candidate,)
    assert selection.primary_hits == (candidate,)


def test_unitless_numeric_anchors_require_local_quantity_context():
    assert _unitless_numeric_anchors(
        "The device state machine is described in 3 paragraphs."
    ) == frozenset()
    assert _unitless_numeric_anchors("USB 3.2 section 9.4.2.") == frozenset()
    assert _unitless_numeric_anchors("USB2 supports 4 downstream ports.") == frozenset(
        {"4"}
    )
    assert _unitless_numeric_anchors("The value is 8.") == frozenset({"8"})
    assert _unitless_numeric_anchors("The percentage is 50%.") == frozenset()


def test_selector_does_not_bind_value_across_a_second_identifier():
    candidate = _hit(
        "usb32",
        "10.16.2.10",
        "PORT_POWER is distinct from PORT_RESET = 4.",
        0,
    )

    selection = select_evidence(
        "What is the PORT_POWER value?",
        "PORT_POWER = 4.",
        [candidate],
    )

    assert selection.selected_hits == ()
    assert selection.primary_hits == ()


def test_selector_binds_value_to_the_nearest_identifier():
    candidate = _hit(
        "usb32",
        "10.16.2.10",
        "PORT_POWER is distinct from PORT_RESET = 4.",
        0,
    )

    selection = select_evidence(
        "What is the PORT_RESET value?",
        "PORT_RESET = 4.",
        [candidate],
    )

    assert [hit.chunk.chunk_id for hit in selection.selected_hits] == [
        candidate.chunk.chunk_id
    ]
    assert [hit.chunk.chunk_id for hit in selection.primary_hits] == [
        candidate.chunk.chunk_id
    ]


def test_selector_abstains_when_answer_hex_literal_is_not_in_candidates():
    candidate = _hit(
        "usb32",
        "10.16.2.10",
        "PORT_POWER = 8 (0x0008).",
        0,
    )

    selection = select_evidence(
        "What is the PORT_POWER selector value?",
        "PORT_POWER = 0x0009.",
        [candidate],
    )

    assert selection.selected_hits == ()
    assert selection.primary_hits == ()


def test_selector_accepts_hex_alias_in_candidate_evidence():
    candidate = _hit(
        "usb32",
        "10.16.2.10",
        "PORT_POWER = 8 (0x0008).",
        0,
    )

    selection = select_evidence(
        "What is the PORT_POWER selector value?",
        "PORT_POWER = 0x0008.",
        [candidate],
    )

    assert [hit.chunk.chunk_id for hit in selection.selected_hits] == [
        candidate.chunk.chunk_id
    ]
    assert [hit.chunk.chunk_id for hit in selection.primary_hits] == [
        candidate.chunk.chunk_id
    ]


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


def test_selector_rejects_swapped_cross_generation_literals():
    question = "Compare USB 2.0 and USB 3.2 PORT_POWER requirements"
    answer = "USB 2.0 PORT_POWER = 8 V; USB 3.2 PORT_POWER = 9 V."
    usb2 = _hit(
        "usb20_fw",
        "11.24.2.7.1.6",
        "USB 2.0 PORT_POWER feature value is 9 V.",
        0,
    )
    usb3 = _hit(
        "usb32",
        "10.3.1.1",
        "USB 3.2 PORT_POWER feature value is 8 V.",
        1,
    )

    selection = select_evidence(question, answer, [usb2, usb3])

    assert selection.selected_hits == ()
    assert selection.primary_hits == ()


def test_selector_requires_each_explicit_cross_scope_to_contribute_evidence():
    question = "Compare PORT_POWER requirements"
    answer = "Both define PORT_POWER state."
    usb2 = _hit(
        "usb20_fw",
        "11.24.2.7.1.6",
        "USB 2.0 PORT_POWER reflects the current power state.",
        0,
    )
    usb3 = _hit(
        "usb32",
        "10.3.1.1",
        "USB 3.2 downstream port PORT_POWER reflects the power state.",
        1,
    )

    selection = select_evidence(
        question,
        answer,
        [usb2, usb3],
        required_scopes=("USB_2_0", "USB_3_X"),
    )

    assert {hit.chunk.source_id for hit in selection.selected_hits} == {
        "usb20_fw",
        "usb32",
    }
    assert {hit.chunk.source_id for hit in selection.primary_hits} == {
        "usb20_fw",
        "usb32",
    }


def test_selector_abstains_when_an_explicit_cross_scope_has_no_evidence():
    question = "Compare PORT_POWER requirements"
    answer = "Both define PORT_POWER state."
    usb2 = _hit(
        "usb20_fw",
        "11.24.2.7.1.6",
        "USB 2.0 PORT_POWER reflects the current power state.",
        0,
    )

    selection = select_evidence(
        question,
        answer,
        [usb2],
        required_scopes=("USB_2_0", "USB_3_X"),
    )

    assert selection.selected_hits == ()
    assert selection.primary_hits == ()


def test_selector_requires_shared_literal_in_each_generation_group():
    question = "Compare USB 2.0 and USB 3.2 PORT_POWER requirements"
    answer = "USB 2.0 and USB 3.2 PORT_POWER = 8 V."
    usb2 = _hit(
        "usb20_fw",
        "11.24.2.7.1.6",
        "USB 2.0 PORT_POWER feature value is 9 V.",
        0,
    )
    usb3 = _hit(
        "usb32",
        "10.3.1.1",
        "USB 3.2 PORT_POWER feature value is 8 V.",
        1,
    )

    selection = select_evidence(question, answer, [usb2, usb3])

    assert selection.selected_hits == ()
    assert selection.primary_hits == ()


def test_selector_accepts_shared_literal_when_each_generation_supports_it():
    question = "Compare USB 2.0 and USB 3.2 PORT_POWER requirements"
    answer = "USB 2.0 and USB 3.2 PORT_POWER = 8 V."
    usb2 = _hit(
        "usb20_fw",
        "11.24.2.7.1.6",
        "USB 2.0 PORT_POWER feature value is 8 V.",
        0,
    )
    usb3 = _hit(
        "usb32",
        "10.3.1.1",
        "USB 3.2 PORT_POWER feature value is 8 V.",
        1,
    )

    selection = select_evidence(question, answer, [usb2, usb3])

    assert {hit.chunk.source_id for hit in selection.selected_hits} == {
        "usb20_fw",
        "usb32",
    }
    assert {hit.chunk.source_id for hit in selection.primary_hits} == {
        "usb20_fw",
        "usb32",
    }


def test_selector_splits_usb_hub_common_by_claimed_generation():
    question = "What are the PORT_POWER values?"
    answer = "For USB 2.0 the value is 8 V; for USB 3.2 it is 9 V."
    usb2 = _hit(
        "usb20_fw",
        "11.24.2.7.1.6",
        "USB 2.0 PORT_POWER feature value is 9 V.",
        0,
    )
    usb3 = _hit(
        "usb32",
        "10.3.1.1",
        "USB 3.2 PORT_POWER feature value is 8 V.",
        1,
    )

    selection = select_evidence(
        question,
        answer,
        [usb2, usb3],
        required_scopes=("USB_HUB_COMMON",),
    )

    assert selection.selected_hits == ()
    assert selection.primary_hits == ()


def test_selector_accepts_usb_hub_common_generation_specific_values():
    question = "What are the PORT_POWER values?"
    answer = "For USB 2.0 the value is 8 V; for USB 3.2 it is 9 V."
    usb2 = _hit(
        "usb20_fw",
        "11.24.2.7.1.6",
        "USB 2.0 PORT_POWER feature value is 8 V.",
        0,
    )
    usb3 = _hit(
        "usb32",
        "10.3.1.1",
        "USB 3.2 PORT_POWER feature value is 9 V.",
        1,
    )

    selection = select_evidence(
        question,
        answer,
        [usb2, usb3],
        required_scopes=("USB_HUB_COMMON",),
    )

    assert {hit.chunk.source_id for hit in selection.selected_hits} == {
        "usb20_fw",
        "usb32",
    }
    assert {hit.chunk.source_id for hit in selection.primary_hits} == {
        "usb20_fw",
        "usb32",
    }


def test_selector_binds_modal_field_value_without_cross_identifier_support():
    question = "What is the PORT_POWER value?"
    answer = "PORT_POWER should be 99 V."
    candidate = _hit(
        "usb32",
        "10.16.2.10",
        "PORT_POWER should be 8 V; PORT_RESET is 99 V.",
        0,
    )

    selection = select_evidence(question, answer, [candidate])

    assert selection.selected_hits == ()
    assert selection.primary_hits == ()


def test_selector_accepts_modal_field_value_for_the_correct_identifier():
    question = "What is the PORT_RESET value?"
    answer = "PORT_RESET shall be 99 V."
    candidate = _hit(
        "usb32",
        "10.16.2.10",
        "PORT_POWER should be 8 V; PORT_RESET is 99 V.",
        0,
    )

    selection = select_evidence(question, answer, [candidate])

    assert [hit.chunk.chunk_id for hit in selection.selected_hits] == [
        candidate.chunk.chunk_id
    ]
    assert [hit.chunk.chunk_id for hit in selection.primary_hits] == [
        candidate.chunk.chunk_id
    ]


def test_selector_returns_no_selected_evidence_for_model_abstention():
    hit = _hit("usb32", "7.5", "eSS.Inactive timeout and RxDetect timeout.", 0)

    selection = select_evidence(
        "PM_LC_TIMER 的 x1 與 x2 是多少？",
        "INSUFFICIENT_EVIDENCE\n目前沒有足夠的直接證據。",
        [hit],
    )

    assert selection.selected_hits == ()
    assert selection.primary_hits == ()
