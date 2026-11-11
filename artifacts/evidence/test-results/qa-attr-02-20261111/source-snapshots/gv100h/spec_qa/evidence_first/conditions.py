"""Source-exact candidate qualifiers, alternatives and table relationships."""
from dataclasses import asdict
import re

from gv100h.spec_qa.retrieval.table_family_pack import table_families
from .contracts import Source, make_window, verify_window

_QUALIFIER = re.compile(r'\b(if|when|while|unless|except|only|not|never|shall|must|may|can|regardless|otherwise|speed|frame|microframe|bcdUSB|ClearFeature)\b|\(micro\)frame|short[ -]packet', re.I)
_EXCEPTION = re.compile(r'\b(unless|except|not|never|only|regardless|otherwise|however)\b', re.I)
_ALTERNATIVE = re.compile(r'\b(or|may|can|alternatively)\b', re.I)


def attach_conditions(context, windows, *, corpus_chunks):
    """Consume only owned corpus data; annotations never mean DIRECT_SUPPORT.

    Mark missing displayed context and incomplete table families UNRESOLVED.
    Full source originals and parent windows are never deleted or rewritten.
    """
    windows = tuple(windows); chunks = tuple(corpus_chunks)
    by_id = {c.chunk_id: c for c in chunks}
    if len(by_id) != len(chunks): raise ValueError('Ambiguous corpus identity')
    for source in context.sources:
        original = by_id.get(source.chunk_id)
        if original is None or any(getattr(original, key) != value for key, value in asdict(source).items()):
            raise ValueError('Condition source outside owned corpus')
    families, membership = table_families(chunks)
    attachments, relations = [], []
    selected = {w.chunk_id for w in windows}
    for window in windows:
        verify_window(window, context)
        source = context.source(window.chunk_id);text = source.content
        lines = [];cursor = 0
        for line in text.splitlines(keepends=True):
            lines.append((cursor, cursor + len(line), line));cursor += len(line)
        intervals = []
        for i, (_a, _b, line) in enumerate(lines):
            if not any(pattern.search(line) for pattern in (_QUALIFIER, _EXCEPTION, _ALTERNATIVE)): continue
            start, end = lines[max(0, i-1)][0], lines[min(len(lines)-1, i+1)][1]
            kinds = {'qualifier_candidate'} if _QUALIFIER.search(line) else set()
            if _EXCEPTION.search(line): kinds.add('exception_or_counterexample_candidate')
            if _ALTERNATIVE.search(line): kinds.add('alternative_candidate')
            if intervals and start <= intervals[-1][1]:
                a,b,old=intervals[-1];intervals[-1]=(a,max(b,end),old|kinds)
            else:intervals.append((start,end,kinds))
        for start,end,kinds in intervals:
            span = make_window(context, source.chunk_id, start, end)
            covered = window.start <= start and end <= window.end
            attachments.append({'parent_evidence_id': window.evidence_id, 'span': span.as_record(),
                'roles': sorted(kinds), 'status': 'CANDIDATE',
                'retention_status': 'RETAINED' if covered else 'UNRESOLVED',
                'needs_window_expansion': not covered, 'semantic_support_status': 'NOT_REVIEWED'})
        family = membership.get(source.chunk_id)
        if family:
            ids = [c.chunk_id for c in families[family]]
            if not any(r['family_key_candidate']==list(family) for r in relations):
                missing = [cid for cid in ids if cid not in selected]
                cropped = [cid for cid in ids if cid in selected and not any(
                    w.chunk_id == cid and w.start == 0 and w.end == len(by_id[cid].content) for w in windows)]
                relations.append({'family_key_candidate': list(family), 'member_ids': ids,
                    'missing_member_ids': missing, 'cropped_member_ids': cropped, 'status': 'CANDIDATE',
                    'retention_status': 'UNRESOLVED' if missing or cropped else 'RETAINED',
                    'semantic_support_status': 'NOT_REVIEWED'})
    return {'attachments': attachments, 'table_relations': relations,
        'retention_status': 'UNRESOLVED' if any(a['needs_window_expansion'] for a in attachments)
            or any(r['missing_member_ids'] or r['cropped_member_ids'] for r in relations) else 'RETAINED',
        'semantic_coverage': 'NOT_REVIEWED',
        'unconfirmed': ['候選條件／例外來自原文字面線索；未證明所有自然語言條件、反例或語意關係均已辨識。']}
