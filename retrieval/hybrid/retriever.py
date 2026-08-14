from typing import List, Dict, Any
from retrieval.canonical.retriever import CanonicalSpecRetriever
from retrieval.bm25.retriever import BM25Retriever


class HybridRetriever:
    """
    Hybrid Retriever utilizing Reciprocal Rank Fusion (RRF)
    between BM25 Lexical search and Canonical Knowledge Layer governance.
    """

    def __init__(self, doc_dir: str = "fixtures/synthetic-spec", rrf_k: int = 60):
        self.canonical = CanonicalSpecRetriever(spec_dir=doc_dir)
        self.bm25 = BM25Retriever(doc_dir=doc_dir)
        self.rrf_k = rrf_k

    def query(self, query_str: str, top_k: int = 3, **kwargs) -> List[Dict[str, Any]]:
        can_hits = self.canonical.query(query_str, top_k=10, **kwargs)
        bm25_hits = self.bm25.query(query_str, top_k=10, **kwargs)

        combined_scores = {}
        doc_lookup = {}

        for rank, hit in enumerate(can_hits):
            f = hit["file"]
            doc_lookup[f] = hit
            combined_scores[f] = combined_scores.get(f, 0.0) + (1.0 / (self.rrf_k + rank + 1))

        for rank, hit in enumerate(bm25_hits):
            f = hit["file"]
            if f not in doc_lookup:
                doc_lookup[f] = hit
            combined_scores[f] = combined_scores.get(f, 0.0) + (1.0 / (self.rrf_k + rank + 1))

        results = []
        for f, score in sorted(combined_scores.items(), key=lambda x: x[1], reverse=True):
            item = doc_lookup[f].copy()
            item["score"] = round(score, 5)
            results.append(item)

        return results[:top_k]
