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
from typing import Any, FrozenSet, List, Mapping, Optional, Sequence, Tuple

import pdfplumber

from gv100h.spec_qa.contracts.corpus_source_resolver import resolve_contained_path
from gv100h.spec_qa.contracts.evidence_contract import AuthorityLevel
from gv100h.spec_qa.contracts.governed_chunk import GovernedChunk

# A heading line: one or more dot-separated digit groups, then whitespace,
# then a nonempty title -- e.g. "10.16.2.1 Hub Class Feature Selectors".
_HEADING_PATTERN = re.compile(r"^(?P<section>\d+(?:\.\d+)*)\s+(?P<title>\S.*)$")
_SECTION_HEADING_LEFT_EDGE = 95.0
_NUMERIC_ONLY_TITLE_PATTERN = re.compile(r"^[\d\s.+\-/():–—]+$")
_MEASUREMENT_ONLY_TITLE_PATTERN = re.compile(
    r"^(?:[+-]?\d+(?:\.\d+)?\s*)?"
    r"(?:ohms?|Ω|volts?|mv|uv|ma|ua|mhz|khz|ns|us|ms|ps|bits?)$",
    re.IGNORECASE,
)
_BIT_FIELD_LABEL_PATTERN = re.compile(r"^\d+(?:\s*:\s*\d+)?(?:\s|$)")


class _PageLine(str):
    """Text event carrying an internal PDF style classification."""

    def __new__(cls, text: str, *, is_heading: bool) -> "_PageLine":
        value = str.__new__(cls, text)
        value.is_heading = is_heading
        return value


def _looks_like_section_heading(line: Mapping[str, Any], text: str) -> bool:
    """Require heading-like PDF typography for numeric section candidates.

    The locked USB specification headings start at the document text margin
    (roughly x=72--90), while diagram/table labels and bit-field rows are
    indented into the figure/table area. Typography is still required for
    lines with PDF character metadata, but it is not sufficient on its own:
    numeric-only, measurement-only, and bit-field labels must not mutate the
    section state even when a PDF happens to render them bold or large. A
    line without character metadata remains accepted for the lightweight fake
    pages used by callers/tests.
    """
    heading_match = _HEADING_PATTERN.match(text)
    if not heading_match:
        return False
    title = heading_match.group("title").strip()
    if (
        _NUMERIC_ONLY_TITLE_PATTERN.fullmatch(title)
        or _MEASUREMENT_ONLY_TITLE_PATTERN.fullmatch(title)
        or _BIT_FIELD_LABEL_PATTERN.match(title)
    ):
        return False
    chars = line.get("chars")
    if not chars:
        return True
    x0 = line.get("x0")
    if x0 is None:
        positions = [char.get("x0") for char in chars if char.get("x0") is not None]
        x0 = min(positions) if positions else None
    if x0 is not None and float(x0) > _SECTION_HEADING_LEFT_EDGE:
        return False
    font_names = {
        str(char.get("fontname", ""))
        for char in chars
        if char.get("fontname")
    }
    if any(
        re.search(r"bold|black|heavy|semibold|demi", font, re.IGNORECASE)
        for font in font_names
    ):
        return True
    sizes = [
        float(char["size"])
        for char in chars
        if char.get("size") is not None
    ]
    return bool(sizes) and max(sizes) >= 11.0

# corpus.lock.yaml `included_chapters` entries are either a bare chapter
# number ("6") or an inclusive range ("8-11").
_CHAPTER_RANGE_PATTERN = re.compile(r"^(?P<start>\d+)-(?P<end>\d+)$")

_PAGE_EDGE_TOLERANCE = 65.0
_TOC_ENTRY_PATTERN = re.compile(
    r"^\d+(?:\.\d+)*\s+\S.*\.{3,}\s*(?:\d+|[ivxlcdm]+)\s*$",
    re.IGNORECASE,
)
_PAGE_FURNITURE_PATTERNS = (
    re.compile(r"^Revision\s+.+Universal Serial Bus", re.IGNORECASE),
    re.compile(r"^June\s+\d{4}\s+Specification$", re.IGNORECASE),
    re.compile(r"^Universal Serial Bus Specification Revision\b", re.IGNORECASE),
    re.compile(r"^Copyright\b", re.IGNORECASE),
    re.compile(r"^SS Hub.*Compliance", re.IGNORECASE),
    re.compile(r"^Preface\s+\d{2}/\d{2}/\d{4}$", re.IGNORECASE),
    re.compile(r"^\d{2}/\d{2}/\d{4}$"),
)

