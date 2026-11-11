"""Bounded lexical condition discovery, not an engineering sufficiency oracle.

Only already retrieved, owned paragraphs can donate candidates. Exact query
identifiers and explicit applicability words select whole original chunks;
neither answer values nor source locations participate in selection.
"""
import re

from .query_guards import identifier_tokens, normalized_query, requested_identifiers


_RULE = re.compile(r'\b(?:must|shall|required|requires|limited|range|only|reserved|'
                   r'valid|invalid|except|unless|cannot|maximum|minimum)\b|\bat (?:most|least)\b', re.I)
_AXES = {
    'speed': {'low-speed': ('low-speed', 'low speed', '低速'),
              'full-speed': ('full-speed', 'full speed', '全速'),
              'high-speed': ('high-speed', 'high speed', '高速')},
    'transfer': {'isochronous': ('isochronous', '等時', '同步傳輸'),
                 'interrupt': ('interrupt', '中斷'),
                 'bulk': ('bulk', '大量', '批量'),
                 'control': ('control', '控制')},
}


def applicability(text):
    text = normalized_query(text)
    # Shared suffix spelling is typography, not a new applicability inference.
    text = re.sub(r'\b(low|full|high)-?/(low|full|high)-speed\b',
                  r'\1-speed \2-speed', text)
    return {axis: sorted(name for name, aliases in names.items()
                        if any(re.search(r'(?<![a-z0-9_])' + re.escape(alias)
                                         + r'(?![a-z0-9_])', text) for alias in aliases))
            for axis, names in _AXES.items()}


def condition_candidates(question, hits, *, source_keys=None, topic=None, topics=None):
    fields = requested_identifiers(question)
    wanted = applicability(question)
    candidates = []
    if not fields:
        return fields, wanted, candidates
    for rank, hit in enumerate(hits, 1):
        c = hit.chunk
        if c.chunk_kind != 'paragraph' or (source_keys is not None
                and (c.source_id, c.revision) not in source_keys):
            continue
        if not any(field in c.content for field in fields) or not _RULE.search(c.content):
            continue
        # Require a rule in the same sentence as the exact identifier. Mere
        # index entries, broad descriptor words and a rule elsewhere do not count.
        sentences = re.split(r'(?<=[.!?;])\s+', c.content)
        matched = sorted(field for field in fields if any(
            field in sentence and _RULE.search(sentence) and field in identifier_tokens(sentence)
            for sentence in sentences))
        if not matched:
            continue
        if topic and topics:
            named = set(topics(c.content))
            if named and topic not in named:
                continue
        axes = applicability(c.content)
        if any(wanted[a] and axes[a] and not set(wanted[a]) & set(axes[a]) for a in wanted):
            continue
        candidates.append((hit, {'chunk_id': c.chunk_id, 'source_id': c.source_id,
            'revision': c.revision, 'section': c.section, 'page_or_anchor': c.page_or_anchor,
            'fields': matched, 'applicability_words': axes, 'bm25_rank': rank}))
    return fields, wanted, candidates


def coverage_trace(fields, wanted, candidates, selected):
    rows = [row for _, row in candidates]
    missing = [row for row in rows if row['chunk_id'] not in selected]
    status = ('INCOMPLETE' if missing else 'IDENTIFIED_CANDIDATES_RETAINED'
              if rows else 'NOT_ASSESSED')
    trace = {'status': status, 'fields': sorted(fields), 'requested_applicability': wanted,
        'condition_candidates': rows, 'missing_candidates': missing,
        'semantic_support_status': 'NOT_REVIEWED', 'overall_answer_sufficiency': 'NOT_ASSESSED',
        'reason': 'exact_identifier_and_rule_in_same_sentence_over_existing_hits'}
    if missing:
        locations = list(dict.fromkeys(f"{r['source_id']} · {r['revision']} · §{r['section']} · {r['page_or_anchor']}"
                                      for r in missing))
        trace['notice'] = ('欄位條件候選未完整選入：缺 ' + str(len(missing)) + ' 段（'
                           + '；'.join(locations) + '）。表格結構完整不代表問題條件完整，請核對原規格。')
    elif rows:
        trace['notice'] = ('已保留本次識別的 ' + str(len(rows))
                           + ' 段欄位條件候選；各段速度與傳輸類型須分別核對。'
                             '這只檢查已識別候選的保留情況，未確認所有必要條件、例外或工程語意完整。')
    else:
        trace['notice'] = '尚未識別可確認的欄位條件候選；表格結構完整不代表問題條件完整。'
    return trace
