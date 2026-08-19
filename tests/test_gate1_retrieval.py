import pytest
from retrieval.hybrid.retriever import GovernedLexicalHybridRetriever, HybridRetriever
from retrieval.canonical.retriever import CanonicalSpecRetriever
from retrieval.bm25.retriever import BM25Retriever
from retrieval.vector.retriever import TFCosineRetriever, VectorRetrieverStub
from retrieval.evaluator import Gate1RetrievalEvaluator


def test_gate1_retriever_names_describe_implemented_algorithms():
    assert VectorRetrieverStub is TFCosineRetriever
    assert HybridRetriever is GovernedLexicalHybridRetriever
    assert TFCosineRetriever.__doc__ and "not dense" in TFCosineRetriever.__doc__.lower()
    hybrid_doc = GovernedLexicalHybridRetriever.__doc__ or ""
    assert "not" in hybrid_doc.lower()
    assert "dense-plus-sparse" in hybrid_doc.lower()


class _DenseTestEncoder:
    def encode(self, texts, **kwargs):
        return [[1.0, 0.0] for _ in texts]


def test_gate1_dense_arm_is_explicit_opt_in():
    default = Gate1RetrievalEvaluator()
    assert not {
        "dense_embedding",
        "standard_dense_hybrid",
        "governed_dense_hybrid",
    }.intersection(default.retrievers)

    opt_in = Gate1RetrievalEvaluator(
        dense_model="test/fake-dense",
        dense_model_revision="test-revision",
        dense_encoder=_DenseTestEncoder(),
    )
    assert "dense_embedding" in opt_in.retrievers
    assert "standard_dense_hybrid" in opt_in.retrievers
    assert "governed_dense_hybrid" in opt_in.retrievers
    assert opt_in.retrievers["dense_embedding"].model_name == "test/fake-dense"
    assert opt_in.retrievers["dense_embedding"].model_revision == "test-revision"


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
    assert "tf_cosine" in summary
    assert "governed_lexical_hybrid" in summary
    assert "vector_rag" not in summary
    assert "hybrid" not in summary

    # Gate 1 Exit criteria for spec-reference-kit
    srk = summary["spec-reference-kit"]
    assert srk["queries_evaluated"] == 15
    assert srk["recall@1"] >= 90.0
    assert srk["wrong_version_rate"] == 0.0
    assert srk["customer_leak_rate"] == 0.0