# A source's PDF-ingestible locator scheme. Kept as its own check (not
# folded into ``is_source_eligible_as_answer_evidence``) because
# "eligible as answer evidence" and "is a PDF this pipeline can ingest" are
# two different questions -- e.g. ``hub_reference`` is eligible answer
# evidence (layer=governed_reference) but its locator is
# ``repo://Gavin0099/usb-if-hub-spec-reference@...``, not a PDF this module
# understands.
_PDF_LOCATOR_PATTERN = re.compile(r"^env://[^/]+/.+")


def parse_included_chapters(entries: Sequence[Any]) -> FrozenSet[str]:
    """
    Expand a ``corpus.lock.yaml`` ``included_chapters`` list (bare chapter
    numbers and/or ``"start-end"`` inclusive ranges, e.g. ``["5", "8-11"]``)
    into the flat set of permitted chapter strings.
    """
    chapters: set = set()
    for raw_entry in entries:
        entry = str(raw_entry).strip()
        range_match = _CHAPTER_RANGE_PATTERN.match(entry)
        if range_match:
            start, end = int(range_match.group("start")), int(range_match.group("end"))
            if start > end:
                raise PdfIngestionError(f"invalid included_chapters range: {entry!r}")
            chapters.update(str(n) for n in range(start, end + 1))
        elif entry.isdigit():
            chapters.add(entry)
        else:
            raise PdfIngestionError(f"unrecognized included_chapters entry: {entry!r}")
    return frozenset(chapters)


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
        top = line.get("top")
        bottom = line.get("bottom")
        if not text or top is None or bottom is None:
            continue
        if _within_any_table(top):
            continue
        if _is_page_furniture(text, top=top, bottom=bottom, page_height=page.height):
            continue
        if _TOC_ENTRY_PATTERN.match(text):
            continue
        events.append(
            (
                top,
                "line",
                _PageLine(
                    text,
                    is_heading=_looks_like_section_heading(line, text),
                ),
            )
        )
    for table in tables:
        rows = table.extract()
        if rows:
            events.append((table.bbox[1], "table", rows))
    events.sort(key=lambda event: event[0])
    return events


def _is_page_furniture(
    text: str,
    *,
    top: float,
    bottom: float,
    page_height: float,
) -> bool:
    """Identifies fixed USB-spec page headers/footers without removing
    ordinary body text that happens to contain the same words away from the
    page edges."""
    at_top = top <= _PAGE_EDGE_TOLERANCE
    at_bottom = bottom >= page_height - _PAGE_EDGE_TOLERANCE
    if not (at_top or at_bottom):
        return False
    if at_bottom and re.fullmatch(r"(?:\d+|[ivxlcdm]+)", text, re.IGNORECASE):
        return True
    return any(pattern.match(text) for pattern in _PAGE_FURNITURE_PATTERNS)


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
    included_chapters: Optional[Sequence[Any]] = None,
) -> List[GovernedChunk]:
    """
    Ingest one PDF into an ordered list of ``GovernedChunk`` records.

    Fails closed (raises ``PdfIngestionError``) rather than returning a
    partial/empty result when the hash check fails or zero chunks were
    produced -- an ingestion pipeline that silently returns nothing looks
    identical to "the PDF has no content", which is a much more dangerous
    failure mode than a loud error.

    ``included_chapters`` (``corpus.lock.yaml``'s Phase-1 chapter allowlist
    for this source, e.g. ``["6", "7", "9", "10"]``) is enforced HERE, not as
    a post-hoc filter: a section outside the allowlist never becomes a
    ``GovernedChunk`` at all -- being a locked/hash-verified source only
    proves the PDF wasn't swapped, it is not itself authorization to cite
    every chapter in that PDF as Phase-1 evidence. ``None`` (the default)
    means "no chapter restriction declared for this source", not "all
    chapters pre-approved" -- callers reading from ``corpus.lock.yaml``
    should always pass the source's own ``included_chapters`` value.
    """
    verify_source_hash(pdf_path, expected_sha256)
    allowed_chapters = (
        parse_included_chapters(included_chapters) if included_chapters is not None else None
    )

    chunks: List[GovernedChunk] = []
    current_section: Optional[str] = None
    index = 0

    def _chapter_allowed(section: str) -> bool:
        if allowed_chapters is None:
            return True
        return section.split(".", 1)[0].strip() in allowed_chapters

    def _emit(section: str, page_or_anchor: str, chunk_kind: str, content: str) -> None:
        nonlocal index
        if not _chapter_allowed(section):
            return
        chunks.append(
            GovernedChunk.build(
                source_id=source_id,
                document=document,
                revision=revision,
                section=section,
                page_or_anchor=page_or_anchor,
                authority_level=authority_level,
                chunk_kind=chunk_kind,
                content=content,
                index=index,
            )
        )
        index += 1

    def _flush_paragraph(buffer: List[str], page_or_anchor: str) -> None:
        if not buffer or current_section is None:
            return
        _emit(current_section, page_or_anchor, "paragraph", "\n".join(buffer))

    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            page_or_anchor = f"p.{page_number}"
            paragraph_buffer: List[str] = []
            for _, kind, payload in _page_events(page):
                if kind == "line":
                    heading_match = _HEADING_PATTERN.match(payload)
                    if heading_match and getattr(payload, "is_heading", True):
                        _flush_paragraph(paragraph_buffer, page_or_anchor)
                        paragraph_buffer = []
                        current_section = heading_match.group("section")
                        _emit(current_section, page_or_anchor, "heading_only", payload)
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
                    table_content = _serialize_table(payload)
                    if table_content.strip():
                        _emit(current_section, page_or_anchor, "table", table_content)
            _flush_paragraph(paragraph_buffer, page_or_anchor)

    if not chunks:
        reason = (
            "no recognizable section heading found"
            if allowed_chapters is None
            else f"no section matched included_chapters={sorted(allowed_chapters)}"
        )
        raise PdfIngestionError(f"{pdf_path} produced zero governed chunks ({reason})")
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


