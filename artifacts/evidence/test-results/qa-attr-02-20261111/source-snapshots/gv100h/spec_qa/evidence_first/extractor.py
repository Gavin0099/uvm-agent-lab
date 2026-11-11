"""Conservative continuous paragraph windows and explicitly candidate markers.

Keep atomic paragraphs/tables whole. For multi-paragraph chunks retain every
lexical anchor and condition/exception candidate, plus adjacent paragraphs.
No relevance, semantic support, adjacency across chunks or sufficiency claim.
"""
import re

from .contracts import make_window

_CONDITION = re.compile(r'\b(if|when|while|unless|except|only|not|never|shall|must|speed|frame|microframe)\b', re.I)
_EXCEPTION = re.compile(r'\b(unless|except|not|never|however|otherwise)\b', re.I)
_CAPTION = re.compile(r'^\s*Table\s+\d+(?:[-.]\d+)*\.', re.I)


def extract_windows(context, *, query_terms=(), family_by_id=None):
    windows, structures = [], []
    terms = tuple(t.casefold() for t in query_terms if isinstance(t, str) and t)
    for source in context.sources:
        text = source.content
        markers, cursor = [], 0
        for line in text.splitlines(keepends=True):
            kinds = []
            if _CONDITION.search(line): kinds.append('condition_candidate')
            if _EXCEPTION.search(line): kinds.append('exception_candidate')
            if _CAPTION.match(line): kinds.append('table_caption_candidate')
            if source.chunk_kind == 'table' and line.strip(): kinds.append('table_row_candidate')
            if kinds:
                markers.append({'start': cursor, 'end': cursor + len(line),
                    'quote': line, 'roles': kinds, 'status': 'CANDIDATE'})
            cursor += len(line)
        # Paragraph boundaries are source separators, never invented sentences.
        paragraphs = []
        start = 0
        for separator in re.finditer(r'\n[ \t]*\n', text):
            if text[start:separator.start()].strip():
                paragraphs.append((start, separator.start()))
            start = separator.end()
        if text[start:].strip(): paragraphs.append((start, len(text)))
        anchors = [i for i, (a, b) in enumerate(paragraphs)
                   if any(term in text[a:b].casefold() for term in terms)]
        table = source.chunk_kind == 'table' or any('table_caption_candidate' in m['roles'] for m in markers)
        a, b = 0, len(text)
        if table:
            reason = 'full_table_or_caption_preserved'
        elif len(paragraphs) < 2:
            reason = 'atomic_paragraph_no_safe_internal_boundary'
        elif not anchors:
            reason = 'no_original_text_anchor_full_fallback'
        else:
            marked = [i for i, (lo, hi) in enumerate(paragraphs)
                      if any(m['start'] < hi and m['end'] > lo for m in markers)]
            required = anchors + marked
            first, last = max(0, min(required)-1), min(len(paragraphs)-1, max(required)+1)
            a, b = paragraphs[first][0], paragraphs[last][1]
            reason = 'all_anchor_and_marker_paragraphs_plus_neighbors'
        if markers:
            a = min(a, min(m["start"] for m in markers))
            b = max(b, max(m["end"] for m in markers))
        window = make_window(context, source.chunk_id, a, b)
        windows.append(window)
        for marker in markers:
            marker['covered_by_window'] = a <= marker['start'] and marker['end'] <= b
        structures.append({'evidence_id': window.evidence_id, 'chunk_id': source.chunk_id,
            'selection_reason': reason, 'full_source_retained': True,
            'semantic_coverage': 'NOT_REVIEWED', 'markers': markers,
            'family_key_candidate': list((family_by_id or {}).get(source.chunk_id, ())) or None})
    return tuple(windows), structures
