"""Request-scoped PDF layout gate for the product query path.

Each source that has PDF-page windows is bound once per request through
UnifiedPdfAuthority. Layout entries are built from the exact bytes that the
authority pinned and validated. The supplement is returned only when every
source finalizes and the PDF root generation and withdrawal state are unchanged
at the final check. The root is read once as a snapshot at request start and
used for every locate. Validity is as of that final check; later changes are
not retroactive. Otherwise the whole supplement is withheld.
Evidence text is never altered by this gate. Table supplements are a separate
field built from the same pinned PDF bytes; they never replace quote, hash or offset.
"""
from base64 import b64decode
from hashlib import sha256
import json
from threading import Lock

from .contracts import verify_window
from .pdf_layout import NOTICE, PdfLayout
from .pdf_request_table_projection import CONFIRMED, NOTICE as TABLE_NOTICE, project_pages_from_bytes
from .source_authority_candidate import AuthorityError, SourcePin
from .unified_pdf_authority_candidate import UnifiedPdfAuthority

_VALIDATED = 'PDF_HASH_MATCH_AT_VALIDATION'
_FAIL_CLOSED = frozenset({'PDF_HASH_MISMATCH'})  # baseline raised ValueError -> HTTP 400
_NOT_PROJECTED = 'NOT_PROJECTED'
_PROJECTED = 'PROJECTED'


def _not_projected():
    return {'status': _NOT_PROJECTED, 'reason': None, 'tables': [], 'unconfirmed_tables': 0,
            'unconfirmed_reasons': [], 'notice': TABLE_NOTICE}


def _table_builder(pages):
    def build(raw):
        try:
            projected = project_pages_from_bytes(raw, pages)
            body = {'status': _PROJECTED, 'reason': None,
                    'pages': {str(n): [t.as_record() for t in tables]
                              for n, tables in projected.items()}}
        except Exception:  # a table is a supplement; its failure must not withhold layout
            body = {'status': 'UNCONFIRMED', 'reason': 'TABLE_PROJECTION_FAILED', 'pages': {}}
        return json.dumps(body, ensure_ascii=False, sort_keys=True,
                          separators=(',', ':')).encode('utf-8')
    return build


def _parse_tables(encoded):
    try:
        payload = json.loads(b64decode(encoded, validate=True).decode('utf-8'))
        if (type(payload) is not dict or payload.get('status') not in {_PROJECTED, 'UNCONFIRMED'}
                or type(payload.get('pages')) is not dict):
            raise ValueError('table payload shape')
        return payload
    except (ValueError, TypeError, UnicodeError):
        return {'status': 'UNCONFIRMED', 'reason': 'TABLE_PAYLOAD_INVALID', 'pages': {}}


def _table_supplement(entry, payload):
    if payload['status'] != _PROJECTED:
        return {**_not_projected(), 'status': 'UNCONFIRMED', 'reason': payload.get('reason')}
    tables = payload['pages'].get(str(entry['pdf_page']), [])
    confirmed = [t for t in tables if t['status'] == CONFIRMED]
    return {'status': 'PDF_RULING_GRID_CONFIRMED' if confirmed else 'NO_CONFIRMED_TABLE',
            'reason': None, 'tables': confirmed,
            'unconfirmed_tables': len(tables) - len(confirmed),
            'unconfirmed_reasons': [t['reason'] for t in tables if t['status'] != CONFIRMED],
            'notice': TABLE_NOTICE}


def _layout_builder(layout, context, group, source_id):
    def build(raw):
        # Pinned bytes come from the authority; no second read happens here.
        digest = sha256(raw).hexdigest()
        entries = layout.annotate(context, group,
                                  documents={source_id: (raw, digest)})['entries']
        return json.dumps(entries, ensure_ascii=False, sort_keys=True,
                          separators=(',', ':')).encode('utf-8')
    return build


