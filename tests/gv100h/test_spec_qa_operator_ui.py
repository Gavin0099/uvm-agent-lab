import json
from http.client import HTTPConnection
from threading import Thread

import pytest

from gv100h.spec_qa.contracts.evidence_contract import GroundedAnswer
from gv100h.spec_qa.operator_ui.adapter import OperatorQAAdapter
from gv100h.spec_qa.operator_ui.contract import (
    ABSTAIN_EXPLAINER,
    CLAIM_CEILING,
    FROZEN_QA_RESPONSE_FIELDS,
    to_operator_view,
)
from gv100h.spec_qa.operator_ui.fixtures import get_fixture
from gv100h.spec_qa.operator_ui.server import OperatorUIHandler


def _as_grounded(resp):
    return GroundedAnswer(
        status=resp.status,
        claims=list(resp.claims),
        claim_evidence_ids=[list(ids) for ids in resp.claim_evidence_ids],
        citations=list(resp.citations),
        scope=resp.scope,
        boundary=resp.boundary_code,
        evidence_ids=list(resp.evidence_ids),
    )


@pytest.mark.unit
@pytest.mark.parametrize("name", ["answered", "abstain", "conflict"])
def test_fixtures_satisfy_grounded_answer_contract(name):
    resp = get_fixture(name)
    grounded = _as_grounded(resp)
    assert grounded.status == resp.status


@pytest.mark.unit
def test_answered_view_shows_section_and_authority_badges_without_pdf_href():
    view = to_operator_view(get_fixture("answered"))
    assert view.status == "answer"
    assert view.citations[0].section == "10.16.2.1"
    assert view.citations[0].authority_level == "authoritative"
    assert view.citations[0].has_pdf_anchor is False
    assert view.citations[0].pdf_href is None
    assert CLAIM_CEILING in view.claim_ceiling


@pytest.mark.unit
def test_abstain_view_explains_governance_not_ignorance():
    view = to_operator_view(get_fixture("abstain"))
    assert view.status == "abstain"
    assert view.boundary_code == "OUT_OF_SCOPE"
    assert ABSTAIN_EXPLAINER in view.boundary_reason
    assert view.citations[0].has_pdf_anchor is False


@pytest.mark.unit
def test_conflict_view_keeps_boundary_code():
    view = to_operator_view(get_fixture("conflict"))
    assert view.status == "conflict"
    assert view.boundary_code == "AUTHORITY_MISMATCH"
    assert view.is_abstain is True
    assert len(view.citations) == 2


@pytest.mark.unit
def test_frozen_fields_are_explicit():
    assert FROZEN_QA_RESPONSE_FIELDS == (
        "status",
        "answer",
        "claims",
        "citations",
        "boundary_code",
        "scope",
        "claim_evidence_ids",
        "evidence_ids",
        "is_abstain",
    )


@pytest.mark.unit
def test_adapter_fixture_path_does_not_require_question():
    adapter = OperatorQAAdapter()
    view = adapter.ask("", source="fixture", fixture="abstain")
    assert view.status == "abstain"
    assert view.source == "fixture"


@pytest.mark.unit
def test_html_shell_is_labeled_operator_ui():
    html = (OperatorUIHandler.__init__.__globals__["UI_DIR"] / "index.html").read_text(encoding="utf-8")
    assert "Operator UI / development shell" in html
    assert "not POC-1 qualification" in html
    assert "explicit_cross_scope" in html


@pytest.mark.unit
def test_api_qa_returns_fixture_payload(monkeypatch):
    from http.server import HTTPServer
    from gv100h.spec_qa.operator_ui import server as ui_server

    adapter = OperatorQAAdapter()
    httpd = HTTPServer(("127.0.0.1", 0), lambda *args, **kwargs: OperatorUIHandler(*args, adapter=adapter, **kwargs))
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = httpd.server_address
        conn = HTTPConnection(host, port, timeout=5)
        conn.request(
            "POST",
            "/api/qa",
            body=json.dumps({"source": "fixture", "fixture": "answered", "question": "unused"}),
            headers={"Content-Type": "application/json"},
        )
        resp = conn.getresponse()
        payload = json.loads(resp.read().decode("utf-8"))
        assert resp.status == 200
        assert payload["status"] == "answer"
        assert payload["citations"][0]["pdf_href"] is None
        assert payload["citations"][0]["has_pdf_anchor"] is False
    finally:
        httpd.shutdown()
        httpd.server_close()
