"""Fail-closed loader for the S56-C receipt-bound benchmark corpus.

Frozen acceptance-benchmark citations resolve against the corpus bound by
the archived S56-C receipt (4330 chunks), whose sanitized identity is in
contracts/spec_qa_frozen_corpus_s56c_identity.json, not against whatever
ingestion is on the current branch. The recorded ingestion is kept verbatim
in s56c_pdf_ingestion.py and checked against its archived SHA-256. The recorded
authoring commit is historical metadata, not proof that GitHub contains it.
This loader refuses to
return chunks unless every pin below matches, so a drifted ingestion, lock, or
source PDF fails instead of silently changing citation identities.

Why two corpus digests: the receipt digest also hashes BM25 retrieval tokens, so
it depends on the retriever's tokenization. ``chunk_identity_sha256`` covers
chunk IDs and content hashes only and was measured from the same reproduced
corpus; a mismatch on only the receipt digest means tokenization drifted while
chunk identities are intact.

The pins were verified with pdfplumber 0.11.10 and pdfminer.six 20260107.

The frozen module is executed from the exact bytes that were hashed, into a fresh
module object that is never registered in ``sys.modules``. Importing the BM25
retriever below also imports the current branch's ingestion module; that module
is imported but never called here.
"""

from __future__ import annotations

import hashlib
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional, Sequence, Tuple

import yaml
from pydantic import ConfigDict

from gv100h.spec_qa.contracts.governed_chunk import GovernedChunk
from gv100h.spec_qa.retrieval.real_corpus_retriever import GovernedChunkBM25Retriever

PINNED_INGESTION_SHA256 = "fc4951ef8c4c83e2dea38eadf3a2dc6d1da324aeccfc52278d9b4693467716fe"
PINNED_CORPUS_LOCK_SHA256 = "ce319b2044178d02b12f79e2ebb5b6a113d9ae3ef28914f8473bf9c0021769a8"
PINNED_SOURCE_IDS: Tuple[str, ...] = ("usb20_fw", "usb20_se", "usb32", "superspeed_hub_lvs")
PINNED_CHUNK_COUNT = 4330
PINNED_CHUNK_IDENTITY_SHA256 = "194b3712981ee73e3b7d88096cbe4f7a8f40630a060f58b603ff36fd3f1ee353"
PINNED_CORPUS_SHA256 = "8aef81aa6857d9107df56a1b14dbd0c1f1e83d8295018a7c41a9b99b87496293"

_FROZEN_INGESTION_PATH = Path(__file__).with_name("s56c_pdf_ingestion.py")
_FROZEN_INGESTION_MODULE = "gv100h.spec_qa.frozen_corpus.s56c_pdf_ingestion"
DEFAULT_LOCK_PATH = Path(__file__).resolve().parents[1] / "contracts" / "corpus.lock.yaml"


class ReceiptBoundCorpusError(RuntimeError):
    """The receipt-bound corpus could not be reproduced exactly."""


class _ReceiptBoundChunk(GovernedChunk):
    """Detached, immutable scalar snapshot owned by a verified corpus."""

    model_config = ConfigDict(frozen=True)


@dataclass(frozen=True)
class ReceiptBoundCorpus:
    chunks: Tuple[GovernedChunk, ...]
    corpus_sha256: str
    chunk_identity_sha256: str
    _by_id: Mapping[str, GovernedChunk] = field(repr=False, compare=False)

    def get_chunk(self, chunk_id: str) -> Optional[GovernedChunk]:
        return self._by_id.get(chunk_id)


