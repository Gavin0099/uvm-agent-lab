"""Read-only PDF ruling-grid projection for USB setup-request tables.

Not ingestion; never touches the frozen Corpus. The product reaches it only
through supplement_gate.py, as a separate table supplement built from the same
pinned PDF bytes as the layout. Column bands come from the PDF's own vertical
ruling edges, and words are assigned by their x-centre. A table is CONFIRMED
only when every header word owns exactly one column band and every column has
at least one value word in the first ruled row below the header. Anything else
is UNCONFIRMED and must not be treated as a verified table.
"""
from bisect import bisect_right
from collections import OrderedDict
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from threading import Lock

import pdfplumber

SETUP_HEADER_KEYS = (
    'bmrequesttype', 'brequest', 'wvalue', 'windex', 'wlength', 'data',
)
CONFIRMED = 'PDF_RULING_GRID_CONFIRMED'
UNCONFIRMED = 'UNCONFIRMED'
NOTICE = '由 PDF 格線與字元座標投影；僅供核對，不取代原頁。'
_LINE_TOL = 2.0
_EDGE_TOL = 1.5
_CACHE_LIMIT = 128
_CACHE = OrderedDict()  # (pdf sha256, 1-based page) -> tuple[ProjectedTable]
_CACHE_LOCK = Lock()


@dataclass(frozen=True)
class ProjectedTable:
    page_index: int
    status: str
    reason: str
    headers: tuple
    values: tuple
    column_bounds: tuple
    row_band: tuple

    def as_record(self):
        return {'pdf_page': self.page_index + 1, 'status': self.status,
                'reason': self.reason, 'headers': list(self.headers),
                'values': list(self.values)}


def _cx(word):
    return (word['x0'] + word['x1']) / 2


def _mid_y(edge):
    return (edge['top'] + edge['bottom']) / 2


def _cy(word):
    return (word['top'] + word['bottom']) / 2


def _cluster(values, tol):
    groups = []
    for value in sorted(values):
        if groups and value - groups[-1][-1] <= tol:
            groups[-1].append(value)
        else:
            groups.append([value])
    return [sum(group) / len(group) for group in groups]


def _lines(words):
    groups = []
    for word in sorted(words, key=lambda w: (w['top'], w['x0'])):
        if groups and abs(word['top'] - groups[-1][0]['top']) <= _LINE_TOL:
            groups[-1].append(word)
        else:
            groups.append([word])
    return groups


def _header_words(line):
    """Return the six setup-header words in x order, or None if not exactly present."""
    picked = []
    for key in SETUP_HEADER_KEYS:
        hits = [w for w in line if w['text'].lower() == key]
        if len(hits) != 1:
            return None
        picked.append(hits[0])
    if [w['x0'] for w in picked] != sorted(w['x0'] for w in picked):
        return None
    return picked


def _band(bounds, x):
    if not bounds[0] <= x < bounds[-1]:
        return None
    return bisect_right(bounds, x) - 1


def _project_row(bounds, header_words, value_words):
    """Pure geometry: assign header and value words to column bands.

    Returns (status, reason, headers, values). Never guesses a column.
    """
    columns = len(bounds) - 1
    if columns != len(header_words):
        return UNCONFIRMED, 'column_count_mismatch', (), ()
    headers = [None] * columns
    for word in header_words:
        index = _band(bounds, _cx(word))
        if index is None or headers[index] is not None:
            return UNCONFIRMED, 'header_not_one_per_column', (), ()
        headers[index] = word['text']
    cells = [[] for _ in range(columns)]
    for word in sorted(value_words, key=lambda w: (w['top'], w['x0'])):
        index = _band(bounds, _cx(word))
        if index is None:
            return UNCONFIRMED, 'value_outside_columns', (), ()
        cells[index].append(word)
    if any(not cell for cell in cells):
        return UNCONFIRMED, 'empty_column', (), ()
    return CONFIRMED, '', tuple(headers), tuple(_cell_text(cell) for cell in cells)


def _cell_text(words):
    # Words on the same visual line are joined with a space; visual line breaks
    # inside a cell are kept as newlines so stacked values stay paired.
    return '\n'.join(
        ' '.join(w['text'] for w in sorted(line, key=lambda w: w['x0']))
        for line in _lines(words)
    )


