"""Read-only, bounded PDF typography projection alongside unchanged quotes.

This is not ingestion or mathematical interpretation. Only glyph runs in an
exactly aligned source span can receive a superscript/subscript presentation.
The original source contract, hashes, offsets and retrieval order stay intact.
"""
from collections import OrderedDict
from hashlib import sha256
from io import BytesIO
import os
from pathlib import Path
import re
from statistics import median
from threading import Lock

import pdfplumber
import yaml

from gv100h.spec_qa.frozen_corpus.receipt_bound_corpus import (
    DEFAULT_LOCK_PATH, PINNED_CORPUS_LOCK_SHA256,
)
from .contracts import verify_window

NOTICE = '封存文字未保留所有 PDF 排版；未確認的公式、下標與圖表請核對 PDF 原頁。'
_PAGE = re.compile(r'p\.(\d+)')
# Opened PDF objects kept per process; each pins a parsed page tree.
_DOCUMENT_LIMIT = 3


def _compact(text):
    positions = [i for i, char in enumerate(text) if not char.isspace()]
    return ''.join(text[i] for i in positions), positions


def _occurrences(text, needle):
    start = 0
    while needle:
        found = text.find(needle, start)
        if found < 0:
            return
        yield found
        start = found + 1


def _script_runs(line):
    """Recognize geometry, never infer powers from flattened text spelling."""
    chars = [c for c in line.get('chars', ()) if c.get('text', '').strip()]
    if len(chars) < 3 or any(not c.get('upright', True) for c in chars):
        return []
    # Multi-codepoint glyphs cannot be mapped one-to-one with source offsets.
    if any(len(c['text']) != 1 for c in chars):
        return []
    size = max(float(c['size']) for c in chars)
    body = [c for c in chars if float(c['size']) >= size * .9]
    if not body or size <= 0:
        return []
    # Font bounding boxes differ across fonts. The PDF text matrix origin
    # gives the baseline, including small glyphs whose top appears lower.
    if any(len(c.get('matrix', ())) != 6 for c in chars):
        return []
    baseline = median(c['matrix'][5] for c in body)
    # Overprinted/overlapping glyphs and rotated text have ambiguous order.
    if any(b['x0'] < a['x1'] - size * .15 for a, b in zip(chars, chars[1:])):
        return []
    kinds = []
    for char in chars:
        small = .35 * size <= float(char['size']) <= .8 * size
        kind = None
        rise = char['matrix'][5] - baseline
        if small and .15 * size <= rise <= .9 * size:
            kind = 'sup'
        elif small and -.6 * size <= rise <= -.1 * size:
            kind = 'sub'
        kinds.append(kind)
    runs = []
    i = 0
    while i < len(chars):
        kind = kinds[i]
        if kind is None:
            i += 1
            continue
        end = i + 1
        while end < len(chars) and kinds[end] == kind:
            end += 1
        # Require a nearby baseline anchor. A detached footnote line, small
        # caption or distant column must not be attached to preceding text.
        if (i > 0 and kinds[i-1] is None
                and chars[i-1]['text'] not in ',.;:'
                and float(chars[i-1]['size']) >= size * .9
                and -.15 * size <= chars[i]['x0'] - chars[i-1]['x1'] <= size * .6
                and all(b['x0'] - a['x1'] <= size * .6
                        for a, b in zip(chars[i:end], chars[i+1:end]))):
            runs.append((i, end, kind))
        else:
            # A whole-line supplement must not flatten another detected
            # script run just because its anchor is ambiguous (e.g. a
            # subscript immediately following a superscript).
            return []
        i = end
    return runs


