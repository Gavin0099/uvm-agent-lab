"""Opt-in CPU search; reuses the existing owned loader, Retriever and packer.

No prompt construction, typed-question profile, model runtime, external source,
benchmark manifest, ledger or production host is used.
"""
import time
import unicodedata
import uuid
import re

from gv100h.spec_qa.operator_ui.trial_runtime import load_corpus
from gv100h.spec_qa.operator_ui.free_question import TERMS, validate_question
from gv100h.spec_qa.operator_ui.table_identity_candidate_v0_2 import resolve_exact_evidence
from gv100h.spec_qa.retrieval.real_corpus_retriever import GovernedChunkBM25Retriever
from .contracts import RequestContext, Source
from .extractor import extract_windows
from .candidates import retrieve_candidates
from .query_guards import requested_revisions, revision_key, requested_identifiers, identifier_tokens
from dataclasses import asdict
from gv100h.spec_qa.retrieval.table_family_pack import table_families

SCOPES = {'usb20': frozenset({'usb20_fw', 'usb20_se'}),
          'usb32': frozenset({'usb32'}),
          'superspeed_hub_lvs': frozenset({'superspeed_hub_lvs'})}
VERSIONS = {'usb20': {'2', '2.0'}, 'usb32': {'3.2'},
            'superspeed_hub_lvs': {'3', '3.0', '3.1', '3.2'}}
_VERSION = re.compile(r'(?<![a-z0-9_])usb[\s-]*(?:v(?:ersion)?[\s-]*)?([0-9]+(?:\s*\.\s*(?:[0-9]+|x))*)')
NOTICE = '以下為既有凍結 USB Corpus 中身分與原文已核對的候選證據。'
UNCONFIRMED = '尚未驗證這些條文是否足以回答問題；本流程不產生工程結論。'


def requested_versions(question):
    """Normalize version spelling only; source text/question stay untouched.

    Unicode dash punctuation plus soft hyphen/minus may separate USB/version.
    The ASCII identifier boundary prevents matching descriptor field bcdUSB.
    """
    text = unicodedata.normalize('NFKC', question).casefold()
    text = ''.join('-' if unicodedata.category(ch) == 'Pd' or ch in '\u00ad\u2212'
                   else ch for ch in text)
    return {re.sub(r'\s+', '', m.group(1)) for m in _VERSION.finditer(text)}


