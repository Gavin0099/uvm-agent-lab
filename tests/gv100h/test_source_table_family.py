"""Independent arbitrary-table fixtures; no Q005 answers or private mappings."""

import inspect

import json

import pytest

from gv100h.spec_qa.contracts.governed_chunk import GovernedChunk

from gv100h.spec_qa.retrieval.table_family_pack import (
    evidence_size, pack_table_families, table_families,
)

from gv100h.spec_qa.retrieval.real_corpus_retriever import GovernedChunkRetrievalHit

def chunk(content, index, *, kind="paragraph", source="manual", section="3.1", revision="1"):
    return GovernedChunk.build(source_id=source, document="Fixture", revision=revision,
        section=section, page_or_anchor=f"p.{index + 1}", authority_level="authoritative",
        chunk_kind=kind, content=content, index=index)

def hits(chunks):
    # Explicit fixture ranks model actual BM25 hits, rather than unreported rank.
    return [GovernedChunkRetrievalHit(c, float(100 - i), ("arbitrary",),
        retrieval_rank=i + 1, original_bm25_rank=i + 1) for i, c in enumerate(chunks)]

def test_continuation_family_is_atomic_and_keeps_original_content_and_scores():
    cap = chunk("Table 73-4. Arbitrary specimens", 0)
    row = chunk("sample | reading\nalpha | 31", 1, kind="table")
    cont = chunk("Table 73-4. Arbitrary specimens (continued)", 2)
    tail = chunk("beta | 62", 3, kind="table")
    corpus = [cap, row, cont, tail]
    ranked = hits([row, tail, cont, cap])
    result = pack_table_families(corpus, ranked, max_chars=10000, max_chunks=4)
    assert [r["chunk_id"] for r in result["evidence"]] == [row.chunk_id, cap.chunk_id, cont.chunk_id, tail.chunk_id]
    assert result["selected_bm25_ranks"] == [1, 4, 3, 2]
    assert result["events"][0]["expanded"] is True
    for record in result["evidence"]:
        original = next(c for c in corpus if c.chunk_id == record["chunk_id"])
        assert record["content"] == original.content
        assert record["content_sha256"] == original.content_sha256
        assert record["score"] == next(h.score for h in ranked if h.chunk == original)

@pytest.mark.parametrize("field,value", [("source", "other"), ("section", "3.2"), ("revision", "2")])
def test_identical_caption_number_does_not_cross_source_section_revision(field, value):
    a = chunk("Table 73-4. Alpha", 0)
    b = chunk("Table 73-4. Beta", 1, **{field: value})
    families, membership = table_families([a, b])
    assert membership[a.chunk_id] != membership[b.chunk_id]
    assert len(families) == 2

def test_new_heading_and_ambiguous_multi_caption_break_association():
    cap = chunk("Table 73-4. Alpha", 0)
    heading = chunk("New topic", 1, kind="heading_only")
    orphan = chunk("orphan | 7", 2, kind="table")
    ambiguous = chunk("Table 73-4. Alpha\nTable 91. Beta", 3)
    second_orphan = chunk("orphan | 9", 4, kind="table")
    _, membership = table_families([cap, heading, orphan, ambiguous, second_orphan])
    assert set(membership) == {cap.chunk_id}

def test_oversize_family_falls_back_to_seed_without_cherry_picking():
    cap = chunk("Table 73-4. Alpha", 0)
    row = chunk("x | 13", 1, kind="table")
    cont = chunk("Table 73-4. Alpha (continued)", 2)
    other = chunk("Unrelated", 3)
    result = pack_table_families([cap, row, cont, other], hits([row, other, cap, cont]), max_chunks=2, max_chars=10000)
    assert [r["chunk_id"] for r in result["evidence"]] == [row.chunk_id, other.chunk_id]
    assert result["events"][0]["expanded"] is False