def _align_line(content, lines, index):
    """Match whitespace-insensitively, retaining exact original coordinates.

    Nearby PDF lines disambiguate repeated lines; ambiguous text is declined.
    No substitutions, Unicode normalization, cross-source concatenation or
    page-number/Gold routing is permitted.
    """
    source, positions = _compact(content)
    texts = [_compact(''.join(c.get('text', '') for c in line.get('chars', ())))[0]
             for line in lines]
    current = texts[index]
    page_text = ''.join(texts)
    if not current:
        return None
    for before, after in ((1, 1), (1, 0), (0, 1), (0, 0)):
        lo, hi = max(0, index-before), min(len(lines), index+after+1)
        context = ''.join(texts[lo:hi])
        hits = list(_occurrences(source, context))
        # Unique in BOTH the frozen source and the PDF. Repeated page text
        # with different formatting is not evidence for either occurrence.
        if len(hits) == 1 and len(list(_occurrences(page_text, context))) == 1:
            start = hits[0] + sum(len(t) for t in texts[lo:index])
            return positions[start:start+len(current)]
    return None


def project_typography(content, lines):
    """Return bounded exact-source fragments; absence means unconfirmed."""
    fragments = []
    seen = set()
    for index, line in enumerate(lines):
        runs = _script_runs(line)
        if not runs:
            continue
        positions = _align_line(content, lines, index)
        if not positions:
            continue
        start, end = positions[0], positions[-1] + 1
        if (start, end) in seen:
            continue
        seen.add((start, end))
        parts, geometry, cursor = [], [], start
        chars = [c for c in line['chars'] if c.get('text', '').strip()]
        for lo, hi, kind in runs:
            a, b = positions[lo], positions[hi-1] + 1
            if a > cursor:
                parts.append({'kind': 'text', 'text': content[cursor:a]})
            parts.append({'kind': kind, 'text': content[a:b]})
            geometry.append({'start': a, 'end': b, 'kind': kind,
                             'glyphs': [{'text': c['text'], 'size': c['size'],
                                         'baseline_y': c['matrix'][5],
                                         'bbox': [c['x0'], c['top'], c['x1'], c['bottom']]}
                                        for c in chars[lo:hi]],
                             'anchor': {'text': chars[lo-1]['text'],
                                        'size': chars[lo-1]['size'],
                                        'baseline_y': chars[lo-1]['matrix'][5]}})
            cursor = b
        if cursor < end:
            parts.append({'kind': 'text', 'text': content[cursor:end]})
        quote = content[start:end]
        if ''.join(p['text'] for p in parts) != quote:
            raise ValueError('PDF projection changed source text')
        fragments.append({'start': start, 'end': end, 'quote': quote, 'parts': parts,
                          'geometry': geometry})
    return fragments


def _resolve_root(value):
    return Path(value).resolve()


