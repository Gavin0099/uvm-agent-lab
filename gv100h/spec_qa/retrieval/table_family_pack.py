"""Opt-in table-family packing; immutable chunks, unchanged BM25 scores.

Selection consumes corpus structure and ranked hits only. It has no question,
query, Gold, page targeting, model, filesystem or answer-value input.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict

from gv100h.spec_qa.retrieval.real_corpus_retriever import GovernedChunkRetrievalHit

# Supported source layout: numbered label, period delimiter, non-empty title.
# A leading "Table N gives/describes ..." is a reference, not a caption.
_CAPTION = re.compile(r"^\s*Table\s+(\d+(?:[-.]\d+)*)\.\s+\S.*$", re.IGNORECASE)
_UNRESOLVED_LABEL = re.compile(
    r"^\s*Table\s+\d+(?:[-.]\d+)*(?:\s*$|[.:]\s*.*$|\s+[-–—]\s*.*$)",
    re.IGNORECASE,
)


def table_caption_lines(content):
    """Return (one-based line, table number, original line) for supported captions."""
    return [(i, m.group(1), line) for i, line in enumerate(content.splitlines(), 1)
            if (m := _CAPTION.match(line))]


def evidence_size(records):
    """Characters occupied by EVIDENCE at the original prompt's indentation."""
    return len(json.dumps({"EVIDENCE": records}, ensure_ascii=False, indent=2))


def table_families(chunks):
    """Associate single-caption and table chunks, bounded by source and section."""
    families = defaultdict(list)
    membership = {}
    scope = active = None
    ids = [c.chunk_id for c in chunks]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate corpus chunk identity")
    for chunk in chunks:
        current = (chunk.source_id, chunk.revision, chunk.section)
        if current != scope:
            scope, active = current, None
        captions = [number for _, number, _ in table_caption_lines(chunk.content)]
        unclear = any(_UNRESOLVED_LABEL.match(line) and not _CAPTION.match(line)
                      for line in chunk.content.splitlines())
        if len(captions) == 1 and not unclear:
            active = (*scope, captions[0])
        elif captions or unclear or chunk.chunk_kind == "heading_only":
            active = None
        if active is not None and (len(captions) == 1 or chunk.chunk_kind == "table"):
            families[active].append(chunk)
            membership[chunk.chunk_id] = active
    return dict(families), membership


def pack_table_families(chunks, ranked_hits, *, max_chars, max_chunks=20):
    """Add whole table families after seeds, within both fixed evidence ceilings.

    Oversized groups fall back to the seed; no partial family cherry-picking.
    Baseline seeds are the first max_chunks BM25 hits. The reported rank is
    final packet position, while scores and known original rank remain in the trace.
    BM25 hits may fall back to their explicit retrieval_rank; a reference hit
    without original rank stays unknown. Candidate order never supplies it.
    """
    if type(max_chunks) is not int or max_chunks <= 0 or type(max_chars) is not int or max_chars < evidence_size([]):
        raise ValueError("invalid evidence budget")
    chunks, ranked_hits = tuple(chunks), tuple(ranked_hits)
    by_id = {c.chunk_id: c for c in chunks}
    families, membership = table_families(chunks)
    hit_by_id = {}
    ranks = {}
    candidate_positions = {}
    for rank, hit in enumerate(ranked_hits, 1):
        cid = hit.chunk.chunk_id
        if cid in hit_by_id or cid not in by_id or hit.chunk != by_id[cid]:
            raise ValueError("ranked hit is duplicate or outside immutable corpus")
        hit_by_id[cid] = hit
        ranks[cid] = hit.original_bm25_rank
        if ranks[cid] is None and hit.retrieval_origin == "bm25":
            ranks[cid] = hit.retrieval_rank
        candidate_positions[cid] = rank
    selected, seen, events = [], set(), []

    def records(group):
        result = list(selected)
        for chunk in group:
            hit = hit_by_id.get(chunk.chunk_id, GovernedChunkRetrievalHit(chunk, 0.0, ()))
            result.append(dict(hit.as_record(), rank=len(result) + 1))
        return result

    def fits(candidate):
        return len(candidate) <= max_chunks and evidence_size(candidate) <= max_chars

    for seed in ranked_hits[:max_chunks]:
        cid = seed.chunk.chunk_id
        if cid in seen:
            continue
        family = membership.get(cid)
        group = [seed.chunk] + [c for c in families.get(family, ())
                              if c.chunk_id != cid and c.chunk_id not in seen]
        candidate = records(group)
        expanded = len(group) > 1 and fits(candidate)
        if not fits(candidate):
            group = [seed.chunk]
            candidate = records(group)
        accepted = fits(candidate)
        events.append({"seed_id": cid, "seed_bm25_rank": ranks[cid],
                       "seed_candidate_position": candidate_positions[cid],
                       "family_key": list(family) if family else None,
                       "expanded": expanded, "accepted": accepted,
                       "added_ids": [c.chunk_id for c in group] if accepted else []})
        if accepted:
            selected = candidate
            seen.update(c.chunk_id for c in group)
    return {"evidence": selected, "events": events,
            "selected_bm25_ranks": [ranks.get(r["chunk_id"]) for r in selected],
            "budget": {"max_chunks": max_chunks, "used_chunks": len(selected),
                       "max_chars": max_chars, "used_chars": evidence_size(selected)}}
