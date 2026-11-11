"""Candidate-only descriptor topic selection over unchanged BM25 hits.

Public descriptor names identify a topic, never an answer or source location.
Table membership and same-section prose come only from the owned corpus.
Structural retention is not semantic sufficiency or human review.
"""
import re
import unicodedata

from gv100h.spec_qa.operator_ui.free_question_retrieval import retrieve_free_question
from gv100h.spec_qa.retrieval.real_corpus_retriever import GovernedChunkRetrievalHit
from gv100h.spec_qa.retrieval.table_family_pack import pack_table_families, table_caption_lines, table_families
from .coverage import condition_candidates, coverage_trace


_TOPICS = {
    'device qualifier descriptor': ('裝置限定描述符', '裝置限定描述子'),
    'other speed configuration descriptor': ('其他速率組態描述符', '其他速率組態描述子'),
    'device descriptor': ('裝置描述符', '裝置描述子', '設備描述符'),
    'configuration descriptor': ('組態描述符', '組態描述子', '配置描述符'),
    'interface descriptor': ('介面描述符', '介面描述子'),
    'endpoint descriptor': ('端點描述符', '端點描述子'),
    'string descriptor': ('字串描述符', '字串描述子'),
    'hub descriptor': ('集線器描述符', '集線器描述子'),
}


def _topics(text):
    text = unicodedata.normalize('NFKC', text).casefold()
    text = ''.join('-' if unicodedata.category(c) == 'Pd' else c for c in text)
    spans = []
    for topic, aliases in _TOPICS.items():
        # ASCII boundaries protect identifiers; underscores are allowed only
        # between the words of a complete public descriptor name.
        pattern = r'(?<![a-z0-9_])' + r'[\s_-]+'.join(topic.split()) + r'(?![a-z0-9_])'
        spans.extend((m.start(), m.end(), topic) for m in re.finditer(pattern, text))
        for alias in aliases:
            spans.extend((m.start(), m.end(), topic) for m in re.finditer(re.escape(alias), text))
    occupied, found = set(), set()
    for start, end, topic in sorted(spans, key=lambda s: (-(s[1]-s[0]), s[0], s[2])):
        positions = set(range(start, end))
        if not occupied.intersection(positions):
            occupied.update(positions)
            found.add(topic)
    return sorted(found)


def _field_layout(members):
    """Recognize a descriptor layout, rather than a table about one field."""
    return any({'offset', 'field', 'size'} <= {
        cell.strip().casefold() for cell in line.split('|')}
        for c in members if c.chunk_kind == 'table' for line in c.content.splitlines())


def _local_structure(chunks, sections, legacy_families):
    """Supplement candidate structure; never rewrite the legacy family parser.

    A full caption may share a paragraph with a bare reference. Only the full
    caption can bind its immediately following table. Unknown local structure
    remains required/unresolved instead of silently vanishing from coverage.
    """
    scope = lambda c: (c.source_id, c.revision, c.section)
    recovered, required = {}, set()
    # Keep inherited table ownership; the new scan independently accounts for
    # every full caption, including captions rejected by the old parser.
    linked = {c.chunk_id for key, members in legacy_families.items() if key[:3] in sections
              for c in members if c.chunk_kind == 'table'}
    for i, chunk in enumerate(chunks):
        if scope(chunk) not in sections:
            continue
        captions = table_caption_lines(chunk.content)
        if chunk.chunk_kind == 'table' or captions:
            required.add(chunk.chunk_id)
        if chunk.chunk_kind != 'paragraph' or len(captions) != 1 or i+1 >= len(chunks):
            continue
        following = chunks[i+1]
        if (scope(following) != scope(chunk) or following.chunk_kind != 'table'
                or table_caption_lines(following.content)):
            continue
        key = (*scope(chunk), captions[0][1])
        members = recovered.setdefault(key, [])
        for member in (chunk, following):
            if member not in members:
                members.append(member)
            linked.add(member.chunk_id)
    return recovered, required, required - linked


