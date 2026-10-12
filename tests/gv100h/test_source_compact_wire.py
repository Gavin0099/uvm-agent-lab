"""Synthetic request-local representation fixtures, never a live-model result."""
from copy import deepcopy
import json

import pytest

from gv100h.spec_qa.contracts.governed_chunk import GovernedChunk
from gv100h.spec_qa.source_binding.compact_wire import (
    prepare_candidate, verify_packet, encode_fixture, decode_response,
)
from gv100h.spec_qa.source_binding.strict_json import strict_object


def packet(*, request_id="a" * 32, input_compact=True, output_compact=True, reading_type="integer"):
    chunks = tuple(GovernedChunk.build(source_id="manual", document="Fixture", revision="1",
        section="3.1", page_or_anchor=f"p.{i+1}", authority_level="authoritative",
        chunk_kind="paragraph", content=text, index=i)
        for i, text in enumerate(["A specimen can be tested while disconnected.", "The applicable scope is one specimen."]))
    text = {"type": "string", "minLength": 1}
    obj = lambda props: {"type": "object", "additionalProperties": False,
                        "required": list(props), "properties": props}
    value = obj({"reading": {"type": reading_type}, "condition": text, "scope": text, "modality": text})
    claim = obj({"claim_id": {"const": "reading"}, "relation": {"const": "describes_specimen"},
        "value": value, "citation_ids": {"type": "array", "minItems": 1, "uniqueItems": True, "items": text},
        "display_text": obj({"locale": {"const": "zh-Hant"}, "text": text})})
    schema = obj({"schema": {"const": "fixture.v1"}, "question_id": {"const": "natural-query"},
        "response_citation_ids": {"type": "array", "minItems": 1, "uniqueItems": True, "items": text},
        "claims": {"type": "array", "minItems": 1, "maxItems": 1, "prefixItems": [claim], "items": False}})
    body = {"QUESTION": "What is the specimen reading under its condition?",
            "EVIDENCE": [c.model_dump() for c in chunks], "OUTPUT_SCHEMA": schema}
    messages = [{"role": "system", "content": "Use sources and retain qualifiers."},
                {"role": "user", "content": json.dumps(body)}]
    prepared = prepare_candidate(messages, request_id=request_id, trusted_chunks=chunks,
        input_compact=input_compact, output_compact=output_compact,
        cross_chunk_rule="Shared source metadata alone does not establish a relationship.")
    answer = {"schema": "fixture.v1", "question_id": "natural-query", "response_citation_ids": [c.chunk_id for c in chunks],
        "claims": [{"claim_id": "reading", "relation": "describes_specimen",
                    "value": {"reading": 31, "condition": "disconnected", "scope": "one specimen", "modality": "can"},
                    "citation_ids": [c.chunk_id for c in chunks],
                    "display_text": {"locale": "zh-Hant", "text": "單一樣本在未連接條件下可以測量；讀值31。"}}]}
    return prepared, answer, chunks


@pytest.mark.parametrize("input_compact,output_compact", [(False, False), (True, False), (False, True), (True, True)])
def test_fixture_roundtrip_retains_all_semantic_values_and_original_sources(input_compact, output_compact):
    prepared, answer, chunks = packet(input_compact=input_compact, output_compact=output_compact)
    assert verify_packet(prepared["messages"], prepared["context"]) == [c.model_dump() for c in chunks]
    encoded = encode_fixture(json.dumps(answer), prepared["context"])
    assert decode_response(json.dumps(encoded), prepared["context"]) == answer
    assert len(prepared["context"].bindings()) == 2


def test_request_scope_unknown_alias_and_cross_request_output_are_rejected():
    prepared, answer, _ = packet()
    wire = encode_fixture(answer, prepared["context"])
    unknown = deepcopy(wire); unknown["claims"][0]["citation_ids"] = ["E99"]
    with pytest.raises(ValueError): decode_response(json.dumps(unknown), prepared["context"])
    other, _, _ = packet(request_id="b" * 32)
    with pytest.raises(ValueError): decode_response(json.dumps(wire), other["context"])


@pytest.mark.parametrize("change", ["source_catalog", "text", "alias", "order"])
def test_candidate_mutation_is_not_silently_restored(change):
    prepared, _, _ = packet()
    messages = deepcopy(prepared["messages"])
    body = json.loads(messages[1]["content"])
    if change == "source_catalog": body["SOURCE_CATALOG"]["S1"]["revision"] = "2"
    elif change == "text": body["EVIDENCE"][0]["content"] = "Changed source"
    elif change == "alias": body["EVIDENCE"][0]["evidence_ref"] = "E2"
    else: body["EVIDENCE"].reverse()
    messages[1]["content"] = json.dumps(body)
    with pytest.raises(ValueError): verify_packet(messages, prepared["context"])


@pytest.mark.parametrize("field", ["reading", "condition", "scope", "modality"])
def test_missing_semantic_field_is_not_filled_by_backend(field):
    prepared, answer, _ = packet()
    wire = encode_fixture(answer, prepared["context"])
    del wire["claims"][0]["value"][field]
    with pytest.raises(ValueError): decode_response(json.dumps(wire), prepared["context"])


def test_refusal_retains_reason_and_has_no_invented_answer():
    prepared, _, _ = packet()
    refusal = {"status": "insufficient_evidence", "reason": "The necessary condition is not confirmed."}
    wire = encode_fixture(refusal, prepared["context"])
    assert decode_response(json.dumps(wire), prepared["context"]) == refusal


@pytest.mark.parametrize("raw", ['{"x":1,"x":2}', '{"value":NaN}', '[]', '```json\n{}\n```'])
def test_strict_object_rejects_non_object_duplicate_nonfinite_or_wrapped_json(raw):
    with pytest.raises(ValueError): strict_object(raw)


@pytest.mark.parametrize("number", ["1e999", "-1e999"])
def test_overflow_number_is_rejected_by_strict_object_and_decoder(number):
    with pytest.raises(ValueError): strict_object('{"reading":' + number + '}')
    prepared, answer, _ = packet(reading_type="number")
    wire = json.dumps(encode_fixture(answer, prepared["context"]))
    wire = wire.replace('"reading": 31', '"reading": ' + number)
    with pytest.raises(ValueError): decode_response(wire, prepared["context"])


@pytest.mark.parametrize("number", [float("inf"), float("-inf"), float("nan")])
def test_python_fixture_entry_cannot_bypass_finite_json(number):
    prepared, answer, _ = packet(reading_type="number")
    wire = encode_fixture(answer, prepared["context"])
    wire["claims"][0]["value"]["reading"] = number
    with pytest.raises(ValueError): decode_response(wire, prepared["context"])
    answer["claims"][0]["value"]["reading"] = number
    with pytest.raises(ValueError): encode_fixture(answer, prepared["context"])


def test_large_finite_number_remains_legal_and_unchanged():
    prepared, answer, _ = packet(reading_type="number")
    answer["claims"][0]["value"]["reading"] = 1e308
    wire = encode_fixture(answer, prepared["context"])
    restored = decode_response(json.dumps(wire, allow_nan=False), prepared["context"])
    assert restored == answer
    json.dumps(restored, allow_nan=False)
