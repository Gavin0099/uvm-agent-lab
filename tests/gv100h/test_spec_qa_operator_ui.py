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
from gv100h.spec_qa.operator_ui.fixtures import (
    FIXTURE_DOCUMENT,
    FIXTURE_ID_PREFIX,
    FIXTURES,
    get_fixture,
)
from gv100h.spec_qa.operator_ui.server import OperatorUIHandler
from gv100h.spec_qa.retrieval.governed_retriever import GovernedSpecRetriever


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


def _fixture_evidence_ids(resp):
    ids = set(resp.evidence_ids)
    ids.update(citation.evidence_id for citation in resp.citations)
    for bound in resp.claim_evidence_ids:
        ids.update(bound)
    return ids


def _production_evidence_ids():
    ids = {ev.evidence_id for ev in GovernedSpecRetriever.EVIDENCE_REGISTRY}
    ids.update(be.evidence_id for be in GovernedSpecRetriever.BOUNDARY_EVIDENCE_REGISTRY)
    return ids


@pytest.mark.unit
@pytest.mark.parametrize("name", ["answered", "abstain", "conflict"])
def test_fixtures_satisfy_grounded_answer_contract(name):
    resp = get_fixture(name)
    grounded = _as_grounded(resp)
    assert grounded.status == resp.status


@pytest.mark.unit
def test_fixture_evidence_ids_are_synthetic_and_disjoint_from_production():
    production_ids = _production_evidence_ids()
    for name, resp in FIXTURES.items():
        fixture_ids = _fixture_evidence_ids(resp)
        assert fixture_ids, name
        assert all(evidence_id.startswith(FIXTURE_ID_PREFIX) for evidence_id in fixture_ids), (
            name,
            fixture_ids,
        )
        overlap = fixture_ids & production_ids
        assert overlap == set(), (name, overlap)
        for citation in resp.citations:
            if citation.citation_kind == "normative":
                assert citation.document == FIXTURE_DOCUMENT
                assert citation.revision == "synthetic-v1"


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
    ui_dir = OperatorUIHandler.__init__.__globals__["UI_DIR"]
    html = (ui_dir / "index.html").read_text(encoding="utf-8")
    assert "Operator UI / development shell" in html
    assert "not POC-1 qualification" in html
    assert "explicit_cross_scope" in html
    assert "Fixture mode ignores query" in html
    assert "DATA SOURCE" in html
    assert 'id="dataSource"' in html
    assert "單一範圍" in html
    assert "跨規格範圍" in html
    assert "範例資料" in html
    assert "實際查詢服務" in html
    assert "正常回答" in html
    assert ">single_scope<" not in html
    assert ">answered<" not in html
    assert "開發模式" in html
    assert "判定代碼" in html
    assert "邊界代碼" not in html


@pytest.mark.unit
def test_html_shell_uses_ask_answer_source_hierarchy():
    ui_dir = OperatorUIHandler.__init__.__globals__["UI_DIR"]
    html = (ui_dir / "index.html").read_text(encoding="utf-8")
    css = (ui_dir / "styles.css").read_text(encoding="utf-8")
    assert 'id="advancedFold"' in html
    assert 'id="evidenceFold"' in html
    assert 'id="governanceFold"' in html
    assert 'id="sourceLine"' in html
    assert 'id="askBtn"' in html
    assert "class=\"workbench\"" in html or "class='workbench'" in html
    assert "輸入 USB 規格問題後，這裡會顯示有依據的回答。" in html
    assert "進階設定" in html
    assert "查看引用原文" in html
    assert "技術詳細資訊" in html
    assert "預覽範例" in html
    assert "USB 3.x Hub Class 的 PORT_POWER feature selector 值是多少？" in html
    assert "下游埠可以在哪些 link state 發出 Warm Reset？" not in html
    assert 'id="developerCitations"' in html
    assert 'id="fixtureIgnoreHint"' in html
    assert html.index('id="governanceFold"') < html.index('id="fixtureIgnoreHint"')
    assert "以可追溯來源詢問 USB 規格。" in html
    assert "證據明細" not in html
    assert "邊界與治理" not in html
    assert ".card" in css
    assert "--space-1:" in css
    assert "appearance: none" in css
    assert "Inter" in css or "Geist" in css
    assert "Iowan Old Style" not in css
    ask_at = html.index('id="askHeading"')
    answer_at = html.index('id="answerHeading"')
    source_at = html.index('id="sourceLine"')
    advanced_at = html.index('id="advancedFold"')
    evidence_at = html.index('id="evidenceFold"')
    governance_at = html.index('id="governanceFold"')
    data_source_at = html.index("DATA SOURCE")
    assert ask_at < answer_at < source_at
    assert ask_at < advanced_at < answer_at
    assert answer_at < evidence_at < governance_at
    assert data_source_at > governance_at
    assert ".workbench" in css
    assert ".paper" in css
    assert ".layout" not in css
    assert "--paper:" in css
    assert "#0b1020" not in css


