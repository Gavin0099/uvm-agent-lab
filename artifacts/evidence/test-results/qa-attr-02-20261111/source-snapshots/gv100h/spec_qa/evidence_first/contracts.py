"""Pure request-bound windows over backend-owned original source records.

Source identity here means exact identity/text against the owned frozen corpus.
It does not assert relevance, semantic support, sufficiency, or current PDF QA.
"""
from dataclasses import asdict, dataclass, fields
import hashlib
import json
import re
from typing import Mapping

VERSION = 'evidence-first.window.v1'


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class Source:
    chunk_id: str
    source_id: str
    document: str
    revision: str
    section: str
    page_or_anchor: str
    content_sha256: str
    content: str
    chunk_kind: str

    @classmethod
    def from_record(cls, record: Mapping):
        source = cls(**{f.name: record[f.name] for f in fields(cls)})
        if any(not isinstance(getattr(source, f.name), str) or not getattr(source, f.name)
               for f in fields(cls)):
            raise ValueError('Nonempty source fields required')
        if hashlib.sha256(source.content.encode('utf-8')).hexdigest() != source.content_sha256:
            raise ValueError('Source content hash mismatch')
        return source


@dataclass(frozen=True)
class RequestContext:
    """Owned in memory, never accepted from a caller JSON or a model response."""
    request_id: str
    question: str
    scope: str
    corpus_sha256: str
    sources: tuple[Source, ...]

    def __post_init__(self):
        if not isinstance(self.request_id, str) or not re.fullmatch('[0-9a-f]{32}', self.request_id):
            raise ValueError('Invalid request identity')
        if not isinstance(self.question, str) or not self.question.strip():
            raise ValueError('Question required')
        if not isinstance(self.scope, str) or not self.scope:
            raise ValueError('Source scope required')
        if not isinstance(self.corpus_sha256, str) or not re.fullmatch('[0-9a-f]{64}', self.corpus_sha256):
            raise ValueError('Corpus digest required')
        if type(self.sources) is not tuple or any(type(s) is not Source for s in self.sources):
            raise ValueError('Owned immutable sources required')
        if len({s.chunk_id for s in self.sources}) != len(self.sources):
            raise ValueError('Duplicate source identity')
        for source in self.sources:
            Source.from_record(asdict(source))

    @property
    def binding(self):
        return digest(asdict(self))

    def source(self, chunk_id):
        for source in self.sources:
            if source.chunk_id == chunk_id:
                return source
        raise ValueError('Source outside this request')


@dataclass(frozen=True)
class EvidenceWindow:
    request_id: str
    request_binding_sha256: str
    evidence_id: str
    chunk_id: str
    source_id: str
    document: str
    revision: str
    section: str
    page_or_anchor: str
    content_sha256: str
    start: int
    end: int
    byte_start: int
    byte_end: int
    quote: str
    contract_version: str = VERSION
    offset_unit: str = 'unicode_codepoint_half_open'
    normalization: str = 'none'
    source_identity_verified: bool = True
    semantic_support_status: str = 'NOT_REVIEWED'

    def as_record(self):
        return asdict(self)


def _evidence_id(context, chunk_id, start, end):
    return context.request_id + ':' + digest([chunk_id, start, end])


def verify_window(window: EvidenceWindow, context: RequestContext):
    if type(window) is not EvidenceWindow or type(context) is not RequestContext:
        raise ValueError('Window and owned request context required')
    if (window.request_id != context.request_id
            or window.request_binding_sha256 != context.binding):
        raise ValueError('Foreign request, question, corpus or source snapshot')
    source = context.source(window.chunk_id)
    for name in ['source_id', 'document', 'revision', 'section', 'page_or_anchor', 'content_sha256']:
        if getattr(window, name) != getattr(source, name):
            raise ValueError('Source identity mismatch')
    if any(type(getattr(window, name)) is not int for name in ['start', 'end', 'byte_start', 'byte_end']):
        raise ValueError('Integer source offsets required')
    if not 0 <= window.start < window.end <= len(source.content):
        raise ValueError('Source range outside original chunk')
    if source.content[window.start:window.end] != window.quote:
        raise ValueError('Quote is not a continuous original source span')
    if (window.byte_start != len(source.content[:window.start].encode('utf-8'))
            or window.byte_end != len(source.content[:window.end].encode('utf-8'))):
        raise ValueError('UTF-8 byte offsets mismatch')
    if window.evidence_id != _evidence_id(context, source.chunk_id, window.start, window.end):
        raise ValueError('Evidence alias mismatch')
    if (window.contract_version != VERSION
            or window.offset_unit != 'unicode_codepoint_half_open'
            or window.normalization != 'none'
            or window.source_identity_verified is not True
            or window.semantic_support_status != 'NOT_REVIEWED'):
        raise ValueError('Unsupported contract or unreviewed semantic assertion')
    return window


