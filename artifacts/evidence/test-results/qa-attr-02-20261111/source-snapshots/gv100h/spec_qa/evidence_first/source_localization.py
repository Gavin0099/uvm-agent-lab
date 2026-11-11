"""Versioned, read-only source localization overlay (QL2-01).

The frozen corpus keeps its pinned chunk identities and its sticky ``section``
labels. This overlay re-reads the locked PDF geometry and reports where a chunk
is actually located on its physical page:

- ``CONFIRMED``: the localized anchor equals the frozen section label.
- ``LOCALIZED``: a different body anchor in effect at the chunk's first line.
- ``PAGE_LEVEL``: the chunk's first line was not matched; the page's carried-in
  anchor is used.
- ``NON_BODY_PAGE``: the page belongs to an index or table-of-contents run, so
  no body section applies.
- ``UNRESOLVED``: the anchor could not be decided; fail closed, no section.
- ``NOT_INDEXED``: the page has no entry in the localization index.

Rules: footers and headers (outside the body band) never establish a section;
test-procedure anchors (``TD n.n``) at the text margin are body anchors; numeric
headings reuse the frozen heading typography check. The frozen ingestion module
is read, never edited, and its pins are not changed.

Index build (``python -X utf8 -m gv100h.spec_qa.evidence_first.source_localization``)
reads the locked PDFs once and writes ``source_localization_index.json`` next to
this module. Runtime lookups use only that index.
"""
from __future__ import annotations

import functools
import hashlib
import json
import re
import sys
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

LOCALIZATION_VERSION = 'ql2-01-source-localization-v1'
INDEX_PATH = Path(__file__).with_name('source_localization_index.json')

INDEX_RUN_MIN_PAGES = 5
REF_LINE_RATIO = 0.5
BODY_TOP_FRACTION = 0.09
BODY_BOTTOM_FRACTION = 0.90
TEST_ANCHOR_MAX_X0 = 95.0
MIN_MATCH_CHARS = 8
MATCH_PREFIX_CHARS = 30

_DOTTED_REF = re.compile(r'\b\d{1,2}\.\d{1,2}(?:\.\d{1,2}){0,3}\b')
_REF_TAIL = re.compile(r'\d+(?:\.\d+)*(?:,\s*\d+(?:\.\d+)*)*\s*$')
_TEST_ANCHOR = re.compile(r'^TD\s*(\d+\.\d+)\s+(\S.*)$')
_NON_ALNUM = re.compile(r'[^0-9a-z]+')


@functools.lru_cache(maxsize=1)
def _frozen_heading_rules():
    from gv100h.spec_qa.frozen_corpus.receipt_bound_corpus import _load_frozen_ingestion
    module = _load_frozen_ingestion()
    return module._HEADING_PATTERN, module._looks_like_section_heading


def _norm(text: str) -> str:
    return _NON_ALNUM.sub('', text.lower())


def _is_ref_line(text: str) -> bool:
    return bool(_DOTTED_REF.search(text) and _REF_TAIL.search(text))


def _summarize_page(number: int, page: Any, heading_pattern, looks_like_heading) -> Dict[str, Any]:
    height = float(page.height)
    low, high = height * BODY_TOP_FRACTION, height * BODY_BOTTOM_FRACTION
    lines: List[Dict[str, Any]] = []
    body_count = 0
    ref_count = 0
    for raw in page.extract_text_lines(layout=False):
        text = raw['text'].strip()
        top = float(raw.get('top', 0))
        if not low <= top < high or not text:
            continue
        body_count += 1
        if _is_ref_line(text):
            ref_count += 1
        anchor = None
        x0 = float(raw.get('x0', 0))
        heading = heading_pattern.match(text)
        if heading and looks_like_heading(raw, text):
            anchor = {'section': heading.group('section'),
                      'title': heading.group('title').strip(), 'kind': 'NUMERIC'}
        else:
            test = _TEST_ANCHOR.match(text)
            if test and x0 <= TEST_ANCHOR_MAX_X0:
                anchor = {'section': f'TD {test.group(1)}',
                          'title': test.group(2).strip(), 'kind': 'TEST'}
        lines.append({'top': round(top, 1), 'text': text, 'norm': _norm(text),
                      'anchor': anchor})
    return {'number': number, 'body_lines': body_count, 'ref_lines': ref_count,
            'lines': lines}


