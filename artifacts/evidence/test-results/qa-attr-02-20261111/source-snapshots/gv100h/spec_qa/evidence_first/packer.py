"""Conservative, coverage-preserving interval packing over owned Top20 sources.

No unreviewed semantic role is discarded for a size target. A soft budget or
missing table member returns an incomplete bundle with the original candidates.
"""
from .conditions import attach_conditions
from .contracts import full_windows, make_window, verify_window, window_from_record


def pack_evidence(context, windows, *, corpus_chunks, target_chars=39739):
    if type(target_chars) is not int or target_chars < 1:
        raise ValueError('Positive integer character target required')
    windows = tuple(windows); chunks = tuple(corpus_chunks)
    for w in windows:
        verify_window(w, context)
    conditions = attach_conditions(context, windows, corpus_chunks=chunks)
    ranges = {}
    for w in windows:
        ranges.setdefault(w.chunk_id, []).append((w.start, w.end))
    for attachment in conditions['attachments']:
        span = window_from_record(attachment['span'], context)
        ranges.setdefault(span.chunk_id, []).append((span.start, span.end))
    missing = []
    for relation in conditions['table_relations']:
        missing.extend(relation['missing_member_ids'])
        for cid in relation['member_ids']:
            if cid not in relation['missing_member_ids']:
                ranges[cid] = [(0, len(context.source(cid).content))]
    packed = []
    for source in context.sources:
        merged = []
        for start, end in sorted(ranges.get(source.chunk_id, ())):
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
            else:
                merged.append((start, end))
        # One continuous envelope per source also retains the context between
        # disjoint fragments. Never concatenate quotations across a hidden gap.
        if merged:
            packed.append(make_window(context, source.chunk_id, merged[0][0], merged[-1][1]))
    reasons = []
    if missing:
        reasons.append('table_family_member_outside_original_candidates')
    if sum(len(w.quote) for w in packed) > target_chars:
        reasons.append('character_target_cannot_be_met_without_unreviewed_deletion')
    if reasons:
        # The target is advisory, never permission to truncate evidence.
        packed = list(full_windows(context))
    # Enforce actual displayed retention, independently of lexical role labels.
    if any(not any(p.chunk_id == w.chunk_id and p.start <= w.start and w.end <= p.end
                   for p in packed) for w in windows):
        raise ValueError('Packing lost an original evidence interval')
    retained = attach_conditions(context, packed, corpus_chunks=chunks)
    return {
        'status': 'INCOMPLETE' if reasons else 'CANDIDATE_UNREVIEWED',
        'request_id': context.request_id, 'request_binding_sha256': context.binding,
        'evidence': [w.as_record() for w in packed],
        'original_candidates': [w.as_record() for w in windows],
        'fallback_reasons': reasons, 'missing_table_member_ids': sorted(set(missing)),
        'conditions': retained, 'semantic_coverage': 'NOT_REVIEWED',
        'overall_answer_sufficiency': 'NOT_ASSESSED',
        'selection_trace': [{'chunk_id': source.chunk_id,
            'decision': 'INCLUDED' if source.chunk_id in ranges or reasons else 'EXCLUDED',
            'reason': 'full_original_fallback' if reasons else
                'original_intervals_and_candidate_conditions_retained' if source.chunk_id in ranges else
                'no_input_interval_or_condition',
            'selected_ranges': [[w.start, w.end] for w in packed if w.chunk_id == source.chunk_id]}
            for source in context.sources],
        'comparison': {'original_source_chars': sum(len(s.content) for s in context.sources),
            'original_window_chars': sum(len(w.quote) for w in windows),
            'bundle_chars': sum(len(w.quote) for w in packed),
            'original_window_count': len(windows), 'bundle_window_count': len(packed),
            'token_counts': 'NOT_MEASURED', 'tokenizer_executed': False},
        'unconfirmed': ['合併重疊區間並保留原候選及已識別條件；未證明這是語意完整或最小證據包。'],
    }