def is_official_raw_pdf_source(source_id: str, corpus_lock: Mapping[str, Any]) -> bool:
    """
    True only for sources this PDF ingestion pipeline can actually ingest:
    ``layer == "official_raw"`` AND a supported ``env://`` PDF locator.

    Deliberately separate from ``is_source_eligible_as_answer_evidence`` --
    a source can be legitimate answer evidence without being a PDF this
    module understands (e.g. ``hub_reference`` is
    ``layer=governed_reference`` with a ``repo://...`` locator, not a PDF).
    "eligible as answer evidence" and "ingestible as a PDF" are two
    different questions; conflating them would let this pipeline attempt to
    hash/open a non-PDF source as if it were one.
    """
    source = corpus_lock.get("sources", {}).get(source_id, {})
    if source.get("layer") != "official_raw":
        return False
    return bool(_PDF_LOCATOR_PATTERN.match(str(source.get("source_locator", ""))))


def resolve_source_locator(source_locator: str, *, raw_root: Optional[Path] = None) -> Path:
    """
    Resolve a corpus.lock.yaml ``source_locator`` of the form
    ``env://VARNAME/relative/path`` to a real filesystem path, using either
    an explicit ``raw_root`` override or the ``VARNAME`` environment
    variable. Fails closed (raises) rather than silently skipping a source
    whose raw PDF isn't available in the current environment.

    The resolved path is required to stay contained under its root (rejects
    ``..`` traversal, an absolute relative-path segment, or a symlink that
    escapes the root) via the same ``resolve_contained_path`` primitive
    ``CorpusSourceResolver`` uses -- this is the same raw-corpus trust
    boundary in both places, enforced once instead of twice.
    """
    import os

    match = re.fullmatch(r"env://(?P<var>[^/]+)/(?P<rel>.+)", source_locator)
    if not match:
        raise PdfIngestionError(f"unsupported source_locator format: {source_locator!r}")
    rel_path = match.group("rel")
    if raw_root is not None:
        root = Path(raw_root)
    else:
        var_name = match.group("var")
        base = os.environ.get(var_name)
        if not base:
            raise PdfIngestionError(
                f"source_locator {source_locator!r} requires environment variable "
                f"{var_name!r}, which is not set -- the raw PDF corpus is not bound "
                "in this environment"
            )
        root = Path(base)
    try:
        return resolve_contained_path(root, rel_path)
    except ValueError as exc:
        raise PdfIngestionError(f"source_locator {source_locator!r}: {exc}") from None


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
    if not is_source_eligible_as_answer_evidence(source_id, corpus_lock):
        raise PdfIngestionError(
            f"source {source_id!r} is not eligible as Phase-1 answer evidence"
        )
    if not is_official_raw_pdf_source(source_id, corpus_lock):
        raise PdfIngestionError(
            f"source {source_id!r} is not an official_raw env:// PDF source"
        )
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
        included_chapters=source.get("included_chapters"),
    )


def load_accepted_chunks(
    source_ids: Sequence[str],
    corpus_lock: Mapping[str, Any],
    *,
    raw_root: Optional[Path] = None,
) -> List[GovernedChunk]:
    """
    Ingest every listed source and return only the chunks whose source is
    both eligible as answer evidence AND an ``official_raw`` PDF this
    pipeline can actually ingest -- the "retrieval can obtain accepted
    evidence" proof, without any ranking/embedding. A legitimate but
    non-PDF answer-evidence source (e.g. ``hub_reference``) is skipped here
    rather than attempted and failing on its unsupported locator scheme.
    """
    accepted: List[GovernedChunk] = []
    for source_id in source_ids:
        if not is_source_eligible_as_answer_evidence(source_id, corpus_lock):
            continue
        if not is_official_raw_pdf_source(source_id, corpus_lock):
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