def retrieve_candidates(retriever, question, vocabulary, *, max_chars, max_chunks=20):
    """Promote explicit descriptor structure before the existing fixed budget.

    Unnamed topics retain the old packet exactly. Multiple named types retain
    the baseline with an explicit unknown-completeness notice. No topic is
    guessed from an identifier, a generic descriptor query or description.
    """
    baseline = retrieve_free_question(retriever, question, vocabulary,
        max_chars=max_chars, max_chunks=max_chunks, section_leads=True)
    topics = _topics(question)
    if not topics:
        return baseline
    if len(topics) != 1:
        return {**baseline, 'topic_selection': {
            'topics': topics, 'status': 'MULTIPLE_TOPICS_NOT_ASSESSED',
            'structure_complete': False,
            'notice': '問題包含多種描述符，尚未確認各種類型的證據是否完整。'}}
    topic = topics[0]
    families, _ = table_families(retriever.chunks)
    matching = []
    for key, members in families.items():
        caption_topics = {name for c in members for _, _, line in table_caption_lines(c.content)
                          for name in _topics(line)}
        if caption_topics == {topic} and any(c.chunk_kind == 'table' for c in members):
            matching.append((key, members))
    if not matching:
        return {**baseline, 'topic_selection': {
            'topics': topics, 'status': 'NO_MATCHING_TABLE_FAMILY',
            'structure_complete': False,
            'notice': '目前未找到可確認屬於指定描述符的完整表族；候選證據完整性待確認。'}}

    primary = retriever.query(baseline['retrieval_query'], top_k=len(retriever))
    context = retriever.query(baseline['context_query'], top_k=len(retriever))
    ranks = {h.chunk.chunk_id: i for i, h in enumerate(primary, 1)}
    hit_by_id = {h.chunk.chunk_id: h for h in context}
    hit_by_id.update((h.chunk.chunk_id, h) for h in primary)
    rank_key = lambda entry: (min((ranks.get(c.chunk_id, len(retriever)+1)
                                  for c in entry[1]), default=len(retriever)+1), entry[0])
    # Field-layout families establish the primary section. A topic-named bit
    # table is useful supporting evidence, but must not expand a whole other
    # section or replace the descriptor's layout and its local restrictions.
    primary_families = [entry for entry in matching if _field_layout(entry[1])]
    if not primary_families:
        primary_families = list(matching)
    primary_keys = {key for key, _ in primary_families}
    primary_sections = {key[:3] for key in primary_keys}
    recovered, local_required, unresolved = _local_structure(
        retriever.chunks, primary_sections, families)
    # All records remain original owned chunks. The existing packer is not
    # given an invented family map: recovered members each become real seeds.
    for key, members in recovered.items():
        merged = list(families.get(key, ()))
        merged.extend(c for c in members if c not in merged)
        families[key] = merged
    primary_families = [(key, families[key]) for key, _ in primary_families]
    matching = [(key, families[key]) for key, _ in matching]
    local_families = []
    matched_keys = {key for key, _ in matching}
    for key, members in families.items():
        if key in matched_keys or key[:3] not in primary_sections:
            continue
        names = {name for c in members for _, _, line in table_caption_lines(c.content)
                 for name in _topics(line)}
        if not (names - {topic}) and any(c.chunk_kind == 'table' for c in members):
            local_families.append((key, members))
    supporting_families = [entry for entry in matching if entry[0] not in primary_keys]
    matching = (sorted(primary_families, key=rank_key)
                + sorted(local_families, key=rank_key)
                + sorted(supporting_families, key=rank_key))
    sections = {key[:3] for key, _ in matching}
    prose = [c for c in retriever.chunks
             if (c.source_id, c.revision, c.section) in sections
             and c.chunk_kind == 'paragraph' and not table_caption_lines(c.content)
             and c.content.strip()]
    required = {c.chunk_id for _, members in matching for c in members}
    required.update(c.chunk_id for c in prose)
    required.update(local_required)

    # A caption seed expands its whole family through the existing packer.
    # Supplemental prose without a lexical hit keeps score zero/rank None;
    # its provenance is the exact same source/revision/section, not a Gold ID.
    priority = [c for key, members in matching
                for c in (members if key in recovered else members[:1])] + prose
    priority.extend(c for c in retriever.chunks if c.chunk_id in local_required)
    ordered, seen = [], set()
    for c in priority:
        if c.chunk_id not in seen:
            ordered.append(hit_by_id.get(c.chunk_id, GovernedChunkRetrievalHit(c, 0.0, ())))
            seen.add(c.chunk_id)
    fields, wanted, conditions = condition_candidates(question, primary,
        source_keys={(key[0], key[1]) for key in primary_keys}, topic=topic, topics=_topics)
    for hit, _ in conditions:
        if hit.chunk.chunk_id not in seen:
            ordered.append(hit)
            seen.add(hit.chunk.chunk_id)
    for cid in baseline['context_seed_ids']:
        if cid not in seen:
            ordered.append(hit_by_id[cid])
            seen.add(cid)
    for h in primary:
        if h.chunk.chunk_id not in seen:
            ordered.append(h)
            seen.add(h.chunk.chunk_id)
    packed = pack_table_families(retriever.chunks, ordered,
        max_chars=max_chars, max_chunks=max_chunks)
    packed['selected_seed_ranks'] = packed['selected_bm25_ranks']
    packed['selected_bm25_ranks'] = [ranks.get(r['chunk_id']) for r in packed['evidence']]
    for event in packed['events']:
        event['seed_selection_rank'] = event['seed_bm25_rank']
        event['seed_bm25_rank'] = ranks.get(event['seed_id'])
    selected = {r['chunk_id'] for r in packed['evidence']}
    missing = sorted(required - selected)
    complete = not missing and not unresolved
    trace = {'topics': topics, 'status': 'SELECTED_STRUCTURE' if complete else 'INCOMPLETE',
        'structure_complete': complete, 'semantic_support_status': 'NOT_REVIEWED',
        'family_keys': [list(key) for key, _ in matching],
        'primary_family_keys': [list(key) for key, _ in sorted(primary_families, key=rank_key)],
        'local_family_keys': [list(key) for key, _ in sorted(local_families, key=rank_key)],
        'supporting_family_keys': [list(key) for key, _ in sorted(supporting_families, key=rank_key)],
        'priority_seed_ids': [c.chunk_id for c in priority],
        'required_structure_ids': sorted(required), 'missing_structure_ids': missing,
        'unresolved_structure_ids': sorted(unresolved),
        'bounded_caption_family_keys': [list(key) for key in recovered],
        'reason': 'explicit_descriptor_name_matches_owned_caption_and_section'}
    if not complete:
        trace['notice'] = '指定描述符的表族與同節說明尚未完整確認或選入；目前證據不完整。'
    result = {**baseline, **packed, 'topic_selection': trace}
    if fields:
        result['coverage_selection'] = coverage_trace(fields, wanted, conditions, selected)
    return result
