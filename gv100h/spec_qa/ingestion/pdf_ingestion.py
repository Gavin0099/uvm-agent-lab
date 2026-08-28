"""
Deterministic, fail-closed raw-PDF ingestion into ``GovernedChunk`` records.

Scope discipline for this module (Machine A / PDF-RAG track, bounded PR):
raw PDF -> governed chunk schema -> queryable section/table chunks. This
module deliberately does NOT do embedding, reranking, or LLM synthesis, and
it does NOT modify ``qa_service.py``'s existing decision logic or the live
``EVIDENCE_REGISTRY`` -- see ``GovernedChunk.to_citation()`` for how a chunk
proves Evidence Contract compatibility without being wired into the live
answer path.

Determinism and fail-closed rules enforced here:
- A PDF is only ingested after its whole-file sha256 is verified against the
  ``content_sha256`` locked in ``corpus.lock.yaml`` for that source -- the
  same hash-before-trust discipline
  ``GovernedSpecRetriever._verify_document_source`` already applies to
  physical source binding, applied here at ingestion time instead.
- Chunking never fabricates a section: text encountered before the first
  recognized heading on a source is dropped rather than attributed to a
  guessed section.
- The chunker is a pure function of PDF bytes -- same input always produces
  the same ``GovernedChunk`` list (same ``chunk_id``/``content_sha256``
  values), which is what lets a test assert ingestion is deterministic.
"""
import hashlib
import re
from pathlib import Path
from typing import Any, List, Mapping, Optional, Sequence, Tuple

import pdfplumber

from gv100h.spec_qa.contracts.evidence_contract import AuthorityLevel
from gv100h.spec_qa.contracts.governed_chunk import GovernedChunk

# A heading line: one or more dot-separated digit groups, then whitespace,
# then a nonempty title -- e.g. "10.16.2.1 Hub Class Feature Selectors".
_HEADING_PATTERN = re.compile(r"^(?P<section>\d+(?:\.\d+)*)\s+(?P<title>\S.*)$")

# corpus.lock.yaml source "role" -> Citation/GovernedChunk authority_level.
# Mirrors the mapping already implicit in governed_retriever.py's
# hand-authored EVIDENCE_REGISTRY (every entry there is "authoritative"
# regardless of whether its source's role is "canonical_structured_reference"
# or "normative_official") -- kept here rather than imported so this
# ingestion module does not depend on governed_retriever.py.
ROLE_TO_AUTHORITY_LEVEL: Mapping[str, AuthorityLevel] = {
    "canonical_structured_reference": "authoritative",
    "normative_official": "authoritative",
}


class PdfIngestionError(ValueError):
    """Raised when a PDF fails deterministic, fail-closed ingestion."""


def verify_source_hash(pdf_path: Path, expected_sha256: str) -> str:
    """
    Fail-closed hash check: refuse to ingest a PDF whose content does not
    match the ``content_sha256`` locked in ``corpus.lock.yaml``. Returns the
    observed digest on success.
    """
    if not pdf_path.is_file():
        raise PdfIngestionError(f"PDF source file does not exist: {pdf_path}")
    observed = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    if observed.lower() != str(expected_sha256).lower():
        raise PdfIngestionError(
            f"{pdf_path} content_sha256 mismatch: expected {expected_sha256}, got {observed} "
            "-- refusing to ingest an unverified/tampered/stale PDF"
        )
    return observed


def _page_events(page: "pdfplumber.page.Page") -> List[Tuple[float, str, Any]]:
    """
    Reconstruct one page as a single top-to-bottom ordered sequence of
    ``("line", text)`` and ``("table", rows)`` events.

    pdfplumber's line/word extraction and its table detection are
    independent passes over the same underlying characters, so a table's
    cell text would otherwise also show up as ordinary "line" events --
    each table's bounding box is used to drop the line events that fall
    inside it, so table content is only ever chunked once, as a table.
    """
    tables = page.find_tables()
    table_bboxes = [table.bbox for table in tables]

    def _within_any_table(top: float) -> bool:
        return any(bbox[1] <= top <= bbox[3] for bbox in table_bboxes)

    events: List[Tuple[float, str, Any]] = []
    for line in page.extract_text_lines(layout=False):
        text = (line.get("text") or "").strip()
        if text and not _within_any_table(line["top"]):
            events.append((line["top"], "line", text))
    for table in tables:
        rows = table.extract()
        if rows:
            events.append((table.bbox[1], "table", rows))
    events.sort(key=lambda event: event[0])
    return events


