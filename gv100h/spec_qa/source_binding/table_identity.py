"""Pure candidate application checks against caller-supplied authoritative chunks.

The caller must bind trusted_chunks to its locked corpus receipt. Sent evidence
is compared to that independent snapshot; it is never promoted to the snapshot.
No question, Gold, answer vocabulary, retrieval or neighbor substitution.
"""
from collections.abc import Mapping
import re

from jsonschema import Draft202012Validator

from gv100h.spec_qa.contracts.governed_chunk import GovernedChunk
from gv100h.spec_qa.contracts.table_identity import table_identity_schema
from gv100h.spec_qa.retrieval.table_family_pack import table_caption_lines, table_families


def resolve_exact_evidence(citation_ids, *, sent_evidence, trusted_chunks):
    """Resolve exact IDs/content/provenance, with no same-page/hash fallback."""
    if not isinstance(sent_evidence, (list, tuple)) or not isinstance(trusted_chunks, (list, tuple)):
        raise ValueError("source unconfirmed: sent evidence and trusted snapshot lists required")
    if (not isinstance(citation_ids, (list, tuple)) or not citation_ids
            or any(not isinstance(cid, str) or not cid.strip() for cid in citation_ids)
            or len(citation_ids) != len(set(citation_ids))):
        raise ValueError("source unconfirmed: missing or duplicate citation IDs")
    trusted = {}
    for item in trusted_chunks:
        if not isinstance(item, (GovernedChunk, Mapping)):
            raise ValueError("source unconfirmed: malformed trusted record")
        data = item.model_dump() if isinstance(item, GovernedChunk) else dict(item)
        chunk = GovernedChunk.model_validate(data)
        if chunk.chunk_id in trusted:
            raise ValueError("source unconfirmed: ambiguous duplicate trusted identity")
        if any(not getattr(chunk, key).strip() for key in ("source_id", "revision", "document", "section", "page_or_anchor")):
            raise ValueError("source unconfirmed: incomplete trusted metadata")
        trusted[chunk.chunk_id] = chunk
    sent = {}
    for item in sent_evidence:
        if not isinstance(item, Mapping) or not isinstance(item.get("chunk_id"), str):
            raise ValueError("source unconfirmed: missing sent chunk identity")
        if item["chunk_id"] in sent:
            raise ValueError("source unconfirmed: ambiguous duplicate sent identity")
        sent[item["chunk_id"]] = item
    resolved = {}
    for cid in citation_ids:
        if cid not in sent or cid not in trusted:
            raise ValueError("source unconfirmed: citation is absent from sent evidence or trusted snapshot")
        chunk = trusted[cid]
        if any(sent[cid].get(key) != value for key, value in chunk.model_dump().items()):
            raise ValueError("source unconfirmed: exact content/hash/provenance differs from trusted snapshot")
        resolved[cid] = chunk
    return resolved


def bind_table_location(value, citation_ids, *, sent_evidence, trusted_chunks):
    """Bind an explicit table identity/location; does not judge any question answer."""
    if not isinstance(value, Mapping) or not isinstance(citation_ids, (list, tuple)):
        raise ValueError("source unconfirmed: location and explicit caption IDs required")
    identity = value.get("table")
    if list(Draft202012Validator(table_identity_schema()).iter_errors(identity)):
        raise ValueError("source unconfirmed: malformed table identity")
    if len(citation_ids) != 1:
        raise ValueError("source unconfirmed: one explicit caption citation required")
    resolved = resolve_exact_evidence(citation_ids, sent_evidence=sent_evidence, trusted_chunks=trusted_chunks)
    chunk = resolved[citation_ids[0]]
    families, membership = table_families([chunk])
    captions = table_caption_lines(chunk.content)
    if chunk.chunk_id not in membership or len(captions) != 1 or len(families) != 1:
        raise ValueError("source unconfirmed: unresolved or ambiguous caption")
    _, number, line = captions[0]
    observed = {"source_id": chunk.source_id, "revision": chunk.revision, "number": number}
    if identity != observed:
        raise ValueError("source unconfirmed: source/revision/table number does not match cited caption")
    continued = bool(re.search(r"\(continued\)\s*$", line, re.IGNORECASE))
    if (type(value.get("continuation")) is not bool or value["continuation"] != continued
            or value.get("section") != chunk.section or value.get("page") != chunk.page_or_anchor):
        raise ValueError("source unconfirmed: continuation/section/page differs from cited source")
    return {"status": "PASS", "table": observed, "citation_id": chunk.chunk_id,
            "content_sha256": chunk.content_sha256, "source_text": chunk.content,
            "section": chunk.section, "page": chunk.page_or_anchor, "continuation": continued}
