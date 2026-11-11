"""Lexical free-question retrieval with room for explanatory source paragraphs.

This consumes only question text, public vocabulary and an eligible immutable
corpus. Identifier decomposition supplies search terms, never answer values or
an intent plan. Source scope remains the adapter's responsibility.
"""
from __future__ import annotations

import re

from gv100h.spec_qa.retrieval.real_corpus_retriever import GovernedChunkRetrievalHit
from gv100h.spec_qa.retrieval.table_family_pack import pack_table_families, table_caption_lines


# General terminology from the earlier offline lexical comparison. Ambiguous
# words deliberately retrieve alternatives; they do not decide a cause/state.
EXTRA_TERMS = {
    "主機": "host", "設備": "device", "連接埠": "port",
    "頻寬": "bandwidth", "帶寬": "bandwidth",
    "延遲": "latency", "保證": "guarantee guaranteed",
    "省電": "power suspend", "低功耗": "power suspend",
    "喚醒": "wakeup resume", "恢復": "resume",
    "重試": "retry retries", "重傳": "retry retransmission",
    "斷線": "disconnect disconnection", "斷開": "disconnect disconnection",
    "拔除": "detach detachment", "重新連線": "reconnect connection",
    "重連": "reconnect connection", "插上": "attach attachment",
    "接上": "connect connection", "連接": "connect connection",
    "連線": "connect connection", "錯誤": "error errors",
    "失敗": "error failure", "異常": "error failure",
    "停止": "stop termination", "終止": "termination",
    "辨識": "enumeration identification", "識別": "identification",
    "裝置資訊": "device descriptor", "設備資訊": "device descriptor",
    "讀取": "read request", "關掉": "disable power",
    "關閉": "disable", "停用": "disable disabled",
    "通知": "notification report", "通報": "report reporting",
    "下游": "downstream", "上游": "upstream", "電源": "power",
    "非同步": "asynchronous",
}
_ASCII_TERM = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:[.-][A-Za-z0-9_]+)*|\d+(?:\.\d+)+")
_CAMEL_PART = re.compile(r"[A-Z]+(?=[A-Z][a-z]|[^A-Za-z]|$)|[A-Z]?[a-z]+|\d+")
_SCOPE_LABEL = re.compile(r"(?<![A-Za-z0-9_])usb\s*2(?:\.0)?(?![\d.])", re.I)
_STOP_WORDS = frozenset("""
    a an and are as at be been by can could did do does for from had has have
    how i if in into is it its may me of on or please should than that the their
    them these they this those to us was were what when where which who why will
    with would you your usb specification spec
""".split())


def _lexical_terms(question, vocabulary):
    """Separate ASCII identifiers and translate longest non-overlapping aliases.

    The earlier spelling-preflight candidate established the CJK/ASCII boundary
    failure; extracting ASCII spans here also handles punctuation and keeps the
    caller's original question unchanged. No spelling correction is attempted.
    """
    if not isinstance(question, str) or not question.strip():
        raise ValueError("nonempty question required")
    aliases = {**EXTRA_TERMS, **vocabulary}
    spans = [(match.start(), match.end(), alias, english)
             for alias, english in aliases.items()
             for match in re.finditer(re.escape(alias), question)]
    occupied, translations = set(), []
    for start, end, alias, english in sorted(spans, key=lambda row: (-(row[1] - row[0]), row[0], row[2])):
        positions = set(range(start, end))
        if not positions.intersection(occupied):
            occupied.update(positions)
            translations.append((start, english))
    # Protocol/version labels are metadata shared by all eligible chunks and
    # must not manufacture positive hits for otherwise unknown questions.
    text = _SCOPE_LABEL.sub(" ", question)
    text += " " + " ".join(english for _, english in sorted(translations))
    return [word for word in _ASCII_TERM.findall(text)
            if len(word) > 1 and word.casefold() not in _STOP_WORDS]


def search_query(question, vocabulary):
    """Return a source-independent lexical query, retaining named identifiers."""
    return " ".join(dict.fromkeys(word.casefold() for word in _lexical_terms(question, vocabulary)))


def context_query(question, vocabulary):
    """Expose words inside identifiers so definitions can compete with tables."""
    words = []
    for word in _lexical_terms(question, vocabulary):
        parts = _CAMEL_PART.findall(word.replace("_", " ").replace("-", " "))
        # A short lowercase prefix followed by a capitalized name is an
        # identifier prefix (bLength, wValue, bmAttributes), not a topic.
        if len(parts) > 1 and len(parts[0]) <= 2 and parts[0].islower() and any(c.isupper() for c in word):
            parts = parts[1:]
        if not parts or (len(parts) == 1 and parts[0] == word):
            parts = [word]
        words.extend({"max": "maximum", "min": "minimum"}.get(part.casefold(), part.casefold()) for part in parts
                     if len(part) > 1 and part.casefold() not in _STOP_WORDS)
    return " ".join(dict.fromkeys(words))


# Top primary-query hits whose section lead paragraph is offered as a seed.
SECTION_LEAD_SEED_RANKS = 10


def _section_key(chunk):
    return (chunk.source_id, chunk.revision, chunk.section)


