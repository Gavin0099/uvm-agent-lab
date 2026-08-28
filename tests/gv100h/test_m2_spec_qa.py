import copy
import hashlib
import pytest
import sys
import subprocess
from pathlib import Path
from types import SimpleNamespace
import yaml
from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gv100h.spec_qa.retrieval.governed_retriever import GovernedSpecRetriever
from gv100h.spec_qa.api.qa_service import GovernedQAService, QAResponse
from gv100h.spec_qa.contracts.evidence_contract import Citation, EvidenceContractError, GroundedAnswer
from gv100h.spec_qa.contracts.retrieval_policy import RetrievalPolicy, RetrievalPolicyError
from gv100h.spec_qa.contracts.poc1_acceptance_contract import (
    AcceptanceQuestion,
    CitationRequirements,
    GoldClaim,
    GoldOracle,
    GradingWeights,
)
from gv100h.spec_qa.evaluation.final_evaluator import FinalPOC1Evaluator
from gv100h.spec_qa.evaluation.deterministic_evaluator import DeterministicSpecQAEvaluator
from gv100h.coding_eval.governance_ab_runner import ABExperimentSummary
from gv100h.qualification.evaluator import QualificationPolicyEvaluator
from gv100h.spec_qa.contracts.corpus_binding_receipt import (
    CorpusBindingReceiptError,
    build_corpus_binding_receipt,
    load_corpus_binding_receipt,
    verify_corpus_binding_receipt,
)


@pytest.mark.unit
def test_governed_retriever_query():
    retriever = GovernedSpecRetriever()
    results = retriever.query(
        "PORT_POWER", retrieval_policy=RetrievalPolicy(answer_scope="USB_3_X")
    )
    assert len(results) > 0
    assert results[0].evidence_id == "USB3-FEAT-PORT_POWER"
    assert results[0].scope == "USB_3_X"


@pytest.mark.unit
def test_governed_retriever_abstains_when_only_scope_and_generic_words_match():
    # Regression for the "Warm Reset / tReset" danger: the query shares a
    # matching target_scope with USB_3_X evidence and mentions the bare word
    # "link" (from "link training"), but is not actually about
    # PORT_LINK_STATE or any other registered evidence topic. Neither scope
    # match alone nor a generic shared word may create a candidate; the
    # retriever must return no results so the caller abstains instead of
    # confidently citing irrelevant evidence.
    retriever = GovernedSpecRetriever()
    results = retriever.query(
        "USB 3.2 Warm Reset tReset link training 完成後最短最長時間是多少？",
        retrieval_policy=RetrievalPolicy(answer_scope="USB_3_X"),
    )
    assert results == []


@pytest.mark.unit
def test_governed_retriever_abstains_on_pure_scope_match_without_topic_signal():
    # A matching target_scope with zero topic/term relevance must never by
    # itself qualify any evidence entry as a candidate.
    retriever = GovernedSpecRetriever()
    results = retriever.query(
        "completely unrelated benign question",
        retrieval_policy=RetrievalPolicy(answer_scope="USB_3_X"),
    )
    assert results == []


@pytest.mark.unit
def test_governed_retriever_still_finds_genuine_port_link_state_match():
    # Sanity check: tightening the generic-token/scope rules must not break
    # legitimate PORT_LINK_STATE queries that use the specific feature name.
    retriever = GovernedSpecRetriever()
    results = retriever.query(
        "PORT_LINK_STATE feature selector value",
        retrieval_policy=RetrievalPolicy(answer_scope="USB_3_X"),
    )
    assert len(results) > 0
    assert results[0].evidence_id == "USB3-FEAT-PORT_LINK_STATE"


@pytest.mark.unit
def test_governed_retriever_finds_natural_language_port_power_question():
    # PR #29 review regression: a realistic user-phrased question (matching
    # the style of PR #23's user_realistic acceptance questions) must not be
    # abstained away just because it doesn't use the exact "PORT_POWER" /
    # "port_power" token. Naive `.split()` tokenization previously turned
    # every content word into a stopword, punctuation-suffixed token, or a
    # hyphen-glued compound that never matched anything, driving
    # topic_score to 0 for a question that is clearly about PORT_POWER.
    retriever = GovernedSpecRetriever()
    results = retriever.query(
        "Which USB 2.0 Hub Class feature controls downstream-port power, "
        "and what operation invokes that feature?",
        retrieval_policy=RetrievalPolicy(answer_scope="USB_2_0"),
    )
    assert len(results) > 0
    assert results[0].evidence_id == "USB2-FEAT-PORT_POWER"


@pytest.mark.unit
def test_governed_retriever_tokenizer_normalizes_hyphens_and_punctuation():
    # Isolates the tokenizer fix: a hyphenated compound ("port-power") must
    # be split into its constituent words so "power" alone can still match
    # evidence content, and trailing punctuation ("feature,") must not be
    # treated as part of the word. Uses "power" (not "downstream", which is
    # a generic Hub structural term stoplisted after the Warm Reset /
    # "link states" false-positive regression) as the genuine discriminator.
    retriever = GovernedSpecRetriever()
    results = retriever.query("Explain the port-power feature, please.")
    result_ids = {r.evidence_id for r in results}
    assert "USB3-FEAT-PORT_POWER" in result_ids


@pytest.mark.unit
def test_governed_retriever_matches_section_ref_by_exact_and_prefix():
    # Generalized section-reference matching (segment-wise prefix
    # comparison) must work for section numbers with no hardcoded rule,
    # such as USB2-FEAT-PORT_POWER's "11.24.2.1" section.
    retriever = GovernedSpecRetriever()
    results = retriever.query("What does USB 2.0 section 11.24.2.1 define?")
    result_ids = {r.evidence_id for r in results}
    assert "USB2-FEAT-PORT_POWER" in result_ids

    # A shorter section prefix ("11.23") must still match the longer,
    # fully-qualified section id ("11.23.2.1") it is a genuine prefix of.
    prefix_results = retriever.query("What is defined in USB 2.0 section 11.23?")
    prefix_result_ids = {r.evidence_id for r in prefix_results}
    assert "USB2-HUB-DESC-FORMAT" in prefix_result_ids


@pytest.mark.unit
def test_governed_retriever_bare_section_reference_query_finds_evidence():
    # PR #29 review regression: a bare section-number query (no surrounding
    # sentence) must resolve via the generalized section-reference matcher,
    # not depend on any hardcoded per-section rule. USB2-FEAT-PORT_POWER's
    # real section ("11.24.2.1") was previously missing from the old
    # hardcoded 4-section rule set entirely.
    retriever = GovernedSpecRetriever()
    results = retriever.query("11.24.2.1")
    assert len(results) > 0
    assert results[0].evidence_id == "USB2-FEAT-PORT_POWER"


@pytest.mark.unit
def test_governed_retriever_finds_bare_link_state_natural_language_question():
    # PR #29 review regression: "link state" (without a leading "port")
    # must still resolve to PORT_LINK_STATE. Both "link" and "state" are
    # individually in `_GENERIC_TOKENS`, so a realistic question that never
    # says the word "port" (e.g. "What is the link state feature selector
    # value?") must not be driven to topic_score=0 and abstained.
    retriever = GovernedSpecRetriever()
    results = retriever.query(
        "What is the link state feature selector value?",
        retrieval_policy=RetrievalPolicy(answer_scope="USB_3_X"),
    )
    assert len(results) > 0
    assert results[0].evidence_id == "USB3-FEAT-PORT_LINK_STATE"


@pytest.mark.unit
def test_governed_retriever_warm_reset_link_states_question_still_abstains():
    # PR #29 review regression (2nd pass): the bare "link state" compound
    # alias reopened the exact Warm Reset false-positive this whole fix set
    # out to close, because "link state" is a substring of "link states".
    # This is PR #23's actual user_realistic Warm Reset question, which is
    # NOT a PORT_LINK_STATE feature-selector question and has no
    # corresponding evidence in the (currently 5-entry) registry -- the
    # retriever must abstain, not guess PORT_LINK_STATE just because "link
    # state[s]" appears as a substring. This expectation should change only
    # if/when real Warm Reset evidence is added to the registry.
    retriever = GovernedSpecRetriever()
    results = retriever.query(
        "In USB 3.2, which link states allow a downstream port "
        "to issue a Warm Reset, and what are the minimum and "
        "maximum tReset durations?",
        retrieval_policy=RetrievalPolicy(answer_scope="USB_3_X"),
    )
    assert results == []


@pytest.mark.unit
def test_governed_retriever_warm_reset_operation_question_still_abstains():
    # PR #29 review regression (3rd pass): before the strong-signal /
    # lexical-bonus split, an ordinary content word with no curated concept
    # meaning ("used", from PORT_POWER's "Used with SetPortFeature...")
    # happening to appear in an unrelated Warm Reset question was, on its
    # own, enough to manufacture a false PORT_POWER candidate via the
    # generic-token overlap loop -- an unbounded stoplist whack-a-mole
    # problem. With only 5 embedded evidence entries and no genuine
    # PORT_POWER/section/PORT_LINK_STATE concept signal present, the
    # retriever must abstain.
    retriever = GovernedSpecRetriever()
    results = retriever.query(
        "What operation is used to initiate a Warm Reset "
        "on a USB 3.2 downstream port?",
        retrieval_policy=RetrievalPolicy(answer_scope="USB_3_X"),
    )
    assert results == []


@pytest.mark.unit
def test_governed_retriever_warm_reset_enable_link_question_still_abstains():
    # PR #29 review regression (3rd pass), sibling of the above: "enable"
    # is another ordinary content word (from PORT_POWER's "enable VBUS
    # power...") with no curated concept meaning; a bare mention of "link"
    # (without "link state" plus a qualifier) must not resurrect the
    # original PORT_LINK_STATE false positive either.
    retriever = GovernedSpecRetriever()
    results = retriever.query(
        "Does Warm Reset enable the link on a USB 3.2 downstream port?",
        retrieval_policy=RetrievalPolicy(answer_scope="USB_3_X"),
    )
    assert results == []


@pytest.mark.unit
def test_governed_retriever_link_power_management_question_still_abstains():
    # PR #29 review regression (4th pass): a bare "power" *substring* match
    # was too permissive -- "USB 3.2 link power management states" is a
    # Link Power Management (LPM) question, not a PORT_POWER question, but
    # the word "power" appears in it. With no "port_power"/"port power"
    # phrase, no feature-selector qualifier word, and no genuine
    # PORT_LINK_STATE/section signal present, the retriever must abstain
    # rather than surface PORT_POWER just because "power" is mentioned.
    retriever = GovernedSpecRetriever()
    results = retriever.query(
        "What are the USB 3.2 link power management states?",
        retrieval_policy=RetrievalPolicy(answer_scope="USB_3_X"),
    )
    assert results == []


@pytest.mark.unit
def test_governed_retriever_power_management_timeout_question_still_abstains():
    # PR #29 review regression (4th pass), sibling of the above: "power" on
    # its own (no "port_power"/"port power" phrase, no feature-selector
    # qualifier) must not manufacture a false PORT_POWER candidate.
    retriever = GovernedSpecRetriever()
    results = retriever.query(
        "What are the power management timeout rules in USB 3.2?",
        retrieval_policy=RetrievalPolicy(answer_scope="USB_3_X"),
    )
    assert results == []


@pytest.mark.unit
def test_governed_retriever_link_power_management_feature_question_still_abstains():
    # PR #29 review regression (5th pass): "power" + a feature-selector
    # qualifier word is STILL not high-precision enough on its own -- this
    # question is about USB 3.2 Link Power Management, not the Hub Class
    # PORT_POWER feature selector, yet it contains both "power" and
    # "feature". A bare "power" token must co-occur with BOTH explicit
    # port/VBUS context (port/downstream/vbus) AND a feature-selector
    # qualifier to count as a strong PORT_POWER signal; "power"+"feature"
    # alone, with no port/VBUS context, must not.
    retriever = GovernedSpecRetriever()
    results = retriever.query(
        "Which feature controls link power management in USB 3.2?",
        retrieval_policy=RetrievalPolicy(answer_scope="USB_3_X"),
    )
    assert results == []


@pytest.mark.unit
def test_governed_retriever_power_management_behavior_feature_question_still_abstains():
    # PR #29 review regression (5th pass), sibling of the above.
    retriever = GovernedSpecRetriever()
    results = retriever.query(
        "What feature defines power management behavior in USB 3.2?",
        retrieval_policy=RetrievalPolicy(answer_scope="USB_3_X"),
    )
    assert results == []


@pytest.mark.unit
def test_governed_retriever_setportfeature_port_reset_question_still_abstains():
    # PR #29 review regression (6th pass): `SetPortFeature` is a generic Hub
    # Class request that applies to every feature selector, not just
    # PORT_POWER -- this question is explicitly about PORT_RESET, and must
    # not be routed to PORT_POWER just because the word "setportfeature"
    # appears in it.
    retriever = GovernedSpecRetriever()
    results = retriever.query(
        "Which selector value is used with SetPortFeature(PORT_RESET) "
        "on a USB 3.2 hub?",
        retrieval_policy=RetrievalPolicy(answer_scope="USB_3_X"),
    )
    assert results == []


@pytest.mark.unit
def test_governed_retriever_vbus_current_limit_question_still_abstains():
    # PR #29 review regression (6th pass), sibling of the above: bare
    # "VBUS" is an electrical/power-delivery term, not a Hub Class
    # PORT_POWER selector question, and must not establish a PORT_POWER
    # candidate on its own.
    retriever = GovernedSpecRetriever()
    results = retriever.query(
        "What is the VBUS current limit in USB 3.2?",
        retrieval_policy=RetrievalPolicy(answer_scope="USB_3_X"),
    )
    assert results == []


@pytest.mark.unit
def test_governed_retriever_section_ref_does_not_collide_with_unrelated_section():
    # A bare version-like fragment ("3.2") must never match an unrelated
    # section id merely because "3.2" happens to be a substring of it (e.g.
    # "11.23.2.1"). Segment-wise prefix comparison (not substring
    # containment) is required to avoid this collision.
    retriever = GovernedSpecRetriever()
    results = retriever.query("USB 3.2 random unrelated benign question")
    assert results == []


@pytest.mark.unit
def test_governed_retriever_single_scope_is_a_hard_filter_not_a_bonus():
    # This closes the PR #29-carried-forward KNOWN LIMITATION: under the
    # RetrievalPolicy contract, `single_scope` (the default retrieval_mode)
    # is a hard evidence-scope eligibility gate, not a reranking bonus. A
    # topically relevant query must NOT surface out-of-scope evidence when
    # the caller has not explicitly asked for it.
    retriever = GovernedSpecRetriever()
    results = retriever.query(
        "PORT_POWER feature selector value",
        retrieval_policy=RetrievalPolicy(answer_scope="USB_2_0"),
    )
    result_ids = {r.evidence_id for r in results}
    assert result_ids == {"USB2-FEAT-PORT_POWER"}


