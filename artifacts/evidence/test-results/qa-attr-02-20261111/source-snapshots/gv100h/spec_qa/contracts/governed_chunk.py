"""
Governed Chunk contract for PDF-ingested Spec QA evidence.

This is the schema a raw-PDF ingestion pipeline must produce before its
content can ever become a ``Citation`` (``evidence_contract.py``). It exists
as its own module -- not bolted onto ``GovernedEvidence``
(``governed_retriever.py``) -- because a chunk has an obligation
``GovernedEvidence`` never had: every field must be *traceable back to a
real PDF location it was mechanically extracted from* (a real page number,
a self-consistent content hash), not hand-authored prose.

Design principle (mirrors ``evidence_contract.py``'s own layering rule):
this module is a pure schema/validation layer. It must not import from
``ingestion/`` or ``api/`` -- the ingestion pipeline depends on this
contract, not the other way around.
"""
import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from gv100h.spec_qa.contracts.evidence_contract import AuthorityLevel, Citation

ChunkKind = Literal["paragraph", "table", "heading_only"]

_CHUNK_ID_INDEX_SEGMENT = re.compile(r"^\d+$")


class GovernedChunkError(ValueError):
    """Raised when a GovernedChunk violates the Governed Chunk contract."""


class GovernedChunk(BaseModel):
    """
    A single deterministically-extracted unit of PDF text, plus enough
    provenance to become a normative ``Citation``.

    ``chunk_id``/``content_sha256`` are re-derived and cross-checked at
    validation time (not just trusted from caller input) so a chunk can
    never claim a hash that doesn't actually match its own ``content`` --
    fail-closed self-consistency, the same discipline
    ``evidence_contract.py``'s field validators apply to citation fields.
    """

    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    document: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    chapter: str = Field(min_length=1)
    section: str = Field(min_length=1)
    # A REAL PDF page (or page range), e.g. "p.482" -- never a fallback
    # reuse of ``section`` the way the hand-authored
    # ``GovernedEvidence``/``to_citation()`` path in ``governed_retriever.py``
    # currently does in the absence of any real PDF.
    page_or_anchor: str = Field(min_length=1)
    authority_level: AuthorityLevel
    chunk_kind: ChunkKind
    content: str = Field(min_length=1)
    content_sha256: str

    def __init__(self, **data):
        # See Citation.__init__ in evidence_contract.py for why this
        # re-raises as a plain GovernedChunkError instead of leaking
        # pydantic_core.ValidationError.
        try:
            super().__init__(**data)
        except ValidationError as exc:
            messages = "; ".join(error["msg"] for error in exc.errors())
            raise GovernedChunkError(messages) from exc

    @field_validator("content_sha256", mode="after")
    @classmethod
    def _content_sha256_shape(cls, value: str) -> str:
        if len(value) != 64 or not all(c in "0123456789abcdef" for c in value.lower()):
            raise ValueError("content_sha256 must be a 64-character lowercase hex sha256 digest")
        return value.lower()

    @model_validator(mode="after")
    def _content_sha256_matches_content(self) -> "GovernedChunk":
        expected = hashlib.sha256(self.content.encode("utf-8")).hexdigest()
        if self.content_sha256 != expected:
            raise GovernedChunkError(
                f"content_sha256 {self.content_sha256!r} does not match sha256(content) {expected!r} "
                "-- a chunk's declared hash must always match its own content"
            )
        return self

    @field_validator("content", mode="after")
    @classmethod
    def _content_must_not_be_whitespace_only(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content must not be blank or whitespace-only")
        return value

    @model_validator(mode="after")
    def _chapter_matches_section(self) -> "GovernedChunk":
        if self.chapter != self._derive_chapter(self.section):
            raise GovernedChunkError(
                f"chapter {self.chapter!r} does not match the leading numeric segment of "
                f"section {self.section!r}"
            )
        return self

    @model_validator(mode="after")
    def _chunk_id_matches_derived_identity(self) -> "GovernedChunk":
        """
        ``chunk_id`` is part of a chunk's evidence identity, not just an
        opaque label -- a citation's ``evidence_id`` (``to_citation()``
        below) is only as trustworthy as the ``chunk_id`` it echoes. Recompute
        it from the complete provenance tuple so a change to document,
        revision, authority, or any other identity field cannot retain the
        same evidence ID.
        """
        prefix = f"{self.source_id}:{self.section}:{self.page_or_anchor}:"
        if not self.chunk_id.startswith(prefix):
            raise GovernedChunkError(
                f"chunk_id {self.chunk_id!r} is not derived from this chunk's own "
                "source_id/section/page_or_anchor/content_sha256 "
                f"(expected {prefix}<index>:<full-provenance-digest>)"
            )
        index_segment, separator, _digest = self.chunk_id[len(prefix) :].partition(":")
        if not separator or not _CHUNK_ID_INDEX_SEGMENT.match(index_segment):
            raise GovernedChunkError(
                f"chunk_id {self.chunk_id!r} index segment {index_segment!r} is not a "
                "non-negative integer"
            )
        expected = self._derive_chunk_id(
            source_id=self.source_id,
            document=self.document,
            revision=self.revision,
            chapter=self.chapter,
            section=self.section,
            page_or_anchor=self.page_or_anchor,
            authority_level=self.authority_level,
            chunk_kind=self.chunk_kind,
            content_sha256=self.content_sha256,
            index=int(index_segment),
        )
        if self.chunk_id != expected:
            raise GovernedChunkError(
                f"chunk_id {self.chunk_id!r} is not derived from this chunk's own "
                "complete provenance (document/revision/authority and all "
                f"identity fields); expected {expected!r}"
            )
        return self

    @staticmethod
    def _derive_chunk_id(
        *,
        source_id: str,
        document: str,
        revision: str,
        chapter: str,
        section: str,
        page_or_anchor: str,
        authority_level: AuthorityLevel,
        chunk_kind: ChunkKind,
        content_sha256: str,
        index: int,
    ) -> str:
        identity = json.dumps(
            {
                "authority_level": authority_level,
                "chapter": chapter,
                "chunk_kind": chunk_kind,
                "content_sha256": content_sha256,
                "document": document,
                "index": index,
                "page_or_anchor": page_or_anchor,
                "revision": revision,
                "section": section,
                "source_id": source_id,
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        provenance_digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        return f"{source_id}:{section}:{page_or_anchor}:{index}:{provenance_digest}"

    @staticmethod
    def _derive_chapter(section: str) -> str:
        chapter = section.split(".")[0].strip()
        if not chapter or not chapter.isdigit():
            raise GovernedChunkError(
                f"section {section!r} does not start with a numeric chapter segment; "
                "cannot derive a chunk chapter"
            )
        return chapter

    @classmethod
    def build(
        cls,
        *,
        source_id: str,
        document: str,
        revision: str,
        section: str,
        page_or_anchor: str,
        authority_level: AuthorityLevel,
        chunk_kind: ChunkKind,
        content: str,
        index: int,
    ) -> "GovernedChunk":
        """
        Deterministic constructor: derives ``chapter``/``content_sha256``/
        ``chunk_id`` from the other fields instead of trusting caller-supplied
        values for them, so the same PDF ingested twice always produces
        byte-identical chunks (including their IDs).
        """
        chapter = cls._derive_chapter(section)
        content_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
        chunk_id = cls._derive_chunk_id(
            source_id=source_id,
            document=document,
            revision=revision,
            chapter=chapter,
            section=section,
            page_or_anchor=page_or_anchor,
            authority_level=authority_level,
            chunk_kind=chunk_kind,
            content_sha256=content_sha256,
            index=index,
        )
        return cls(
            chunk_id=chunk_id,
            source_id=source_id,
            document=document,
            revision=revision,
            chapter=chapter,
            section=section,
            page_or_anchor=page_or_anchor,
            authority_level=authority_level,
            chunk_kind=chunk_kind,
            content=content,
            content_sha256=content_sha256,
        )

    def to_citation(self, *, excerpt_max_len: int = 240) -> Citation:
        """
        Resolve this chunk into a normative ``Citation``
        (``evidence_contract.py``). This is the concrete proof that a real,
        PDF-derived ``GovernedChunk`` is shape-compatible with the same
        Answer and Evidence Contract ``GovernedQAService`` already enforces
        for hand-authored ``GovernedEvidence`` -- without this PR wiring the
        chunk into the live ``EVIDENCE_REGISTRY``/``qa_service.py`` answer
        path (that live cutover is separate, later, integration work).
        """
        excerpt = self.content
        if excerpt_max_len:
            excerpt = excerpt[:excerpt_max_len].rstrip()
        return Citation(
            evidence_id=self.chunk_id,
            document=self.document,
            revision=self.revision,
            chapter=self.chapter,
            section=self.section,
            page_or_anchor=self.page_or_anchor,
            authority_level=self.authority_level,
            excerpt=excerpt,
            citation_kind="normative",
        )
