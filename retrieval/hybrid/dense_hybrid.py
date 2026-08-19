from typing import Any, Dict, List, Optional, Set

from retrieval.bm25.retriever import BM25Retriever
from retrieval.canonical.retriever import CanonicalSpecRetriever
from retrieval.vector.dense_retriever import DenseEmbeddingRetriever, EmbeddingEncoder


class StandardDenseHybridRetriever:
    """Un-governed BM25 + dense embedding RRF baseline."""

    retriever_kind = "standard_dense_lexical_hybrid"

    def __init__(
        self,
        doc_dir: str = "fixtures/synthetic-spec",
        dense_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        dense_model_revision: Optional[str] = None,
        dense_encoder: Optional[EmbeddingEncoder] = None,
        rrf_k: int = 60,
    ):
        self.rrf_k = rrf_k
        self.bm25 = BM25Retriever(doc_dir=doc_dir)
        self.dense = DenseEmbeddingRetriever(
            doc_dir=doc_dir,
            model_name=dense_model,
            model_revision=dense_model_revision,
            encoder=dense_encoder,
        )

    def query(
        self,
        query_str: str,
        top_k: int = 3,
        allowed_files: Optional[Set[str]] = None,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        candidate_k = max(10, top_k)
        lexical_hits = self.bm25.query(
            query_str,
            top_k=candidate_k,
            allowed_files=allowed_files,
            **kwargs,
        )
        dense_hits = self.dense.query(
            query_str,
            top_k=candidate_k,
            allowed_files=allowed_files,
            **kwargs,
        )

        lexical_by_file = {hit["file"]: hit for hit in lexical_hits}
        dense_by_file = {hit["file"]: hit for hit in dense_hits}
        combined_scores: Dict[str, float] = {}
        doc_lookup: Dict[str, Dict[str, Any]] = {}
        for rank, hit in enumerate(lexical_hits):
            file_name = hit["file"]
            doc_lookup.setdefault(file_name, hit)
            combined_scores[file_name] = combined_scores.get(file_name, 0.0) + (
                1.0 / (self.rrf_k + rank + 1)
            )
        for rank, hit in enumerate(dense_hits):
            file_name = hit["file"]
            doc_lookup[file_name] = hit
            combined_scores[file_name] = combined_scores.get(file_name, 0.0) + (
                1.0 / (self.rrf_k + rank + 1)
            )

        results = []
        for file_name, score in sorted(
            combined_scores.items(), key=lambda item: (-item[1], item[0])
        ):
            item = doc_lookup[file_name].copy()
            item.update(
                {
                    "score": round(score, 6),
                    "fusion": "rrf",
                    "retriever_kind": self.retriever_kind,
                    "allowed_files_applied": allowed_files is not None,
                    "dense_model_name": self.dense.model_name,
                    "dense_model_revision": self.dense.model_revision,
                    "bm25_score": lexical_by_file.get(file_name, {}).get("score"),
                    "dense_score": dense_by_file.get(file_name, {}).get("score"),
                    "bm25_rank": next(
                        (rank + 1 for rank, hit in enumerate(lexical_hits) if hit["file"] == file_name),
                        None,
                    ),
                    "dense_rank": next(
                        (rank + 1 for rank, hit in enumerate(dense_hits) if hit["file"] == file_name),
                        None,
                    ),
                    "rrf_k": self.rrf_k,
                    "rrf_formula": "sum(1 / (rrf_k + rank + 1))",
                }
            )
            results.append(item)
        return results[:top_k]


class GovernedDenseHybridRetriever(StandardDenseHybridRetriever):
    """Canonical eligibility prefilter followed by BM25 + dense RRF."""

    retriever_kind = "governed_dense_lexical_hybrid"

    def __init__(self, doc_dir: str = "fixtures/synthetic-spec", **kwargs: Any):
        self.canonical = CanonicalSpecRetriever(spec_dir=doc_dir)
        super().__init__(doc_dir=doc_dir, **kwargs)
        self._canonical_by_file = self.canonical.metadata_for_files(
            self.canonical.indexed_files
        )

    def query(
        self,
        query_str: str,
        top_k: int = 3,
        target_version: Optional[str] = None,
        caller_customer_tier: Optional[str] = None,
        allow_drafts: bool = False,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        eligible_files = self.canonical.eligible_files(
            target_version=target_version,
            caller_customer_tier=caller_customer_tier,
            allow_drafts=allow_drafts,
        )
        for file_name in eligible_files:
            self.canonical.verify_file_hash(file_name)
        results = super().query(
            query_str,
            top_k=top_k,
            allowed_files=eligible_files,
            **kwargs,
        )
        for item in results:
            canonical = self._canonical_by_file.get(item["file"])
            if canonical:
                item.update(
                    {
                        "canonical_hash": canonical["canonical_hash"],
                        "doc_id": canonical["doc_id"],
                        "version": canonical["version"],
                        "authority": canonical["authority"],
                        "customer_tier": canonical["customer_tier"],
                    }
                )
            item["retriever_kind"] = self.retriever_kind
            item["governance_prefilter"] = True
            item["eligible_file_count"] = len(eligible_files)
        return results
