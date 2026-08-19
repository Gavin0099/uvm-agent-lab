import hashlib
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Sequence, Set


class EmbeddingEncoder(Protocol):
    """Encoder output may use any scale; the retriever applies L2 normalization."""

    def encode(self, texts: Sequence[str], **kwargs: Any) -> Any:
        ...


class DenseBackendUnavailable(RuntimeError):
    """Raised when the optional dense embedding backend is not installed."""


class DenseEmbeddingRetriever:
    """
    Dense embedding retriever backed by an injected encoder or sentence-transformers.

    Governance filters are intentionally absent: this is a retrieval baseline,
    not the governed canonical retriever. Callers must apply governance before
    treating its results as admissible context.
    """

    retriever_kind = "dense_embedding"

    def __init__(
        self,
        doc_dir: str = "fixtures/synthetic-spec",
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        model_revision: Optional[str] = None,
        encoder: Optional[EmbeddingEncoder] = None,
    ):
        self.doc_dir = Path(doc_dir).resolve()
        self.model_name = model_name
        self.model_revision = model_revision
        self.encoder = encoder or self._load_encoder()
        self.docs = self._load_documents()
        self.corpus_sha256 = self._compute_corpus_sha256()
        self.embedding_normalization = "l2"
        self.embeddings = self._encode([doc["text"] for doc in self.docs])
        self.embedding_dimension = len(self.embeddings[0]) if self.embeddings else 0

    def _load_encoder(self) -> EmbeddingEncoder:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise DenseBackendUnavailable(
                "Dense retrieval requires the optional 'rag' dependency "
                "(sentence-transformers) or an injected encoder."
            ) from exc

        kwargs = {}
        if self.model_revision:
            kwargs["revision"] = self.model_revision
        return SentenceTransformer(self.model_name, **kwargs)

    def _load_documents(self) -> List[Dict[str, str]]:
        documents = []
        for path in sorted(self.doc_dir.glob("*.md")):
            try:
                documents.append({"file": path.name, "text": path.read_text(encoding="utf-8")})
            except OSError:
                continue
        return documents

    def _compute_corpus_sha256(self) -> str:
        digest = hashlib.sha256()
        for document in self.docs:
            digest.update(document["file"].encode("utf-8"))
            digest.update(b"\0")
            digest.update(document["text"].encode("utf-8"))
        return digest.hexdigest()

    @staticmethod
    def _normalize(vector: Sequence[float]) -> List[float]:
        values = [float(value) for value in vector]
        norm = math.sqrt(sum(value * value for value in values))
        if norm == 0.0:
            return [0.0 for _ in values]
        return [value / norm for value in values]

    def _encode(self, texts: Sequence[str]) -> List[List[float]]:
        encoded = self.encoder.encode(
            list(texts),
            convert_to_numpy=True,
            normalize_embeddings=False,
        )
        return [self._normalize(vector) for vector in encoded]

    @staticmethod
    def _metadata(text: str) -> Dict[str, str]:
        metadata = {
            "version": "unknown",
            "authority": "unknown",
            "customer_tier": "unknown",
        }
        for key in metadata:
            marker = f'{key}: "'
            if marker in text:
                metadata[key] = text.split(marker, 1)[1].split('"', 1)[0]
        return metadata

    def query(
        self,
        query_str: str,
        top_k: int = 3,
        allowed_files: Optional[Set[str]] = None,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        if not query_str.strip() or not self.docs:
            return []

        query_vector = self._encode([query_str])[0]
        results = []
        for document, embedding in zip(self.docs, self.embeddings):
            if allowed_files is not None and document["file"] not in allowed_files:
                continue
            score = sum(left * right for left, right in zip(query_vector, embedding))
            item = {
                "score": round(score, 6),
                "file": document["file"],
                "snippet": document["text"][:350].strip(),
                "model_name": self.model_name,
                "model_revision": self.model_revision,
                "corpus_sha256": self.corpus_sha256,
                "embedding_dimension": self.embedding_dimension,
                "embedding_normalization": self.embedding_normalization,
                "retriever_kind": self.retriever_kind,
            }
            item.update(self._metadata(document["text"]))
            results.append(item)

        results.sort(key=lambda item: (-item["score"], item["file"]))
        return results[:top_k]