def chunk_identity_sha256(chunks: Sequence[GovernedChunk]) -> str:
    digest = hashlib.sha256()
    for chunk in chunks:
        digest.update(chunk.chunk_id.encode("utf-8"))
        digest.update(b"\0")
        digest.update(chunk.content_sha256.encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _verify_file_sha256(path: Path, expected: str, label: str) -> bytes:
    try:
        source = path.read_bytes()
        actual = hashlib.sha256(source).hexdigest()
    except OSError as exc:
        raise ReceiptBoundCorpusError(f"cannot read {label} {path}: {exc}") from exc
    if actual != expected:
        raise ReceiptBoundCorpusError(
            f"{label} {path} has SHA-256 {actual}, expected pinned {expected}"
        )
    return source


def _verify_corpus_identity(chunks: Sequence[GovernedChunk]) -> str:
    """Check count, chunk identities, and the receipt digest; return the receipt digest."""
    if len(chunks) != PINNED_CHUNK_COUNT:
        raise ReceiptBoundCorpusError(
            f"chunk count {len(chunks)} differs from pinned {PINNED_CHUNK_COUNT}"
        )
    if len({chunk.chunk_id for chunk in chunks}) != len(chunks):
        raise ReceiptBoundCorpusError("chunk IDs are not unique")
    identity = chunk_identity_sha256(chunks)
    if identity != PINNED_CHUNK_IDENTITY_SHA256:
        raise ReceiptBoundCorpusError(
            f"chunk identity SHA-256 {identity} differs from pinned "
            f"{PINNED_CHUNK_IDENTITY_SHA256}"
        )
    digest = GovernedChunkBM25Retriever(chunks).corpus_sha256
    if digest != PINNED_CORPUS_SHA256:
        raise ReceiptBoundCorpusError(
            f"chunk identities match but the receipt corpus digest {digest} differs from "
            f"pinned {PINNED_CORPUS_SHA256}; retrieval tokenization has drifted"
        )
    return digest


def _load_frozen_ingestion() -> types.ModuleType:
    """Verify the frozen ingestion file, then execute exactly the bytes that were hashed."""
    try:
        source = _FROZEN_INGESTION_PATH.read_bytes()
    except OSError as exc:
        raise ReceiptBoundCorpusError(
            f"cannot read frozen ingestion implementation {_FROZEN_INGESTION_PATH}: {exc}"
        ) from exc
    actual = hashlib.sha256(source).hexdigest()
    if actual != PINNED_INGESTION_SHA256:
        raise ReceiptBoundCorpusError(
            f"frozen ingestion implementation {_FROZEN_INGESTION_PATH} has SHA-256 {actual}, "
            f"expected pinned {PINNED_INGESTION_SHA256}"
        )
    module = types.ModuleType(_FROZEN_INGESTION_MODULE)
    module.__file__ = str(_FROZEN_INGESTION_PATH)
    exec(compile(source, str(_FROZEN_INGESTION_PATH), "exec"), module.__dict__)
    return module


def load_receipt_bound_corpus(
    *, raw_root: Path, lock_path: Optional[Path] = None
) -> ReceiptBoundCorpus:
    """Rebuild the receipt-bound corpus from the locked PDFs, failing closed on any drift."""
    frozen_ingestion = _load_frozen_ingestion()
    resolved_lock = Path(lock_path) if lock_path is not None else DEFAULT_LOCK_PATH
    lock_bytes = _verify_file_sha256(resolved_lock, PINNED_CORPUS_LOCK_SHA256, "corpus lock")
    corpus_lock = yaml.safe_load(lock_bytes)
    try:
        chunks = tuple(
            _ReceiptBoundChunk.model_validate(chunk.model_dump())
            for chunk in frozen_ingestion.load_accepted_chunks(
                PINNED_SOURCE_IDS, corpus_lock, raw_root=Path(raw_root)
            )
        )
    except (OSError, ValueError) as exc:
        raise ReceiptBoundCorpusError(f"frozen ingestion failed: {exc}") from exc
    corpus_sha256 = _verify_corpus_identity(chunks)
    return ReceiptBoundCorpus(
        chunks=chunks,
        corpus_sha256=corpus_sha256,
        chunk_identity_sha256=chunk_identity_sha256(chunks),
        _by_id=types.MappingProxyType({chunk.chunk_id: chunk for chunk in chunks}),
    )
