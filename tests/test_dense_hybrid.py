from pathlib import Path

from retrieval.hybrid.dense_hybrid import (
    GovernedDenseHybridRetriever,
    StandardDenseHybridRetriever,
)
from retrieval.canonical.retriever import CanonicalSpecIntegrityError


class FlatEncoder:
    def encode(self, texts, **kwargs):
        return [[1.0, 0.0] for _ in texts]


def _write_docs(tmp_path: Path) -> None:
    (tmp_path / "allowed.md").write_text(
        '---\nversion: "1.0"\nauthority: "authoritative"\ncustomer_tier: "tier_1_partner"\ndoc_id: "ALLOWED"\n---\nReset requirement allowed.\n',
        encoding="utf-8",
    )
    (tmp_path / "draft.md").write_text(
        '---\nversion: "1.0"\nauthority: "draft"\ncustomer_tier: "tier_1_partner"\ndoc_id: "DRAFT"\n---\nReset requirement draft.\n',
        encoding="utf-8",
    )
    (tmp_path / "restricted.md").write_text(
        '---\nversion: "2.1"\nauthority: "authoritative"\ncustomer_tier: "tier_a_partner_restricted"\ndoc_id: "RESTRICTED"\n---\nReset requirement restricted.\n',
        encoding="utf-8",
    )


def test_standard_dense_hybrid_fuses_bm25_and_dense_without_governance(tmp_path: Path):
    _write_docs(tmp_path)
    retriever = StandardDenseHybridRetriever(
        doc_dir=str(tmp_path),
        dense_model="test/flat",
        dense_encoder=FlatEncoder(),
    )

    hits = retriever.query("reset requirement", top_k=10)

    assert retriever.retriever_kind == "standard_dense_lexical_hybrid"
    assert {hit["file"] for hit in hits} == {"allowed.md", "draft.md", "restricted.md"}
    assert all(hit["fusion"] == "rrf" for hit in hits)
    assert all(hit["allowed_files_applied"] is False for hit in hits)
    assert all(hit["rrf_k"] == 60 for hit in hits)
    assert all("bm25_rank" in hit and "dense_rank" in hit for hit in hits)


def test_governed_dense_hybrid_prefilters_before_scoring(tmp_path: Path):
    _write_docs(tmp_path)
    retriever = GovernedDenseHybridRetriever(
        doc_dir=str(tmp_path),
        dense_model="test/flat",
        dense_encoder=FlatEncoder(),
    )

    hits = retriever.query(
        "reset requirement",
        top_k=10,
        target_version="1.0",
        caller_customer_tier="tier_1_partner",
    )

    assert [hit["file"] for hit in hits] == ["allowed.md"]
    assert hits[0]["retriever_kind"] == "governed_dense_lexical_hybrid"
    assert hits[0]["governance_prefilter"] is True
    assert hits[0]["allowed_files_applied"] is True
    assert hits[0]["doc_id"] == "ALLOWED"
    assert hits[0]["authority"] == "authoritative"
    assert hits[0]["version"] == "1.0"
    assert hits[0]["customer_tier"] == "tier_1_partner"
    assert hits[0]["canonical_hash"].startswith("sha256:")


def test_governed_dense_hybrid_rejects_changed_canonical_file(tmp_path: Path):
    _write_docs(tmp_path)
    retriever = GovernedDenseHybridRetriever(
        doc_dir=str(tmp_path),
        dense_model="test/flat",
        dense_encoder=FlatEncoder(),
    )
    (tmp_path / "allowed.md").write_text("tampered\n", encoding="utf-8")

    try:
        retriever.query(
            "reset requirement",
            top_k=10,
            target_version="1.0",
            caller_customer_tier="tier_1_partner",
        )
    except CanonicalSpecIntegrityError as exc:
        assert "Canonical hash mismatch" in str(exc)
    else:
        raise AssertionError("governed retrieval accepted a changed canonical file")