def test_exact_character_boundary_and_one_character_short_are_observable():
    a = chunk("Table 73-4. Alpha", 0)
    b = chunk("x | 13", 1, kind="table")
    ranked = hits([a, b])
    budget = evidence_size([dict(h.as_record(), rank=i) for i, h in enumerate(ranked, 1)])
    exact = pack_table_families([a, b], ranked, max_chars=budget, max_chunks=2)
    short = pack_table_families([a, b], ranked, max_chars=budget - 1, max_chunks=2)
    assert exact["budget"]["used_chars"] == budget
    assert len(exact["evidence"]) == 2
    assert len(short["evidence"]) == 1
    assert not short["events"][0]["expanded"]

def test_no_family_matches_preserve_seed_order_and_never_exceed_chunk_budget():
    corpus = [chunk(f"Unrelated item {i}", i) for i in range(25)]
    result = pack_table_families(corpus, hits(corpus), max_chars=100000)
    assert len(result["evidence"]) == 20
    assert [r["chunk_id"] for r in result["evidence"]] == [c.chunk_id for c in corpus[:20]]

def test_nonpositive_score_family_member_keeps_identity_and_zero_score():
    a = chunk("Table 73-4. Alpha", 0)
    b = chunk("x | 13", 1, kind="table")
    result = pack_table_families([a, b], hits([a]), max_chars=10000, max_chunks=2)
    assert result["evidence"][1]["chunk_id"] == b.chunk_id
    assert result["evidence"][1]["score"] == 0

@pytest.mark.parametrize("kwargs", [{"max_chunks": 0, "max_chars": 100}, {"max_chunks": True, "max_chars": 100}, {"max_chars": -1}, {"max_chars": 1.5}])
def test_invalid_budget_rejected(kwargs):
    with pytest.raises(ValueError, match="budget"):
        pack_table_families([], [], **kwargs)

def test_duplicate_and_foreign_hits_rejected():
    a, b = chunk("A", 0), chunk("B", 1)
    with pytest.raises(ValueError, match="duplicate"):
        pack_table_families([a, a], hits([a]), max_chars=10000)
    with pytest.raises(ValueError, match="duplicate"):
        pack_table_families([a], hits([a, a]), max_chars=10000)
    with pytest.raises(ValueError, match="outside"):
        pack_table_families([a], hits([b]), max_chars=10000)

def test_no_gold_or_question_parameter_and_empty_pack_stays_well_formed():
    assert set(inspect.signature(pack_table_families).parameters) == {"chunks", "ranked_hits", "max_chars", "max_chunks"}
    result = pack_table_families([], [], max_chars=evidence_size([]))
    assert result["evidence"] == []
    assert result["budget"]["used_chars"] == evidence_size([])
    assert json.loads(json.dumps(result)) == result


def test_original_bm25_rank_survives_reference_expansion_order():
    a = chunk("First unrelated entry", 0)
    b = chunk("Second unrelated entry", 1)
    ranked = [GovernedChunkRetrievalHit(a, 3.0, (), retrieval_rank=9, original_bm25_rank=21),
              GovernedChunkRetrievalHit(b, 0.0, (), retrieval_origin="table_reference", retrieval_rank=10)]
    result = pack_table_families([a, b], ranked, max_chars=10000, max_chunks=2)
    assert result["selected_bm25_ranks"] == [21, None]
    assert [e["seed_bm25_rank"] for e in result["events"]] == [21, None]
    assert [e["seed_candidate_position"] for e in result["events"]] == [1, 2]
    assert [r["chunk_id"] for r in result["evidence"]] == [a.chunk_id, b.chunk_id]
    assert result["evidence"][0]["original_bm25_rank"] == 21
    assert result["evidence"][1]["original_bm25_rank"] is None


@pytest.mark.parametrize("origin,rank,expected", [("bm25", 7, 7), ("bm25", None, None), ("table_reference", 7, None)])
def test_unknown_original_rank_has_only_explicit_bm25_fallback(origin, rank, expected):
    a = chunk("Arbitrary entry", 0)
    hit = GovernedChunkRetrievalHit(a, 3.0, (), retrieval_origin=origin, retrieval_rank=rank)
    result = pack_table_families([a], [hit], max_chars=10000, max_chunks=1)
    assert result["selected_bm25_ranks"] == [expected]
    assert result["events"][0]["seed_bm25_rank"] == expected
