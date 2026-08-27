import copy
import hashlib
import pytest
import sys
import subprocess
from pathlib import Path
import yaml

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
    # abstain response must declare a boundary code and no claims/citations,
    # and the boundary_code/claims/scope must survive onto QAResponse itself
    # (Codex review P1), not just be validated and discarded internally.
    assert resp.status == "abstain"
    assert resp.citations == []
    assert resp.evidence_ids == []
    assert resp.claims == []
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
    for key in ("status", "claims", "citations", "scope", "boundary_code", "evidence_ids"):
        assert key in dumped

    reconstructed = GroundedAnswer(
        status=dumped["status"],
        claims=dumped["claims"],
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

    evaluator = _evaluator_with_resolver(_StubEvidenceResolver(["USB4-OUT-OF-SCOPE"]))
    result = evaluator.evaluate_response(question, final_response)
    assert result.passed is True
    assert result.citation_complete is True
    assert result.fabricated_citation is False


class _RetrieverBackedEvidenceResolver:
    """
    Wraps a real GovernedSpecRetriever so evaluate_response() checks
    resolvability against the actual answer-evidence AND boundary-evidence
    registries -- unlike _StubEvidenceResolver above (which accepts
    whatever ID it is told about), this resolver can actually fail to
    resolve an evidence_id, the same way a production resolver would.
    """

    def __init__(self, retriever: GovernedSpecRetriever):
        self._retriever = retriever

    def get_evidence_by_id(self, evidence_id: str):
        return self._retriever.get_evidence_by_id(
            evidence_id
        ) or self._retriever.get_boundary_evidence_by_id(evidence_id)


@pytest.mark.contract
def test_full_contract_chain_usb4_boundary_abstain_uses_real_registered_evidence():
    # Codex review (PR #33, P1): the chain test above proves the SHAPE is
    # admissible using a hand-built QAResponse and a stub resolver that
    # accepts any ID it's told about -- it does not prove the *runtime*
    # produces this shape, nor that the citation resolves against the real
    # Boundary Evidence Registry rather than an ad-hoc string. This test
    # proves the full, real chain: GovernedQAService.answer_question()
    # (real retriever, real BOUNDARY_EVIDENCE_REGISTRY) -> QAResponse ->
    # to_final_qa_response() -> FinalPOC1Evaluator, resolved by a resolver
    # backed by the same real GovernedSpecRetriever instance -- no stub, no
    # fabricated evidence_id.
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

    evaluator = _evaluator_with_resolver(_RetrieverBackedEvidenceResolver(service.retriever))
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

    evaluator = _evaluator_with_resolver(_RetrieverBackedEvidenceResolver(service.retriever))
    result = evaluator.evaluate_response(question, final_response)
    assert result.fabricated_citation is True
