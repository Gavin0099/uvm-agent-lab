import pytest
from retrieval.canonical.retriever import CanonicalSpecRetriever
from retrieval.bm25.retriever import BM25Retriever
from retrieval.evaluator import Gate1RetrievalEvaluator


def test_canonical_retriever_filters_unapproved_drafts():
    retriever = CanonicalSpecRetriever(spec_dir="fixtures/synthetic-spec")
    
    # Query matching draft text but without allow_drafts flag
    hits = retriever.query("USB3 Warm Reset 20 clock cycles draft proposal", top_k=3, allow_drafts=False)
    
    for h in hits:
        assert h["authority"] == "authoritative", f"Draft doc '{h['file']}' should not be returned"


def test_canonical_retriever_enforces_customer_tier_boundaries():
    retriever = CanonicalSpecRetriever(spec_dir="fixtures/synthetic-spec")
    
    # Standard caller without Tier-A permissions
    hits_unauth = retriever.query(
        "Tier-A proprietary register secret key access",
        top_k=3,
        caller_customer_tier="tier_1_partner"
    )
    for h in hits_unauth:
        assert h["customer_tier"] != "tier_a_partner_restricted", "Restricted customer spec leaked to standard tier!"

    # Authorized Tier-A caller
    hits_auth = retriever.query(
        "Tier-A proprietary register secret key access",
        top_k=3,
        caller_customer_tier="tier_a_partner_restricted"
    )
    assert any(h["customer_tier"] == "tier_a_partner_restricted" for h in hits_auth), "Authorized caller could not retrieve Tier-A spec!"


def test_gate1_evaluator_runs_all_15_queries():
    evaluator = Gate1RetrievalEvaluator()
    summary = evaluator.evaluate()

    assert "spec-reference-kit" in summary
    assert "bm25" in summary
    assert "vector_rag" in summary
    assert "hybrid" in summary

    # Gate 1 Exit criteria for spec-reference-kit
    srk = summary["spec-reference-kit"]
    assert srk["queries_evaluated"] == 15
    assert srk["recall@1"] >= 90.0
    assert srk["wrong_version_rate"] == 0.0
    assert srk["customer_leak_rate"] == 0.0
