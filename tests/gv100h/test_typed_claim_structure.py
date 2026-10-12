"""Synthetic wire fixtures; expected answers and benchmark mappings are absent."""
import copy
import json

import pytest

from gv100h.spec_qa.contracts.typed_claim_structure import (
    TypedClaimStructureError, TypedClaimStructurePayload,
    parse_typed_claim_structure, typed_claim_structure_schema,
)

CID = "manual:3.1:p.1:0:" + "a" * 64
OTHER = "manual:3.1:p.2:1:" + "b" * 64
VERSION = "synthetic_claim_payload.v1"


def fixture():
    return {"schema": VERSION, "question_id": "unseen-question",
        "response_citation_ids": [CID], "claims": [{"claim_id": "sample.limit",
        "relation": "maximum", "value": {"magnitude": 31, "condition": "when detached"},
        "citation_ids": [CID], "display_text": {"locale": "zh-Hant", "text": "在指定條件下，上限31。"}}]}


def parse(raw, **kwargs):
    options = {"schema_version": VERSION, "question_id": "unseen-question", "prompt_citation_ids": [CID]}
    options.update(kwargs)
    return parse_typed_claim_structure(raw, **options)


def test_unseen_claim_roundtrips_values_qualifier_and_localized_text():
    original = fixture()
    parsed = parse(json.dumps(original, ensure_ascii=False))
    assert parsed.model_dump(mode="json", by_alias=True) == original
    assert json.loads(parsed.model_dump_json()) == original
    assert parsed.claims[0].value["condition"] == "when detached"


def test_shape_does_not_claim_answer_correctness_or_required_claim_coverage():
    original = fixture()
    original["claims"][0]["relation"] = "unreviewed-relation"
    original["claims"][0]["value"] = "unverified-answer"
    parsed = parse(json.dumps(original))
    assert parsed.claims[0].value == "unverified-answer"
    assert not hasattr(parsed, "answer_correct")


@pytest.mark.parametrize("raw", ["{}", "[]", "null", "true", "", "```json\n{}\n```", '{} {}', '{"schema":'])
def test_malformed_or_non_answer_envelopes_are_rejected(raw):
    with pytest.raises(TypedClaimStructureError):
        parse(raw)


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity", "1e999"])
def test_non_finite_json_values_are_rejected(constant):
    raw = json.dumps(fixture()).replace('31', constant, 1)
    with pytest.raises(TypedClaimStructureError):
        parse(raw)


def test_python_dto_non_finite_nested_value_is_rejected():
    original = fixture()
    original["claims"][0]["value"] = {"nested": [float("inf")]}
    with pytest.raises(ValueError):
        TypedClaimStructurePayload.model_validate(original)


@pytest.mark.parametrize("key", ["root", "nested"])
def test_duplicate_json_keys_are_rejected_at_every_depth(key):
    raw = json.dumps(fixture())
    if key == "root":
        raw = raw[:-1] + ', "question_id": "different"}'
    else:
        raw = raw.replace('"magnitude": 31', '"magnitude": 31, "magnitude": 62')
    with pytest.raises(TypedClaimStructureError, match="duplicate JSON key"):
        parse(raw)


@pytest.mark.parametrize("target", ["schema", "question_id", "claim_id", "relation", "text"])
def test_blank_identity_or_display_fields_are_rejected(target):
    original = fixture()
    where = original if target in ("schema", "question_id") else (
        original["claims"][0]["display_text"] if target == "text" else original["claims"][0])
    where[target] = " "
    with pytest.raises(TypedClaimStructureError):
        parse(json.dumps(original))


@pytest.mark.parametrize("target", ["root", "claim", "display"])
def test_unknown_fields_are_rejected(target):
    original = fixture()
    where = {"root": original, "claim": original["claims"][0], "display": original["claims"][0]["display_text"]}[target]
    where["unpublished_field"] = True
    with pytest.raises(TypedClaimStructureError):
        parse(json.dumps(original))


@pytest.mark.parametrize("change", ["response_duplicate", "claim_duplicate", "duplicate_identity", "missing_response", "outside_prompt", "malformed_id", "empty_claims"])
def test_citation_membership_and_unique_claim_identity_are_enforced(change):
    original = fixture()
    if change == "response_duplicate":
        original["response_citation_ids"].append(CID)
    elif change == "claim_duplicate":
        original["claims"][0]["citation_ids"].append(CID)
    elif change == "duplicate_identity":
        original["claims"].append(copy.deepcopy(original["claims"][0]))
    elif change == "missing_response":
        original["claims"][0]["citation_ids"] = [OTHER]
    elif change == "outside_prompt":
        original["response_citation_ids"].append(OTHER)
    elif change == "malformed_id":
        original["claims"][0]["citation_ids"] = ["manual:bad-id"]
    else:
        original["claims"] = []
    with pytest.raises(TypedClaimStructureError):
        parse(json.dumps(original))


@pytest.mark.parametrize("pool", [CID, [], [CID, CID], ["E1"], [None], None])
def test_request_citation_binding_itself_must_be_well_formed(pool):
    with pytest.raises(TypedClaimStructureError):
        parse(json.dumps(fixture()), prompt_citation_ids=pool)


@pytest.mark.parametrize("field", ["schema_version", "question_id"])
def test_request_version_and_question_cannot_be_crossed(field):
    with pytest.raises(TypedClaimStructureError, match="differs from request"):
        parse(json.dumps(fixture()), **{field: "other"})


def test_public_schema_only_binds_wire_version_not_answer_values():
    schema = typed_claim_structure_schema(schema_version=VERSION)
    assert schema["properties"]["schema"]["const"] == VERSION
    assert schema["additionalProperties"] is False
    claim = schema["$defs"]["TypedClaimStructureRecord"]
    assert claim["properties"]["citation_ids"]["uniqueItems"] is True
    assert schema["properties"]["response_citation_ids"]["uniqueItems"] is True
    assert "unique" in schema["properties"]["claims"]["description"]
    assert "const" not in claim["properties"]["claim_id"]
    assert "enum" not in claim["properties"]["relation"]
    assert "required_value" not in json.dumps(schema)
    assert "allowed_citation_ids" not in json.dumps(schema)
    assert "DRAFT-L1" not in json.dumps(schema)


def test_refusal_is_not_misrouted_to_the_answer_contract():
    with pytest.raises(TypedClaimStructureError):
        parse(json.dumps({"status": "insufficient_evidence", "reason": "No direct source."}))