@pytest.mark.unit
def test_governed_retriever_explicit_cross_scope_allows_declared_out_of_scope_evidence():
    # The caller (never the retriever) decides when a question legitimately
    # needs cross-scope evidence, by explicitly declaring
    # retrieval_mode="explicit_cross_scope" with a non-empty
    # allowed_evidence_scopes. This is the escape hatch that keeps questions
    # like "is PORT_LINK_STATE supported in USB 2.0?" answerable without
    # reopening the hard-filter gate for every other query.
    retriever = GovernedSpecRetriever()
    results = retriever.query(
        "PORT_POWER feature selector value",
        retrieval_policy=RetrievalPolicy(
            answer_scope="USB_2_0",
            retrieval_mode="explicit_cross_scope",
            allowed_evidence_scopes=("USB_2_0", "USB_3_X"),
        ),
    )
    result_ids = {r.evidence_id for r in results}
    assert "USB2-FEAT-PORT_POWER" in result_ids
    assert "USB3-FEAT-PORT_POWER" in result_ids
    # The evidence matching answer_scope must still be ranked first.
    assert results[0].evidence_id == "USB2-FEAT-PORT_POWER"


@pytest.mark.unit
def test_governed_retriever_unscoped_query_is_unaffected_by_retrieval_policy():
    # Omitting retrieval_policy entirely must preserve the pre-existing
    # unscoped behavior: any evidence scope is eligible, only topic
    # relevance decides candidacy.
    retriever = GovernedSpecRetriever()
    results = retriever.query("PORT_POWER feature selector value")
    result_ids = {r.evidence_id for r in results}
    assert "USB2-FEAT-PORT_POWER" in result_ids
    assert "USB3-FEAT-PORT_POWER" in result_ids


@pytest.mark.unit
def test_retrieval_policy_single_scope_defaults_allowed_evidence_scopes():
    policy = RetrievalPolicy(answer_scope="USB_2_0")
    assert policy.allowed_evidence_scopes == ("USB_2_0",)
    assert policy.domain == "USB_HUB"


@pytest.mark.unit
def test_retrieval_policy_single_scope_rejects_mismatched_allowed_scopes():
    with pytest.raises(RetrievalPolicyError, match="single_scope retrieval_mode requires"):
        RetrievalPolicy(
            answer_scope="USB_2_0",
            retrieval_mode="single_scope",
            allowed_evidence_scopes=("USB_2_0", "USB_3_X"),
        )


@pytest.mark.unit
def test_retrieval_policy_explicit_cross_scope_requires_non_empty_allowed_scopes():
    with pytest.raises(RetrievalPolicyError, match="explicit_cross_scope retrieval_mode requires"):
        RetrievalPolicy(answer_scope="USB_2_0", retrieval_mode="explicit_cross_scope")


@pytest.mark.unit
def test_retrieval_policy_rejects_unknown_domain():
    with pytest.raises(RetrievalPolicyError, match="unknown retrieval domain"):
        RetrievalPolicy(domain="HID", answer_scope="USB_2_0")


@pytest.mark.contract
def test_poc1_corpus_lock_binds_governed_reference_and_blocks_incomplete_claims():
    retriever = GovernedSpecRetriever()

    assert retriever.corpus_id == "usb-hub-poc1-phase1"
    assert retriever.knowledge_repo == "Gavin0099/usb-if-hub-spec-reference"
    assert retriever.knowledge_repo_commit == "808f23c24bd8651da9cdcd63ea8669126917a379"
    assert retriever.corpus_binding_status == "phase1_bound"
    assert retriever.lock_binding_status == "phase1_bound"
    assert retriever.runtime_binding_status == "unverified"
    assert retriever.physical_binding_verified is False
    assert retriever.corpus_lock["sources"]["hub_reference"]["binding_status"] == "locked"
    assert retriever.corpus_lock["binding_requirements"]["content_hash_algorithm"] == "sha256_tracked_relative_posix_path_content_bytes_v3"
    assert retriever.corpus_lock["sources"]["usb32"]["revision"] == "Rev 1.1"
    assert retriever.corpus_lock["sources"]["superspeed_hub_lvs"]["revision"] == "Rev 1.15"
    assert retriever.corpus_lock["sources"]["usb4"]["included"] is False
    assert retriever.corpus_lock["benchmark"]["independent_from_corpus"] is True
    assert retriever.qualification_blocked is True
    assert any(
        "runtime source usb20_fw physical binding is unverified" in reason
        for reason in retriever.qualification_block_reasons
    )


def _write_corpus_lock(tmp_path, lock):
    lock_path = tmp_path / "corpus.lock.yaml"
    lock_path.write_text(yaml.safe_dump(lock, sort_keys=False), encoding="utf-8")
    return str(lock_path)


def _create_bound_reference_repo(tmp_path, lock):
    repo_path = tmp_path / "reference"
    (repo_path / "exports").mkdir(parents=True)
    (repo_path / "exports" / "hub_governed_surface_manifest.yaml").write_text(
        "manifest_id: test\n", encoding="utf-8"
    )
    (repo_path / "README.md").write_text("bound reference\n", encoding="utf-8")
    subprocess.run(["git", "init", "--quiet", str(repo_path)], check=True)
    subprocess.run(["git", "-C", str(repo_path), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(repo_path), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo_path), "commit", "--quiet", "-m", "bind fixture"], check=True)
    commit = subprocess.check_output(
        ["git", "-C", str(repo_path), "rev-parse", "HEAD"], text=True
    ).strip()
    content_hash, _file_count = GovernedSpecRetriever._compute_knowledge_repo_content_hash(repo_path)
    lock["sources"]["hub_reference"]["commit"] = commit
    lock["sources"]["hub_reference"]["content_sha256"] = content_hash
    lock["sources"]["hub_reference"]["binding_status"] = "locked"
    return repo_path


def _make_phase1_bound_lock(lock):
    lock["status"] = "phase1_bound"
    for source_id, source in lock["sources"].items():
        if source.get("phase") != "phase_1":
            continue
        source["binding_status"] = "locked"
        source.pop("source_locator", None)
        if source_id != "hub_reference":
            source["content_sha256"] = "a" * 64
    return lock


def _create_phase1_bound_sources(tmp_path, lock):
    lock = _make_phase1_bound_lock(lock)
    repo_path = _create_bound_reference_repo(tmp_path, lock)
    source_paths = {"hub_reference": repo_path}
    for source_id in ("usb20_fw", "usb20_se", "usb32", "superspeed_hub_lvs"):
        source_path = tmp_path / f"{source_id}.pdf"
        source_path.write_bytes(f"{source_id} bound fixture\n".encode("utf-8"))
        source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
        lock["sources"][source_id]["content_sha256"] = source_hash
        lock["sources"][source_id]["source_locator"] = (
            f"env://USB_SPEC_QA_RAW_ROOT/{source_id}.pdf"
        )
        source_paths[source_id] = source_path
    return lock, source_paths


def _create_committed_lock_repo(tmp_path, lock):
    repo_path = tmp_path / "consumer"
    lock_path = repo_path / "gv100h" / "spec_qa" / "contracts" / "corpus.lock.yaml"
    lock_path.parent.mkdir(parents=True)
    lock_path.write_text(yaml.safe_dump(lock, sort_keys=False), encoding="utf-8")
    subprocess.run(["git", "init", "--quiet", str(repo_path)], check=True)
    subprocess.run(["git", "-C", str(repo_path), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(repo_path), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo_path), "commit", "--quiet", "-m", "bind corpus lock"], check=True)
    return repo_path, lock_path


@pytest.mark.contract
def test_corpus_binding_receipt_verifies_all_required_sources(tmp_path):
    lock, source_paths = _create_phase1_bound_sources(
        tmp_path,
        copy.deepcopy(GovernedSpecRetriever().corpus_lock),
    )
    consumer_root, lock_path = _create_committed_lock_repo(tmp_path, lock)
    retriever = GovernedSpecRetriever(
        source_paths=source_paths,
        corpus_lock_path=str(lock_path),
        require_physical_binding=True,
    )

    receipt = build_corpus_binding_receipt(retriever, repo_root=consumer_root)
    receipt_path = tmp_path / "corpus-binding-receipt.json"
    receipt_path.write_text(receipt.model_dump_json(indent=2), encoding="utf-8")
    loaded = load_corpus_binding_receipt(receipt_path)
    verified = verify_corpus_binding_receipt(
        loaded,
        retriever,
        repo_root=consumer_root,
    )

    assert loaded.receipt_hash
    assert loaded.required_source_ids == list(retriever.REQUIRED_PHASE1_SOURCES)
    assert loaded.physical_binding_verified is True
    expected_hash = hashlib.sha256(source_paths["usb32"].read_bytes()).hexdigest()
    assert loaded.observed_source_hashes["usb32"] == expected_hash
    assert verified["receipt_hash"] == loaded.receipt_hash


@pytest.mark.contract
def test_corpus_binding_receipt_cannot_be_built_from_blocked_retriever():
    with pytest.raises(CorpusBindingReceiptError, match="unverified"):
        build_corpus_binding_receipt(GovernedSpecRetriever())


@pytest.mark.contract
def test_corpus_binding_receipt_rejects_tampered_digest(tmp_path):
    lock, source_paths = _create_phase1_bound_sources(
        tmp_path,
        copy.deepcopy(GovernedSpecRetriever().corpus_lock),
    )
    consumer_root, lock_path = _create_committed_lock_repo(tmp_path, lock)
    retriever = GovernedSpecRetriever(
        source_paths=source_paths,
        corpus_lock_path=str(lock_path),
        require_physical_binding=True,
    )
    receipt = build_corpus_binding_receipt(retriever, repo_root=consumer_root)
    tampered = receipt.model_copy(update={"receipt_hash": "0" * 64})

    with pytest.raises(ValueError, match="receipt hash does not match"):
        verify_corpus_binding_receipt(
            tampered,
            retriever,
            repo_root=consumer_root,
        )


@pytest.mark.contract
def test_qa_evaluator_propagates_corpus_receipt_and_dataset_hash(tmp_path):
    lock, source_paths = _create_phase1_bound_sources(
        tmp_path,
        copy.deepcopy(GovernedSpecRetriever().corpus_lock),
    )
    consumer_root, lock_path = _create_committed_lock_repo(tmp_path, lock)
    retriever = GovernedSpecRetriever(
        source_paths=source_paths,
        corpus_lock_path=str(lock_path),
        require_physical_binding=True,
    )
    receipt = build_corpus_binding_receipt(retriever, repo_root=consumer_root)
    receipt_path = tmp_path / "corpus-binding-receipt.json"
    receipt_path.write_text(receipt.model_dump_json(indent=2), encoding="utf-8")

    evaluator = DeterministicSpecQAEvaluator(
        corpus_binding_receipt_path=str(receipt_path),
        retriever=retriever,
    )
    result = evaluator.run_benchmark(lambda _query, _scope, **_kwargs: ("", []))

    assert result.corpus_receipt_status == "verified"
    assert result.corpus_binding_receipt_hash == receipt.receipt_hash
    assert result.dataset_hash == hashlib.sha256(
        evaluator.dataset_file.read_bytes()
    ).hexdigest()


@pytest.mark.contract
def test_policy_revalidates_corpus_receipt_after_qa_evaluation(tmp_path):
    lock, source_paths = _create_phase1_bound_sources(
        tmp_path,
        copy.deepcopy(GovernedSpecRetriever().corpus_lock),
    )
    consumer_root, lock_path = _create_committed_lock_repo(tmp_path, lock)
    retriever = GovernedSpecRetriever(
        source_paths=source_paths,
        corpus_lock_path=str(lock_path),
        require_physical_binding=True,
    )
    receipt = build_corpus_binding_receipt(retriever, repo_root=consumer_root)
    receipt_path = tmp_path / "corpus-binding-receipt.json"
    receipt_path.write_text(receipt.model_dump_json(indent=2), encoding="utf-8")
    qa_result = DeterministicSpecQAEvaluator(
        corpus_binding_receipt_path=str(receipt_path),
        retriever=retriever,
    ).run_benchmark(lambda _query, _scope, **_kwargs: ("", []))
    coding_summary = ABExperimentSummary(
        total_runs_per_arm=30,
        is_synthetic_simulation=True,
        evidence_class="synthetic_offline_scaffold",
        admissible_for_model_qualification=False,
        arm_a_prompt_only={},
        arm_b_governed_sidecar={},
        governance_benefit={},
    )
    hardware_profile = {
        "total_requests": 100,
        "corruption_count": 0,
        "hardware_observed": False,
    }

    def evaluate_policy():
        return QualificationPolicyEvaluator().evaluate(
            qa_result,
            coding_summary,
            hardware_profile,
            corpus_binding_receipt_path=receipt_path,
            corpus_retriever=retriever,
            corpus_repo_root=consumer_root,
        )

    decision = evaluate_policy()
    corpus_gate = next(
        gate
        for gate in decision.gates
        if gate.gate_name == "spec_qa.corpus_binding_verified"
    )
    assert qa_result.corpus_receipt_status == "verified"
    assert corpus_gate.passed is True

    receipt_path.write_text(
        receipt.model_copy(update={"receipt_hash": "0" * 64}).model_dump_json(
            indent=2
        ),
        encoding="utf-8",
    )
    decision = evaluate_policy()
    corpus_gate = next(
        gate
        for gate in decision.gates
        if gate.gate_name == "spec_qa.corpus_binding_verified"
    )
    assert corpus_gate.passed is False


@pytest.mark.contract
def test_qa_evaluator_marks_missing_receipt(tmp_path):
    evaluator = DeterministicSpecQAEvaluator(
        corpus_binding_receipt_path=str(tmp_path / "missing-receipt.json")
    )
    result = evaluator.run_benchmark(lambda _query, _scope, **_kwargs: ("", []))

    assert result.corpus_receipt_status == "missing"
    assert result.corpus_binding_receipt_hash is None