def _unconfirmed(page_index, reason):
    return ProjectedTable(page_index, UNCONFIRMED, reason, (), (), (), ())


def _project_one(page_index, header, words, horizontals, verticals):
    rules = _cluster([_mid_y(e) for e in horizontals], _EDGE_TOL)
    top = min(w['top'] for w in header)
    bottom = max(w['bottom'] for w in header)
    above = [y for y in rules if y <= top + _EDGE_TOL]
    below = [y for y in rules if y >= bottom - _EDGE_TOL]
    if not above or not below:
        return _unconfirmed(page_index, 'no_ruled_header_row')
    rule_top = max(above)
    rule_bottom = min(below)
    if rule_bottom <= rule_top:
        return _unconfirmed(page_index, 'no_ruled_header_row')
    # Outer borders are often drawn as rule ends, not full-height verticals.
    header_rules = [
        e for e in horizontals
        if abs(_mid_y(e) - rule_top) <= _EDGE_TOL or abs(_mid_y(e) - rule_bottom) <= _EDGE_TOL
    ]
    left = min(e['x0'] for e in header_rules)
    right = max(e['x1'] for e in header_rules)
    if left > min(w['x0'] for w in header) or right < max(w['x1'] for w in header):
        return _unconfirmed(page_index, 'header_outside_ruled_extent')
    interior = [
        v['x0'] for v in verticals
        if v['top'] <= rule_top + _EDGE_TOL and v['bottom'] >= rule_bottom - _EDGE_TOL
        and left < v['x0'] < right
    ]
    bounds = _cluster(interior + [left, right], _EDGE_TOL)
    if len(bounds) < 2:
        return _unconfirmed(page_index, 'no_column_bounds')
    below_value = [y for y in rules if y > rule_bottom + _EDGE_TOL]
    if not below_value:
        return _unconfirmed(page_index, 'no_ruled_value_row')
    value_bottom = min(below_value)
    left, right = bounds[0], bounds[-1]
    value_words = [
        w for w in words
        if rule_bottom < _cy(w) < value_bottom and left <= _cx(w) < right
    ]
    status, reason, headers, values = _project_row(bounds, header, value_words)
    return ProjectedTable(
        page_index, status, reason, headers, values,
        tuple(round(x, 2) for x in bounds),
        (round(rule_bottom, 2), round(value_bottom, 2)),
    )


def project_page(page, page_index):
    """Project every six-column setup-request header found on one pdfplumber page."""
    words = page.extract_words()
    if not words:
        return []
    horizontals = [e for e in page.edges if e['orientation'] == 'h']
    verticals = [e for e in page.edges if e['orientation'] == 'v']
    tables = []
    for line in _lines(words):
        header = _header_words(line)
        if header is not None:
            tables.append(_project_one(page_index, header, words, horizontals, verticals))
    return tables


def project_setup_request_tables(pdf_path, expected_sha256):
    """Hash-check the PDF first; raise ValueError on any identity mismatch."""
    data = Path(pdf_path).read_bytes()
    if sha256(data).hexdigest() != expected_sha256:
        raise ValueError('PDF hash mismatch')
    tables = []
    with pdfplumber.open(BytesIO(data)) as pdf:
        for index, page in enumerate(pdf.pages):
            tables.extend(project_page(page, index))
    return tuple(tables)


def project_pages_from_bytes(raw, pages):
    """Project 1-based pages from caller-pinned PDF bytes; cache keyed by content hash."""
    digest = sha256(raw).hexdigest()
    wanted = sorted(set(pages))
    found, missing = {}, []
    with _CACHE_LOCK:
        for number in wanted:
            key = (digest, number)
            if key in _CACHE:
                _CACHE.move_to_end(key)
                found[number] = _CACHE[key]
            else:
                missing.append(number)
    if not missing:
        return found
    with pdfplumber.open(BytesIO(raw)) as pdf:
        if any(not 1 <= number <= len(pdf.pages) for number in missing):
            raise ValueError('PDF page outside source')
        fresh = {number: tuple(project_page(pdf.pages[number - 1], number - 1))
                 for number in missing}
    with _CACHE_LOCK:
        for number, tables in fresh.items():
            _CACHE[(digest, number)] = tables
        while len(_CACHE) > _CACHE_LIMIT:
            _CACHE.popitem(last=False)
    return {**found, **fresh}
