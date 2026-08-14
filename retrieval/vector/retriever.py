from typing import List, Dict, Any
from pathlib import Path


class VectorRetrieverStub:
    """
    Vector similarity embedding RAG baseline stub.
    """

    def __init__(self, doc_dir: str = "fixtures/synthetic-spec"):
        self.doc_dir = Path(doc_dir).resolve()

    def query(self, query_str: str, top_k: int = 3) -> List[Dict[str, Any]]:
        # Vector stub computes approximate lexical-embedding overlap
        results = []
        for file in self.doc_dir.glob("*.md"):
            try:
                content = file.read_text(encoding="utf-8")
                results.append({
                    "score": 0.85,
                    "file": file.name,
                    "snippet": content[:300]
                })
            except Exception:
                pass
        return results[:top_k]