@pytest.mark.contract
def test_qa_evaluator_marks_tampered_receipt_as_mismatch(tmp_path):
    lock, source_paths = _create_phase1_bound_sources(
        tmp_path,
        copy.deepcopy(GovernedSpecRetriever().corpus_lock),
    )
    consumer_root, lock_path = _create_committed_lock_repo(tmp_path, lock)
    retriever = GovernedSpecRetriever(
        source_paths=source_paths,
        corpus_lock_path=str(lock_path),
        require_physical_binding=True,
    )
    receipt = build_corpus_binding_receipt(retriever, repo_root=consumer_root)
    tampered_path = tmp_path / "tampered-corpus-binding-receipt.json"
    tampered_path.write_text(
        receipt.model_copy(update={"receipt_hash": "0" * 64}).model_dump_json(
            indent=2
        ),
        encoding="utf-8",
    )

    evaluator = DeterministicSpecQAEvaluator(
        corpus_binding_receipt_path=str(tampered_path),
        retriever=retriever,
    )
    result = evaluator.run_benchmark(lambda _query, _scope, **_kwargs: ("", []))

    assert result.corpus_receipt_status == "mismatch"
    assert result.corpus_binding_receipt_hash is None


@pytest.mark.contract
@pytest.mark.parametrize(
    "mutation,expected_message",
    [
        ("missing_layer", "required layers missing"),
        ("malformed_layer", "layer official_raw must be a mapping"),
        ("missing_source", "required Phase 1 source IDs missing"),
        ("missing_scope", "requires one of"),
        ("invalid_authority", "invalid authority role"),
        ("invalid_binding", "invalid binding_status"),
        ("invalid_hash_algorithm", "content hash algorithm does not match binding contract"),
        ("include_usb4", "USB4 must be excluded"),
        ("answer_from_evaluation", "evaluation_only layer must not be answer evidence"),
        ("missing_pending_policy", "pending_markers_block is incomplete"),
    ],
)
def test_poc1_corpus_lock_rejects_invalid_contract(tmp_path, mutation, expected_message):
    lock = copy.deepcopy(GovernedSpecRetriever().corpus_lock)
    if mutation == "missing_layer":
        lock["layers"].pop("official_raw")
    elif mutation == "malformed_layer":
        lock["layers"]["official_raw"] = "invalid"
    elif mutation == "missing_source":
        lock["sources"].pop("usb32")
    elif mutation == "missing_scope":
        lock["sources"]["usb20_fw"].pop("included_chapters")
    elif mutation == "invalid_authority":
        lock["sources"]["usb32"]["role"] = "community_reference"
    elif mutation == "invalid_binding":
        lock["sources"]["usb32"]["binding_status"] = "unknown"
    elif mutation == "invalid_hash_algorithm":
        lock["sources"]["hub_reference"]["content_hash_algorithm"] = "sha256_sorted_content_bytes_v1"
    elif mutation == "include_usb4":
        lock["sources"]["usb4"]["included"] = True
    elif mutation == "answer_from_evaluation":
        lock["layers"]["evaluation_only"]["allowed_as_answer_evidence"] = True
    elif mutation == "missing_pending_policy":
        lock["binding_requirements"]["pending_markers_block"] = []

    with pytest.raises(ValueError, match=expected_message):
        GovernedSpecRetriever(corpus_lock_path=_write_corpus_lock(tmp_path, lock))


@pytest.mark.contract
def test_poc1_governed_reference_binding_verifies_commit_hash_and_entrypoint(tmp_path):
    lock = copy.deepcopy(GovernedSpecRetriever().corpus_lock)
    repo_path = _create_bound_reference_repo(tmp_path, lock)
    retriever = GovernedSpecRetriever(
        knowledge_repo_path=str(repo_path),
        corpus_lock_path=_write_corpus_lock(tmp_path, lock),
    )

    assert retriever.bound_repo_head_commit == lock["sources"]["hub_reference"]["commit"]
    assert retriever.bound_repo_files_hash == lock["sources"]["hub_reference"]["content_sha256"]
    assert retriever.binding_mode == "live_repo_bound (2 files verified)"
    assert retriever.runtime_bindings["hub_reference"]["status"] == "verified"
    assert retriever.runtime_binding_status == "unverified"
    assert retriever.physical_binding_verified is False
    assert retriever.qualification_blocked is True


@pytest.mark.contract
def test_poc1_governed_reference_binding_ignores_untracked_files(tmp_path):
    lock = copy.deepcopy(GovernedSpecRetriever().corpus_lock)
    repo_path = _create_bound_reference_repo(tmp_path, lock)
    (repo_path / "untracked.md").write_text("ignored from Git tree hash\n", encoding="utf-8")

    retriever = GovernedSpecRetriever(
        knowledge_repo_path=str(repo_path),
        corpus_lock_path=_write_corpus_lock(tmp_path, lock),
    )

    assert retriever.bound_repo_files_hash == lock["sources"]["hub_reference"]["content_sha256"]


@pytest.mark.contract
def test_poc1_governed_reference_binding_rejects_tracked_content_drift(tmp_path):
    lock = copy.deepcopy(GovernedSpecRetriever().corpus_lock)
    repo_path = _create_bound_reference_repo(tmp_path, lock)
    (repo_path / "README.md").write_text("tracked drift\n", encoding="utf-8")

    with pytest.raises(ValueError, match="content hash does not match corpus lock"):
        GovernedSpecRetriever(
            knowledge_repo_path=str(repo_path),
            corpus_lock_path=_write_corpus_lock(tmp_path, lock),
        )


@pytest.mark.contract
def test_poc1_governed_reference_binding_rejects_missing_checkout(tmp_path):
    with pytest.raises(FileNotFoundError, match="governed reference path does not exist"):
        GovernedSpecRetriever(knowledge_repo_path=str(tmp_path / "missing-reference"))


@pytest.mark.contract
def test_poc1_phase1_bound_requires_physical_binding_path(tmp_path):
    lock = _make_phase1_bound_lock(copy.deepcopy(GovernedSpecRetriever().corpus_lock))

    with pytest.raises(ValueError, match="physical corpus binding requires paths for"):
        GovernedSpecRetriever(
            corpus_lock_path=_write_corpus_lock(tmp_path, lock),
            require_physical_binding=True,
        )


@pytest.mark.contract
def test_poc1_phase1_bound_without_physical_binding_stays_blocked(tmp_path):
    lock = _make_phase1_bound_lock(copy.deepcopy(GovernedSpecRetriever().corpus_lock))
    retriever = GovernedSpecRetriever(corpus_lock_path=_write_corpus_lock(tmp_path, lock))

    assert retriever.lock_binding_status == "phase1_bound"
    assert retriever.runtime_binding_status == "unverified"
    assert retriever.physical_binding_verified is False
    assert retriever.qualification_blocked is True
    assert any("physical binding is unverified" in reason for reason in retriever.qualification_block_reasons)


@pytest.mark.contract
def test_poc1_phase1_bound_with_verified_reference_but_missing_raw_stays_blocked(tmp_path):
    lock = _make_phase1_bound_lock(copy.deepcopy(GovernedSpecRetriever().corpus_lock))
    repo_path = _create_bound_reference_repo(tmp_path, lock)
    retriever = GovernedSpecRetriever(
        source_paths={"hub_reference": repo_path},
        corpus_lock_path=_write_corpus_lock(tmp_path, lock),
    )

    assert retriever.lock_binding_status == "phase1_bound"
    assert retriever.runtime_bindings["hub_reference"]["status"] == "verified"
    assert retriever.runtime_bindings["usb20_fw"]["status"] == "unverified"
    assert retriever.runtime_bindings["usb32"]["status"] == "unverified"
    assert retriever.runtime_binding_status == "unverified"
    assert retriever.physical_binding_verified is False
    assert retriever.qualification_blocked is True


@pytest.mark.contract
def test_poc1_raw_source_hash_mismatch_fails_closed(tmp_path):
    lock, source_paths = _create_phase1_bound_sources(tmp_path, copy.deepcopy(GovernedSpecRetriever().corpus_lock))
    source_paths["usb20_fw"].write_bytes(b"different raw source bytes\n")

    with pytest.raises(ValueError, match="source usb20_fw content hash does not match"):
        GovernedSpecRetriever(
            source_paths=source_paths,
            corpus_lock_path=_write_corpus_lock(tmp_path, lock),
            require_physical_binding=True,
        )


@pytest.mark.contract
def test_poc1_raw_source_missing_fails_closed(tmp_path):
    lock, source_paths = _create_phase1_bound_sources(tmp_path, copy.deepcopy(GovernedSpecRetriever().corpus_lock))
    source_paths.pop("usb32")

    with pytest.raises(ValueError, match="physical corpus binding requires paths for: usb32"):
        GovernedSpecRetriever(
            source_paths=source_paths,
            corpus_lock_path=_write_corpus_lock(tmp_path, lock),
            require_physical_binding=True,
        )


@pytest.mark.contract
def test_poc1_all_required_sources_verified_unblocks_qualification(tmp_path):
    lock, source_paths = _create_phase1_bound_sources(tmp_path, copy.deepcopy(GovernedSpecRetriever().corpus_lock))
    retriever = GovernedSpecRetriever(
        source_paths=source_paths,
        corpus_lock_path=_write_corpus_lock(tmp_path, lock),
        require_physical_binding=True,
    )

    assert all(
        binding["status"] == "verified"
        for binding in retriever.runtime_bindings.values()
    )
    assert retriever.runtime_binding_status == "verified"
    assert retriever.physical_binding_verified is True
    assert retriever.qualification_blocked is False


@pytest.mark.contract
@pytest.mark.parametrize(
    "mutation,expected_message",
    [
        ("commit", "commit does not match corpus lock"),
        ("content_sha256", "content hash does not match corpus lock"),
        ("entrypoint", "canonical entrypoint is missing"),
    ],
)
def test_poc1_governed_reference_binding_rejects_physical_drift(tmp_path, mutation, expected_message):
    lock = copy.deepcopy(GovernedSpecRetriever().corpus_lock)
    repo_path = _create_bound_reference_repo(tmp_path, lock)
    if mutation == "commit":
        lock["sources"]["hub_reference"]["commit"] = "0" * 40
    elif mutation == "content_sha256":
        lock["sources"]["hub_reference"]["content_sha256"] = "f" * 64
    else:
        lock["sources"]["hub_reference"]["canonical_entrypoint"] = "exports/missing.yaml"

    with pytest.raises(ValueError, match=expected_message):
        GovernedSpecRetriever(
            knowledge_repo_path=str(repo_path),
            corpus_lock_path=_write_corpus_lock(tmp_path, lock),
        )


@pytest.mark.unit
def test_governed_qa_service_abstention():
    service = GovernedQAService()
    resp = service.answer_question("Windows xHCI driver internals")
    assert resp.is_abstain is True
    assert "無法支持" in resp.answer
    assert len(resp.cited_evidences) == 0
    # Evidence Contract fields (docs/USB_SPEC_QA_POC1_SCOPE.md §5): an
    # abstain response must declare a boundary code. Deliberately
    # claims=[]/citations=[]/evidence_ids=[] -- a generic keyword match here
    # does not correspond to any single registered corpus/governance fact.
    # A generic BoundaryEvidence entry backed by
    # hub_reference.known_limits was tried and removed (Codex review,
    # PR #33, P1, 2nd pass): known_limits only proves ONE source lacks
    # coverage of a topic, not that the entire Phase 1 corpus does, so citing
    # it as a corpus-wide boundary fact would itself be an unsupported
    # inferential leap.
    assert resp.status == "abstain"
    assert resp.claims == []
    assert resp.citations == []
    assert resp.evidence_ids == []
    assert resp.boundary_code == "OUT_OF_SCOPE"
    assert resp.scope


@pytest.mark.unit
def test_governed_qa_service_usb4_abstains_with_real_registered_boundary_evidence():
    # Codex review (PR #33, P1): unlike the generic OUT_OF_SCOPE abstain
    # above (empty claims/citations), a USB4 query has a real, registered
    # BoundaryEvidence backing it (GovernedSpecRetriever.
    # BOUNDARY_EVIDENCE_REGISTRY) -- the runtime response must cite it, not
    # abstain silently.
    service = GovernedQAService()
    resp = service.answer_question("USB4 Hub 的 Warm Reset 規範為何？")
    assert resp.status == "abstain"
    assert resp.boundary_code == "OUT_OF_SCOPE"
    assert resp.claims == [
        service.retriever.get_boundary_evidence_by_id(
            "POC1-BOUNDARY-USB4-EXCLUDED"
        ).claim
    ]
    assert len(resp.citations) == 1
    assert resp.citations[0].evidence_id == "POC1-BOUNDARY-USB4-EXCLUDED"
    assert resp.citations[0].document is None  # boundary shape, not normative
    assert resp.evidence_ids == ["POC1-BOUNDARY-USB4-EXCLUDED"]
    assert resp.scope == "USB4_SPEC"


@pytest.mark.unit
def test_governed_qa_service_rejects_allowed_evidence_scopes_without_answer_scope():
    # Codex review regression (PR #31, P1): QARequest permits declaring
    # allowed_evidence_scopes without answer_scope, but RetrievalPolicy
    # requires answer_scope to build a policy at all. Silently falling
    # through to an unscoped query would let the retriever cite evidence
    # outside the caller's explicitly declared hard boundary -- this
    # combination must be rejected, not silently widened.
    service = GovernedQAService()
    with pytest.raises(ValueError, match="allowed_evidence_scopes was provided without answer_scope"):
        service.answer_question(
            "PORT_POWER feature selector value",
            allowed_evidence_scopes=["USB_2_0"],
        )


@pytest.mark.unit
def test_governed_qa_service_rejects_empty_allowed_evidence_scopes_without_answer_scope():
    # Codex review regression (PR #33, P2, fresh finding on 90a6e1a): the
    # "provided without answer_scope" check above used truthiness, so an
    # explicitly empty allowed_evidence_scopes=[] was falsy and silently
    # bypassed the rejection instead of being treated as "provided".
    service = GovernedQAService()
    with pytest.raises(ValueError, match="allowed_evidence_scopes was provided without answer_scope"):
        service.answer_question(
            "PORT_POWER feature selector value",
            allowed_evidence_scopes=[],
        )


@pytest.mark.unit
def test_governed_qa_service_rejects_empty_allowed_evidence_scopes_with_answer_scope():
    # Codex review regression (PR #33, P2, fresh finding on 90a6e1a): the
    # same truthiness conversion turned an explicitly empty
    # allowed_evidence_scopes=[] into None before reaching RetrievalPolicy,
    # so single_scope silently derived (answer_scope,) instead of enforcing
    # its contract that a provided list must equal exactly (answer_scope,).
    service = GovernedQAService()
    with pytest.raises(RetrievalPolicyError, match="single_scope retrieval_mode requires"):
        service.answer_question(
            "PORT_POWER feature selector value",
            "USB_2_0",
            allowed_evidence_scopes=[],
        )


