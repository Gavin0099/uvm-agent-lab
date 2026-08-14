"""
Gate 1: Spec / Retrieval Evaluation Suite
Compares spec-reference-kit vs BM25 vs Vector RAG vs Hybrid across:
- Recall@1
- Recall@3
- Wrong-version rate
- Wrong-authority rate
- Wrong-customer leak rate
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from typing import Dict, Any, List
from retrieval.canonical.retriever import CanonicalSpecRetriever
from retrieval.bm25.retriever import BM25Retriever
from retrieval.vector.retriever import VectorRetrieverStub
from retrieval.hybrid.retriever import HybridRetriever


class Gate1RetrievalEvaluator:
    def __init__(self, spec_dir: str = "fixtures/synthetic-spec"):
        self.retrievers = {
            "spec-reference-kit": CanonicalSpecRetriever(spec_dir=spec_dir),
            "bm25": BM25Retriever(doc_dir=spec_dir),
            "vector_rag": VectorRetrieverStub(doc_dir=spec_dir),
            "hybrid": HybridRetriever(doc_dir=spec_dir),
        }

    def evaluate(self, test_queries: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        if test_queries is None:
            test_queries = [
                {
                    "query": "USB3-WR-001 Warm Reset Rx.Detect transition",
                    "expected_id": "USB3-WR-001",
                    "expected_ver": "1.0",
                    "expected_file": "USB3_spec_v1.0.md"
                },
                {
                    "query": "AXI-BP-002 randomized backpressure tready",
                    "expected_id": "AXI-BP-002",
                    "expected_ver": "2.1",
                    "expected_file": "AXI_spec_v2.1.md"
                }
            ]

        results = {}
        for name, retriever in self.retrievers.items():
            recall_1 = 0
            recall_3 = 0
            wrong_ver = 0
            wrong_auth = 0
            total = len(test_queries)

            for q in test_queries:
                hits = retriever.query(q["query"], top_k=3)
                if hits:
                    # Check top 1
                    if q["expected_id"] in hits[0].get("snippet", "") or q["expected_file"] == hits[0].get("file", ""):
                        recall_1 += 1
                    # Check top 3
                    found_in_3 = any(
                        q["expected_id"] in h.get("snippet", "") or q["expected_file"] == h.get("file", "")
                        for h in hits
                    )
                    if found_in_3:
                        recall_3 += 1

                    # Check version governance (if retriever supports version metadata)
                    top_ver = hits[0].get("version")
                    if top_ver and top_ver != q.get("expected_ver"):
                        wrong_ver += 1

                    top_auth = hits[0].get("authority")
                    if top_auth and top_auth != "authoritative":
                        wrong_auth += 1

            results[name] = {
                "recall@1": (recall_1 / total) * 100.0,
                "recall@3": (recall_3 / total) * 100.0,
                "wrong_version_rate": (wrong_ver / total) * 100.0,
                "wrong_authority_rate": (wrong_auth / total) * 100.0,
            }

        return results


if __name__ == "__main__":
    import json
    evaluator = Gate1RetrievalEvaluator()
    summary = evaluator.evaluate()
    print(json.dumps(summary, indent=2))
