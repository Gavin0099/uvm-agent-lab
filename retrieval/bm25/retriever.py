import math
from pathlib import Path
from typing import List, Dict, Any, Optional, Set


class BM25Retriever:
    """
    Standard BM25 Keyword Baseline Retriever.
    Note: Lacks version-pinning, authority awareness, and customer-tier boundary enforcement.
    """

    def __init__(self, doc_dir: str = "fixtures/synthetic-spec", k1: float = 1.5, b: float = 0.75):
        self.doc_dir = Path(doc_dir).resolve()
        self.k1 = k1
        self.b = b
        self.docs = []
        self._build_index()

    def _build_index(self):
        for f in sorted(self.doc_dir.glob("*.md")):
            try:
                text = f.read_text(encoding="utf-8")
                words = [w.lower() for w in text.split() if len(w) > 1]
                self.docs.append({
                    "file": f.name,
                    "text": text,
                    "words": words,
                    "len": len(words)
                })
            except Exception:
                pass
        self.avg_doc_len = sum(d["len"] for d in self.docs) / max(1, len(self.docs))
        self.num_docs = len(self.docs)

    def query(
        self,
        query_str: str,
        top_k: int = 3,
        allowed_files: Optional[Set[str]] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        query_tokens = [q.lower() for q in query_str.split() if len(q) > 1]
        scores = []
        active_docs = [
            doc for doc in self.docs
            if allowed_files is None or doc["file"] in allowed_files
        ]
        active_avg_doc_len = sum(d["len"] for d in active_docs) / max(1, len(active_docs))
        active_num_docs = len(active_docs)

        for d in active_docs:
            score = 0.0
            doc_words = d["words"]
            doc_len = d["len"]
            
            for q in query_tokens:
                freq = doc_words.count(q)
                if freq > 0:
                    df = sum(1 for other in active_docs if q in other["words"])
                    idf = math.log(1 + (active_num_docs - df + 0.5) / (df + 0.5))
                    tf_component = (freq * (self.k1 + 1)) / (freq + self.k1 * (1 - self.b + self.b * (doc_len / max(1, active_avg_doc_len))))
                    score += idf * tf_component

            if score > 0:
                # Extract meta attributes if present in markdown text
                ver = "unknown"
                auth = "unknown"
                cust = "unknown"
                if "version: \"" in d["text"]:
                    ver = d["text"].split("version: \"")[1].split("\"")[0]
                if "authority: \"" in d["text"]:
                    auth = d["text"].split("authority: \"")[1].split("\"")[0]
                if "customer_tier: \"" in d["text"]:
                    cust = d["text"].split("customer_tier: \"")[1].split("\"")[0]

                scores.append({
                    "score": round(score, 3),
                    "file": d["file"],
                    "version": ver,
                    "authority": auth,
                    "customer_tier": cust,
                    "snippet": d["text"][:350].strip()
                })

        scores.sort(key=lambda x: x["score"], reverse=True)
        return scores[:top_k]