@pytest.mark.unit
def test_governed_qa_service_routes_domain_into_retrieval_policy():
    # Codex review regression (PR #31, P2): QARequest accepts a `domain`
    # field, but answer_question() had no corresponding parameter, so every
    # request was silently treated as USB_HUB regardless of the declared
    # domain. Passing an unknown domain must now surface RetrievalPolicy's
    # own domain validation instead of being silently dropped.
    service = GovernedQAService()
    with pytest.raises(RetrievalPolicyError, match="unknown retrieval domain"):
        service.answer_question(
            "PORT_POWER feature selector value",
            "USB_2_0",
            domain="HID",
        )


@pytest.mark.contract
def test_golden_30_deterministic_benchmark():
    evaluator = DeterministicSpecQAEvaluator()
    service = GovernedQAService()

    def mock_agent_call(
        query_text: str,
        expected_scope: str,
        *,
        retrieval_mode: str = "single_scope",
        allowed_evidence_scopes=None,
    ):
        resp = service.answer_question(
            query_text,
            expected_scope,
            retrieval_mode=retrieval_mode,
            allowed_evidence_scopes=allowed_evidence_scopes,
        )
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


@pytest.mark.unit
def test_governed_evidence_registry_entries_declare_source_id():
    # Every embedded evidence entry must carry a source_id so it can be
    # traced back to corpus.lock.yaml and resolved into a Citation.
    retriever = GovernedSpecRetriever()
    assert len(retriever.EVIDENCE_REGISTRY) == 5
    for ev in retriever.EVIDENCE_REGISTRY:
        assert ev.source_id == "hub_reference"
        assert ev.source_id in retriever.corpus_lock["sources"]


@pytest.mark.unit
def test_governed_retriever_rejects_evidence_with_unregistered_source_id():
    # Fail closed at load time: an evidence entry whose source_id is not a
    # known corpus.lock.yaml source can never be resolved into a Citation,
    # so it must never be allowed into the registry in the first place.
    retriever = GovernedSpecRetriever()
    bad_evidence = copy.deepcopy(retriever.EVIDENCE_REGISTRY[0])
    bad_evidence.source_id = "not_a_real_source"
    retriever.EVIDENCE_REGISTRY = retriever.EVIDENCE_REGISTRY + [bad_evidence]
    with pytest.raises(ValueError, match="unregistered source_id"):
        retriever._validate_evidence_registry_provenance(retriever.corpus_lock)


@pytest.mark.unit
def test_governed_retriever_rejects_answer_evidence_from_excluded_source():
    # Codex review (PR #33, P1): "usb4" IS a known/registered corpus.lock.yaml
    # source_id (its exclusion is itself traceable), but it is phase_2 and
    # included=false -- registered does not mean eligible as answer evidence.
    # An evidence entry that references it must be rejected at load time,
    # not silently surfaced by query()/to_citation() as ordinary evidence.
    retriever = GovernedSpecRetriever()
    assert retriever.corpus_lock["sources"]["usb4"]["included"] is False
    bad_evidence = copy.deepcopy(retriever.EVIDENCE_REGISTRY[0])
    bad_evidence.source_id = "usb4"
    retriever.EVIDENCE_REGISTRY = retriever.EVIDENCE_REGISTRY + [bad_evidence]
    with pytest.raises(ValueError, match="not eligible as answer evidence"):
        retriever._validate_evidence_registry_provenance(retriever.corpus_lock)


@pytest.mark.unit
def test_governed_retriever_rejects_answer_evidence_from_evaluation_only_layer():
    # Codex review (PR #33, P1): even a phase_1, included source is not
    # eligible as answer evidence if its declared layer is not marked
    # allowed_as_answer_evidence=true in corpus.lock.yaml (e.g. an
    # "evaluation_only" layer source, per corpus.lock.yaml's own
    # layers.evaluation_only.allowed_as_answer_evidence: false).
    retriever = GovernedSpecRetriever()
    corpus_lock = copy.deepcopy(retriever.corpus_lock)
    corpus_lock["sources"]["hub_reference"]["layer"] = "evaluation_only"
    with pytest.raises(ValueError, match="not eligible as answer evidence"):
        retriever._validate_evidence_registry_provenance(corpus_lock)


@pytest.mark.unit
def test_governed_retriever_boundary_evidence_registry_seeded_with_usb4_exclusion():
    # Codex review (PR #33, P1): the Boundary Evidence Registry is a
    # first-class, separate registry from EVIDENCE_REGISTRY -- seeded only
    # with a boundary fact already proven by governed metadata (USB4's
    # Phase 1 exclusion), not an invented placeholder.
    retriever = GovernedSpecRetriever()
    boundary_evidence = retriever.get_boundary_evidence_by_id("POC1-BOUNDARY-USB4-EXCLUDED")
    assert boundary_evidence is not None
    assert boundary_evidence.source_id == "usb4"
    assert boundary_evidence.boundary_code == "OUT_OF_SCOPE"
    assert retriever.corpus_lock["sources"]["usb4"]["included"] is False
    assert retriever.corpus_lock["sources"]["usb4"]["phase"] == "phase_2"

    assert retriever.get_boundary_evidence_by_id("NOT-A-REAL-ID") is None


@pytest.mark.unit
def test_governed_retriever_to_boundary_citation_is_boundary_shaped():
    # A boundary citation must carry only evidence_id/excerpt -- no normative
    # document/revision/chapter/section/page_or_anchor/authority_level, per
    # poc1_acceptance_contract.py's "boundary_evidence" citation mode.
    retriever = GovernedSpecRetriever()
    boundary_evidence = retriever.get_boundary_evidence_by_id("POC1-BOUNDARY-USB4-EXCLUDED")
    citation = retriever.to_boundary_citation(boundary_evidence)
    assert citation.evidence_id == "POC1-BOUNDARY-USB4-EXCLUDED"
    assert citation.excerpt
    assert citation.document is None
    assert citation.revision is None
    assert citation.chapter is None
    assert citation.section is None
    assert citation.page_or_anchor is None
    assert citation.authority_level is None


@pytest.mark.unit
def test_governed_retriever_rejects_boundary_evidence_with_unregistered_source_id():
    from gv100h.spec_qa.retrieval.governed_retriever import BoundaryEvidence

    retriever = GovernedSpecRetriever()
    bad_boundary_evidence = BoundaryEvidence(
        evidence_id="FAKE-BOUNDARY",
        boundary_code="OUT_OF_SCOPE",
        claim="irrelevant",
        scope="USB4_SPEC",
        source_id="not_a_real_source",
        excerpt="irrelevant",
    )
    retriever.BOUNDARY_EVIDENCE_REGISTRY = retriever.BOUNDARY_EVIDENCE_REGISTRY + [bad_boundary_evidence]
    with pytest.raises(ValueError, match="unregistered source_id"):
        retriever._validate_boundary_evidence_registry_provenance(retriever.corpus_lock)


@pytest.mark.unit
def test_governed_retriever_rejects_boundary_evidence_id_colliding_with_answer_evidence():
    from gv100h.spec_qa.retrieval.governed_retriever import BoundaryEvidence

    retriever = GovernedSpecRetriever()
    colliding_boundary_evidence = BoundaryEvidence(
        evidence_id="USB3-FEAT-PORT_POWER",
        boundary_code="OUT_OF_SCOPE",
        claim="irrelevant",
        scope="USB4_SPEC",
        source_id="usb4",
        excerpt="irrelevant",
    )
    retriever.BOUNDARY_EVIDENCE_REGISTRY = retriever.BOUNDARY_EVIDENCE_REGISTRY + [colliding_boundary_evidence]
    with pytest.raises(ValueError, match="must not collide"):
        retriever._validate_boundary_evidence_registry_provenance(retriever.corpus_lock)


@pytest.mark.unit
def test_governed_retriever_to_citation_resolves_hub_reference_provenance():
    # hub_reference has no document/revision keys in corpus.lock.yaml, only
    # repo/commit -- to_citation() must fall back to those. chapter is
    # derived from the evidence's own section ("10.16.2.1" -> "10").
    retriever = GovernedSpecRetriever()
    ev = retriever.get_evidence_by_id("USB3-FEAT-PORT_POWER")
    citation = retriever.to_citation(ev)
    assert isinstance(citation, Citation)
    assert citation.evidence_id == "USB3-FEAT-PORT_POWER"
    assert citation.document == "Gavin0099/usb-if-hub-spec-reference"
    assert citation.revision == "808f23c24bd8651da9cdcd63ea8669126917a379"
    assert citation.chapter == "10"
    assert citation.section == ev.section
    assert citation.authority_level == ev.authority_level
    assert citation.excerpt is not None


@pytest.mark.unit
def test_governed_retriever_to_citation_derives_chapter_for_all_registry_entries():
    # Every embedded evidence entry's section starts with a numeric chapter
    # segment consistent with corpus.lock.yaml's declared included_chapters
    # (USB 3.x sections start with 10, USB 2.0 sections start with 11).
    retriever = GovernedSpecRetriever()
    for ev in retriever.EVIDENCE_REGISTRY:
        citation = retriever.to_citation(ev)
        assert citation.chapter == ev.section.split(".")[0]
        assert citation.chapter.isdigit()


@pytest.mark.unit
def test_governed_retriever_to_citation_rejects_non_numeric_chapter_section():
    # Independent review follow-up: _derive_chapter's fail-closed branch
    # (a section that does not start with a numeric chapter segment, e.g.
    # an annex-style reference) must actually be exercised, not just
    # assumed correct because every current registry entry is numeric.
    from gv100h.spec_qa.retrieval.governed_retriever import GovernedEvidence

    retriever = GovernedSpecRetriever()
    bad_evidence = GovernedEvidence(
        evidence_id="FAKE-ANNEX-EVIDENCE",
        authority_level="authoritative",
        scope="USB_3_X",
        claim_level="normative_requirement",
        section="Annex.A.1",
        title="fake annex section",
        content="irrelevant",
        source_id="hub_reference",
    )
    with pytest.raises(EvidenceContractError, match="does not start with a numeric chapter segment"):
        retriever.to_citation(bad_evidence)


@pytest.mark.unit
def test_governed_retriever_to_citation_truncates_long_excerpts():
    retriever = GovernedSpecRetriever()
    ev = retriever.get_evidence_by_id("USB3-FEAT-PORT_POWER")
    citation = retriever.to_citation(ev, excerpt_max_len=10)
    assert citation.excerpt is not None
    assert len(citation.excerpt) <= 10


@pytest.mark.unit
def test_governed_qa_service_answer_populates_evidence_contract_fields():
    # An "answer" response must expose status/claims/citations/scope/
    # evidence_ids per the Evidence Contract, in addition to the legacy
    # free-text fields -- the response is the complete evaluated contract,
    # not just a subset (Codex review P1).
    service = GovernedQAService()
    resp = service.answer_question(
        "PORT_POWER feature selector value", "USB_3_X"
    )
    assert resp.is_abstain is False
    assert resp.status == "answer"
    assert resp.claims
    assert resp.boundary_code is None
    assert resp.scope
    assert len(resp.citations) > 0
    assert resp.evidence_ids == [c.evidence_id for c in resp.citations]
    assert set(resp.evidence_ids) == {ev.evidence_id for ev in resp.cited_evidences}
    for citation in resp.citations:
        assert citation.document
        assert citation.revision
        assert citation.chapter
        assert citation.section


@pytest.mark.contract
def test_governed_qa_service_response_projects_onto_grounded_answer():
    # This proves QAResponse's structured fields are internally consistent
    # with the Evidence Contract shape (GroundedAnswer/Citation) -- but this
    # alone is NOT sufficient evidence that a QAResponse is admissible to the
    # separate downstream FinalPOC1Evaluator contract (FinalQAResponse uses
    # extra="forbid" and a different citation shape). See the
    # test_full_contract_chain_* tests below, which is where that stronger,
    # actually-load-bearing claim is verified end to end (Codex review,
    # PR #33, P1).
    service = GovernedQAService()
    resp = service.answer_question("PORT_POWER feature selector value", "USB_3_X")
    dumped = resp.model_dump()
    for key in ("status", "claims", "claim_evidence_ids", "citations", "scope", "boundary_code", "evidence_ids"):
        assert key in dumped

    reconstructed = GroundedAnswer(
        status=dumped["status"],
        claims=dumped["claims"],
        claim_evidence_ids=dumped["claim_evidence_ids"],
        citations=dumped["citations"],
        scope=dumped["scope"],
        boundary=dumped["boundary_code"],
        evidence_ids=dumped["evidence_ids"],
    )
    assert reconstructed.status == "answer"


class _StubEvidenceResolver:
    """Resolves exactly the evidence IDs it's told about -- enough to drive
    FinalPOC1Evaluator.evaluate_response() without loading a real manifest
    file or corpus.lock.yaml receipt."""

    def __init__(self, known_ids):
        self._known_ids = set(known_ids)

    def get_evidence_by_id(self, evidence_id):
        return evidence_id if evidence_id in self._known_ids else None


class _StubEvidenceResolverWithCanonicalBoundary(_StubEvidenceResolver):
    """Extends _StubEvidenceResolver with get_canonical_citation_by_id(),
    resolving every known id to a boundary-shaped canonical record
    (document=None). Used by chain tests that hand-build a boundary/abstain
    QAResponse and need canonical evidence-shape verification to actually
    succeed for a legitimate boundary citation (Codex review, PR #33, fresh
    finding on ad0542c: FinalPOC1Evaluator now fails closed on every
    citation -- normative or boundary-shaped -- whose canonical
    evidence-shape cannot be verified). This is deliberately a SEPARATE
    class from _StubEvidenceResolver, which stays canonical-lookup-free on
    purpose: it is what
    test_final_evaluator_fails_closed_on_normative_citation_without_canonical_resolver
    uses to prove the opposite behavior (fail closed when canonical lookup
    is unavailable).

    ``excerpts`` optionally maps evidence_id -> the resolver's canonical
    excerpt text, so callers can prove the excerpt_or_evidence_id identity
    check (Codex review, PR #33, fresh finding on 88200c5) actually
    verifies a real canonical excerpt, not just a None default that would
    only ever satisfy the evidence_id-fallback branch of that check.
    """

    def __init__(self, known_ids, excerpts=None):
        super().__init__(known_ids)
        self._excerpts = dict(excerpts or {})

    def get_evidence_by_id(self, evidence_id):
        # Overrides the parent's bare-string return: _trusted_source_text()
        # (final_evaluator.py) needs a raw record exposing ``.excerpt``/
        # ``.content`` to verify a genuine, non-fallback excerpt against the
        # trusted source text (Codex review, PR #33, fresh finding on
        # d4f3bf7). A bare string has neither attribute, which would make
        # every non-evidence_id-fallback excerpt unverifiable here.
        if evidence_id not in self._known_ids:
            return None
        return SimpleNamespace(excerpt=self._excerpts.get(evidence_id))

    def get_canonical_citation_by_id(self, evidence_id):
        if evidence_id not in self._known_ids:
            return None
        return SimpleNamespace(
            document=None,
            revision=None,
            chapter=None,
            section=None,
            page_or_anchor=None,
            authority_level=None,
            excerpt=self._excerpts.get(evidence_id),
        )