def _serialize_table(rows: List[List[Optional[str]]]) -> str:
    """Serialize an extracted table's rows into flat, citable chunk text."""
    return "\n".join(" | ".join((cell or "").strip() for cell in row) for row in rows)


def chunk_pdf(
    pdf_path: Path,
    *,
    source_id: str,
    document: str,
    revision: str,
    authority_level: AuthorityLevel,
    expected_sha256: str,
) -> List[GovernedChunk]:
    """
    Ingest one PDF into an ordered list of ``GovernedChunk`` records.

    Fails closed (raises ``PdfIngestionError``) rather than returning a
    partial/empty result when the hash check fails or zero chunks were
    produced -- an ingestion pipeline that silently returns nothing looks
    identical to "the PDF has no content", which is a much more dangerous
    failure mode than a loud error.
    """
    verify_source_hash(pdf_path, expected_sha256)

    chunks: List[GovernedChunk] = []
    current_section: Optional[str] = None
    index = 0

    def _flush_paragraph(buffer: List[str], page_or_anchor: str) -> None:
        nonlocal index
        if not buffer or current_section is None:
            return
        chunks.append(
            GovernedChunk.build(
                source_id=source_id,
                document=document,
                revision=revision,
                section=current_section,
                page_or_anchor=page_or_anchor,
                authority_level=authority_level,
                chunk_kind="paragraph",
                content="\n".join(buffer),
                index=index,
            )
        )
        index += 1

    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            page_or_anchor = f"p.{page_number}"
            paragraph_buffer: List[str] = []
            for _, kind, payload in _page_events(page):
                if kind == "line":
                    heading_match = _HEADING_PATTERN.match(payload)
                    if heading_match:
                        _flush_paragraph(paragraph_buffer, page_or_anchor)
                        paragraph_buffer = []
                        current_section = heading_match.group("section")
                        chunks.append(
                            GovernedChunk.build(
                                source_id=source_id,
                                document=document,
                                revision=revision,
                                section=current_section,
                                page_or_anchor=page_or_anchor,
                                authority_level=authority_level,
                                chunk_kind="heading_only",
                                content=payload,
                                index=index,
                            )
                        )
                        index += 1
                        continue
                    if current_section is None:
                        # No heading has been seen yet for this source --
                        # do not fabricate a section attribution for
                        # front-matter/cover-page text; drop it rather than
                        # guess.
                        continue
                    paragraph_buffer.append(payload)
                else:  # kind == "table"
                    _flush_paragraph(paragraph_buffer, page_or_anchor)
                    paragraph_buffer = []
                    if current_section is None:
                        continue
                    chunks.append(
                        GovernedChunk.build(
                            source_id=source_id,
                            document=document,
                            revision=revision,
                            section=current_section,
                            page_or_anchor=page_or_anchor,
                            authority_level=authority_level,
                            chunk_kind="table",
                            content=_serialize_table(payload),
                            index=index,
                        )
                    )
                    index += 1
            _flush_paragraph(paragraph_buffer, page_or_anchor)

    if not chunks:
        raise PdfIngestionError(
            f"{pdf_path} produced zero governed chunks (no recognizable section heading found)"
        )
    return chunks


