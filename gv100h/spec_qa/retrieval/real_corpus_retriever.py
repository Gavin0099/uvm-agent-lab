"""Deterministic BM25 retrieval over PDF-derived GovernedChunk records.

This is the first real-corpus retrieval layer for Spec QA. It keeps the
retrieved GovernedChunk intact so callers retain source, revision, section,
page, authority, and evidence identity when producing a citation.

The index is intentionally in-memory and dependency-free for v1. It does not
perform embeddings, reranking, answer synthesis, or policy decisions. Corpus
eligibility remains owned by PDF ingestion; this module only ranks the chunks
it is given and offers a constructor that loads accepted chunks from a corpus
lock.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from gv100h.spec_qa.contracts.governed_chunk import GovernedChunk
from gv100h.spec_qa.ingestion.pdf_ingestion import load_accepted_chunks

DEFAULT_REAL_CORPUS_SOURCE_IDS: Tuple[str, ...] = (
    "usb20_fw",
    "usb20_se",
    "usb32",
    "superspeed_hub_lvs",
)

_TOKEN_PATTERN = re.compile(r"\w+(?:[.-]\w+)*", re.UNICODE)
_SECTION_CAPTION_PATTERN = re.compile(
    r"^\s*(?:Table|Figure)\s+\d+(?:[-.]\d+)*\b.*$", re.IGNORECASE
)
_TARGET_FIELDS = frozenset(
    {
        "chunk_id",
        "source_id",
        "section",
        "section_prefix",
        "page_or_anchor",
        "chapter",
        "chunk_kind",
    }
)


@dataclass(frozen=True)
class GovernedChunkRetrievalHit:
    """A ranked result that preserves the original governed chunk."""

    chunk: GovernedChunk
    score: float
    matched_terms: Tuple[str, ...]

    def as_record(self) -> Dict[str, Any]:
        """Return a small metadata-rich record for inspection or adapters."""
        return {
            "score": round(self.score, 6),
            "matched_terms": self.matched_terms,
            "chunk_id": self.chunk.chunk_id,
            "source_id": self.chunk.source_id,
            "document": self.chunk.document,
            "revision": self.chunk.revision,
            "chapter": self.chunk.chapter,
            "section": self.chunk.section,
            "page_or_anchor": self.chunk.page_or_anchor,
            "authority_level": self.chunk.authority_level,
            "chunk_kind": self.chunk.chunk_kind,
            "content": self.chunk.content,
            "content_sha256": self.chunk.content_sha256,
        }


def _tokenize(text: str) -> Tuple[str, ...]:
    return tuple(
        token.casefold()
        for token in _TOKEN_PATTERN.findall(text)
        if len(token) > 1
    )


def _section_context(chunks: Sequence[GovernedChunk]) -> Dict[Tuple[str, str], str]:
    """Collect deterministic headings and table/figure captions per section."""
    context: Dict[Tuple[str, str], List[str]] = {}
    for chunk in chunks:
        key = (chunk.source_id, chunk.section)
        entries = context.setdefault(key, [])
        if chunk.chunk_kind == "heading_only":
            entries.append(chunk.content.strip())
        for line in chunk.content.splitlines():
            candidate = line.strip()
            if _SECTION_CAPTION_PATTERN.match(candidate):
                entries.append(candidate)

    deduplicated: Dict[Tuple[str, str], str] = {}
    for key, entries in context.items():
        deduplicated[key] = " ".join(dict.fromkeys(entry for entry in entries if entry))
    return deduplicated


def _index_text(chunk: GovernedChunk, context: str) -> str:
    return " ".join(
        (
            chunk.source_id,
            chunk.document,
            chunk.revision,
            chunk.chapter,
            chunk.section,
            chunk.page_or_anchor,
            chunk.chunk_kind,
            context,
            chunk.content,
        )
    )


def _matches_target(chunk: GovernedChunk, target: Mapping[str, Any]) -> bool:
    if "chunk_id" in target and chunk.chunk_id != target["chunk_id"]:
        return False
    if "source_id" in target and chunk.source_id != target["source_id"]:
        return False
    if "section" in target and chunk.section != target["section"]:
        return False
    if "section_prefix" in target and not chunk.section.startswith(target["section_prefix"]):
        return False
    if "page_or_anchor" in target and chunk.page_or_anchor != target["page_or_anchor"]:
        return False
    if "chapter" in target and chunk.chapter != target["chapter"]:
        return False
    if "chunk_kind" in target and chunk.chunk_kind != target["chunk_kind"]:
        return False
    return True


def _hit_metadata(hit: GovernedChunkRetrievalHit, rank: int) -> Dict[str, Any]:
    chunk = hit.chunk
    return {
        "rank": rank,
        "score": round(hit.score, 6),
        "matched_terms": list(hit.matched_terms),
        "chunk_id": chunk.chunk_id,
        "source_id": chunk.source_id,
        "document": chunk.document,
        "revision": chunk.revision,
        "chapter": chunk.chapter,
        "section": chunk.section,
        "page_or_anchor": chunk.page_or_anchor,
        "authority_level": chunk.authority_level,
        "chunk_kind": chunk.chunk_kind,
    }


def evaluate_retrieval(
    retriever: "GovernedChunkBM25Retriever",
    cases: Sequence[Mapping[str, Any]],
    *,
    top_k: int = 5,
) -> Dict[str, Any]:
    """Evaluate metadata-labelled queries without exposing indexed content."""
    if top_k < 1:
        raise ValueError("top_k must be greater than zero")
    if not cases:
        raise ValueError("at least one retrieval case is required")

    rows: List[Dict[str, Any]] = []
    reciprocal_rank_total = 0.0
    recall_counts = {1: 0, 3: 0, 5: 0}
    # Metrics need the complete ranking to distinguish a below-cutoff target
    # from a missing target; only the displayed top_hits are limited below.
    query_top_k = max(len(retriever), 5)

    for case in cases:
        raw_case_id = case.get("id")
        raw_query = case.get("query")
        target = case.get("target")
        if (
            not isinstance(raw_case_id, str)
            or not raw_case_id.strip()
            or not isinstance(raw_query, str)
            or not raw_query.strip()
            or not isinstance(target, Mapping)
        ):
            raise ValueError("each retrieval case requires id, query, and target")
        case_id = raw_case_id
        query = raw_query
        unknown_target_fields = set(target) - _TARGET_FIELDS
        if unknown_target_fields:
            raise ValueError(
                "each retrieval target contains unknown constraints: "
                f"{sorted(unknown_target_fields)}"
            )
        if not (set(target) & _TARGET_FIELDS):
            raise ValueError(
                "each retrieval target requires at least one recognized constraint"
            )

        hits = retriever.query(
            query,
            top_k=query_top_k,
            allowed_source_ids=case.get("allowed_source_ids"),
        )
        target_rank = next(
            (
                rank
                for rank, hit in enumerate(hits, start=1)
                if _matches_target(hit.chunk, target)
            ),
            None,
        )
        if target_rank is not None:
            reciprocal_rank_total += 1.0 / target_rank
            for cutoff in recall_counts:
                if target_rank <= cutoff:
                    recall_counts[cutoff] += 1

        rows.append(
            {
                "id": case_id,
                "target_rank": target_rank,
                "hit_count": len(hits),
                "top_hits": [
                    _hit_metadata(hit, rank)
                    for rank, hit in enumerate(hits[:top_k], 1)
                ],
            }
        )

    total = len(rows)
    return {
        "retriever_kind": retriever.retriever_kind,
        "corpus_sha256": retriever.corpus_sha256,
        "queries_evaluated": total,
        "recall@1": round(recall_counts[1] * 100.0 / total, 2),
        "recall@3": round(recall_counts[3] * 100.0 / total, 2),
        "recall@5": round(recall_counts[5] * 100.0 / total, 2),
        "mrr": round(reciprocal_rank_total / total, 3),
        "cases": rows,
    }


class GovernedChunkBM25Retriever:
    """Rank real ``GovernedChunk`` records with a deterministic BM25 index."""

    retriever_kind = "governed_chunk_bm25_v1"

    def __init__(
        self,
        chunks: Sequence[GovernedChunk],
        *,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        if k1 <= 0:
            raise ValueError("k1 must be greater than zero")
        if not 0 <= b <= 1:
            raise ValueError("b must be between zero and one")

        self.k1 = k1
        self.b = b
        self._chunks = tuple(chunks)
        chunk_ids = [chunk.chunk_id for chunk in self._chunks]
        if len(chunk_ids) != len(set(chunk_ids)):
            raise ValueError("GovernedChunkBM25Retriever requires unique chunk_id values")

        context = _section_context(self._chunks)
        self._tokens = tuple(
            _tokenize(_index_text(chunk, context.get((chunk.source_id, chunk.section), "")))
            for chunk in self._chunks
        )
        self._term_sets = tuple(frozenset(tokens) for tokens in self._tokens)
        self._term_frequencies = tuple(Counter(tokens) for tokens in self._tokens)
        self._document_frequency = Counter(
            term for terms in self._term_sets for term in terms
        )
        self._average_document_length = (
            sum(len(tokens) for tokens in self._tokens) / len(self._tokens)
            if self._tokens
            else 0.0
        )
        digest = hashlib.sha256()
        for chunk in sorted(self._chunks, key=lambda item: item.chunk_id):
            digest.update(chunk.chunk_id.encode("utf-8"))
            digest.update(b"\0")
            digest.update(chunk.content_sha256.encode("ascii"))
            digest.update(b"\0")
        self.corpus_sha256 = digest.hexdigest()

    @classmethod
    def from_corpus_lock(
        cls,
        corpus_lock: Mapping[str, Any],
        *,
        source_ids: Sequence[str] = DEFAULT_REAL_CORPUS_SOURCE_IDS,
        raw_root: Optional[Path] = None,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> "GovernedChunkBM25Retriever":
        """Load accepted official PDF chunks and build the v1 index."""
        chunks = load_accepted_chunks(source_ids, corpus_lock, raw_root=raw_root)
        return cls(chunks, k1=k1, b=b)

    @property
    def chunks(self) -> Tuple[GovernedChunk, ...]:
        return self._chunks

    def __len__(self) -> int:
        return len(self._chunks)

    def query(
        self,
        query: str,
        top_k: int = 5,
        *,
        allowed_source_ids: Optional[Iterable[str]] = None,
    ) -> List[GovernedChunkRetrievalHit]:
        """Return the top matching chunks, optionally limited by source ID."""
        if top_k <= 0 or not query.strip() or not self._chunks:
            return []

        query_terms = tuple(dict.fromkeys(_tokenize(query)))
        if not query_terms:
            return []

        if allowed_source_ids is None:
            active_indices = list(range(len(self._chunks)))
        else:
            allowed = set(allowed_source_ids)
            active_indices = [
                index
                for index, chunk in enumerate(self._chunks)
                if chunk.source_id in allowed
            ]
        if not active_indices:
            return []

        active_count = len(active_indices)
        average_length = sum(
            len(self._tokens[index]) for index in active_indices
        ) / active_count
        if allowed_source_ids is None:
            document_frequency = self._document_frequency
        else:
            document_frequency = Counter(
                term
                for index in active_indices
                for term in self._term_sets[index]
            )

        ranked: List[GovernedChunkRetrievalHit] = []
        for index in active_indices:
            frequencies = self._term_frequencies[index]
            document_length = len(self._tokens[index])
            score = 0.0
            matched_terms: List[str] = []
            for term in query_terms:
                frequency = frequencies.get(term, 0)
                if not frequency:
                    continue
                matched_terms.append(term)
                document_frequency_value = document_frequency[term]
                inverse_document_frequency = math.log(
                    1.0
                    + (active_count - document_frequency_value + 0.5)
                    / (document_frequency_value + 0.5)
                )
                denominator = frequency + self.k1 * (
                    1.0
                    - self.b
                    + self.b * document_length / max(1.0, average_length)
                )
                score += inverse_document_frequency * (
                    frequency * (self.k1 + 1.0) / denominator
                )

            if score > 0.0:
                ranked.append(
                    GovernedChunkRetrievalHit(
                        chunk=self._chunks[index],
                        score=score,
                        matched_terms=tuple(matched_terms),
                    )
                )

        ranked.sort(key=lambda hit: (-hit.score, hit.chunk.chunk_id))
        return ranked[:top_k]