class SupplementGate:
    """Serialized by the caller's service lock; withdraw/reinstate may run from
    another thread, so the shared state is guarded here."""

    def __init__(self, layout):
        if not isinstance(layout, PdfLayout):
            raise ValueError('PdfLayout required')
        self.layout = layout
        self._lock = Lock()
        self._generation = 0
        self._withdrawn = set()

    def withdraw(self, source_id):
        with self._lock:
            self._withdrawn.add(source_id)
            self._generation += 1

    def reinstate(self, source_id):
        with self._lock:
            self._withdrawn.discard(source_id)
            self._generation += 1

    def _state(self):
        with self._lock:
            return self._generation, frozenset(self._withdrawn)

    def annotate(self, context, windows):
        layout = self.layout
        windows = tuple(windows)
        for window in windows:
            verify_window(window, context)
        root, root_generation = layout.snapshot()
        gate_generation, withdrawn = self._state()

        groups = {}  # source_id -> (source, (path, sha), [window indices])
        for index, window in enumerate(windows):
            source = context.source(window.chunk_id)
            if layout.pdf_page_of(source) is None:
                continue
            located = layout.locate(source, root)
            if located is None:
                continue
            groups.setdefault(source.source_id, (source, located, []))[2].append(index)

        base = layout.annotate(context, windows,
                               documents={sid: None for sid in groups})['entries']
        if not groups:
            return self._record(context, 'NOT_REQUIRED', None, base, [], {})

        failure, tokens, authorities = None, {}, {}
        for source_id, (source, (path, expected), indices) in groups.items():
            if source_id in withdrawn:
                failure = 'SOURCE_WITHDRAWN'
                break
            group = tuple(windows[i] for i in indices)
            pin = SourcePin(source_id=source_id, scope=context.scope,
                            revision=source.revision, path=path, pdf_sha256=expected)
            pages = {layout.pdf_page_of(context.source(windows[i].chunk_id)) for i in indices}
            authority = UnifiedPdfAuthority(
                pin, table_builder=_table_builder(pages),
                layout_builder=_layout_builder(layout, context, group, source_id))
            authorities[source_id] = authority
            try:
                tokens[source_id] = authority.begin(context, group)
            except AuthorityError as exc:
                failure = exc.reason
                break
            except Exception:  # supplement-only failure; the evidence path is unaffected
                failure = 'PROJECTION_UNCONFIRMED'
                break

        if failure is not None:
            for source_id, token in tokens.items():
                authorities[source_id].cancel(token, context)
            return self._withheld(context, failure, groups, base, {})

        results = {sid: authorities[sid].finalize(tok, context) for sid, tok in tokens.items()}

        payloads, tables = {}, {}
        for source_id, result in results.items():
            if result['source_status'] != _VALIDATED:
                failure = result['reason'] or 'PROJECTION_UNCONFIRMED'
                break
            try:
                payload = json.loads(b64decode(result['layout'], validate=True).decode('utf-8'))
            except (ValueError, TypeError, UnicodeError):
                failure = 'PROJECTION_UNCONFIRMED'
                break
            indices = groups[source_id][2]
            if (type(payload) is not list
                    or [e.get('evidence_id') for e in payload]
                    != [windows[i].evidence_id for i in indices]):
                failure = 'PROJECTION_UNCONFIRMED'
                break
            payloads[source_id] = payload
            tables[source_id] = _parse_tables(result['table'])

        current_generation, current_withdrawn = self._state()
        if failure is None and current_withdrawn & set(groups):
            failure = 'SOURCE_WITHDRAWN'
        elif failure is None and (layout.root_generation != root_generation
                                  or current_generation != gate_generation):
            failure = 'SOURCE_CONFIGURATION_CHANGED'

        if failure is not None:
            return self._withheld(context, failure, groups, base, results)

        table_supplements = {}
        for source_id, payload in payloads.items():
            for index, entry in zip(groups[source_id][2], payload):
                table_supplements[entry['evidence_id']] = _table_supplement(entry, tables[source_id])
                base[index] = entry
        sources = [self._source_record(sid, groups[sid][0], groups[sid][1][1], results.get(sid))
                   for sid in groups]
        return self._record(context, 'VALIDATED', None, base, sources, table_supplements)

    def _withheld(self, context, failure, groups, base, results):
        if failure in _FAIL_CLOSED:
            raise ValueError('PDF content hash mismatch')
        # Base entries were annotated without documents, so they carry no fragments.
        sources = [self._source_record(sid, groups[sid][0], groups[sid][1][1], results.get(sid))
                   for sid in groups]
        return self._record(context, 'WITHHELD', failure, base, sources, {})

    @staticmethod
    def _source_record(source_id, source, expected, result):
        record = {'source_id': source_id, 'revision': source.revision,
                  'pdf_sha256': expected, 'source_status': None, 'reason': None,
                  'validated_at_monotonic': None, 'response_binding_sha256': None}
        if result is not None:
            record.update(source_status=result['source_status'], reason=result['reason'],
                          validated_at_monotonic=result['validated_at'],
                          response_binding_sha256=result['response_binding_sha256'])
        return record

    @staticmethod
    def _record(context, status, reason, entries, sources, table_supplements):
        return {'notice': NOTICE, 'request_id': context.request_id,
                'request_binding_sha256': context.binding,
                'semantic_support_status': 'NOT_REVIEWED',
                'original_text_changed': False, 'entries': entries,
                'table_supplements': dict(table_supplements),
                'source_authority': {'status': status, 'reason': reason,
                                     'table_supplement': _PROJECTED if status == 'VALIDATED' else _NOT_PROJECTED,
                                     'sources': sources}}
