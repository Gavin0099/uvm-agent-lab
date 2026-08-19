import yaml
import hashlib


class CanonicalSpecIntegrityError(RuntimeError):
    """Raised when an indexed canonical document changes after indexing."""
from pathlib import Path
from typing import List, Dict, Any, Optional


class CanonicalSpecRetriever:
    """
    Certified Spec-Reference-Kit Canonical Knowledge Retriever.
    Enforces:
    - Zero draft/deprecated leakage (only returns authoritative specs unless requested).
    - Customer tier access boundary enforcement (prevents restricted customer leakage).
    - Version pinning.
    - Cryptographic provenance tracking (SHA-256 canonical hash).
    """

    def __init__(self, spec_dir: str = "fixtures/synthetic-spec"):
        self.spec_dir = Path(spec_dir).resolve()
        self._index = self._build_index()

    def _build_index(self) -> List[Dict[str, Any]]:
        docs = []
        for file in sorted(self.spec_dir.glob("*.md")):
            try:
                content = file.read_text(encoding="utf-8")
                meta = {}
                body = content
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        meta = yaml.safe_load(parts[1]) or {}
                        body = parts[2]

                doc_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                docs.append({
                    "file": file.name,
                    "title": meta.get("title", file.name),
                    "version": str(meta.get("version", "1.0")),
                    "authority": str(meta.get("authority", "authoritative")).lower(),
                    "customer_tier": str(meta.get("customer_tier", "internal_engineering")).lower(),
                    "doc_id": meta.get("doc_id", "DOC-001"),
                    "content": body,
                    "canonical_hash": f"sha256:{doc_hash}",
                })
            except Exception:
                continue
        return docs

    def query(
        self,
        query_str: str,
        top_k: int = 3,
        target_version: Optional[str] = None,
        caller_customer_tier: Optional[str] = None,
        allow_drafts: bool = False,
    ) -> List[Dict[str, Any]]:
        tokens = [t.lower() for t in query_str.split() if len(t) > 2]
        results = []

        for doc in self._index:
            # 1. Authority Filter: Reject unapproved drafts and deprecated specs by default
            if not allow_drafts and doc["authority"] != "authoritative":
                continue

            # 2. Customer Tier Governance: Reject docs exceeding caller's customer tier
            if doc["customer_tier"] == "tier_a_partner_restricted":
                if caller_customer_tier != "tier_a_partner_restricted":
                    # Access denied to restricted tier
                    continue

            doc_text = (doc["title"] + " " + doc["content"]).lower()
            
            # Match score computation
            score = 0.0
            for t in tokens:
                if t in doc_text:
                    if "-" in t and len(t) >= 6:  # Requirement ID match bonus
                        score += 15.0
                    else:
                        score += 1.0

            if score > 0:
                # Version pinning bonus / penalty
                if target_version:
                    if doc["version"] == target_version:
                        score *= 2.0
                    else:
                        score *= 0.1

                results.append({
                    "score": round(score, 2),
                    "doc_id": doc["doc_id"],
                    "version": doc["version"],
                    "authority": doc["authority"],
                    "customer_tier": doc["customer_tier"],
                    "file": doc["file"],
                    "canonical_hash": doc["canonical_hash"],
                    "snippet": doc["content"][:350].strip(),
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def eligible_files(
        self,
        target_version: Optional[str] = None,
        caller_customer_tier: Optional[str] = None,
        allow_drafts: bool = False,
    ) -> set[str]:
        """Return files eligible for retrieval before lexical or dense scoring."""
        eligible = set()
        for doc in self._index:
            if not allow_drafts and doc["authority"] != "authoritative":
                continue
            if (
                doc["customer_tier"] == "tier_a_partner_restricted"
                and caller_customer_tier != "tier_a_partner_restricted"
            ):
                continue
            if target_version is not None and doc["version"] != target_version:
                continue
            eligible.add(doc["file"])
        return eligible

    def metadata_for_files(self, files: set[str]) -> Dict[str, Dict[str, Any]]:
        """Return canonical provenance metadata for a set of indexed files."""
        return {
            doc["file"]: doc
            for doc in self._index
            if doc["file"] in files
        }

    @property
    def indexed_files(self) -> set[str]:
        return {doc["file"] for doc in self._index}

    def verify_file_hash(self, file_name: str) -> None:
        """Fail closed if a canonical file no longer matches its indexed hash."""
        metadata = self.metadata_for_files({file_name}).get(file_name)
        if metadata is None:
            raise CanonicalSpecIntegrityError(
                f"Canonical file is not in the indexed corpus: {file_name}"
            )
        path = self.spec_dir / file_name
        try:
            actual_hash = hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
        except (OSError, UnicodeError) as exc:
            raise CanonicalSpecIntegrityError(
                f"Canonical file cannot be read: {file_name}"
            ) from exc
        expected_hash = metadata["canonical_hash"].removeprefix("sha256:")
        if actual_hash != expected_hash:
            raise CanonicalSpecIntegrityError(
                f"Canonical hash mismatch for {file_name}"
            )