def _evaluator_with_resolver(resolver) -> FinalPOC1Evaluator:
    # Bypass __init__ (which loads a real manifest file from disk) --
    # evaluate_response() only touches self.evidence_resolver.
    evaluator = FinalPOC1Evaluator.__new__(FinalPOC1Evaluator)
    evaluator.evidence_resolver = resolver
    return evaluator


_CHAIN_GRADING_WEIGHTS = GradingWeights(
    factual_correctness=0.3,
    citation_correctness=0.3,
    source_authority=0.2,
    scope_control=0.1,
    uncertainty_behavior=0.1,
)


@pytest.mark.contract
def test_full_contract_chain_answer_round_trip_through_final_evaluator():
    # The invariant Codex's review actually cares about: a QAResponse that
    # is internally valid per GroundedAnswer/Citation must ALSO be
    # admissible to FinalPOC1Evaluator once projected through the explicit
    # adapter. Each layer being green in isolation (Evidence Contract valid,
    # QAResponse valid) is not sufficient proof of this -- this test proves
    # the full chain: GovernedQAService -> QAResponse -> to_final_qa_response()
    # -> FinalQAResponse -> FinalPOC1Evaluator.evaluate_response().
    service = GovernedQAService()
    resp = service.answer_question("PORT_POWER feature selector value", "USB_3_X")
    final_response = resp.to_final_qa_response()

    question = AcceptanceQuestion(
        question_id="CHAIN-TEST-ANSWER-1",
        layer="L1",
        priority="P0",
        category="single_spec_fact",
        question="PORT_POWER feature selector value",
        expected_status="answer",
        expected_scope="USB_3_X",
        accepted_source_ids=["hub_reference"],
        required_citation_fields=CitationRequirements(
            document=True,
            revision=True,
            section=True,
            page_or_anchor=True,
            excerpt_or_evidence_id=True,
            scope=True,
            boundary_code=False,
            chapter=True,
            authority_level=True,
            mode="normative_source",
        ),
        gold=GoldOracle(
            accepted_evidence_ids=list(resp.evidence_ids),
            required_claims=[GoldClaim(claim_id="c1", assertion=resp.claims[0], required=True)],
            section_anchors=[c.section for c in resp.citations],
            required_facts=[],
        ),
        grading=_CHAIN_GRADING_WEIGHTS,
        independently_reviewed=True,
    )

    # Real retriever, not _StubEvidenceResolver: cuREi (Codex review, PR #33,
    # P1) makes FinalPOC1Evaluator fail closed on a normative citation's
    # canonical provenance when the resolver cannot verify it. Proving this
    # full chain "passes" requires a resolver that can actually verify
    # provenance, the same way production does.
    evaluator = _evaluator_with_resolver(service.retriever)
    result = evaluator.evaluate_response(question, final_response)
    assert result.passed is True
    assert result.citation_complete is True
    assert result.fabricated_citation is False
    assert result.authority_violation is False


@pytest.mark.contract
def test_full_contract_chain_boundary_abstain_round_trip_through_final_evaluator():
    # Mirrors the answer-path chain test above, but for the P1 abstain fix:
    # a GroundedAnswer-valid abstain that asserts a boundary claim backed by
    # a boundary citation must also be admissible to the evaluator's
    # "boundary_evidence" citation mode.
    boundary_citation = Citation(
        evidence_id="USB4-OUT-OF-SCOPE",
        excerpt="Phase 1 corpus does not include the USB4 specification.",
        citation_kind="boundary",
    )
    claim_text = "目前 Phase 1 corpus 不包含 USB4 specification，因此沒有足夠 evidence 回答。"
    resp = QAResponse(
        answer=claim_text,
        scope="USB4_SPEC",
        cited_evidences=[],
        claim_level="abstain_boundary_claim",
        boundary="Exceeds governed knowledge surface.",
        is_abstain=True,
        status="abstain",
        claims=[claim_text],
        claim_evidence_ids=[["USB4-OUT-OF-SCOPE"]],
        citations=[boundary_citation],
        boundary_code="OUT_OF_SCOPE",
        evidence_ids=["USB4-OUT-OF-SCOPE"],
    )
    # GroundedAnswer itself must also accept this shape -- if it didn't,
    # QAResponse.model_validate would already have rejected the response
    # (only reachable if _build_response() had skipped the check).
    GroundedAnswer(
        status=resp.status,
        claims=resp.claims,
        claim_evidence_ids=resp.claim_evidence_ids,
        citations=resp.citations,
        scope=resp.scope,
        boundary=resp.boundary_code,
        evidence_ids=resp.evidence_ids,
    )

    final_response = resp.to_final_qa_response()

    question = AcceptanceQuestion(
        question_id="CHAIN-TEST-ABSTAIN-1",
        layer="L4",
        priority="P0",
        category="uncertainty_conflict",
        question="USB4 Hub 的 Warm Reset 規範為何？",
        expected_status="abstain",
        expected_scope="USB4_SPEC",
        accepted_source_ids=[],
        required_citation_fields=CitationRequirements(
            document=False,
            revision=False,
            section=False,
            page_or_anchor=False,
            excerpt_or_evidence_id=True,
            scope=True,
            boundary_code=True,
            mode="boundary_evidence",
        ),
        gold=GoldOracle(
            boundary_evidence_ids=["USB4-OUT-OF-SCOPE"],
            required_claims=[GoldClaim(claim_id="b1", assertion=claim_text, required=True)],
            boundary_code="OUT_OF_SCOPE",
        ),
        grading=_CHAIN_GRADING_WEIGHTS,
        independently_reviewed=True,
    )

    evaluator = _evaluator_with_resolver(_StubEvidenceResolverWithCanonicalBoundary(
        ["USB4-OUT-OF-SCOPE"],
        excerpts={
            "USB4-OUT-OF-SCOPE": "Phase 1 corpus does not include the USB4 specification.",
        },
    ))
    result = evaluator.evaluate_response(question, final_response)
    assert result.passed is True
    assert result.citation_complete is True
    assert result.fabricated_citation is False


@pytest.mark.contract
def test_full_contract_chain_usb4_boundary_abstain_uses_real_registered_evidence():
    # Codex review (PR #33, P1): the chain test above proves the SHAPE is
    # admissible using a hand-built QAResponse and a stub resolver that
    # accepts any ID it's told about -- it does not prove the *runtime*
    # produces this shape, nor that the citation resolves against the real
    # Boundary Evidence Registry rather than an ad-hoc string. This test
    # proves the full, real chain: GovernedQAService.answer_question()
    # (real retriever, real BOUNDARY_EVIDENCE_REGISTRY) -> QAResponse ->
    # to_final_qa_response() -> FinalPOC1Evaluator, resolved DIRECTLY by the
    # production GovernedSpecRetriever -- no test-only wrapper, no stub, no
    # fabricated evidence_id. GovernedSpecRetriever.get_evidence_by_id()
    # itself resolves both EVIDENCE_REGISTRY and BOUNDARY_EVIDENCE_REGISTRY
    # (resolvable != retrievable_as_answer), so the evaluator-facing
    # EvidenceResolver protocol is satisfied by the retriever alone.
    service = GovernedQAService()
    resp = service.answer_question("USB4 Hub 的 Warm Reset 規範為何？")

    assert resp.status == "abstain"
    assert resp.boundary_code == "OUT_OF_SCOPE"
    assert resp.claims
    assert resp.citations
    assert resp.citations[0].evidence_id == "POC1-BOUNDARY-USB4-EXCLUDED"

    final_response = resp.to_final_qa_response()

    question = AcceptanceQuestion(
        question_id="CHAIN-TEST-ABSTAIN-USB4-REAL",
        layer="L4",
        priority="P0",
        category="uncertainty_conflict",
        question="USB4 Hub 的 Warm Reset 規範為何？",
        expected_status="abstain",
        expected_scope=resp.scope,
        accepted_source_ids=[],
        required_citation_fields=CitationRequirements(
            document=False,
            revision=False,
            section=False,
            page_or_anchor=False,
            excerpt_or_evidence_id=True,
            scope=True,
            boundary_code=True,
            mode="boundary_evidence",
        ),
        gold=GoldOracle(
            boundary_evidence_ids=list(resp.evidence_ids),
            required_claims=[GoldClaim(claim_id="b1", assertion=resp.claims[0], required=True)],
            boundary_code="OUT_OF_SCOPE",
        ),
        grading=_CHAIN_GRADING_WEIGHTS,
        independently_reviewed=True,
    )

    evaluator = _evaluator_with_resolver(service.retriever)
    result = evaluator.evaluate_response(question, final_response)
    assert result.passed is True
    assert result.citation_complete is True
    assert result.fabricated_citation is False


@pytest.mark.contract
def test_full_contract_chain_usb4_boundary_abstain_flags_fabricated_citation():
    # Negative control for the test above: a resolver backed by the real
    # registries must actually be able to fail -- proving the previous
    # test's `fabricated_citation is False` is a real resolution outcome,
    # not a resolver that trivially accepts everything.
    service = GovernedQAService()
    resp = service.answer_question("USB4 Hub 的 Warm Reset 規範為何？")
    final_response = resp.to_final_qa_response()
    # Corrupt the resolvable evidence_id into one that was never registered.
    final_response = final_response.model_copy(
        update={
            "citations": [
                citation.model_copy(update={"evidence_id": "NOT-A-REGISTERED-BOUNDARY-ID"})
                for citation in final_response.citations
            ]
        }
    )

    question = AcceptanceQuestion(
        question_id="CHAIN-TEST-ABSTAIN-USB4-FABRICATED",
        layer="L4",
        priority="P0",
        category="uncertainty_conflict",
        question="USB4 Hub 的 Warm Reset 規範為何？",
        expected_status="abstain",
        expected_scope=resp.scope,
        accepted_source_ids=[],
        required_citation_fields=CitationRequirements(
            document=False,
            revision=False,
            section=False,
            page_or_anchor=False,
            excerpt_or_evidence_id=True,
            scope=True,
            boundary_code=True,
            mode="boundary_evidence",
        ),
        gold=GoldOracle(
            boundary_evidence_ids=["NOT-A-REGISTERED-BOUNDARY-ID"],
            required_claims=[GoldClaim(claim_id="b1", assertion=resp.claims[0], required=True)],
            boundary_code="OUT_OF_SCOPE",
        ),
        grading=_CHAIN_GRADING_WEIGHTS,
        independently_reviewed=True,
    )

    evaluator = _evaluator_with_resolver(service.retriever)
    result = evaluator.evaluate_response(question, final_response)
    assert result.fabricated_citation is True


@pytest.mark.unit
def test_governed_retriever_concept_to_value_still_finds_port_link_state():
    retriever = GovernedSpecRetriever()
    results = retriever.query(
        "What is the PORT_LINK_STATE feature selector value?",
        retrieval_policy=RetrievalPolicy(answer_scope="USB_3_X"),
    )
    assert results[0].evidence_id == "USB3-FEAT-PORT_LINK_STATE"
    assert results[0].selector_value == 5


@pytest.mark.unit
def test_governed_retriever_known_value_looks_up_port_link_state():
    retriever = GovernedSpecRetriever()
    results = retriever.query(
        "Which USB 3.x Hub Class feature selector has value 5?",
        retrieval_policy=RetrievalPolicy(answer_scope="USB_3_X"),
    )
    assert [ev.evidence_id for ev in results] == ["USB3-FEAT-PORT_LINK_STATE"]


@pytest.mark.unit
def test_governed_retriever_value_5_wording_variant_looks_up_port_link_state():
    retriever = GovernedSpecRetriever()
    results = retriever.query(
        "What feature selector corresponds to value 5 in USB 3.x?",
        retrieval_policy=RetrievalPolicy(answer_scope="USB_3_X"),
    )
    assert [ev.evidence_id for ev in results] == ["USB3-FEAT-PORT_LINK_STATE"]


@pytest.mark.unit
def test_governed_retriever_unknown_selector_value_999_abstains():
    retriever = GovernedSpecRetriever()
    results = retriever.query(
        "Which USB 3.x Hub Class feature selector has value 999?",
        retrieval_policy=RetrievalPolicy(answer_scope="USB_3_X"),
    )
    assert results == []


@pytest.mark.unit
def test_qa_service_unknown_selector_value_999_abstains():
    service = GovernedQAService()
    resp = service.answer_question(
        "Which USB 3.x Hub Class feature selector has value 999?",
        answer_scope="USB_3_X",
    )
    assert resp.is_abstain is True
    assert resp.cited_evidences == []


@pytest.mark.unit
def test_governed_retriever_selector_5_on_usb2_requires_explicit_cross_scope():
    retriever = GovernedSpecRetriever()
    single = retriever.query(
        "If software uses feature selector 5 on a USB 2.0 hub, "
        "should it be treated like PORT_POWER? Explain why.",
        retrieval_policy=RetrievalPolicy(answer_scope="USB_2_0"),
    )
    assert "USB3-FEAT-PORT_LINK_STATE" not in {ev.evidence_id for ev in single}

    results = retriever.query(
        "If software uses feature selector 5 on a USB 2.0 hub, "
        "should it be treated like PORT_POWER? Explain why.",
        retrieval_policy=RetrievalPolicy(
            answer_scope="USB_2_0",
            retrieval_mode="explicit_cross_scope",
            allowed_evidence_scopes=("USB_2_0", "USB_3_X"),
        ),
    )
    result_ids = {ev.evidence_id for ev in results}
    assert "USB3-FEAT-PORT_LINK_STATE" in result_ids
    assert "USB2-FEAT-PORT_POWER" in result_ids


@pytest.mark.unit
def test_numeric_tokens_without_selector_cue_do_not_lookup():
    retriever = GovernedSpecRetriever()
    usb3 = RetrievalPolicy(answer_scope="USB_3_X")
    assert retriever.query("Wait 5 ms after Warm Reset", retrieval_policy=usb3) == []
    assert retriever.query("The hub has 5 ports", retrieval_policy=usb3) == []
    assert retriever.query("See section 5 for overview", retrieval_policy=usb3) == []


