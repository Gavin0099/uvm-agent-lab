"""Isolated PDF source freshness and projection-cache candidate.

This module is not wired to search, the preview, or the official source
contract. Its caller must supply pins from a trusted source registry, and a
separately reviewed projection builder. A hash match is not geometry review.

Each bind reads and hashes the current file. Parsed projections may be cached,
but their prior source status cannot be reused. Verification describes the
instant of the last completed read, not continued availability after return.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import stat
from threading import Condition, Lock
from time import monotonic

MAX_SOURCE_BYTES = 64 * 1024 * 1024

class AuthorityError(ValueError):
    """Fail closed without disclosing a private source path."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class SourcePin:
    source_id: str
    scope: str
    revision: str
    path: Path
    pdf_sha256: str

    def __post_init__(self):
        if any(not isinstance(v, str) or not v for v in
               (self.source_id, self.scope, self.revision)):
            raise ValueError('invalid source identity')
        if not isinstance(self.path, Path) or not self.path.is_absolute():
            raise ValueError('source path must be an absolute trusted path')
        if not re.fullmatch(r'[0-9a-f]{64}', self.pdf_sha256):
            raise ValueError('invalid source hash')


@dataclass(frozen=True)
class BoundProjection:
    source_id: str
    scope: str
    revision: str
    request_id: str
    pdf_sha256: str
    projection: bytes
    projection_sha256: str
    entry_id: str
    binding_sha256: str
    validated_at: float
    source_status: str = 'PDF_HASH_MATCH_AT_VALIDATION'
    geometry_status: str = 'UNCONFIRMED'


@dataclass(frozen=True)
class _CacheEntry:
    data: bytes
    content_hash: str
    entry_id: str
    generation: int
    built_at: float