def _section_leads(chunks):
    """Map each section to the paragraph that directly follows its heading.

    Structural only: a heading_only chunk followed by a same-section paragraph
    that carries no table caption. Its text is the section's defining sentence
    and need not repeat any query term.
    """
    leads = {}
    for before, after in zip(chunks, chunks[1:]):
        if (before.chunk_kind == "heading_only" and after.chunk_kind == "paragraph"
                and _section_key(before) == _section_key(after)
                and after.content.strip() and not table_caption_lines(after.content)):
            leads.setdefault(_section_key(before), after)
    return leads


def retrieve_free_question(retriever, question, vocabulary, *, max_chars, max_chunks=20,
                           section_leads=False):
    """Reserve up to one fifth of the chunk budget for direct prose matches.

    Paragraph seeds precede family expansion, preventing high-scoring repeated
    field tables from consuming all evidence positions. Remaining seeds keep
    their original BM25 ordering and score; both query rankings are recorded.
    With section_leads, the lead paragraph of each section among the top
    primary hits is offered right after the prose seeds; the budget is unchanged.
    This is evidence coverage, not a sufficiency or answer-correctness gate.
    """
    query = search_query(question, vocabulary)
    prose_query = context_query(question, vocabulary)
    hits = retriever.query(query, top_k=len(retriever))
    context_hits = retriever.query(prose_query, top_k=len(retriever))
    by_id = {hit.chunk.chunk_id: hit for hit in hits}
    # Validation of budget values remains centralized in the existing packer.
    quota = max_chunks // 5 if type(max_chunks) is int and max_chunks > 0 else 0
    def paragraphs(ranked, terms):
        words = set(terms.split())
        found = []
        for rank, hit in enumerate(ranked, 1):
            chunk = hit.chunk
            content_terms = {word.casefold() for word in _ASCII_TERM.findall(chunk.content)}
            # Captions remain ordinary ranked seeds; allowing their family
            # expansion here could consume the slots reserved for prose.
            if (chunk.chunk_kind == "paragraph" and not table_caption_lines(chunk.content)
                    and len(chunk.content.split()) >= 12
                    and len(words.intersection(content_terms)) >= min(2, len(words))
                    and words):
                found.append((rank, hit))
        return found

    primary_paragraphs = paragraphs(hits, query)
    context_paragraphs = paragraphs(context_hits, prose_query)
    # Preserve prose about the exact identifiers alongside broader definitions.
    # Each list may donate unused positions when the other lacks direct matches.
    candidates = (context_paragraphs[:quota - quota // 2]
                  + primary_paragraphs[:quota // 2]
                  + context_paragraphs + primary_paragraphs)
    contexts, context_ids = [], set()
    for rank, hit in candidates:
        chunk = hit.chunk
        if chunk.chunk_id not in context_ids and len(contexts) < quota:
            contexts.append(by_id.get(chunk.chunk_id, hit))
            context_ids.add(chunk.chunk_id)
    context_ranks = {hit.chunk.chunk_id: rank for rank, hit in enumerate(context_hits, 1)
                     if hit.chunk.chunk_id in context_ids}
    top_ids = {hit.chunk.chunk_id for hit in hits[:SECTION_LEAD_SEED_RANKS]} if section_leads else set()
    lead_ids, lead_hits = set(), []
    if section_leads:
        leads = _section_leads(retriever.chunks)
        for hit in hits[:SECTION_LEAD_SEED_RANKS]:
            lead = leads.get(_section_key(hit.chunk))
            if lead is None or lead.chunk_id in context_ids or lead.chunk_id in top_ids or lead.chunk_id in lead_ids:
                continue
            lead_ids.add(lead.chunk_id)
            lead_hits.append(by_id.get(lead.chunk_id, GovernedChunkRetrievalHit(lead, 0.0, ())))
    # Lead paragraphs follow the top primary hits, so they never displace those hits.
    head = [hit for hit in hits if hit.chunk.chunk_id in top_ids and hit.chunk.chunk_id not in context_ids]
    skip_ids = context_ids | lead_ids | top_ids
    ordered = contexts + head + lead_hits + [hit for hit in hits if hit.chunk.chunk_id not in skip_ids]
    packet = pack_table_families(retriever.chunks, ordered, max_chars=max_chars, max_chunks=max_chunks)
    original_ranks = {hit.chunk.chunk_id: rank for rank, hit in enumerate(hits, 1)}
    # The shared packer's rank describes its input. Retain that separately and
    # expose true primary-query ranks so the coverage step stays auditable.
    packet["selected_seed_ranks"] = packet["selected_bm25_ranks"]
    packet["selected_bm25_ranks"] = [original_ranks.get(row["chunk_id"]) for row in packet["evidence"]]
    for event in packet["events"]:
        event["seed_selection_rank"] = event["seed_bm25_rank"]
        event["seed_bm25_rank"] = original_ranks.get(event["seed_id"])
    packet.update(retrieval_query=query, context_query=prose_query,
                  context_seed_ids=[hit.chunk.chunk_id for hit in contexts],
                  section_lead_ids=[hit.chunk.chunk_id for hit in lead_hits],
                  context_query_ranks=context_ranks,
                  retrieval_kind="lexical BM25 with paragraph coverage + table-family pack")
    return packet
