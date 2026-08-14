from typing import List, Dict, Any
from retrieval.canonical.retriever import CanonicalSpecRetriever
from retrieval.bm25.retriever import BM25Retriever


class HybridRetriever:
    """
    Combines Canonical Spec governance constraints with BM25 term weighting.
    """

    def __init__(self, doc_dir: str = "fixtures/synthetic-spec"):
        self.canonical = CanonicalSpecRetriever(spec_dir=doc_dir)
        self.bm25 = BM25Retriever(doc_dir=doc_dir)

    def query(self, query_str: str, top_k: int = 3) -> List[Dict[str, Any]]:
        # Merges canonical authority scores with lexical search
        can_res = self.canonical.query(query_str, top_k=top_k)
        if can_res:
            return can_res
        return self.bm25.query(query_str, top_k=top_k)