class EvidenceSearch:
    def __init__(self):
        # This existing function checks the sealed snapshot and all corpus pins.
        self.corpus = load_corpus()
        self.retrievers = {}
        self.identifier_vocabularies = {}

    def _retriever(self, scope, *, revision=None):
        if scope not in SCOPES:
            raise ValueError('Unknown source scope')
        key = scope if revision is None else (scope, revision)
        if key not in self.retrievers:
            chunks = tuple(c for c in self.corpus.chunks if c.source_id in SCOPES[scope]
                           and (revision is None or revision_key(c.revision) == revision))
            self.retrievers[key] = GovernedChunkBM25Retriever(chunks)
        return self.retrievers[key]

    def prepare(self, question, *, scope='usb20'):
        """Return public projection and its owned context for internal stages."""
        start = time.perf_counter()
        question = validate_question(question)
        if scope not in SCOPES:
            raise ValueError('Unknown source scope')
        request_id = uuid.uuid4().hex
        versions = requested_versions(question)
        base = {'request_id': request_id, 'question': question, 'scope': scope,
            'notice': NOTICE, 'unconfirmed': [UNCONFIRMED,
                '來源是已封存的原文快照；原文未改，尚未進行真人語意驗收。'],
            'answer': None, 'semantic_support_status': 'NOT_REVIEWED',
            'overall_answer_sufficiency': 'NOT_ASSESSED', 'models_loaded': 0,
            'generations': 0, 'evidence': [], 'corpus_sha256': self.corpus.corpus_sha256}
        if versions - VERSIONS[scope]:
            base.update(status='no_reliable_evidence', reason='requested_version_outside_selected_source_scope',
                searched_scope=scope, retrieval_trace={'retriever_called': False},
                elapsed_seconds=time.perf_counter()-start)
            return base, None
        revisions = requested_revisions(question)
        available = {revision_key(c.revision) for c in self.corpus.chunks
                     if c.source_id in SCOPES[scope]} - {None}
        if revisions and (len(revisions) != 1 or not revisions <= available):
            base['unconfirmed'].append('要求的文件修訂版未完整收錄；不以其他修訂版替代。請核對所選來源。')
            base.update(status='no_reliable_evidence', reason='requested_document_revision_unavailable',
                searched_scope=scope, retrieval_trace={'retriever_called': False,
                    'requested_document_revisions': sorted(revisions),
                    'available_document_revisions': sorted(available)},
                elapsed_seconds=time.perf_counter()-start)
            return base, None
        identifiers = requested_identifiers(question)
        if identifiers:
            key = (scope, tuple(sorted(revisions)))
            if key not in self.identifier_vocabularies:
                vocabulary = set()
                for chunk in self.corpus.chunks:
                    if chunk.source_id in SCOPES[scope] and (not revisions or revision_key(chunk.revision) in revisions):
                        vocabulary.update(identifier_tokens(chunk.content))
                self.identifier_vocabularies[key] = frozenset(vocabulary)
            missing = identifiers - self.identifier_vocabularies[key]
            if missing:
                base['unconfirmed'].append('所選來源未找到精確識別字：' + '、'.join(sorted(missing))
                    + '。請核對完整拼寫與來源範圍；這不表示其他規格中不存在。')
                base.update(status='no_reliable_evidence', reason='exact_identifier_not_found',
                    searched_scope=scope, retrieval_trace={'retriever_called': False,
                        'requested_identifiers': sorted(identifiers), 'missing_identifiers': sorted(missing)},
                    elapsed_seconds=time.perf_counter()-start)
                return base, None
        retriever = (self._retriever(scope, revision=next(iter(revisions)))
                     if revisions else self._retriever(scope))
        packet = retrieve_candidates(retriever, question, TERMS, max_chars=39739, max_chunks=20)
        if packet.get('topic_selection', {}).get('notice'):
            base['unconfirmed'].append(packet['topic_selection']['notice'])
        if packet.get('coverage_selection', {}).get('notice'):
            base['unconfirmed'].append(packet['coverage_selection']['notice'])
        records = packet['evidence']
        # Never publish source metadata or source text from caller-authored data.
        resolved = resolve_exact_evidence([r['chunk_id'] for r in records],
            sent_evidence=records, trusted_chunks=retriever.chunks) if records else {}
        sources = tuple(Source.from_record(resolved[r['chunk_id']].model_dump(mode='json')) for r in records)
        context = RequestContext(request_id, question, scope, self.corpus.corpus_sha256, sources)
        _, membership = table_families(retriever.chunks)
        windows, structures = extract_windows(context, query_terms=packet['context_query'].split(),
            family_by_id=membership)
        if identifiers:
            selected_tokens = set().union(*(identifier_tokens(w.quote) for w in windows))
            if identifiers - selected_tokens:
                base['unconfirmed'].append('精確識別字存在於所選來源，但本次候選原文未完整涵蓋；以下詞彙候選不可當成該識別字的存在證據，請縮小問題範圍。')
        base.update(status='evidence_preview' if windows else 'no_reliable_evidence',
            reason='source_identity_only' if windows else 'no_matching_source',
            evidence=[w.as_record() for w in windows], request_binding_sha256=context.binding,
            source_structure=structures, original_sources=[asdict(s) for s in context.sources],
            retrieval_corpus_sha256=retriever.corpus_sha256,
            retrieval_trace={'retriever_called': True, 'retriever_class': 'GovernedChunkBM25Retriever',
                **{k: v for k, v in packet.items() if k != 'evidence'}},
            searched_scope=scope, elapsed_seconds=time.perf_counter()-start)
        return base, context

    def search(self, question, *, scope='usb20'):
        return self.prepare(question, scope=scope)[0]