@pytest.mark.unit
def test_governed_retriever_single_scope_usb3_does_not_cite_usb2_descriptor():
    retriever = GovernedSpecRetriever()
    results = retriever.query(
        "What is the USB 2.0 Hub Descriptor bDescriptorType?",
        retrieval_policy=RetrievalPolicy(answer_scope="USB_3_X"),
    )
    assert all(ev.scope != "USB_2_0" for ev in results)


@pytest.mark.unit
def test_normalize_feature_selector_query_requires_selector_cue():
    from gv100h.spec_qa.retrieval.query_normalizer import (
        normalize_feature_selector_query,
    )

    parsed = normalize_feature_selector_query(
        "Which USB 3.x Hub Class feature selector has value 5?",
        "USB_3_X",
    )
    assert parsed == {
        "entity_type": "feature_selector",
        "value": 5,
        "scope": "USB_3_X",
    }
    assert normalize_feature_selector_query("Wait 5 ms", "USB_3_X") is None
    assert normalize_feature_selector_query("value 5 → which selector?") == {
        "entity_type": "feature_selector",
        "value": 5,
        "scope": None,
    }


@pytest.mark.unit
def test_named_selector_plus_unrelated_value_is_not_selector_id_lookup():
    from gv100h.spec_qa.retrieval.query_normalizer import (
        normalize_feature_selector_query,
    )

    retriever = GovernedSpecRetriever()
    usb3 = RetrievalPolicy(answer_scope="USB_3_X")
    query_unknown = (
        "For the PORT_LINK_STATE feature selector, is link-state value 3 valid?"
    )
    query_collision = (
        "For the PORT_LINK_STATE feature selector, is value 8 valid?"
    )

    assert normalize_feature_selector_query(query_unknown, "USB_3_X") is None
    assert normalize_feature_selector_query(query_collision, "USB_3_X") is None

    unknown_ids = [ev.evidence_id for ev in retriever.query(query_unknown, retrieval_policy=usb3)]
    collision_ids = [ev.evidence_id for ev in retriever.query(query_collision, retrieval_policy=usb3)]
    assert unknown_ids == ["USB3-FEAT-PORT_LINK_STATE"]
    assert collision_ids == ["USB3-FEAT-PORT_LINK_STATE"]


# ---------------------------------------------------------------------------
# Commit C / Commit D (Codex review, PR #33, follow-up to the 6-thread
# resolution pass): resolvable != retrievable_as_answer, policy validation
# ordering, chapter/authority_level provenance, conflict-boundary-code ->
# provenance-dimension binding, USB4 corpus-membership governance answers,
# and generic OUT_OF_SCOPE boundary evidence for service abstentions.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_evidence_by_id_resolves_boundary_registry_directly():
    # Commit C item 1: the production resolver alone (no test-only wrapper)
    # must resolve BOTH EVIDENCE_REGISTRY and BOUNDARY_EVIDENCE_REGISTRY --
    # this is exactly what FinalPOC1Evaluator.evaluate_response() calls
    # (EvidenceResolver.get_evidence_by_id), so a production
    # GovernedSpecRetriever must satisfy that protocol on its own.
    retriever = GovernedSpecRetriever()
    assert retriever.get_evidence_by_id("USB3-FEAT-PORT_POWER") is not None
    assert retriever.get_evidence_by_id("POC1-BOUNDARY-USB4-EXCLUDED") is not None
    assert retriever.get_evidence_by_id("NOT-A-REGISTERED-ID") is None


@pytest.mark.unit
def test_query_does_not_retrieve_boundary_evidence_as_answer_support():
    # Commit C item 1's other half: resolvable != retrievable_as_answer --
    # query() must keep searching only the answer-eligible EVIDENCE_REGISTRY,
    # never BOUNDARY_EVIDENCE_REGISTRY, even though get_evidence_by_id() now
    # resolves both.
    retriever = GovernedSpecRetriever()
    results = retriever.query(
        "USB4 is excluded from the Phase 1 corpus",
        retrieval_policy=RetrievalPolicy(answer_scope="USB4_SPEC"),
    )
    assert all(ev.evidence_id != "POC1-BOUNDARY-USB4-EXCLUDED" for ev in results)


@pytest.mark.unit
def test_qa_service_policy_validation_runs_before_usb4_early_return():
    # Commit C item 2 (Codex review, PR #33, P2): an invalid domain must be
    # rejected even for a USB4 query, which previously returned its abstain
    # response before RetrievalPolicy was ever constructed.
    service = GovernedQAService()
    with pytest.raises(RetrievalPolicyError, match="unknown retrieval domain"):
        service.answer_question(
            "USB4 Hub 的 Warm Reset 規範為何？",
            answer_scope="USB4_SPEC",
            domain="HID",
        )


@pytest.mark.unit
def test_qa_service_rejects_unknown_retrieval_mode_without_answer_scope():
    # Codex review, PR #33, fresh finding on edf8825: validate_policy_inputs()
    # previously only checked the retrieval_mode == "explicit_cross_scope"
    # branch. RetrievalMode's typing.Literal annotation is not enforced at
    # runtime for a plain function/method parameter -- only pydantic's model
    # validation enforces it, and RetrievalPolicy (which would reject an
    # unknown mode) is never constructed when answer_scope is omitted. An
    # invalid retrieval_mode like "bogus" must still be rejected in that
    # case, not silently accepted through to a USB4 early-return abstain.
    service = GovernedQAService()
    with pytest.raises(RetrievalPolicyError, match="unknown retrieval_mode"):
        service.answer_question(
            "USB4 Hub 的 Warm Reset 規範為何？",
            retrieval_mode="bogus",
        )


@pytest.mark.unit
def test_qa_service_rejects_allowed_evidence_scopes_without_answer_scope_for_usb4_query():
    # Commit C item 2, other half: allowed_evidence_scopes without
    # answer_scope must be rejected even for a query that would otherwise
    # match the USB4 early-return branch.
    service = GovernedQAService()
    with pytest.raises(ValueError, match="allowed_evidence_scopes was provided without answer_scope"):
        service.answer_question(
            "USB4 Hub 的 Warm Reset 規範為何？",
            allowed_evidence_scopes=["USB4_SPEC"],
        )


@pytest.mark.unit
def test_qa_service_policy_validation_runs_before_unsupported_keyword_early_return():
    # Same ordering fix, exercised through the generic unsupported_keywords
    # branch instead of the USB4 branch.
    service = GovernedQAService()
    with pytest.raises(RetrievalPolicyError, match="unknown retrieval domain"):
        service.answer_question(
            "Windows xHCI driver internals",
            answer_scope="USB_HUB",
            domain="HID",
        )


@pytest.mark.unit
def test_qa_service_policy_validation_runs_for_usb4_query_without_answer_scope():
    # Codex review, PR #33, P2 (ctj1M): before this fix, calling
    # answer_question() with an invalid domain but WITHOUT answer_scope
    # skipped policy validation entirely -- RetrievalPolicy is only
    # constructed when answer_scope is not None, so an invalid domain like
    # "HID" would sail through the USB4 branch and return a normal
    # abstention response instead of raising. validate_policy_inputs() now
    # runs unconditionally, closing that gap.
    service = GovernedQAService()
    with pytest.raises(RetrievalPolicyError, match="unknown retrieval domain"):
        service.answer_question(
            "USB4 Hub 的 Warm Reset 規範為何？",
            domain="HID",
        )


@pytest.mark.unit
def test_grounded_answer_answer_status_allows_governance_citation_without_normative_fields():
    # Commit C item 5: a governance-fact citation_kind must NOT be forced to
    # carry normative document-identity fields, unlike an ordinary normative
    # answer citation.
    citation = Citation(
        evidence_id="POC1-BOUNDARY-USB4-EXCLUDED",
        excerpt="corpus.lock.yaml sources.usb4: included=false.",
        citation_kind="governance",
    )
    answer = GroundedAnswer(
        status="answer",
        claims=["USB4 is not included in the Phase 1 corpus."],
        claim_evidence_ids=[["POC1-BOUNDARY-USB4-EXCLUDED"]],
        citations=[citation],
        evidence_ids=["POC1-BOUNDARY-USB4-EXCLUDED"],
        scope="USB4_SPEC",
    )
    assert answer.status == "answer"


@pytest.mark.unit
def test_grounded_answer_governance_citation_rejects_normative_fields():
    with pytest.raises(EvidenceContractError, match="must not declare normative"):
        GroundedAnswer(
            status="answer",
            claims=["USB4 is not included in the Phase 1 corpus."],
            claim_evidence_ids=[["POC1-BOUNDARY-USB4-EXCLUDED"]],
            citations=[
                Citation(
                    evidence_id="POC1-BOUNDARY-USB4-EXCLUDED",
                    document="usb4-spec",
                    excerpt="x",
                    citation_kind="governance",
                )
            ],
            evidence_ids=["POC1-BOUNDARY-USB4-EXCLUDED"],
            scope="USB4_SPEC",
        )


@pytest.mark.unit
def test_grounded_answer_rejects_boundary_kind_citation_for_answer_status():
    # A boundary citation is registered to explain an abstention -- reusing
    # it to back an "answer" would let non-answer evidence masquerade as
    # grounding for a real claim.
    with pytest.raises(EvidenceContractError, match="must not cite boundary-only evidence"):
        GroundedAnswer(
            status="answer",
            claims=["some claim"],
            claim_evidence_ids=[["POC1-BOUNDARY-USB4-EXCLUDED"]],
            citations=[
                Citation(
                    evidence_id="POC1-BOUNDARY-USB4-EXCLUDED",
                    excerpt="x",
                    citation_kind="boundary",
                )
            ],
            evidence_ids=["POC1-BOUNDARY-USB4-EXCLUDED"],
            scope="USB4_SPEC",
        )


@pytest.mark.unit
def test_grounded_answer_rejects_boundary_kind_citation_for_conflict_status():
    with pytest.raises(EvidenceContractError, match="must not cite boundary-only evidence"):
        GroundedAnswer(
            status="conflict",
            claims=["claim A", "claim B"],
            claim_evidence_ids=[["POC1-BOUNDARY-USB4-EXCLUDED"], ["USB2-FEAT-PORT_POWER"]],
            citations=[
                Citation(
                    evidence_id="POC1-BOUNDARY-USB4-EXCLUDED",
                    excerpt="x",
                    citation_kind="boundary",
                ),
                Citation(
                    evidence_id="USB2-FEAT-PORT_POWER",
                    document="usb32-rev1.1",
                    revision="1.0",
                    chapter="10",
                    section="10.16.2.1",
                    page_or_anchor="10.16.2.1",
                    authority_level="authoritative",
                ),
            ],
            evidence_ids=["POC1-BOUNDARY-USB4-EXCLUDED", "USB2-FEAT-PORT_POWER"],
            boundary="UNRESOLVED_CONFLICT",
            scope="USB_3_X",
        )


@pytest.mark.unit
def test_grounded_answer_version_conflict_rejects_same_revision_different_document():
    # Commit C item 4 (Codex review, PR #33, P2): VERSION_CONFLICT must
    # specifically mean the *revision* differs -- two citations from
    # different documents but the SAME revision string are not a version
    # conflict, even though they are technically ">= 2 distinct provenance
    # identities" (the previous, generic check).
    with pytest.raises(EvidenceContractError, match="VERSION_CONFLICT.*distinct revisions"):
        GroundedAnswer(
            status="conflict",
            claims=["claim A", "claim B"],
            claim_evidence_ids=[["USB3-FEAT-PORT_POWER"], ["USB2-FEAT-PORT_POWER"]],
            citations=[
                Citation(
                    evidence_id="USB3-FEAT-PORT_POWER",
                    document="usb32-rev1.1",
                    revision="1.0",
                    chapter="10",
                    section="10.16.2.1",
                    page_or_anchor="10.16.2.1",
                    authority_level="authoritative",
                ),
                Citation(
                    evidence_id="USB2-FEAT-PORT_POWER",
                    document="usb20-fw",
                    revision="1.0",
                    chapter="10",
                    section="10.16.2.1",
                    page_or_anchor="10.16.2.1",
                    authority_level="authoritative",
                ),
            ],
            evidence_ids=["USB3-FEAT-PORT_POWER", "USB2-FEAT-PORT_POWER"],
            boundary="VERSION_CONFLICT",
            scope="USB_3_X",
        )


@pytest.mark.unit
def test_grounded_answer_authority_mismatch_rejects_same_authority_different_revision():
    # Commit C item 4, other half: AUTHORITY_MISMATCH must specifically mean
    # the *authority_level* differs -- two citations with the same
    # authority_level but different revisions are not an authority mismatch.
    with pytest.raises(EvidenceContractError, match="AUTHORITY_MISMATCH.*distinct authority levels"):
        GroundedAnswer(
            status="conflict",
            claims=["claim A", "claim B"],
            claim_evidence_ids=[["USB3-FEAT-PORT_POWER"], ["USB2-FEAT-PORT_POWER"]],
            citations=[
                Citation(
                    evidence_id="USB3-FEAT-PORT_POWER",
                    document="usb32-rev1.1",
                    revision="1.0",
                    chapter="10",
                    section="10.16.2.1",
                    page_or_anchor="10.16.2.1",
                    authority_level="authoritative",
                ),
                Citation(
                    evidence_id="USB2-FEAT-PORT_POWER",
                    document="usb32-rev1.1",
                    revision="1.1",
                    chapter="10",
                    section="10.16.2.1",
                    page_or_anchor="10.16.2.1",
                    authority_level="authoritative",
                ),
            ],
            evidence_ids=["USB3-FEAT-PORT_POWER", "USB2-FEAT-PORT_POWER"],
            boundary="AUTHORITY_MISMATCH",
            scope="USB_3_X",
        )


@pytest.mark.unit
def test_final_qa_citation_preserves_chapter_and_authority_level():
    # Commit C item 3: to_final_qa_response() must no longer silently drop
    # chapter/authority_level -- the P0 provenance fields
    # (docs/USB_SPEC_QA_POC1_SCOPE.md Section 5) must survive the projection
    # onto the evaluator's schema.
    service = GovernedQAService()
    resp = service.answer_question("PORT_POWER feature selector value", "USB_3_X")
    final_response = resp.to_final_qa_response()
    assert final_response.citations
    for citation, final_citation in zip(resp.citations, final_response.citations):
        assert final_citation.chapter == citation.chapter
        assert final_citation.authority_level == citation.authority_level
        assert citation.chapter is not None
        assert citation.authority_level is not None


