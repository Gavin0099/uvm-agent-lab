from pathlib import Path

from gv100h.spec_qa.contracts.governed_chunk import GovernedChunk
from gv100h.spec_qa.retrieval.real_corpus_retriever import (
    GovernedChunkBM25Retriever,
)
from scripts.validate_real_locked_corpus_v1 import (
    DEFAULT_MANIFEST_PATH,
    _rank_target,
    run_validation,
)


def test_validation_reports_not_run_without_locked_raw_corpus(tmp_path):
    result = run_validation(
        raw_root=tmp_path / "missing-locked-corpus",
        manifest_path=DEFAULT_MANIFEST_PATH,
    )

    assert result["status"] == "NOT_RUN"
    assert "official locked raw corpus" in result["reason"]
    assert result["baseline_evidence"]["table_6_30_value_rank_q02"] == 293


def test_validation_records_the_full_target_hit_witness():
    chunk = GovernedChunk.build(
        source_id="usb32",
        document="USB 3.2 Specification",
        revision="Rev 1.1",
        section="6.9.1",
        page_or_anchor="p.131",
        authority_level="authoritative",
        chunk_kind="table",
        content="tReset3 | 80 ms | 100 ms | 120 ms",
        index=0,
    )
    retriever = GovernedChunkBM25Retriever([chunk])

    result = _rank_target(
        retriever,
        {
            "id": "table_6_30_direct",
            "query": "USB 3.2 Table 6-30 Warm Reset tReset 80 ms 120 ms",
            "target": {
                "source_id": "usb32",
                "section": "6.9.1",
                "chunk_kind": "table",
                "contains_all": ["80 ms", "120 ms"],
            },
        },
    )

    assert result["target_rank"] == 1
    assert result["target_hit"]["rank"] == 1
    assert result["target_hit"]["chunk_id"] == chunk.chunk_id
    assert result["target_hit"]["source_id"] == "usb32"
    assert result["target_hit"]["revision"] == "Rev 1.1"
    assert result["target_hit"]["section"] == "6.9.1"
    assert result["target_hit"]["chunk_kind"] == "table"
    assert result["target_hit"]["citation_id"] == chunk.chunk_id