"""Synthetic source identities; shape/provenance PASS is not answer approval."""
from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator

from gv100h.spec_qa.contracts.governed_chunk import GovernedChunk
from gv100h.spec_qa.contracts.table_identity import table_identity_schema
from gv100h.spec_qa.source_binding.table_identity import bind_table_location, resolve_exact_evidence
from gv100h.spec_qa.source_binding.table_relation import TableProvenanceError, verify_single_table_relation


def chunk(text, index, *, kind="paragraph", source="manual", revision="1", section="3.1", document="Fixture"):
    return GovernedChunk.build(source_id=source, document=document, revision=revision,
        section=section, page_or_anchor=f"p.{index + 1}", authority_level="authoritative",
        chunk_kind=kind, content=text, index=index)


def specimen():
    cap = chunk("Table 73-4. Arbitrary specimens", 0)
    row = chunk("sample | reading\nalpha | 31", 1, kind="table")
    cont = chunk("Table 73-4. Arbitrary specimens (continued)", 2)
    records = [c.model_dump() for c in (cap, row, cont)]
    location = {"table": {"source_id": "manual", "revision": "1", "number": "73-4"},
                "continuation": True, "section": "3.1", "page": "p.3"}
    claims = [{"value": {"reading": 31}, "citation_ids": [row.chunk_id]},
              {"value": location, "citation_ids": [cont.chunk_id]}]
    return (cap, row, cont), records, claims


def test_public_identity_has_no_question_answer_vocabulary():
    schema = table_identity_schema()
    assert set(schema["properties"]) == {"source_id", "revision", "number"}
    assert "enum" not in str(schema) and "73-4" not in str(schema)
    Draft202012Validator.check_schema(schema)


def test_continued_table_identity_and_row_use_distinct_original_ids():
    trusted, sent, claims = specimen()
    result = verify_single_table_relation(claims, sent_evidence=sent, trusted_chunks=trusted)
    assert result["status"] == "PASS"
    assert result["citation_ids"] == [trusted[1].chunk_id, trusted[2].chunk_id]
    assert result["caption_binding"]["content_sha256"] == trusted[2].content_sha256
    assert result["numerical_answer_correctness"] == "CHECKED_SEPARATELY"


@pytest.mark.parametrize("field,value", [("source_id", "other"), ("revision", "2"), ("number", "91")])
def test_wrong_public_identity_does_not_bind(field, value):
    trusted, sent, claims = specimen()
    claims[-1]["value"]["table"][field] = value
    with pytest.raises(ValueError):
        bind_table_location(claims[-1]["value"], claims[-1]["citation_ids"], sent_evidence=sent, trusted_chunks=trusted)


@pytest.mark.parametrize("field,value", [("continuation", False), ("page", "p.99"), ("section", "4.1")])
def test_location_is_cited_not_guessed(field, value):
    trusted, sent, claims = specimen()
    claims[-1]["value"][field] = value
    with pytest.raises(ValueError):
        bind_table_location(claims[-1]["value"], claims[-1]["citation_ids"], sent_evidence=sent, trusted_chunks=trusted)


@pytest.mark.parametrize("field,value", [("content", "invented | 31"), ("document", "Wrong file"),
    ("revision", "2"), ("content_sha256", "0" * 64), ("page_or_anchor", "p.99")])
def test_sent_record_never_becomes_its_own_authority(field, value):
    trusted, sent, claims = specimen()
    sent[1][field] = value
    with pytest.raises(ValueError):
        resolve_exact_evidence(claims[0]["citation_ids"], sent_evidence=sent, trusted_chunks=trusted)


@pytest.mark.parametrize("side", ["sent", "trusted", "ids"])
def test_duplicate_identity_fails_closed(side):
    trusted, sent, claims = specimen()
    ids = claims[0]["citation_ids"]
    if side == "sent": sent.append(deepcopy(sent[1]))
    elif side == "trusted": trusted = (*trusted, trusted[1])
    else: ids *= 2
    with pytest.raises(ValueError):
        resolve_exact_evidence(ids, sent_evidence=sent, trusted_chunks=trusted)


def test_unsent_and_same_page_replacement_are_not_old_evidence():
    trusted, sent, claims = specimen()
    substitute = chunk(trusted[1].content, 9, kind="table")
    substitute.page_or_anchor = trusted[1].page_or_anchor
    with pytest.raises(ValueError):
        resolve_exact_evidence([substitute.chunk_id], sent_evidence=sent, trusted_chunks=(*trusted, substitute))
    with pytest.raises(ValueError):
        resolve_exact_evidence(claims[0]["citation_ids"], sent_evidence=sent[:1], trusted_chunks=trusted)


def test_two_valid_tables_do_not_form_one_relation():
    trusted, sent, claims = specimen()
    other = chunk("Table 91. Other specimens", 3)
    sent.append(other.model_dump())
    claims[0]["citation_ids"].append(other.chunk_id)
    with pytest.raises(TableProvenanceError, match="TABLE_FAMILY_MISMATCH"):
        verify_single_table_relation(claims, sent_evidence=sent, trusted_chunks=(*trusted, other))


def test_identical_table_number_across_documents_is_ambiguous():
    trusted, sent, claims = specimen()
    other = chunk("Table 73-4. Separate file", 3, document="Another fixture")
    sent.append(other.model_dump())
    with pytest.raises(TableProvenanceError, match="TABLE_RELATION_AMBIGUOUS"):
        verify_single_table_relation(claims, sent_evidence=sent, trusted_chunks=(*trusted, other))


@pytest.mark.parametrize("caption", ["Table 73-4 explains specimens.", "Table 73-4", "Table 73-4. Alpha\nTable 91. Beta"])
def test_reference_unresolved_or_multiple_caption_is_not_guessed(caption):
    cap = chunk(caption, 0)
    value = {"table": {"source_id": "manual", "revision": "1", "number": "73-4"},
             "continuation": False, "section": "3.1", "page": "p.1"}
    with pytest.raises(ValueError):
        bind_table_location(value, [cap.chunk_id], sent_evidence=[cap.model_dump()], trusted_chunks=[cap])


def test_wrong_answer_can_have_valid_source_identity():
    trusted, sent, claims = specimen()
    claims[0]["value"]["reading"] = 999
    result = verify_single_table_relation(claims, sent_evidence=sent, trusted_chunks=trusted)
    assert result["status"] == "PASS"
    assert result["numerical_answer_correctness"] == "CHECKED_SEPARATELY"
    assert "999" not in trusted[1].content  # independent source contradicts this fixture answer


def test_no_table_declaration_is_not_semantic_approval():
    trusted, sent, claims = specimen()
    result = verify_single_table_relation(claims[:1], sent_evidence=sent, trusted_chunks=trusted)
    assert result["status"] == "NOT_APPLICABLE"
