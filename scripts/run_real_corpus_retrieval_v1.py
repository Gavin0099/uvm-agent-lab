"""Run the metadata-only Real Corpus Retrieval v1 benchmark."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, List, Mapping

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gv100h.spec_qa.retrieval.real_corpus_retriever import (
    DEFAULT_REAL_CORPUS_SOURCE_IDS,
    GovernedChunkBM25Retriever,
    evaluate_retrieval,
    validate_allowed_source_ids,
)

DEFAULT_LOCK_PATH = PROJECT_ROOT / "gv100h/spec_qa/contracts/corpus.lock.yaml"
DEFAULT_QUERIES_PATH = PROJECT_ROOT / "benchmarks/retrieval/real_corpus_queries.json"


def _load_json(path: Path) -> List[Mapping[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, list):
        raise ValueError(f"retrieval benchmark must be a JSON list: {path}")
    return value


def _collect_source_ids(
    cases: List[Mapping[str, Any]], corpus_lock: Mapping[str, Any]
) -> tuple[str, ...]:
    sources = corpus_lock.get("sources")
    if not isinstance(sources, Mapping):
        raise ValueError("corpus lock sources must contain a mapping")

    collected: list[str] = []
    for case in cases:
        if not isinstance(case, Mapping):
            raise ValueError("each retrieval case must be a mapping")
        if "allowed_source_ids" in case:
            source_ids = validate_allowed_source_ids(case["allowed_source_ids"])
        else:
            source_ids = DEFAULT_REAL_CORPUS_SOURCE_IDS
        unknown_source_ids = sorted(set(source_ids) - set(sources))
        if unknown_source_ids:
            raise ValueError(
                "allowed_source_ids contains unknown corpus sources: "
                f"{unknown_source_ids}"
            )
        collected.extend(source_ids)
    return tuple(dict.fromkeys(collected))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the metadata-only Real Corpus Retrieval v1 benchmark."
    )
    parser.add_argument("--raw-root", type=Path, default=None)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK_PATH)
    parser.add_argument("--queries", type=Path, default=DEFAULT_QUERIES_PATH)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    raw_root = args.raw_root
    if raw_root is None:
        configured_root = os.environ.get("USB_SPEC_QA_RAW_ROOT")
        if configured_root:
            raw_root = Path(configured_root)
    if raw_root is None:
        parser.error("--raw-root or USB_SPEC_QA_RAW_ROOT is required")
    if not raw_root.is_dir():
        parser.error(f"raw corpus root does not exist or is not a directory: {raw_root}")

    with args.lock.open("r", encoding="utf-8") as handle:
        corpus_lock = yaml.safe_load(handle)
    if not isinstance(corpus_lock, Mapping):
        parser.error(f"corpus lock must contain a mapping: {args.lock}")

    cases = _load_json(args.queries)
    try:
        source_ids = _collect_source_ids(cases, corpus_lock)
    except ValueError as exc:
        parser.error(str(exc))
    retriever = GovernedChunkBM25Retriever.from_corpus_lock(
        corpus_lock,
        source_ids=source_ids,
        raw_root=raw_root,
    )
    summary = evaluate_retrieval(retriever, cases, top_k=args.top_k)
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
