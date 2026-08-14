from pathlib import Path
from typing import List, Dict, Any


class CanonicalSpecRetriever:
    """
    Certified Spec-Reference-Kit Canonical Retriever.
    Indexes spec metadata, version pinning, customer access constraints, and requirement IDs.
    """

    def __init__(self, spec_dir: str = "fixtures/synthetic-spec"):
        self.spec_dir = Path(spec_dir).resolve()
        self._index = self._build_index()

    def _build_index(self) -> List[Dict[str, Any]]:
        docs = []
        for file in self.spec_dir.glob("*.md"):
            try:
                content = file.read_text(encoding="utf-8")
                # Parse frontmatter and content
                meta = {}
                body = content
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        import yaml
                        meta = yaml.safe_load(parts[1]) or {}
                        body = parts[2]

                docs.append({
                    "file": file.name,
                    "title": meta.get("title", file.name),
                    "version": str(meta.get("version", "1.0")),
                    "authority": meta.get("authority", "authoritative"),
                    "customer_tier": meta.get("customer_tier", "internal"),
                    "doc_id": meta.get("doc_id", "DOC-001"),
                    "content": body,
                })
            except Exception:
                continue
        return docs

    def query(self, query_str: str, top_k: int = 3, target_version: str = None) -> List[Dict[str, Any]]:
        tokens = [t.lower() for t in query_str.split() if len(t) > 2]
        results = []
        for doc in self._index:
            doc_text = (doc["title"] + " " + doc["content"]).lower()
            
            # Match score based on keyword and requirement token matches
            score = 0.0
            for t in tokens:
                if t in doc_text:
                    # Give high boost for requirement IDs (e.g. USB3-WR-001)
                    if "-" in t and len(t) >= 6:
                        score += 10.0
                    else:
                        score += 1.0

            if score > 0:
                if target_version and doc["version"] != target_version:
                    score *= 0.5
                results.append({
                    "score": score,
                    "doc_id": doc["doc_id"],
                    "version": doc["version"],
                    "authority": doc["authority"],
                    "customer_tier": doc["customer_tier"],
                    "file": doc["file"],
                    "snippet": doc["content"][:300],
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
