"""
Gate 1: Spec / Retrieval Comprehensive Evaluation Suite
Compares governed canonical retrieval vs BM25 vs TF cosine vs governed lexical hybrid across:
- Recall@1 (%)
- Recall@3 (%)
- MRR (Mean Reciprocal Rank)
- Wrong-Version Rate (%)
- Wrong-Authority Rate (%)
- Customer-Leak Rate (%)
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from retrieval.canonical.retriever import CanonicalSpecRetriever
from retrieval.bm25.retriever import BM25Retriever
from retrieval.vector.dense_retriever import DenseEmbeddingRetriever, EmbeddingEncoder
from retrieval.vector.retriever import TFCosineRetriever
from retrieval.hybrid.retriever import GovernedLexicalHybridRetriever
from retrieval.hybrid.dense_hybrid import (
    GovernedDenseHybridRetriever,
    StandardDenseHybridRetriever,
)


class Gate1RetrievalEvaluator:
    def __init__(
        self,
        spec_dir: str = "fixtures/synthetic-spec",
        queries_path: str = "benchmarks/retrieval/queries.json",
        dense_model: Optional[str] = None,
        dense_model_revision: Optional[str] = None,
        dense_encoder: Optional[EmbeddingEncoder] = None,
    ):
        self.spec_dir = spec_dir
        self.queries_path = Path(queries_path)
        self.retrievers = {
            "spec-reference-kit": CanonicalSpecRetriever(spec_dir=spec_dir),
            "bm25": BM25Retriever(doc_dir=spec_dir),
            "tf_cosine": TFCosineRetriever(doc_dir=spec_dir),
            "governed_lexical_hybrid": GovernedLexicalHybridRetriever(doc_dir=spec_dir),
        }
        # Dense and dense-hybrid arms are opt-in to keep default Gate 1 offline.
        if dense_model is not None or dense_encoder is not None:
            self.retrievers["dense_embedding"] = DenseEmbeddingRetriever(
                doc_dir=spec_dir,
                model_name=dense_model or "sentence-transformers/all-MiniLM-L6-v2",
                model_revision=dense_model_revision,
                encoder=dense_encoder,
            )
            self.retrievers["standard_dense_hybrid"] = StandardDenseHybridRetriever(
                doc_dir=spec_dir,
                dense_model=dense_model or "sentence-transformers/all-MiniLM-L6-v2",
                dense_model_revision=dense_model_revision,
                dense_encoder=dense_encoder,
            )
            self.retrievers["governed_dense_hybrid"] = GovernedDenseHybridRetriever(
                doc_dir=spec_dir,
                dense_model=dense_model or "sentence-transformers/all-MiniLM-L6-v2",
                dense_model_revision=dense_model_revision,
                dense_encoder=dense_encoder,
            )

    def load_queries(self) -> List[Dict[str, Any]]:
        if self.queries_path.exists():
            with open(self.queries_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def evaluate(self, test_queries: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        queries = test_queries or self.load_queries()
        if not queries:
            raise ValueError("No retrieval test queries provided.")

        results = {}
        total = len(queries)

        for name, retriever in self.retrievers.items():
            recall_1 = 0
            recall_3 = 0
            mrr_total = 0.0
            wrong_ver_count = 0
            wrong_auth_count = 0
            cust_leak_count = 0

            for q in queries:
                kwargs = {}
                if name in [
                    "spec-reference-kit",
                    "governed_lexical_hybrid",
                    "governed_dense_hybrid",
                ]:
                    kwargs["target_version"] = q.get("expected_ver")
                    kwargs["caller_customer_tier"] = q.get("target_customer_tier")

                hits = retriever.query(q["query"], top_k=3, **kwargs)

                if hits:
                    # 1. Rank tracking & Recall
                    hit_rank = None
                    for idx, h in enumerate(hits):
                        is_target = (
                            q["expected_id"] in h.get("snippet", "")
                            or q["expected_file"] == h.get("file", "")
                        )
                        if is_target:
                            hit_rank = idx + 1
                            break

                    if hit_rank == 1:
                        recall_1 += 1
                    if hit_rank is not None and hit_rank <= 3:
                        recall_3 += 1
                        mrr_total += 1.0 / hit_rank

                    # 2. Check Top-1 Governance attributes
                    top_hit = hits[0]
                    top_ver = top_hit.get("version", "unknown")
                    top_auth = top_hit.get("authority", "unknown").lower()
                    top_cust = top_hit.get("customer_tier", "unknown").lower()

                    # Wrong Version detection
                    if top_ver != "unknown" and top_ver != q.get("expected_ver"):
                        wrong_ver_count += 1

                    # Wrong Authority (e.g. unapproved draft or deprecated cited)
                    if top_auth != "unknown" and top_auth != q.get("expected_authority", "authoritative").lower():
                        wrong_auth_count += 1

                    # Customer Leak (restricted tier leaked to standard tier query)
                    expected_tier = q.get("target_customer_tier", "tier_1_partner")
                    if top_cust == "tier_a_partner_restricted" and expected_tier != "tier_a_partner_restricted":
                        cust_leak_count += 1

            results[name] = {
                "queries_evaluated": total,
                "recall@1": round((recall_1 / total) * 100.0, 2),
                "recall@3": round((recall_3 / total) * 100.0, 2),
                "mrr": round(mrr_total / total, 3),
                "wrong_version_rate": round((wrong_ver_count / total) * 100.0, 2),
                "wrong_authority_rate": round((wrong_auth_count / total) * 100.0, 2),
                "customer_leak_rate": round((cust_leak_count / total) * 100.0, 2),
            }

        return results


if __name__ == "__main__":
    evaluator = Gate1RetrievalEvaluator()
    summary = evaluator.evaluate()
    print(json.dumps(summary, indent=2))