def _non_body_runs(summaries: List[Dict[str, Any]]) -> List[List[int]]:
    flagged = [s['body_lines'] > 0 and s['ref_lines'] / s['body_lines'] >= REF_LINE_RATIO
               for s in summaries]
    runs: List[List[int]] = []
    start = None
    for index, is_flagged in enumerate(flagged + [False]):
        if is_flagged and start is None:
            start = index
        elif not is_flagged and start is not None:
            if index - start >= INDEX_RUN_MIN_PAGES:
                runs.append([summaries[start]['number'], summaries[index - 1]['number']])
            start = None
    return runs


def build_index(pdf_bytes: bytes, *, source_id: str, content_sha256: str) -> Dict[str, Any]:
    """Build one source's localization entry from verified PDF bytes."""
    import pdfplumber

    heading_pattern, looks_like_heading = _frozen_heading_rules()
    if hashlib.sha256(pdf_bytes).hexdigest() != content_sha256:
        raise ValueError('PDF content hash mismatch')
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        summaries = [_summarize_page(n, page, heading_pattern, looks_like_heading)
                     for n, page in enumerate(pdf.pages, start=1)]
    runs = _non_body_runs(summaries)
    non_body = {n for start, end in runs for n in range(start, end + 1)}
    carried: Optional[Dict[str, str]] = None
    pages: Dict[str, Dict[str, Any]] = {}
    for summary in summaries:
        number = summary['number']
        if number in non_body:
            pages[str(number)] = {'role': 'NON_BODY'}
            continue
        anchors = []
        for index, line in enumerate(summary['lines']):
            if line['anchor'] is not None:
                anchors.append({'line': index, **line['anchor']})
        pages[str(number)] = {
            'role': 'BODY',
            'carried_in': dict(carried) if carried else None,
            'lines': [{'top': l['top'], 'norm': l['norm']} for l in summary['lines']],
            'anchors': anchors,
        }
        for anchor in anchors:
            carried = {'section': anchor['section'], 'title': anchor['title'],
                       'kind': anchor['kind']}
    return {'source_id': source_id, 'content_sha256': content_sha256,
            'page_count': len(summaries), 'non_body_runs': runs, 'pages': pages}


def build_full_index(raw_root: Path, lock_path: Path) -> Dict[str, Any]:
    import yaml
    sources = yaml.safe_load(lock_path.read_bytes())['sources']
    result: Dict[str, Any] = {'localization_version': LOCALIZATION_VERSION, 'sources': {}}
    for source_id, entry in sources.items():
        locator = entry.get('source_locator', '')
        prefix = 'env://USB_SPEC_QA_RAW_ROOT/'
        if not locator.startswith(prefix):
            continue
        path = (raw_root / locator[len(prefix):]).resolve()
        result['sources'][source_id] = build_index(
            path.read_bytes(), source_id=source_id, content_sha256=entry['content_sha256'])
    return result


