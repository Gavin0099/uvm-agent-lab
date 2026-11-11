"""Read-only query API composing the real retrieval and evidence-only stages."""
import re
import time

from gv100h.spec_qa.frozen_corpus.receipt_bound_corpus import DEFAULT_LOCK_PATH
from .contracts import window_from_record
from .packer import pack_evidence
from .planner import build_plan
from .pdf_layout import PdfLayout
from .search import EvidenceSearch
from .source_localization import SourceLocalization, section_display
from .supplement_gate import SupplementGate

_PAGE = re.compile(r'p\.(\d+)')


class EvidenceService:
    """Caller supplies a question/scope, never source records or an owned context."""

    def __init__(self):
        start = time.perf_counter()
        self.search = EvidenceSearch()
        self.layout = PdfLayout()
        self.supplements = SupplementGate(self.layout)
        self.localization = SourceLocalization.load()
        self.localization.verify_against_lock(DEFAULT_LOCK_PATH)
        self.startup_seconds = time.perf_counter() - start

    def _localize_sections(self, records, context):
        """Display-only localized sections keyed by chunk_id; window records and `section` stay frozen."""
        localization, display = {}, {}
        for record in records:
            source = context.source(record['chunk_id'])
            match = _PAGE.fullmatch(source.page_or_anchor)
            page = int(match.group(1)) if match else -1
            found = self.localization.localize(source.source_id, page,
                                               source.content, source.section)
            localization[record['chunk_id']] = found
            display[record['chunk_id']] = section_display(found)
        return localization, display

    def query(self, question, *, scope='usb20'):
        start = time.perf_counter()
        result, context = self.search.prepare(question, scope=scope)
        result['pipeline'] = ['existing_retriever', 'exact_windows', 'candidate_plan',
                              'candidate_conditions', 'conservative_packer']
        result['startup_seconds'] = self.startup_seconds
        result['retrieval_seconds'] = result['elapsed_seconds']
        if context is None:
            result.update(plan=None, bundle=None, conditions=None, pdf_layout=None)
            result['pipeline'] = ['source_scope_check']
        else:
            windows = [window_from_record(w, context) for w in result['evidence']]
            bundle = pack_evidence(context, windows, corpus_chunks=self.search.corpus.chunks)
            packed = [window_from_record(w, context) for w in bundle['evidence']]
            plan = build_plan(context, packed)
            result['baseline'] = {'evidence': result['evidence'],
                                  'source_structure': result.pop('source_structure')}
            result.update(evidence=bundle['evidence'], plan=plan.as_record(),
                          conditions=bundle['conditions'], bundle=bundle)
            result['unconfirmed'].extend(bundle['unconfirmed'])
            result['pdf_layout'] = self.supplements.annotate(context, packed)
            result['unconfirmed'].append(result['pdf_layout']['notice'])
            if result['pdf_layout']['source_authority']['status'] == 'WITHHELD':
                result['unconfirmed'].append('PDF 版面補充已撤回：未能確認與本次原文來源一致，請以原 PDF 核對。')
            result['section_localization'], result['section_display'] = self._localize_sections(
                result['evidence'], context)
            if not packed:
                result['unconfirmed'].append('目前未取得足以判斷的規格證據。')
            elif bundle['status'] == 'INCOMPLETE':
                result['unconfirmed'].append('證據包未完成；請展開原候選，表格家族或安全精簡目標仍有缺口。')
        result['elapsed_seconds'] = time.perf_counter() - start
        return result