class PdfLayout:
    """Operator-local, hash-locked PDF reads; no browser-controlled paths."""

    def __init__(self, raw_root=None):
        self._root_lock = Lock()
        self._root_state = (None, 0)
        self.root = Path(raw_root or os.environ.get('USB_SPEC_QA_RAW_ROOT')
                         or Path.home() / 'usb-spec-qa-raw')
        raw = DEFAULT_LOCK_PATH.read_bytes()
        if sha256(raw).hexdigest() != PINNED_CORPUS_LOCK_SHA256:
            raise ValueError('PDF source lock changed')
        self.sources = yaml.safe_load(raw)['sources']
        self.pages = OrderedDict()
        self.documents = OrderedDict()  # pinned sha256 -> opened pdfplumber PDF

    @property
    def root(self):
        return self._root_state[0]

    @property
    def root_generation(self):
        return self._root_state[1]

    def snapshot(self):
        """Return (root, generation) as one value."""
        return self._root_state

    @root.setter
    def root(self, value):
        resolved = _resolve_root(value)
        with self._root_lock:
            # One tuple store: readers see the old pair or the new pair, never a mix.
            self._root_state = (resolved, self._root_state[1] + 1)

    @staticmethod
    def pdf_page_of(source):
        match = _PAGE.fullmatch(source.page_or_anchor)
        return int(match[1]) if match else None

    def locate(self, source, root=None):
        """Return (path, expected_pdf_sha256), or None when not operator-local."""
        entry = self.sources.get(source.source_id, {})
        if (entry.get('document') != source.document
                or entry.get('revision') != source.revision):
            raise ValueError('PDF/source identity mismatch')
        locator = entry.get('source_locator', '')
        prefix = 'env://USB_SPEC_QA_RAW_ROOT/'
        if not locator.startswith(prefix):
            return None
        base = self.root if root is None else root
        path = (base / locator[len(prefix):]).resolve()
        if not path.is_relative_to(base):
            raise ValueError('PDF outside operator source root')
        return path, entry['content_sha256']

    def _document(self, source):
        located = self.locate(source)
        if located is None:
            return None
        path, expected = located
        try:
            raw = path.read_bytes()
        except (FileNotFoundError, PermissionError):
            return None
        digest = sha256(raw).hexdigest()
        if digest != expected:
            raise ValueError('PDF content hash mismatch')
        return raw, digest

    def _open(self, raw, digest):
        """Return one parsed PDF per pinned hash. Callers hold the service lock."""
        opened = self.documents.get(digest)
        if opened is None:
            opened = pdfplumber.open(BytesIO(raw))
            self.documents[digest] = opened
            while len(self.documents) > _DOCUMENT_LIMIT:
                self.documents.popitem(last=False)[1].close()
        else:
            self.documents.move_to_end(digest)
        return opened

    def _lines(self, document, number):
        raw, digest = document
        key = (digest, number)
        if key in self.pages:
            self.pages.move_to_end(key)
            return self.pages[key]
        pdf = self._open(raw, digest)
        if not 1 <= number <= len(pdf.pages):
            raise ValueError('PDF page outside source')
        page = pdf.pages[number-1]
        lines = page.extract_text_lines(layout=False)
        labels = []
        for line in lines:
            text, top = line['text'].strip(), line.get('top', 0)
            if top > page.height * .9 and re.fullmatch(r'\d+', text):
                labels.append(text)
            elif top < page.height * .1:
                labels.extend(re.findall(r'(?<!\w)[-–—]\s*(\d+)\s*[-–—](?!\w)', text))
        result = (lines, labels[0] if len(labels) == 1 else None)
        self.pages[key] = result
        while len(self.pages) > 128:
            self.pages.popitem(last=False)
        return result

    def annotate(self, context, windows, documents=None):
        """``documents`` maps source_id to a caller-verified ``(raw, digest)``
        pair, or to None for unavailable. Supplied entries are not re-read."""
        documents = {} if documents is None else documents
        entries = []
        for window in windows:
            verify_window(window, context)
            source = context.source(window.chunk_id)
            match = _PAGE.fullmatch(source.page_or_anchor)
            entry = {'evidence_id': window.evidence_id, 'chunk_id': source.chunk_id,
                     'request_id': context.request_id,
                     'request_binding_sha256': context.binding,
                     'document': source.document, 'revision': source.revision,
                     'source_id': source.source_id, 'page_or_anchor': source.page_or_anchor,
                     'content_sha256': source.content_sha256,
                     'status': 'UNCONFIRMED', 'fragments': [], 'pdf_page': None,
                     'printed_page': None, 'pdf_sha256': None}
            entries.append(entry)
            if match is None:
                continue
            number = int(match[1])
            entry['pdf_page'] = number
            if source.source_id not in documents:
                documents[source.source_id] = self._document(source)
            document = documents[source.source_id]
            if document is None:
                entry['status'] = 'PDF_UNAVAILABLE'
                continue
            lines, label = self._lines(document, number)
            entry.update(pdf_sha256=document[1], printed_page=label)
            fragments = project_typography(source.content, lines)
            entry['fragments'] = [f for f in fragments
                                  if window.start <= f['start'] < f['end'] <= window.end]
            if entry['fragments']:
                entry['status'] = 'PDF_GEOMETRY_ALIGNED'
        return {'notice': NOTICE, 'request_id': context.request_id,
                'request_binding_sha256': context.binding,
                'semantic_support_status': 'NOT_REVIEWED',
                'original_text_changed': False, 'entries': entries}
