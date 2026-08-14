import math
from pathlib import Path
from typing import List, Dict, Any


class BM25Retriever:
    """
    Standard BM25 keyword-based baseline retriever.
    Lacks governance awareness (version pinning or customer restriction checking).
    """

    def __init__(self, doc_dir: str = "fixtures/synthetic-spec"):
        self.doc_dir = Path(doc_dir).resolve()
        self.docs = []
        for f in self.doc_dir.glob("*.md"):
            try:
                self.docs.append({"name": f.name, "text": f.read_text(encoding="utf-8")})
            except Exception:
                pass

    def query(self, query_str: str, top_k: int = 3) -> List[Dict[str, Any]]:
        tokens = query_str.lower().split()
        results = []
        for d in self.docs:
            text_lower = d["text"].lower()
            match_count = sum(text_lower.count(t) for t in tokens)
            if match_count > 0:
                results.append({
                    "score": float(match_count),
                    "file": d["name"],
                    "snippet": d["text"][:300]
                })
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