@pytest.mark.contract
def test_final_evaluator_enforces_chapter_and_authority_level_when_required():
    # Commit C item 3: a question that opts into requiring chapter/
    # authority_level (required_citation_fields.chapter=True,
    # authority_level=True) must fail citation_complete when either is
    # missing, and pass when both are present -- proving the new fields are
    # load-bearing, not merely accepted-and-ignored schema additions.
    service = GovernedQAService()
    resp = service.answer_question("PORT_POWER feature selector value", "USB_3_X")
    final_response = resp.to_final_qa_response()

    question = AcceptanceQuestion(
        question_id="CHAIN-TEST-CHAPTER-AUTHORITY",
        layer="L1",
        priority="P0",
        category="single_spec_fact",
        question="PORT_POWER feature selector value",
        expected_status="answer",
        expected_scope="USB_3_X",
        accepted_source_ids=["hub_reference"],
        required_citation_fields=CitationRequirements(
            document=True,
            revision=True,
            section=True,
            page_or_anchor=True,
            excerpt_or_evidence_id=True,
            scope=True,
            boundary_code=False,
            chapter=True,
            authority_level=True,
            mode="normative_source",
        ),
        gold=GoldOracle(
            accepted_evidence_ids=list(resp.evidence_ids),
            required_claims=[GoldClaim(claim_id="c1", assertion=resp.claims[0], required=True)],
            section_anchors=[c.section for c in resp.citations],
            required_facts=[],
        ),
        grading=_CHAIN_GRADING_WEIGHTS,
        independently_reviewed=True,
    )

    evaluator = _evaluator_with_resolver(service.retriever)
    result = evaluator.evaluate_response(question, final_response)
    assert result.citation_complete is True

    # Strip chapter/authority_level to prove the requirement is enforced,
    # not silently ignored.
    stripped = final_response.model_copy(
        update={
            "citations": [
                citation.model_copy(update={"chapter": None, "authority_level": None})
                for citation in final_response.citations
            ]
        }
    )
    stripped_result = evaluator.evaluate_response(question, stripped)
    assert stripped_result.citation_complete is False


@pytest.mark.contract
def test_final_evaluator_rejects_citation_with_provenance_mismatch_against_canonical_retriever():
    # Codex review, PR #33, P1 (ctj1F): citation_valid must also check that a
    # response citation's provenance fields match the resolver's OWN
    # canonical record for that evidence_id (via
    # GovernedSpecRetriever.get_canonical_citation_by_id), not just that the
    # fields are individually present (citation_complete, a separate check)
    # or that the evidence_id resolves at all (fabricated, also separate). A
    # response could reuse a real evidence_id but attach the wrong
    # chapter/section/authority_level; previously nothing caught that.
    service = GovernedQAService()
    resp = service.answer_question("PORT_POWER feature selector value", "USB_3_X")
    final_response = resp.to_final_qa_response()

    question = AcceptanceQuestion(
        question_id="CHAIN-TEST-PROVENANCE-MISMATCH",
        layer="L1",
        priority="P0",
        category="single_spec_fact",
        question="PORT_POWER feature selector value",
        expected_status="answer",
        expected_scope="USB_3_X",
        accepted_source_ids=["hub_reference"],
        required_citation_fields=CitationRequirements(
            document=True,
            revision=True,
            section=True,
            page_or_anchor=True,
            excerpt_or_evidence_id=True,
            scope=True,
            boundary_code=False,
            chapter=False,
            authority_level=False,
            mode="normative_source",
        ),
        gold=GoldOracle(
            accepted_evidence_ids=list(resp.evidence_ids),
            required_claims=[GoldClaim(claim_id="c1", assertion=resp.claims[0], required=True)],
            section_anchors=[c.section for c in resp.citations],
            required_facts=[],
        ),
        grading=_CHAIN_GRADING_WEIGHTS,
        independently_reviewed=True,
    )

    evaluator = _evaluator_with_resolver(service.retriever)

    # The unmodified response must be valid -- proves the retriever really
    # does back this evidence_id with matching provenance, i.e. this is not
    # a check that would trivially pass regardless of what it compares.
    result = evaluator.evaluate_response(question, final_response)
    assert result.citation_valid is True

    # Corrupting chapter alone (evidence_id/document/etc. left correct, so
    # fabricated/authority_violation stay False) must still be caught.
    mismatched = final_response.model_copy(
        update={
            "citations": [
                citation.model_copy(update={"chapter": "not-the-real-chapter"})
                for citation in final_response.citations
            ]
        }
    )
    mismatched_result = evaluator.evaluate_response(question, mismatched)
    assert mismatched_result.fabricated_citation is False
    assert mismatched_result.authority_violation is False
    assert mismatched_result.citation_valid is False


@pytest.mark.contract
def test_final_evaluator_fails_closed_on_normative_citation_without_canonical_resolver():
    # Codex review, PR #33, P1 (cuREi): a resolver that cannot supply
    # get_canonical_citation_by_id() must NOT give every normative citation
    # a free pass on citation_valid -- "the check could not run" is not the
    # same as "the citation is correct". _StubEvidenceResolver only
    # implements get_evidence_by_id(), the same supported path the repo's
    # own SyntheticEvidenceResolver test stub used to exercise (Codex
    # named that stub directly as evidence the old design was toothless).
    service = GovernedQAService()
    resp = service.answer_question("PORT_POWER feature selector value", "USB_3_X")
    final_response = resp.to_final_qa_response()

    question = AcceptanceQuestion(
        question_id="CHAIN-TEST-FAIL-CLOSED-NO-CANONICAL",
        layer="L1",
        priority="P0",
        category="single_spec_fact",
        question="PORT_POWER feature selector value",
        expected_status="answer",
        expected_scope="USB_3_X",
        accepted_source_ids=["hub_reference"],
        required_citation_fields=CitationRequirements(
            document=True,
            revision=True,
            section=True,
            page_or_anchor=True,
            excerpt_or_evidence_id=True,
            scope=True,
            boundary_code=False,
            chapter=True,
            authority_level=True,
            mode="normative_source",
        ),
        gold=GoldOracle(
            accepted_evidence_ids=list(resp.evidence_ids),
            required_claims=[GoldClaim(claim_id="c1", assertion=resp.claims[0], required=True)],
            section_anchors=[c.section for c in resp.citations],
            required_facts=[],
        ),
        grading=_CHAIN_GRADING_WEIGHTS,
        independently_reviewed=True,
    )

    evaluator = _evaluator_with_resolver(_StubEvidenceResolver(resp.evidence_ids))
    result = evaluator.evaluate_response(question, final_response)
    # citation_complete/fabrication both pass -- only canonical provenance
    # verification is unavailable, and that alone must be enough to fail
    # citation_valid (and therefore grounded/passed).
    assert result.citation_complete is True
    assert result.fabricated_citation is False
    assert result.citation_valid is False
    assert result.passed is False


@pytest.mark.contract
def test_final_evaluator_flags_authority_violation_on_canonical_authority_level_mismatch():
    # Codex review, PR #33, P2 (cuREm): authority_violation must also
    # become True when a citation's authority_level disagrees with the
    # resolver's canonical record for that evidence_id -- not just when the
    # cited evidence_id itself falls outside the question's accepted set.
    # The evidence_id here IS accepted (a pure membership check would say
    # False), so this proves the new canonical-mismatch path is what flips
    # the result, and that it also feeds authority_violations_count.
    service = GovernedQAService()
    resp = service.answer_question("PORT_POWER feature selector value", "USB_3_X")
    final_response = resp.to_final_qa_response()

    question = AcceptanceQuestion(
        question_id="CHAIN-TEST-AUTHORITY-MISMATCH",
        layer="L1",
        priority="P0",
        category="single_spec_fact",
        question="PORT_POWER feature selector value",
        expected_status="answer",
        expected_scope="USB_3_X",
        accepted_source_ids=["hub_reference"],
        required_citation_fields=CitationRequirements(
            document=True,
            revision=True,
            section=True,
            page_or_anchor=True,
            excerpt_or_evidence_id=True,
            scope=True,
            boundary_code=False,
            chapter=False,
            authority_level=False,
            mode="normative_source",
        ),
        gold=GoldOracle(
            accepted_evidence_ids=list(resp.evidence_ids),
            required_claims=[GoldClaim(claim_id="c1", assertion=resp.claims[0], required=True)],
            section_anchors=[c.section for c in resp.citations],
            required_facts=[],
        ),
        grading=_CHAIN_GRADING_WEIGHTS,
        independently_reviewed=True,
    )

    evaluator = _evaluator_with_resolver(service.retriever)

    result = evaluator.evaluate_response(question, final_response)
    assert result.authority_violation is False

    mismatched = final_response.model_copy(
        update={
            "citations": [
                citation.model_copy(update={"authority_level": "not-the-real-authority-level"})
                for citation in final_response.citations
            ]
        }
    )
    mismatched_result = evaluator.evaluate_response(question, mismatched)
    # The cited evidence_id set is unchanged -- still fully accepted -- so
    # only the canonical authority_level mismatch can explain the flip.
    assert set(mismatched_result.cited_evidence_ids).issubset(set(resp.evidence_ids))
    assert mismatched_result.authority_violation is True
    assert mismatched_result.citation_valid is False


@pytest.mark.contract
def test_final_evaluator_rejects_boundary_citation_with_unrequested_chapter_or_authority_level():
    # Codex review, PR #33, P1 (cuREo): _required_citation_fields_present()
    # must reject chapter/authority_level being present when NOT required,
    # symmetrically with the other normative identity fields. This shape is
    # reachable at the FinalQAResponse layer even though
    # GroundedAnswer._check_contract() would reject the equivalent shape at
    # the QAResponse layer -- evaluate_response() accepts any raw dict
    # directly (e.g. from a benchmark answer_fn), so the evaluator's own
    # schema must not rely on GroundedAnswer having already filtered this
    # out upstream.
    question = AcceptanceQuestion(
        question_id="CHAIN-TEST-BOUNDARY-UNREQUESTED-CHAPTER",
        layer="L4",
        priority="P0",
        category="uncertainty_conflict",
        question="USB4 Hub 的 Warm Reset 規範為何？",
        expected_status="abstain",
        expected_scope="USB4_SPEC",
        accepted_source_ids=[],
        required_citation_fields=CitationRequirements(
            document=False,
            revision=False,
            section=False,
            page_or_anchor=False,
            excerpt_or_evidence_id=True,
            scope=True,
            boundary_code=True,
            chapter=False,
            authority_level=False,
            mode="boundary_evidence",
        ),
        gold=GoldOracle(
            boundary_evidence_ids=["USB4-OUT-OF-SCOPE"],
            required_claims=[GoldClaim(claim_id="b1", assertion="boundary claim", required=True)],
            boundary_code="OUT_OF_SCOPE",
        ),
        grading=_CHAIN_GRADING_WEIGHTS,
        independently_reviewed=True,
    )

    response = {
        "status": "abstain",
        "claims": ["boundary claim"],
        "citations": [
            {
                "evidence_id": "USB4-OUT-OF-SCOPE",
                "excerpt_or_evidence_id": "USB4-OUT-OF-SCOPE",
                "scope": "USB4_SPEC",
                "chapter": "10",
                "authority_level": "authoritative",
            }
        ],
        "scope": "USB4_SPEC",
        "boundary_code": "OUT_OF_SCOPE",
    }

    evaluator = _evaluator_with_resolver(_StubEvidenceResolver(["USB4-OUT-OF-SCOPE"]))
    result = evaluator.evaluate_response(question, response)
    assert result.citation_complete is False

    # Control: the identical shape without the unrequested fields must pass
    # -- proving the rejection above is about the unrequested fields, not
    # some unrelated part of this fixture.
    clean_citation = {
        key: value
        for key, value in response["citations"][0].items()
        if key not in ("chapter", "authority_level")
    }
    clean_response = {**response, "citations": [clean_citation]}
    clean_result = evaluator.evaluate_response(question, clean_response)
    assert clean_result.citation_complete is True


@pytest.mark.unit
def test_qa_service_usb4_corpus_membership_question_is_answered_not_abstained():
    # Commit C item 5 (docs/USB_SPEC_QA_POC1_SCOPE.md lines 86-88): a
    # question that is only asking whether USB4 is included in the current
    # corpus must be answered, not abstained -- backed by a governance-fact
    # citation, not a fake USB4 normative-spec citation.
    service = GovernedQAService()
    resp = service.answer_question("Is USB4 included in the Phase 1 corpus?")
    assert resp.status == "answer"
    assert resp.is_abstain is False
    assert resp.boundary_code is None
    assert resp.claims
    assert len(resp.citations) == 1
    assert resp.citations[0].evidence_id == "POC1-BOUNDARY-USB4-EXCLUDED"
    assert resp.citations[0].citation_kind == "governance"
    assert resp.citations[0].document is None  # not a fake normative citation


@pytest.mark.unit
def test_qa_service_generic_usb4_topic_question_still_abstains():
    # Negative control for the test above: a generic USB4 topic question
    # (not a corpus-membership question) must still abstain, proving the
    # membership carve-out is narrow and does not swallow the general USB4
    # exclusion.
    service = GovernedQAService()
    resp = service.answer_question("USB4 Hub 的 Warm Reset 規範為何？")
    assert resp.status == "abstain"
    assert resp.boundary_code == "OUT_OF_SCOPE"


@pytest.mark.unit
def test_qa_service_usb4_feature_question_with_included_is_not_misclassified_as_corpus_membership():
    # Codex review, PR #33, P2 (ctj1P): a broad marker list containing
    # generic single words like "included"/"包含" also matches ordinary
    # substantive USB4 feature questions, misclassifying them as
    # corpus-membership governance questions instead of the required
    # Phase-1-exclusion abstain. The narrowed whole-phrase pattern list must
    # not match these.
    service = GovernedQAService()

    resp_en = service.answer_question("What features are included in USB4?")
    assert resp_en.status == "abstain"
    assert resp_en.boundary_code == "OUT_OF_SCOPE"

    resp_zh = service.answer_question("USB4 包含哪些功能？")
    assert resp_zh.status == "abstain"
    assert resp_zh.boundary_code == "OUT_OF_SCOPE"


@pytest.mark.unit
def test_qa_service_usb4_hub_capability_question_is_not_misclassified_as_corpus_membership():
    # Codex review, PR #33, fresh finding on edf8825: the bare "usb4
    # included in" pattern alone also matches an ordinary hub-capability
    # question ("Is USB4 included in this hub's supported-protocol list?"),
    # which is asking about the hub, not the corpus, and must still abstain
    # as a generic USB4 topic question -- not be misclassified as a
    # corpus-membership governance question for lack of any corpus/phase
    # qualifier in the text.
    service = GovernedQAService()
    resp = service.answer_question(
        "Is USB4 included in this hub's supported-protocol list?"
    )
    assert resp.status == "abstain"
    assert resp.boundary_code == "OUT_OF_SCOPE"