def is_source_eligible_as_answer_evidence(source_id: str, corpus_lock: Mapping[str, Any]) -> bool:
    """
    Mirrors the eligibility rule
    ``GovernedSpecRetriever._validate_evidence_registry_provenance`` already
    applies to the hand-authored ``EVIDENCE_REGISTRY`` (phase_1, not
    excluded, layer allowed as answer evidence) -- duplicated here
    deliberately rather than imported, since ingestion must not depend on
    ``governed_retriever.py``; reconciling into one shared helper is a
    follow-up for the later live-registry integration PR.
    """
    source = corpus_lock.get("sources", {}).get(source_id, {})
    layer = corpus_lock.get("layers", {}).get(source.get("layer"), {})
    return (
        source.get("phase") == "phase_1"
        and source.get("included", True) is not False
        and layer.get("allowed_as_answer_evidence") is True
    )


def resolve_source_locator(source_locator: str, *, raw_root: Optional[Path] = None) -> Path:
    """
    Resolve a corpus.lock.yaml ``source_locator`` of the form
    ``env://VARNAME/relative/path`` to a real filesystem path, using either
    an explicit ``raw_root`` override or the ``VARNAME`` environment
    variable. Fails closed (raises) rather than silently skipping a source
    whose raw PDF isn't available in the current environment.
    """
    import os

    match = re.fullmatch(r"env://(?P<var>[^/]+)/(?P<rel>.+)", source_locator)
    if not match:
        raise PdfIngestionError(f"unsupported source_locator format: {source_locator!r}")
    rel_path = match.group("rel")
    if raw_root is not None:
        return Path(raw_root) / rel_path
    var_name = match.group("var")
    base = os.environ.get(var_name)
    if not base:
        raise PdfIngestionError(
            f"source_locator {source_locator!r} requires environment variable "
            f"{var_name!r}, which is not set -- the raw PDF corpus is not bound "
            "in this environment"
        )
    return Path(base) / rel_path


def ingest_source_from_corpus_lock(
    source_id: str,
    corpus_lock: Mapping[str, Any],
    *,
    raw_root: Optional[Path] = None,
) -> List[GovernedChunk]:
    """
    Ingest one ``official_raw`` PDF source declared in ``corpus.lock.yaml``
    end to end: resolve its locator, verify its locked hash, and chunk it.
    """
    source = corpus_lock.get("sources", {}).get(source_id)
    if not isinstance(source, dict):
        raise PdfIngestionError(f"unknown source_id (not in corpus.lock.yaml): {source_id!r}")
    document = source.get("document")
    revision = source.get("revision")
    if not document or not revision:
        raise PdfIngestionError(
            f"source {source_id!r} has no document/revision declared in corpus.lock.yaml "
            "-- cannot attribute ingested chunks to a citable document"
        )
    authority_level = ROLE_TO_AUTHORITY_LEVEL.get(source.get("role", ""))
    if authority_level is None:
        raise PdfIngestionError(
            f"source {source_id!r} has an unrecognized role {source.get('role')!r}; "
            "cannot derive an authority_level"
        )
    pdf_path = resolve_source_locator(source["source_locator"], raw_root=raw_root)
    return chunk_pdf(
        pdf_path,
        source_id=source_id,
        document=document,
        revision=revision,
        authority_level=authority_level,
        expected_sha256=source["content_sha256"],
    )


def load_accepted_chunks(
    source_ids: Sequence[str],
    corpus_lock: Mapping[str, Any],
    *,
    raw_root: Optional[Path] = None,
) -> List[GovernedChunk]:
    """
    Ingest every listed source and return only the chunks whose source is
    eligible as answer evidence -- the "retrieval can obtain accepted
    evidence" proof, without any ranking/embedding.
    """
    accepted: List[GovernedChunk] = []
    for source_id in source_ids:
        if not is_source_eligible_as_answer_evidence(source_id, corpus_lock):
            continue
        accepted.extend(ingest_source_from_corpus_lock(source_id, corpus_lock, raw_root=raw_root))
    return accepted


def search_chunks(chunks: Sequence[GovernedChunk], query: str) -> List[GovernedChunk]:
    """
    Minimal, deliberately non-ranking substring search over chunk content --
    proves accepted evidence is queryable without introducing embedding,
    reranking, or LLM synthesis in this PR.
    """
    needle = query.strip().lower()
    if not needle:
        return []
    return [chunk for chunk in chunks if needle in chunk.content.lower()]
