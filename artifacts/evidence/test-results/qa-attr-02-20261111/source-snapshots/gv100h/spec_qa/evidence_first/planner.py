"""Deterministic candidate needs, never an entailment/sufficiency judge."""
import re

from gv100h.spec_qa.operator_ui.free_question import TERMS
from gv100h.spec_qa.operator_ui.free_question_retrieval import context_query
from .contracts import EvidenceNeed, make_plan, window_from_record


def build_plan(context, windows):
    windows = tuple(windows)
    labels = [p.strip() for p in re.split(r'[？?；;\n]', context.question) if p.strip()]
    needs = []
    for label in labels:
        words = set(context_query(label, TERMS).split())
        # Lexical overlap only: candidate association, never DIRECT_SUPPORT.
        ids = tuple(w.evidence_id for w in windows if words.intersection(
            word.casefold() for word in re.findall(r'[A-Za-z][A-Za-z0-9_]*', w.quote)))
        needs.append(EvidenceNeed(label, ids, 'FOUND_CANDIDATE' if ids else 'UNRESOLVED'))
    return make_plan(context, windows, needs)


def plan_prepared(result, context):
    """Internal adapter: recheck every public window against the owned context."""
    if context is None:
        if result.get('evidence'):
            raise ValueError('Evidence without owned source context')
        return None
    if (result.get('request_id') != context.request_id or result.get('question') != context.question
            or result.get('scope') != context.scope):
        raise ValueError('Prepared result belongs to another query')
    windows = tuple(window_from_record(w, context) for w in result['evidence'])
    return build_plan(context, windows)