@pytest.mark.unit
def test_app_js_renders_response_as_text_not_html():
    js = (OperatorUIHandler.__init__.__globals__["UI_DIR"] / "app.js").read_text(encoding="utf-8")
    assert "innerHTML" not in js
    assert "createElement" in js
    assert "textContent" in js
    assert "Query is NOT evaluated." in js
    assert "GovernedQAService" in js
    assert "evidenceSummary" in js
    assert "askBtn.disabled" in js
    assert "sourceLine" in js
    assert "developerCitations" in js
    assert "USB 3.x Hub Class 的 PORT_POWER feature selector 值為 8（0x0008）。" in js
    assert "範例回答：" not in js
    assert "governanceFold" in js
    assert "shouldOpenGovernance" in js
    assert "FIXTURE_QUESTIONS" in js
    assert "預覽範例" in js
    assert 'parts.join(" · ")' in js
    assert "權威來源" in js
    assert "RETRIEVAL_HINT" in js
    assert "超出目前範圍" in js
    assert "衝突來源" in js
    assert "AUTHORITY_MISMATCH" in js
    assert "uiKind" in js
    assert "範例來源：" in js
    assert "PORT_POWER feature selector 值為 8（0x0008）。" in js
    assert "Phase 1 corpus" in js
    assert "allowedScopesField" in js
    assert "boundaryBlock" in js
    assert "USB4 Specification 未包含於目前可查詢的 Phase 1 corpus。" in js
    assert "2 個模擬來源" in js
    assert "模擬：" in js
    assert "simulatedSpecName" in js
    assert "PORT_POWER 被視為權威性的 Hub Class selector，值為 8。" in js
    assert "目前展示的來源彼此衝突" in js
    assert "範例來源 A 將" not in js
    assert "USB 2.0 Hub Specification" in js
    assert "resetResultView" in js
    assert "allowedEvidenceScopes" in js
    assert "isUsb4Scope" in js
    assert "out_of_scope_usb4" in js
    assert "這次查詢超出目前可認證範圍" in js
    assert "目前缺少足以支持結論的證據，因此暫不提供結論。" in js
    assert "Phase 1 corpus · ${view.scope" not in js


@pytest.mark.unit
def test_adapter_fixture_path_does_not_construct_service(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("GovernedQAService must not be constructed in fixture mode")

    monkeypatch.setattr(
        "gv100h.spec_qa.operator_ui.adapter.GovernedQAService",
        boom,
    )
    adapter = OperatorQAAdapter()
    view = adapter.ask("Warm Reset 可以在哪些 state 發出？", source="fixture", fixture="answered")
    assert view.source == "fixture"
    assert view.status == "answer"


@pytest.mark.unit
def test_api_qa_returns_fixture_payload():
    from http.server import HTTPServer

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
        assert payload["source"] == "fixture"
        assert payload["citations"][0]["pdf_href"] is None
        assert payload["citations"][0]["has_pdf_anchor"] is False
    finally:
        httpd.shutdown()
        httpd.server_close()
