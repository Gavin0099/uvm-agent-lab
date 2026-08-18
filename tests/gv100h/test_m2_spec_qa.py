import pytest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gv100h.spec_qa.retrieval.governed_retriever import GovernedSpecRetriever
from gv100h.spec_qa.api.qa_service import GovernedQAService
from gv100h.spec_qa.evaluation.deterministic_evaluator import DeterministicSpecQAEvaluator


@pytest.mark.unit
def test_governed_retriever_query():
    retriever = GovernedSpecRetriever()
    results = retriever.query("PORT_POWER", target_scope="USB_3_X")
    assert len(results) > 0
    assert results[0].evidence_id == "USB3-FEAT-PORT_POWER"
    assert results[0].scope == "USB_3_X"


@pytest.mark.unit
def test_governed_qa_service_abstention():
    service = GovernedQAService()
    resp = service.answer_question("Windows xHCI driver internals")
    assert resp.is_abstain is True
    assert "無法支持" in resp.answer
    assert len(resp.cited_evidences) == 0


@pytest.mark.contract
def test_golden_30_deterministic_benchmark():
    evaluator = DeterministicSpecQAEvaluator()
    service = GovernedQAService()

    def mock_agent_call(query_text: str, target_scope: str):
        resp = service.answer_question(query_text, target_scope)
        cited_ids = [ev.evidence_id for ev in resp.cited_evidences]
        return resp.answer, cited_ids

    result = evaluator.run_benchmark(mock_agent_call)
    assert result.total_questions == 30
    assert result.cat_a_accuracy >= 90.0
    assert result.cat_b_version_scope_accuracy == 100.0
    assert result.cat_c_abstain_rate >= 95.0
    assert result.fabricated_citations_count == 0
    assert result.authority_violations_count == 0
    assert result.all_gates_passed is True
