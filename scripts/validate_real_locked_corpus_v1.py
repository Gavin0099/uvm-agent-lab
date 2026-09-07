"""Retrieval-only validation for merged Table Context Reconstruction v1.

This runner never changes retrieval behavior. It verifies locked PDF hashes,
rebuilds accepted GovernedChunk records twice, measures the merged index, and
reports before/after target ranks. Without the official raw corpus it returns
``NOT_RUN`` rather than substituting synthetic evidence for real-corpus proof.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gv100h.spec_qa.ingestion.pdf_ingestion import (
    resolve_source_locator,
    verify_source_hash,
)
from gv100h.spec_qa.retrieval.real_corpus_retriever import (
    DEFAULT_REAL_CORPUS_SOURCE_IDS,
    GovernedChunkBM25Retriever,
)
from gv100h.spec_qa.ingestion.pdf_ingestion import load_accepted_chunks

DEFAULT_LOCK_PATH = PROJECT_ROOT / "gv100h/spec_qa/contracts/corpus.lock.yaml"
DEFAULT_MANIFEST_PATH = (
    PROJECT_ROOT / "benchmarks/retrieval/real_locked_corpus_validation_v1.json"
)


def _load_json(path: Path) -> Mapping[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, Mapping):
        raise ValueError(f"validation manifest must contain an object: {path}")
    return value


def _load_lock(path: Path) -> Mapping[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, Mapping):
        raise ValueError(f"corpus lock must contain an object: {path}")
    return value


def _identity_digest(chunks: Sequence[Any], *, ordered: bool) -> str:
    digest = hashlib.sha256()
    values = chunks if ordered else sorted(chunks, key=lambda chunk: chunk.chunk_id)
    for index, chunk in enumerate(values):
        digest.update(str(index).encode("ascii"))
        digest.update(b"\0")
        digest.update(chunk.chunk_id.encode("utf-8"))
        digest.update(b"\0")
        digest.update(chunk.content_sha256.encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _target_matches(chunk: Any, target: Mapping[str, Any]) -> bool:
    for field in (
        "source_id",
        "section",
        "page_or_anchor",
        "chapter",
        "chunk_kind",
    ):
        if field in target and getattr(chunk, field) != target[field]:
            return False
    if "section_prefix" in target and not chunk.section.startswith(
        str(target["section_prefix"])
    ):
        return False
    content = chunk.content.casefold()
    if any(str(value).casefold() not in content for value in target.get("contains_all", ())):
        return False
    if target.get("contains_any") and not any(
        str(value).casefold() in content for value in target["contains_any"]
    ):
        return False
    return True


def _hit_record(hit: Any, rank: int) -> dict[str, Any]:
    chunk = hit.chunk
    return {
        "rank": rank,
        "score": round(hit.score, 6),
        "matched_terms": list(hit.matched_terms),
        "chunk_id": chunk.chunk_id,
        "source_id": chunk.source_id,
        "revision": chunk.revision,
        "section": chunk.section,
        "page_or_anchor": chunk.page_or_anchor,
        "chunk_kind": chunk.chunk_kind,
        "content_preview": chunk.content[:240],
    }


def _rank_target(retriever: GovernedChunkBM25Retriever, case: Mapping[str, Any]) -> dict[str, Any]:
    hits = retriever.query(
        str(case["query"]),
        top_k=max(1, len(retriever)),
        allowed_source_ids=case.get("allowed_source_ids"),
    )
    target = case.get("target")
    target_rank = None
    if isinstance(target, Mapping):
        for rank, hit in enumerate(hits, start=1):
            if _target_matches(hit.chunk, target):
                target_rank = rank
                break
    diagnostics = []
    for diagnostic in case.get("diagnostic_targets", ()):
        rank = None
        if isinstance(diagnostic, Mapping):
            for candidate_rank, hit in enumerate(hits, start=1):
                if _target_matches(hit.chunk, diagnostic):
                    rank = candidate_rank
                    break
            diagnostics.append({"name": diagnostic.get("name"), "rank": rank})
    return {
        "id": case["id"],
        "query": case["query"],
        "target_rank": target_rank,
        "within_top5": target_rank is not None and target_rank <= 5,
        "diagnostics": diagnostics,
        "top_hits": [_hit_record(hit, rank) for rank, hit in enumerate(hits[:5], 1)],
        "success_condition": case.get("success"),
    }


def run_validation(
    *,
    raw_root: Path | None,
    lock_path: Path = DEFAULT_LOCK_PATH,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> dict[str, Any]:
    manifest = _load_json(manifest_path)
    baseline = manifest.get("baseline_evidence", {})
    if raw_root is None:
        configured_root = os.environ.get("USB_SPEC_QA_RAW_ROOT")
        raw_root = Path(configured_root) if configured_root else None
    base = {
        "validation_version": manifest.get("validation_version"),
        "status": "NOT_RUN",
        "claim_boundary": [
            "retrieval-only; no generation or evidence-selection claim",
            "real locked-corpus evidence requires USB_SPEC_QA_RAW_ROOT",
            "NOT_RUN is not a retrieval failure or a Top-5 result",
        ],
        "baseline_evidence": baseline,
    }
    if raw_root is None or not raw_root.is_dir():
        base["reason"] = "official locked raw corpus is unavailable"
        return base

    corpus_lock = _load_lock(lock_path)
    source_hashes = {}
    for source_id in DEFAULT_REAL_CORPUS_SOURCE_IDS:
        source = corpus_lock["sources"][source_id]
        pdf_path = resolve_source_locator(source["source_locator"], raw_root=raw_root)
        observed = verify_source_hash(pdf_path, source["content_sha256"])
        source_hashes[source_id] = {
            "expected": source["content_sha256"],
            "observed": observed,
            "match": observed == source["content_sha256"],
        }

    chunks_first = load_accepted_chunks(
        DEFAULT_REAL_CORPUS_SOURCE_IDS, corpus_lock, raw_root=raw_root
    )
    chunks_second = load_accepted_chunks(
        DEFAULT_REAL_CORPUS_SOURCE_IDS, corpus_lock, raw_root=raw_root
    )
    retriever_first = GovernedChunkBM25Retriever(chunks_first)
    retriever_second = GovernedChunkBM25Retriever(chunks_second)
    results = [_rank_target(retriever_first, case) for case in manifest["queries"]]
    raw_hashes_match_lock = all(
        record["match"] for record in source_hashes.values()
    )
    chunk_count_matches = len(chunks_first) == baseline.get("chunk_count")
    identity_deterministic = (
        _identity_digest(chunks_first, ordered=True)
        == _identity_digest(chunks_second, ordered=True)
    )
    corpus_deterministic = (
        retriever_first.corpus_sha256 == retriever_second.corpus_sha256
    )
    integrity_pass = all(
        (
            raw_hashes_match_lock,
            chunk_count_matches,
            identity_deterministic,
            corpus_deterministic,
        )
    )
    return {
        **base,
        "status": "PASS" if integrity_pass else "FAIL",
        "raw_source_hashes": source_hashes,
        "chunk_count": len(chunks_first),
        "expected_chunk_count": baseline.get("chunk_count"),
        "raw_hashes_match_lock": raw_hashes_match_lock,
        "chunk_count_matches_baseline": chunk_count_matches,
        "chunk_identity_sha256": _identity_digest(chunks_first, ordered=False),
        "chunk_sequence_sha256": _identity_digest(chunks_first, ordered=True),
        "repeat_chunk_identity_sha256": _identity_digest(chunks_second, ordered=False),
        "repeat_chunk_sequence_sha256": _identity_digest(chunks_second, ordered=True),
        "governed_chunk_identity_deterministic": identity_deterministic,
        "corpus_sha256": retriever_first.corpus_sha256,
        "repeat_corpus_sha256": retriever_second.corpus_sha256,
        "corpus_sha256_deterministic": corpus_deterministic,
        "results": results,
        "table_6_30_top5_pass": any(
            row["id"] == "table_6_30_direct" and row["within_top5"]
            for row in results
        ),
        "table_7_8": "diagnosis_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, default=None)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK_PATH)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    result = run_validation(
        raw_root=args.raw_root,
        lock_path=args.lock,
        manifest_path=args.manifest,
    )
    payload = json.dumps(result, ensure_ascii=True, indent=2)
    if args.output is not None:
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if result["status"] in {"PASS", "NOT_RUN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())