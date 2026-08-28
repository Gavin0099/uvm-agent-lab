"""Operator UI shell for the frozen QAResponse contract.

This package is Machine B in the parallel split:
PDF/RAG may enrich citations later; this UI must not invent retrieval.
"""

from gv100h.spec_qa.operator_ui.contract import (
    FROZEN_QA_RESPONSE_FIELDS,
    OperatorQAView,
    to_operator_view,
)

__all__ = [
    "FROZEN_QA_RESPONSE_FIELDS",
    "OperatorQAView",
    "to_operator_view",
]