@pytest.mark.contract
def test_qa_service_usb4_corpus_membership_answer_is_a_valid_grounded_answer():
    # Replaces the removed test_full_contract_chain_usb4_corpus_membership_
    # answer_passes_evaluator (Codex review, PR #33, P1): that test wrapped
    # the response in a hand-built AcceptanceQuestion with
    # accepted_source_ids=["usb4"], which POC1AcceptanceSet.validate_contract()
    # would reject outright -- "usb4" is not in REQUIRED_POC1_SOURCE_IDS, and
    # is deliberately not added there (that would legitimize citing USB4 as
    # an *answer* evidence source, contradicting its Phase 1 exclusion).
    # Calling it a "full contract chain" proof was misleading: it never
    # actually went through POC1AcceptanceSet/validate_contract() at all.
    #
    # This is a genuine, still end-to-end proof scoped to what actually
    # exists for this citation_kind="governance" answer shape: the runtime
    # QAService -> QAResponse chain, re-validated directly against
    # GroundedAnswer (the same contract _build_response() already enforces
    # internally), plus the projection onto FinalQAResponse. It does not
    # touch POC1AcceptanceSet/AcceptanceQuestion/validate_contract()/
    # REQUIRED_POC1_SOURCE_IDS -- a schema-1.1 acceptance manifest has no
    # citation mode for a governance-fact answer today, and this test does
    # not pretend otherwise.
    service = GovernedQAService()
    resp = service.answer_question("Is USB4 included in the Phase 1 corpus?")

    assert resp.status == "answer"
    assert resp.is_abstain is False
    assert resp.boundary_code is None
    assert len(resp.citations) == 1
    assert resp.citations[0].evidence_id == "POC1-BOUNDARY-USB4-EXCLUDED"
    assert resp.citations[0].citation_kind == "governance"

    # Re-validate the exact fields QAResponse claims to carry against
    # GroundedAnswer directly -- proving the contract still holds, not just
    # trusting that _build_response() validated it once at construction time.
    GroundedAnswer(
        status=resp.status,
        claims=resp.claims,
        claim_evidence_ids=resp.claim_evidence_ids,
        citations=resp.citations,
        scope=resp.scope,
        boundary=resp.boundary_code,
        evidence_ids=resp.evidence_ids,
    )

    # The projection onto the evaluator's schema must also succeed.
    final_response = resp.to_final_qa_response()
    assert final_response.status == "answer"
    assert final_response.citations[0].evidence_id == "POC1-BOUNDARY-USB4-EXCLUDED"


@pytest.mark.unit
def test_qa_service_usb4_corpus_membership_scope_defaults_to_governed_scope():
    # Codex review, PR #33, fresh finding on 88200c5: when the caller does
    # not declare an answer_scope, the response must use the boundary
    # evidence's own governed scope (USB4_SPEC) for this governance-fact
    # answer, not be left unset or copied from somewhere else.
    service = GovernedQAService()
    resp = service.answer_question("Is USB4 included in the Phase 1 corpus?")
    assert resp.scope == "USB4_SPEC"


@pytest.mark.unit
def test_qa_service_usb4_corpus_membership_scope_accepts_matching_answer_scope():
    service = GovernedQAService()
    resp = service.answer_question(
        "Is USB4 included in the Phase 1 corpus?", answer_scope="USB4_SPEC"
    )
    assert resp.scope == "USB4_SPEC"


@pytest.mark.unit
def test_qa_service_usb4_corpus_membership_rejects_conflicting_answer_scope():
    # Codex review, PR #33, fresh finding on 88200c5: `scope=answer_scope or
    # boundary_evidence.scope` used to silently accept an unrelated
    # caller-declared answer_scope (e.g. "USB_2_0") onto this USB4
    # governance-fact answer, mislabeling its true USB4_SPEC scope. This
    # service does not silently override -- nor silently accept -- a
    # conflicting caller-declared answer_scope; it fails closed instead.
    service = GovernedQAService()
    with pytest.raises(ValueError, match="answer_scope"):
        service.answer_question(
            "Is USB4 included in the Phase 1 corpus?", answer_scope="USB_2_0"
        )


@pytest.mark.unit
def test_qa_service_usb4_abstain_scope_defaults_to_governed_scope():
    service = GovernedQAService()
    resp = service.answer_question("USB4 Hub 的 Warm Reset 規範為何？")
    assert resp.scope == "USB4_SPEC"


@pytest.mark.unit
def test_qa_service_usb4_abstain_scope_accepts_matching_answer_scope():
    service = GovernedQAService()
    resp = service.answer_question(
        "USB4 Hub 的 Warm Reset 規範為何？", answer_scope="USB4_SPEC"
    )
    assert resp.scope == "USB4_SPEC"


@pytest.mark.unit
def test_qa_service_usb4_abstain_rejects_conflicting_answer_scope():
    # Same fail-closed rule for the analogous USB4 abstain branch (Codex
    # review, PR #33, fresh finding on 88200c5): the membership path had a
    # protective check while the abstain path did not.
    service = GovernedQAService()
    with pytest.raises(ValueError, match="answer_scope"):
        service.answer_question(
            "USB4 Hub 的 Warm Reset 規範為何？", answer_scope="USB_2_0"
        )


@pytest.mark.unit
def test_qa_service_missing_evidence_abstain_cannot_be_admitted_without_a_boundary_receipt():
    # Commit D item 2 (deliberately NOT Commit C-style): a runtime
    # MISSING_EVIDENCE abstain (zero retrieval results for a given query +
    # scope + policy + corpus revision) is a RUNTIME OBSERVATION, not a
    # static corpus fact -- unlike the USB4/generic-keyword boundary
    # evidence above, it must NOT be backed by a fabricated static citation
    # just to make an acceptance-manifest question "pass". This test proves
    # (rather than silently working around) that limitation: a manifest
    # question requiring boundary evidence for a MISSING_EVIDENCE abstain
    # currently CANNOT be admitted, because no BoundaryEvidence is (or
    # should be) registered for it. Fixing this for real requires a future
    # RetrievalBoundaryReceipt (query/scope/policy/corpus_lock_hash/
    # result_count=0), which is out of scope here and intentionally left
    # unimplemented rather than faked.
    service = GovernedQAService()
    resp = service.answer_question(
        "What is the maximum number of downstream ports on a hypothetical "
        "USB 3.x hub variant that does not exist in any governed source?",
        "USB_3_X",
    )
    assert resp.status == "abstain"
    assert resp.boundary_code == "MISSING_EVIDENCE"
    # The known, tracked limitation: no citation is available to back this
    # abstention, because none may be fabricated.
    assert resp.claims == []
    assert resp.citations == []

    final_response = resp.to_final_qa_response()
    question = AcceptanceQuestion(
        question_id="CHAIN-TEST-MISSING-EVIDENCE-ADMISSION-BLOCKED",
        layer="L4",
        priority="P0",
        category="uncertainty_conflict",
        question="a hypothetical hub variant with no governed evidence",
        expected_status="abstain",
        expected_scope=resp.scope,
        accepted_source_ids=[],
        required_citation_fields=CitationRequirements(
            document=False,
            revision=False,
            section=False,
            page_or_anchor=False,
            excerpt_or_evidence_id=True,
            scope=True,
            boundary_code=True,
            mode="boundary_evidence",
        ),
        gold=GoldOracle(
            boundary_evidence_ids=["SOME-FUTURE-RETRIEVAL-BOUNDARY-RECEIPT-ID"],
            required_claims=[GoldClaim(claim_id="b1", assertion="no evidence found", required=True)],
            boundary_code="MISSING_EVIDENCE",
        ),
        grading=_CHAIN_GRADING_WEIGHTS,
        independently_reviewed=True,
    )
    evaluator = _evaluator_with_resolver(service.retriever)
    result = evaluator.evaluate_response(question, final_response)
    # Admission-blocked: no citation exists to satisfy citation_complete, and
    # the cited evidence set is empty, so evidence_shape_correct is False.
    # This is the correct, honest outcome for an unimplemented
    # RetrievalBoundaryReceipt -- NOT a bug to silently patch by inventing an
    # evidence_id.
    assert result.passed is False
    assert result.citation_complete is False


def _qa_response_kwargs(**overrides) -> dict:
    # Minimal-but-valid QAResponse construction kwargs for the
    # is_abstain/status/boundary_code consistency tests below -- claims/
    # citations/claim_evidence_ids/evidence_ids are deliberately left at
    # their empty defaults since QAResponse's own model_validator does not
    # itself re-derive GroundedAnswer's claim-shape rules (that only
    # happens when _build_response() separately constructs a
    # GroundedAnswer); these tests isolate the
    # is_abstain/status/boundary_code projection check alone.
    base = dict(
        answer="an answer",
        scope="USB_3_X",
        cited_evidences=[],
        claim_level="answer",
        boundary="",
        is_abstain=False,
        status="answer",
        boundary_code=None,
    )
    base.update(overrides)
    return base


@pytest.mark.unit
def test_qa_response_answer_status_with_consistent_fields_passes():
    # Positive control: status="answer" with is_abstain=False and no
    # boundary_code is a valid, consistent QAResponse.
    response = QAResponse(**_qa_response_kwargs())
    assert response.status == "answer"
    assert response.is_abstain is False
    assert response.boundary_code is None


@pytest.mark.unit
def test_qa_response_conflict_status_with_consistent_fields_passes():
    # Positive control: status="conflict" with is_abstain=True and a
    # boundary_code is also a valid, consistent QAResponse (conflict is not
    # an abstention, but it's also not a plain answer -- see the
    # docstring on QAResponse._is_abstain_matches_status()).
    response = QAResponse(
        **_qa_response_kwargs(
            is_abstain=True,
            status="conflict",
            boundary_code="VERSION_CONFLICT",
            boundary="Two sources disagree.",
        )
    )
    assert response.status == "conflict"
    assert response.is_abstain is True
    assert response.boundary_code == "VERSION_CONFLICT"


@pytest.mark.unit
def test_qa_response_rejects_is_abstain_false_for_abstain_status():
    # Codex review, PR #33, P2, fresh finding on d4f3bf7: is_abstain is a
    # legacy fail-safe PROJECTION of status, not an independently settable
    # field -- a caller must not be able to construct
    # status="abstain"/is_abstain=False, which would let a legacy
    # boolean-only downstream consumer treat an abstention as a confident
    # answer.
    with pytest.raises(
        ValidationError,
        match="is_abstain must be the legacy fail-safe projection",
    ):
        QAResponse(
            **_qa_response_kwargs(
                is_abstain=False,
                status="abstain",
                boundary_code="OUT_OF_SCOPE",
                boundary="Exceeds governed knowledge surface.",
            )
        )


@pytest.mark.unit
def test_qa_response_rejects_is_abstain_true_for_answer_status():
    # The reverse inconsistency: status="answer" must always project to
    # is_abstain=False.
    with pytest.raises(
        ValidationError,
        match="is_abstain must be the legacy fail-safe projection",
    ):
        QAResponse(**_qa_response_kwargs(is_abstain=True, status="answer"))


@pytest.mark.unit
def test_qa_response_rejects_is_abstain_false_for_conflict_status():
    # "conflict" is not an abstention semantically, but it must still
    # project is_abstain=True for legacy boolean-only callers -- treating a
    # live source conflict as a plain confident answer would be worse than
    # treating it as "not a normal answer."
    with pytest.raises(
        ValidationError,
        match="is_abstain must be the legacy fail-safe projection",
    ):
        QAResponse(
            **_qa_response_kwargs(
                is_abstain=False,
                status="conflict",
                boundary_code="VERSION_CONFLICT",
                boundary="Two sources disagree.",
            )
        )


@pytest.mark.unit
def test_qa_response_rejects_boundary_code_present_for_answer_status():
    # boundary_code must be absent exactly when status == "answer" -- a
    # confident answer must not simultaneously carry a boundary_code
    # signaling abstention/conflict.
    with pytest.raises(
        ValidationError,
        match="boundary_code must be populated exactly when status is",
    ):
        QAResponse(
            **_qa_response_kwargs(
                is_abstain=False,
                status="answer",
                boundary_code="OUT_OF_SCOPE",
            )
        )


@pytest.mark.unit
def test_qa_response_rejects_missing_boundary_code_for_abstain_status():
    # The reverse: status="abstain" (with is_abstain correctly True) must
    # still populate a boundary_code -- an abstention with no boundary_code
    # gives a caller no machine-readable reason for the abstention.
    with pytest.raises(
        ValidationError,
        match="boundary_code must be populated exactly when status is",
    ):
        QAResponse(
            **_qa_response_kwargs(
                is_abstain=True,
                status="abstain",
                boundary_code=None,
                boundary="Exceeds governed knowledge surface.",
            )
        )


@pytest.mark.unit
def test_qa_response_legacy_only_construction_preserves_abstain_default():
    # Codex review, PR #33, P2, fresh finding on 7c74da3: a caller supplying
    # only the pre-existing legacy fields (no status/boundary_code at all)
    # inherits status="abstain"/boundary_code=None by default -- this must
    # still construct successfully, since it is exactly the previously-valid
    # legacy abstention the additive contract fields were meant to preserve,
    # not a self-contradictory payload. BoundaryCode has no generic
    # "unspecified" member a caller could supply even if forced to.
    response = QAResponse(
        answer="",
        scope="USB_3_X",
        cited_evidences=[],
        claim_level="abstain",
        boundary="Exceeds governed knowledge surface.",
        is_abstain=True,
    )
    assert response.status == "abstain"
    assert response.boundary_code is None
    assert response.is_abstain is True


@pytest.mark.unit
def test_qa_response_legacy_only_construction_still_enforces_is_abstain_projection():
    # The boundary_code consistency check being gated on explicit
    # status/boundary_code use (see previous test) must not weaken the
    # unconditional is_abstain/status projection check from the earlier
    # d4f3bf7 finding: a legacy-only caller claiming is_abstain=False (an
    # answer) while leaving status at its "abstain" default is still a
    # self-contradictory payload and must still be rejected.
    with pytest.raises(
        ValidationError,
        match="is_abstain must be the legacy fail-safe projection",
    ):
        QAResponse(
            answer="some answer",
            scope="USB_3_X",
            cited_evidences=[],
            claim_level="answer",
            boundary="",
            is_abstain=False,
        )
