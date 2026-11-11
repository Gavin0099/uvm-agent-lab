"""Unified PDF response finalizer, wired into the product query path only via
supplement_gate.py (request-scoped, all-or-nothing).

Trusted backend code owns the pin, builders, RequestContext and windows. This
is a prototype contract, not an authenticated capability or geometry review.
The final hash observation is as-of validation, not a future availability
promise. Reuse of a response for a later request requires a fresh finalization.
"""
from base64 import b64decode, b64encode
import json
import secrets
from threading import RLock
from time import monotonic

from .contracts import EvidenceWindow, RequestContext, digest, verify_window
from .source_authority_candidate import AuthorityError, PdfSourceAuthority, SourcePin

_MAX_PROJECTION_BYTES = 1024 * 1024
_MAX_PENDING = 128


class UnifiedPdfAuthority:
    """One trusted pin, one immutable projection, one final source decision.

    Both builders receive exactly the same pinned PDF bytes; neither builder
    can set an authority or geometry status. Pending data never reaches a
    response unless the original source is validated again at finalization.
    """
    def __init__(self, pin, *, table_builder, layout_builder, ttl_seconds=60):
        if not isinstance(pin, SourcePin) or not callable(table_builder) or not callable(layout_builder):
            raise ValueError('trusted pin and builders required')
        self._lock = RLock()
        self._pin = pin
        self._table_builder = table_builder
        self._layout_builder = layout_builder
        self._ttl = ttl_seconds
        self._epoch = 0
        self._withdrawn = False
        self._pending = {}
        self._authority = self._make_authority(pin)

    def _make_authority(self, pin):
        def build(raw):
            table = self._table_builder(raw)
            layout = self._layout_builder(raw)
            if type(table) is not bytes or type(layout) is not bytes:
                raise AuthorityError('PROJECTION_UNCONFIRMED')
            if len(table) + len(layout) > _MAX_PROJECTION_BYTES:
                raise AuthorityError('PROJECTION_TOO_LARGE')
            return json.dumps({'table': b64encode(table).decode('ascii'),
                               'layout': b64encode(layout).decode('ascii')},
                              sort_keys=True, separators=(',', ':')).encode('ascii')
        return PdfSourceAuthority([pin], build, ttl_seconds=self._ttl)

    def replace_source(self, pin):
        """Trusted backend may change location only; outstanding work expires."""
        with self._lock:
            old = self._pin
            if (not isinstance(pin, SourcePin) or
                    (pin.source_id, pin.scope, pin.revision, pin.pdf_sha256) !=
                    (old.source_id, old.scope, old.revision, old.pdf_sha256)):
                raise AuthorityError('SOURCE_IDENTITY_MISMATCH')
            new_authority = self._make_authority(pin)
            if self._withdrawn:
                new_authority.withdraw(pin.source_id)
            self._authority.invalidate(old.source_id)
            self._epoch += 1
            self._pin, self._authority = pin, new_authority

    def withdraw(self):
        with self._lock:
            self._authority.withdraw(self._pin.source_id)
            self._withdrawn = True
            self._epoch += 1

    def reinstate(self):
        with self._lock:
            self._authority.reinstate(self._pin.source_id)
            self._withdrawn = False
            self._epoch += 1

    def begin(self, context, windows):
        """Prepare privately. No PDF projection is exposed before finalization."""
        if type(context) is not RequestContext or type(windows) is not tuple:
            raise ValueError('owned request and window tuple required')
        if any(type(w) is not EvidenceWindow for w in windows):
            raise ValueError('owned evidence windows required')
        for window in windows:
            verify_window(window, context)
        with self._lock:
            self._purge_expired()
            pin, authority, epoch = self._pin, self._authority, self._epoch
            if (context.scope != pin.scope or not any(s.source_id == pin.source_id
                    and s.revision == pin.revision for s in context.sources)):
                raise AuthorityError('SOURCE_IDENTITY_MISMATCH')
            if len(self._pending) >= _MAX_PENDING:
                raise AuthorityError('PENDING_LIMIT')
        bound = authority.bind(pin.source_id, scope=pin.scope, revision=pin.revision,
                               request_id=context.request_id)
        with self._lock:
            self._purge_expired()
            if epoch != self._epoch or authority is not self._authority:
                raise AuthorityError('SOURCE_CONFIGURATION_CHANGED')
            if len(self._pending) >= _MAX_PENDING:
                raise AuthorityError('PENDING_LIMIT')
            token = secrets.token_hex(32)
            self._pending[token] = (context, windows, pin, authority, epoch, bound.entry_id,
                                    monotonic() + self._ttl)
            return token

    def _purge_expired(self):
        """Called under the lock; expired requests cannot hold capacity."""
        now = monotonic()
        for token, pending in list(self._pending.items()):
            if now >= pending[6]:
                del self._pending[token]

    def cancel(self, token, context):
        """Discard a disconnected request without exposing its projections."""
        with self._lock:
            self._purge_expired()
            pending = self._pending.get(token)
            if pending is None or pending[0] != context:
                raise AuthorityError('INVALID_REQUEST')
            del self._pending[token]

    def finalize(self, token, context):
        """Consume one owned request, returning both projections or neither."""
        if type(context) is not RequestContext or not isinstance(token, str):
            raise AuthorityError('INVALID_REQUEST')
        with self._lock:
            self._purge_expired()
            pending = self._pending.get(token)
            if pending is None or pending[0] != context:
                raise AuthorityError('INVALID_REQUEST')
            del self._pending[token]
            owned_context, windows, pin, authority, epoch, entry_id, _deadline = pending
            stale = epoch != self._epoch or authority is not self._authority
        result = {'request_id': context.request_id, 'request_binding_sha256': context.binding,
                  'scope': context.scope, 'corpus_sha256': context.corpus_sha256,
                  'frozen_windows': [w.as_record() for w in windows],
                  'source_id': pin.source_id, 'revision': pin.revision,
                  'source_status': 'UNAVAILABLE', 'reason': None, 'validated_at': None,
                  'pdf_sha256': None, 'table': None, 'layout': None,
                  'geometry_status': 'UNCONFIRMED', 'semantic_support_status': 'NOT_REVIEWED'}
        try:
            if stale:
                raise AuthorityError('SOURCE_CONFIGURATION_CHANGED')
            bound = authority.bind(pin.source_id, scope=pin.scope, revision=pin.revision,
                                   request_id=context.request_id, previous_entry_id=entry_id)
            with self._lock:
                if epoch != self._epoch or authority is not self._authority:
                    raise AuthorityError('SOURCE_CONFIGURATION_CHANGED')
                payload = json.loads(bound.projection)
                if (type(payload) is not dict or set(payload) != {'table', 'layout'}
                        or any(type(payload[k]) is not str for k in payload)):
                    raise AuthorityError('PROJECTION_UNCONFIRMED')
                # Validate the encoding before admitting either derived part.
                for value in payload.values():
                    b64decode(value, validate=True)
                result.update(source_status='PDF_HASH_MATCH_AT_VALIDATION',
                              validated_at=bound.validated_at, pdf_sha256=pin.pdf_sha256,
                              table=payload['table'], layout=payload['layout'])
        except AuthorityError as exc:
            result['reason'] = exc.reason
        except (ValueError, TypeError, UnicodeError, json.JSONDecodeError):
            result['reason'] = 'PROJECTION_UNCONFIRMED'
        result['response_binding_sha256'] = digest(result)
        return result
