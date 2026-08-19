import math
from pathlib import Path
from typing import List, Dict, Any


class TFCosineRetriever:
    """
    Term-frequency cosine retrieval baseline.

    This is not dense embedding retrieval: it uses whitespace-token term
    frequency vectors and cosine similarity as a deterministic lexical baseline.
    Lacks governance metadata filtering.
    """

    def __init__(self, doc_dir: str = "fixtures/synthetic-spec"):
        self.doc_dir = Path(doc_dir).resolve()
        self.docs = []
        self._build_embeddings()

    def _build_embeddings(self):
        for f in sorted(self.doc_dir.glob("*.md")):
            try:
                text = f.read_text(encoding="utf-8")
                words = [w.lower() for w in text.split() if len(w) > 1]
                self.docs.append({
                    "file": f.name,
                    "text": text,
                    "tf": {w: words.count(w) for w in set(words)}
                })
            except Exception:
                pass

    def _cosine_sim(self, q_tf: Dict[str, int], d_tf: Dict[str, int]) -> float:
        dot = sum(q_tf[w] * d_tf.get(w, 0) for w in q_tf)
        q_norm = math.sqrt(sum(v * v for v in q_tf.values()))
        d_norm = math.sqrt(sum(v * v for v in d_tf.values()))
        if q_norm == 0 or d_norm == 0:
            return 0.0
        return dot / (q_norm * d_norm)

    def query(self, query_str: str, top_k: int = 3, **kwargs) -> List[Dict[str, Any]]:
        q_words = [w.lower() for w in query_str.split() if len(w) > 1]
        q_tf = {w: q_words.count(w) for w in set(q_words)}
        
        results = []
        for d in self.docs:
            sim = self._cosine_sim(q_tf, d["tf"])
            if sim > 0:
                ver = "unknown"
                auth = "unknown"
                cust = "unknown"
                if "version: \"" in d["text"]:
                    ver = d["text"].split("version: \"")[1].split("\"")[0]
                if "authority: \"" in d["text"]:
                    auth = d["text"].split("authority: \"")[1].split("\"")[0]
                if "customer_tier: \"" in d["text"]:
                    cust = d["text"].split("customer_tier: \"")[1].split("\"")[0]

                results.append({
                    "score": round(sim, 4),
                    "file": d["file"],
                    "version": ver,
                    "authority": auth,
                    "customer_tier": cust,
                    "snippet": d["text"][:350].strip()
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]


# Backward-compatible import name for historical Gate 1 callers.
VectorRetrieverStub = TFCosineRetriever
