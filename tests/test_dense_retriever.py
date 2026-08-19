import math
from pathlib import Path

import pytest

from retrieval.vector.dense_retriever import DenseEmbeddingRetriever


class FakeDenseEncoder:
    def encode(self, texts, **kwargs):
        vectors = []
        for text in texts:
            lowered = text.lower()
            if "warm reset" in lowered:
                vectors.append([1.0, 0.0])
            elif "sticky register" in lowered:
                vectors.append([0.0, 1.0])
            else:
                vectors.append([0.7, 0.7])
        return vectors


class NonUnitDenseEncoder:
    def encode(self, texts, **kwargs):
        return [[3.0, 4.0] for _ in texts]


def _write_docs(tmp_path: Path) -> None:
    (tmp_path / "reset.md").write_text(
        '---\nversion: "1.0"\nauthority: "authoritative"\ncustomer_tier: "internal_engineering"\n---\nWarm reset behavior.\n',
        encoding="utf-8",
    )
    (tmp_path / "register.md").write_text(
        '---\nversion: "1.0"\nauthority: "authoritative"\ncustomer_tier: "internal_engineering"\n---\nSticky register preservation.\n',
        encoding="utf-8",
    )


def test_dense_retriever_uses_injected_embeddings_and_cosine_ranking(tmp_path: Path):
    _write_docs(tmp_path)
    retriever = DenseEmbeddingRetriever(
        doc_dir=str(tmp_path),
        model_name="test/fake-dense",
        encoder=FakeDenseEncoder(),
    )

    hits = retriever.query("warm reset", top_k=2)

    assert retriever.retriever_kind == "dense_embedding"
    assert retriever.embedding_dimension == 2
    assert hits[0]["file"] == "reset.md"
    assert hits[0]["score"] == 1.0
    assert hits[0]["model_name"] == "test/fake-dense"
    assert hits[0]["model_revision"] is None
    assert len(hits[0]["corpus_sha256"]) == 64
    assert hits[0]["embedding_dimension"] == 2
    assert hits[0]["embedding_normalization"] == "l2"
    assert hits[0]["authority"] == "authoritative"


def test_dense_retriever_is_explicitly_optional_without_backend(tmp_path: Path, monkeypatch):
    _write_docs(tmp_path)

    def missing_backend(*args, **kwargs):
        raise ImportError("missing optional backend")

    monkeypatch.setattr(
        "builtins.__import__",
        lambda name, *args, **kwargs: (
            missing_backend() if name == "sentence_transformers" else __import__(name, *args, **kwargs)
        ),
    )
    with pytest.raises(RuntimeError, match="optional 'rag' dependency"):
        DenseEmbeddingRetriever(doc_dir=str(tmp_path))


def test_dense_retriever_normalizes_injected_encoder_output(tmp_path: Path):
    _write_docs(tmp_path)
    retriever = DenseEmbeddingRetriever(
        doc_dir=str(tmp_path),
        encoder=NonUnitDenseEncoder(),
    )

    for vector in retriever.embeddings:
        assert math.isclose(math.sqrt(sum(value * value for value in vector)), 1.0)
    assert retriever.query("anything", top_k=1)[0]["score"] == 1.0


def test_dense_retriever_handles_zero_vectors_empty_query_and_empty_corpus(tmp_path: Path):
    class ZeroEncoder:
        def encode(self, texts, **kwargs):
            return [[0.0, 0.0] for _ in texts]

    _write_docs(tmp_path)
    retriever = DenseEmbeddingRetriever(doc_dir=str(tmp_path), encoder=ZeroEncoder())
    assert retriever.query("") == []
    assert retriever.query("   ") == []
    assert retriever.query("anything", top_k=2)[0]["score"] == 0.0

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    empty = DenseEmbeddingRetriever(doc_dir=str(empty_dir), encoder=ZeroEncoder())
    assert empty.embedding_dimension == 0
    assert empty.query("anything") == []


def test_dense_retriever_corpus_hash_is_deterministic(tmp_path: Path):
    _write_docs(tmp_path)
    first = DenseEmbeddingRetriever(doc_dir=str(tmp_path), encoder=FakeDenseEncoder())
    second = DenseEmbeddingRetriever(doc_dir=str(tmp_path), encoder=FakeDenseEncoder())
    assert first.corpus_sha256 == second.corpus_sha256