def make_window(context: RequestContext, chunk_id: str, start=0, end=None):
    source = context.source(chunk_id)
    if end is None:
        end = len(source.content)
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(source.content):
        raise ValueError('Invalid continuous span')
    window = EvidenceWindow(context.request_id, context.binding,
        _evidence_id(context, chunk_id, start, end), source.chunk_id, source.source_id,
        source.document, source.revision, source.section, source.page_or_anchor,
        source.content_sha256, start, end, len(source.content[:start].encode('utf-8')),
        len(source.content[:end].encode('utf-8')), source.content[start:end])
    return verify_window(window, context)


def window_from_record(record, context):
    if not isinstance(record, dict) or set(record) != {f.name for f in fields(EvidenceWindow)}:
        raise ValueError('Exact evidence-window record required')
    return verify_window(EvidenceWindow(**record), context)


def full_windows(context):
    return tuple(make_window(context, source.chunk_id) for source in context.sources)


@dataclass(frozen=True)
class EvidenceNeed:
    label: str
    evidence_ids: tuple[str, ...]
    status: str = 'UNRESOLVED'
    semantic_support_status: str = 'NOT_REVIEWED'


@dataclass(frozen=True)
class EvidencePlan:
    request_id: str
    request_binding_sha256: str
    windows: tuple[EvidenceWindow, ...]
    needs: tuple[EvidenceNeed, ...]
    overall_answer_sufficiency: str = 'NOT_ASSESSED'
    semantic_support_status: str = 'NOT_REVIEWED'

    def as_record(self):
        # Public JSON DTO arrays, never a serialized owned RequestContext.
        return {'request_id': self.request_id,
            'request_binding_sha256': self.request_binding_sha256,
            'windows': [w.as_record() for w in self.windows],
            'needs': [dict(asdict(n), evidence_ids=list(n.evidence_ids)) for n in self.needs],
            'overall_answer_sufficiency': self.overall_answer_sufficiency,
            'semantic_support_status': self.semantic_support_status}


def verify_plan(plan: EvidencePlan, context: RequestContext):
    if type(plan) is not EvidencePlan or type(context) is not RequestContext:
        raise ValueError('Plan and owned context required')
    if plan.request_id != context.request_id or plan.request_binding_sha256 != context.binding:
        raise ValueError('Foreign plan request or source snapshot')
    if type(plan.windows) is not tuple or type(plan.needs) is not tuple:
        raise ValueError('Immutable plan collections required')
    if plan.overall_answer_sufficiency != 'NOT_ASSESSED' or plan.semantic_support_status != 'NOT_REVIEWED':
        raise ValueError('Unreviewed plan cannot assert semantic sufficiency')
    ids = set()
    for window in plan.windows:
        verify_window(window, context)
        if window.evidence_id in ids:
            raise ValueError('Duplicate plan window identity')
        ids.add(window.evidence_id)
    for need in plan.needs:
        if type(need) is not EvidenceNeed or not isinstance(need.label, str) or not need.label.strip():
            raise ValueError('Nonempty need label required')
        if (type(need.evidence_ids) is not tuple
                or any(not isinstance(i, str) or i not in ids for i in need.evidence_ids)
                or len(set(need.evidence_ids)) != len(need.evidence_ids)):
            raise ValueError('Need references outside current plan windows')
        if (not isinstance(need.status, str) or need.status not in {'FOUND_CANDIDATE', 'UNRESOLVED'}
                or (need.status == 'FOUND_CANDIDATE' and not need.evidence_ids)
                or need.semantic_support_status != 'NOT_REVIEWED'):
            raise ValueError('Need cannot assert unreviewed semantic support')
    return plan


def make_plan(context, windows=(), needs=()):
    return verify_plan(EvidencePlan(context.request_id, context.binding,
        tuple(windows), tuple(needs)), context)


def plan_from_record(record, context):
    if not isinstance(record, dict) or set(record) != {f.name for f in fields(EvidencePlan)}:
        raise ValueError('Exact evidence-plan record required')
    if type(record['windows']) is not list or type(record['needs']) is not list:
        raise ValueError('Plan DTO arrays required')
    windows = tuple(window_from_record(w, context) for w in record['windows'])
    needs = []
    for value in record['needs']:
        if (type(value) is not dict or set(value) != {f.name for f in fields(EvidenceNeed)}
                or type(value['evidence_ids']) is not list):
            raise ValueError('Exact evidence-need record required')
        needs.append(EvidenceNeed(**dict(value, evidence_ids=tuple(value['evidence_ids']))))
    return verify_plan(EvidencePlan(**dict(record, windows=windows, needs=tuple(needs))), context)