def _identity(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def _read_pinned(pin):
    """Read regular-file bytes, check path/descriptor identity and SHA-256.

    Refuse symlinks and non-regular files. Metadata is a race detector, never
    proof that the content matches the pin; the digest is always recomputed.
    """
    flags = os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_NOFOLLOW', 0)
    try:
        fd = os.open(pin.path, flags)
        with os.fdopen(fd, 'rb') as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_SOURCE_BYTES:
                raise AuthorityError('SOURCE_UNAVAILABLE')
            data = stream.read(MAX_SOURCE_BYTES + 1)
            after = os.fstat(stream.fileno())
            path_state = os.stat(pin.path, follow_symlinks=False)
        if not stat.S_ISREG(path_state.st_mode) or _identity(before) != _identity(after) or _identity(after) != _identity(path_state):
            raise AuthorityError('SOURCE_CHANGED_DURING_READ')
    except OSError as exc:
        raise AuthorityError('SOURCE_UNAVAILABLE') from exc
    if len(data) > MAX_SOURCE_BYTES:
        raise AuthorityError('SOURCE_UNAVAILABLE')
    if sha256(data).hexdigest() != pin.pdf_sha256:
        raise AuthorityError('PDF_HASH_MISMATCH')
    return data, _identity(after)


def _assert_path_identity(pin, expected):
    try:
        current = os.stat(pin.path, follow_symlinks=False)
    except OSError as exc:
        raise AuthorityError('SOURCE_UNAVAILABLE') from exc
    if not stat.S_ISREG(current.st_mode) or _identity(current) != expected:
        raise AuthorityError('SOURCE_CHANGED_DURING_READ')


class PdfSourceAuthority:
    """Own source pins, immutable cached projections, and revocation state.

    The builder receives exactly the SHA-verified bytes. It returns immutable
    bytes and does not certify their PDF geometry. Revocation and invalidation
    advance a generation so an in-flight builder cannot repopulate stale data.
    """

    def __init__(self, pins, builder, *, ttl_seconds=60.0, clock=monotonic):
        pins = tuple(pins)
        if (not pins or any(not isinstance(p, SourcePin) for p in pins)
                or len({p.source_id for p in pins}) != len(pins)):
            raise ValueError('pins must contain unique source identities')
        if not callable(builder) or not callable(clock):
            raise ValueError('builder and clock must be callable')
        if (not isinstance(ttl_seconds, (int, float)) or isinstance(ttl_seconds, bool)
                or not math.isfinite(ttl_seconds) or ttl_seconds <= 0):
            raise ValueError('invalid cache lifetime')
        self._pins = {p.source_id: p for p in pins}
        self._builder = builder
        self._ttl = float(ttl_seconds)
        self._clock = clock
        self._condition = Condition(Lock())
        self._generation = {p.source_id: 0 for p in pins}
        self._withdrawn = set()
        self._cache = {}
        self._inflight = set()
        self._serial = 0
        self._last_clock = None

    def _now(self):
        try:
            now = self._clock()
        except Exception as exc:
            for source_id in self._generation:
                self._generation[source_id] += 1
            self._cache.clear()
            self._condition.notify_all()
            raise AuthorityError('CLOCK_UNAVAILABLE') from exc
        if not isinstance(now, (int, float)) or isinstance(now, bool) or not math.isfinite(now):
            for source_id in self._generation:
                self._generation[source_id] += 1
            self._cache.clear()
            self._condition.notify_all()
            raise AuthorityError('CLOCK_UNAVAILABLE')
        now = float(now)
        if self._last_clock is not None and now < self._last_clock:
            for source_id in self._generation:
                self._generation[source_id] += 1
            self._cache.clear()
            self._condition.notify_all()
            self._last_clock = now
            raise AuthorityError('CLOCK_ROLLBACK')
        self._last_clock = now
        return now

    def _pin(self, source_id, scope, revision):
        pin = self._pins.get(source_id)
        if pin is None or pin.scope != scope or pin.revision != revision:
            raise AuthorityError('SOURCE_IDENTITY_MISMATCH')
        return pin

    def _invalidate_on_failure(self, source_id, generation):
        with self._condition:
            if self._generation[source_id] == generation:
                self._generation[source_id] += 1
                self._cache.pop(source_id, None)
                self._condition.notify_all()

    def invalidate(self, source_id):
        with self._condition:
            if source_id not in self._pins:
                raise AuthorityError('SOURCE_IDENTITY_MISMATCH')
            self._generation[source_id] += 1
            self._cache.pop(source_id, None)
            self._condition.notify_all()

    def withdraw(self, source_id):
        with self._condition:
            if source_id not in self._pins:
                raise AuthorityError('SOURCE_IDENTITY_MISMATCH')
            self._withdrawn.add(source_id)
            self._generation[source_id] += 1
            self._cache.pop(source_id, None)
            self._condition.notify_all()

    def reinstate(self, source_id):
        """Restore only the original trusted pin; old cached entries stay invalid."""
        with self._condition:
            if source_id not in self._pins:
                raise AuthorityError('SOURCE_IDENTITY_MISMATCH')
            self._withdrawn.discard(source_id)
            self._generation[source_id] += 1
            self._cache.pop(source_id, None)
            self._condition.notify_all()

    def bind(self, source_id, *, scope, revision, request_id, previous_entry_id=None):
        """Return projection bytes only after current source and request checks.

        Rebinding an old entry requires its ID to match a still-live cache entry;
        expiry, withdrawal, invalidation or a rebuild rejects that old ID.
        """
        if not isinstance(request_id, str) or not re.fullmatch(r'[0-9a-f]{32}', request_id):
            raise AuthorityError('INVALID_REQUEST_ID')
        pin = self._pin(source_id, scope, revision)
        while True:
            with self._condition:
                if source_id in self._withdrawn:
                    raise AuthorityError('SOURCE_WITHDRAWN')
                generation = self._generation[source_id]
            try:
                data, source_identity = _read_pinned(pin)
            except AuthorityError:
                self._invalidate_on_failure(source_id, generation)
                raise
            with self._condition:
                if source_id in self._withdrawn:
                    raise AuthorityError('SOURCE_WITHDRAWN')
                if self._generation[source_id] != generation:
                    raise AuthorityError('SOURCE_INVALIDATED')
                now = self._now()
                entry = self._cache.get(source_id)
                if entry is not None and entry.generation == generation and 0 <= now-entry.built_at < self._ttl:
                    try:
                        _assert_path_identity(pin, source_identity)
                    except AuthorityError:
                        self._generation[source_id] += 1
                        self._cache.pop(source_id, None)
                        self._condition.notify_all()
                        raise
                    return self._bind_entry(pin, entry, request_id, previous_entry_id, now)
                key = (source_id, generation)
                if key in self._inflight:
                    self._condition.wait()
                    continue  # A waiter must re-read current bytes before use.
                self._inflight.add(key)
            try:
                try:
                    projection = self._builder(data)
                    if type(projection) is not bytes:
                        raise AuthorityError('PROJECTION_UNCONFIRMED')
                except AuthorityError:
                    self._invalidate_on_failure(source_id, generation)
                    raise
                except Exception as exc:
                    self._invalidate_on_failure(source_id, generation)
                    raise AuthorityError('PROJECTION_UNCONFIRMED') from exc
                try:
                    _, source_identity = _read_pinned(pin)  # Revalidate after potentially slow parsing.
                except AuthorityError:
                    self._invalidate_on_failure(source_id, generation)
                    raise
                with self._condition:
                    if source_id in self._withdrawn:
                        raise AuthorityError('SOURCE_WITHDRAWN')
                    if self._generation[source_id] != generation:
                        raise AuthorityError('SOURCE_INVALIDATED')
                    try:
                        _assert_path_identity(pin, source_identity)
                    except AuthorityError:
                        self._generation[source_id] += 1
                        self._cache.pop(source_id, None)
                        self._condition.notify_all()
                        raise
                    now = self._now()
                    self._serial += 1
                    projection_hash = sha256(projection).hexdigest()
                    identifier = sha256(f'{source_id}:{generation}:{self._serial}:{projection_hash}'.encode()).hexdigest()
                    entry = _CacheEntry(projection, projection_hash, identifier, generation, now)
                    self._cache[source_id] = entry
                    return self._bind_entry(pin, entry, request_id, previous_entry_id, now)
            finally:
                with self._condition:
                    self._inflight.discard(key)
                    self._condition.notify_all()

    @staticmethod
    def _bind_entry(pin, entry, request_id, previous_entry_id, now):
        if previous_entry_id is not None and previous_entry_id != entry.entry_id:
            raise AuthorityError('STALE_PROJECTION')
        binding = {'source_id': pin.source_id, 'scope': pin.scope, 'revision': pin.revision,
                   'pdf_sha256': pin.pdf_sha256, 'projection_sha256': entry.content_hash,
                   'entry_id': entry.entry_id, 'request_id': request_id, 'validated_at': now}
        digest = sha256(json.dumps(binding, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        return BoundProjection(**binding, projection=entry.data, binding_sha256=digest)
