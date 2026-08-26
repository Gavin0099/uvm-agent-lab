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
from gv100h.spec_qa.api.qa_service import GovernedQAService
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
    results = retriever.query("PORT_POWER", target_scope="USB_3_X")
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
        target_scope="USB_3_X",
    )
    assert results == []


@pytest.mark.unit
def test_governed_retriever_abstains_on_pure_scope_match_without_topic_signal():
    # A matching target_scope with zero topic/term relevance must never by
    # itself qualify any evidence entry as a candidate.
    retriever = GovernedSpecRetriever()
    results = retriever.query("completely unrelated benign question", target_scope="USB_3_X")
    assert results == []


@pytest.mark.unit
def test_governed_retriever_still_finds_genuine_port_link_state_match():
    # Sanity check: tightening the generic-token/scope rules must not break
    # legitimate PORT_LINK_STATE queries that use the specific feature name.
    retriever = GovernedSpecRetriever()
    results = retriever.query("PORT_LINK_STATE feature selector value", target_scope="USB_3_X")
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
        target_scope="USB_2_0",
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
        "What is the link state feature selector value?", target_scope="USB_3_X"
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
        target_scope="USB_3_X",
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
        target_scope="USB_3_X",
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
        target_scope="USB_3_X",
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
        target_scope="USB_3_X",
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
        target_scope="USB_3_X",
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
def test_governed_retriever_scope_bonus_is_reranking_only_not_a_hard_filter():
    # KNOWN LIMITATION, intentionally documented rather than silently
    # assumed solved (see PR #29 review discussion): target_scope is only a
    # reranking bonus, not a hard evidence-scope boundary. A topically
    # relevant query still surfaces the out-of-scope evidence entry
    # alongside the in-scope one. A hard `if ev.scope != target_scope:
    # continue` filter is NOT a safe substitute here, because some
    # legitimate questions (e.g. "is PORT_LINK_STATE supported in USB 2.0?")
    # must cite out-of-scope evidence to correctly answer a question about
    # the target scope. Properly closing this requires splitting the
    # retrieval contract into `answer_scope` vs `allowed_evidence_scopes`,
    # tracked as follow-up work, not a change to this bonus.
    retriever = GovernedSpecRetriever()
    results = retriever.query("PORT_POWER feature selector value", target_scope="USB_2_0")
    result_ids = {r.evidence_id for r in results}
    assert "USB2-FEAT-PORT_POWER" in result_ids
    assert "USB3-FEAT-PORT_POWER" in result_ids
    # The in-scope evidence must still be ranked first via the scope bonus.
    assert results[0].evidence_id == "USB2-FEAT-PORT_POWER"


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
    result = evaluator.run_benchmark(lambda _query, _scope: ("", []))

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
    ).run_benchmark(lambda _query, _scope: ("", []))
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
    result = evaluator.run_benchmark(lambda _query, _scope: ("", []))

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
    result = evaluator.run_benchmark(lambda _query, _scope: ("", []))

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