class SourceLocalization:
    """Read-only lookups over a built index; never reads PDFs at query time."""

    def __init__(self, index: Mapping[str, Any]):
        if index.get('localization_version') != LOCALIZATION_VERSION:
            raise ValueError('localization index version mismatch')
        self._sources = index['sources']

    @classmethod
    def load(cls, path: Path = INDEX_PATH) -> 'SourceLocalization':
        return cls(json.loads(path.read_text(encoding='utf-8')))

    def verify_against_lock(self, lock_path: Path) -> None:
        """Fail closed unless every indexed source matches the corpus lock digest."""
        import yaml
        locked = yaml.safe_load(Path(lock_path).read_bytes())['sources']
        for source_id, entry in self._sources.items():
            if locked.get(source_id, {}).get('content_sha256') != entry['content_sha256']:
                raise ValueError(f'localization index digest mismatch: {source_id}')

    def localize(self, source_id: str, page: int, chunk_text: str,
                 frozen_section: Optional[str]) -> Dict[str, Any]:
        base = {'localization_version': LOCALIZATION_VERSION, 'frozen_section': frozen_section}
        source = self._sources.get(source_id)
        entry = source and source['pages'].get(str(page))
        if entry is None:
            return {**base, 'status': 'NOT_INDEXED', 'section': None, 'title': None}
        if entry['role'] == 'NON_BODY':
            return {**base, 'status': 'NON_BODY_PAGE', 'section': None, 'title': None}
        anchor, match = self._anchor_for(entry, chunk_text)
        if anchor is None:
            return {**base, 'status': 'UNRESOLVED', 'section': None, 'title': None}
        if match == 'MATCHED':
            status = 'CONFIRMED' if anchor['section'] == frozen_section else 'LOCALIZED'
        else:
            status = match
        return {**base, 'status': status, 'section': anchor['section'],
                'title': anchor['title']}

    @staticmethod
    def _anchor_for(entry: Mapping[str, Any], chunk_text: str):
        """Return (anchor or None, match status) for the chunk's first line on its page."""
        carried = entry.get('carried_in')
        anchors = entry['anchors']
        first = next((line for line in chunk_text.splitlines() if line.strip()), '')
        key = _norm(first)[:MATCH_PREFIX_CHARS]
        candidates: List[int] = []
        if len(key) >= MIN_MATCH_CHARS:
            for position, line in enumerate(entry['lines']):
                probe = line['norm'][:MATCH_PREFIX_CHARS]
                if len(probe) >= MIN_MATCH_CHARS and (key.startswith(probe)
                                                      or probe.startswith(key)):
                    candidates.append(position)
        if not candidates:
            # Unmatched first line: only a page with no body anchors may use the carried-in one.
            if anchors:
                return None, 'UNRESOLVED'
            return (carried, 'PAGE_LEVEL') if carried else (None, 'UNRESOLVED')
        # A prefix can occur under more than one heading on the same page (for example a
        # generic table header row). Several candidates are accepted only when they all
        # resolve to the same in-effect anchor; otherwise the position is ambiguous.
        resolved = []
        for index in candidates:
            in_effect = None
            for anchor in anchors:
                if anchor['line'] <= index:
                    in_effect = anchor
            resolved.append(in_effect)
        if all(anchor is None for anchor in resolved):
            # No heading on this page before the chunk: inherited state, not on-page proof.
            return (carried, 'CARRIED_IN') if carried else (None, 'UNRESOLVED')
        distinct = {json.dumps(anchor, sort_keys=True) for anchor in resolved}
        if None in resolved or len(distinct) != 1:
            return None, 'UNRESOLVED'
        return resolved[0], 'MATCHED'


def section_display(localization: Mapping[str, Any]) -> str:
    """Human-facing section text; the frozen label is never shown as the localized one."""
    status = localization['status']
    if status in ('CONFIRMED', 'LOCALIZED'):
        return localization['section']
    if status in ('CARRIED_IN', 'PAGE_LEVEL'):
        return f"{localization['section']}（承接前頁，本頁未見章節標題）"
    return '未確認章節'


def main(argv: List[str]) -> int:
    from gv100h.spec_qa.frozen_corpus.receipt_bound_corpus import DEFAULT_LOCK_PATH
    import os
    raw_root = Path(os.environ.get('USB_SPEC_QA_RAW_ROOT')
                    or Path.home() / 'usb-spec-qa-raw')
    index = build_full_index(raw_root, DEFAULT_LOCK_PATH)
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, sort_keys=True),
                          encoding='utf-8')
    print(f'wrote {INDEX_PATH} sources={sorted(index["sources"])}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
