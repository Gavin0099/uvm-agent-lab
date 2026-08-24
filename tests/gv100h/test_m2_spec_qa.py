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


@pytest.mark.contract
def test_poc1_corpus_lock_binds_governed_reference_and_blocks_incomplete_claims():
    retriever = GovernedSpecRetriever()

    assert retriever.corpus_id == "usb-hub-poc1-phase1"
    assert retriever.knowledge_repo == "Gavin0099/usb-if-hub-spec-reference"
    assert retriever.knowledge_repo_commit == "808f23c24bd8651da9cdcd63ea8669126917a379"
    assert retriever.corpus_binding_status == "manifest_only_pending_binding"
    assert retriever.lock_binding_status == "manifest_only_pending_binding"
    assert retriever.runtime_binding_status == "unverified"
    assert retriever.physical_binding_verified is False
    assert retriever.corpus_lock["sources"]["hub_reference"]["binding_status"] == "locked"
    assert retriever.corpus_lock["binding_requirements"]["content_hash_algorithm"] == "sha256_tracked_relative_posix_path_content_bytes_v3"
    assert retriever.corpus_lock["sources"]["usb32"]["revision"] == "Rev 1.1"
    assert retriever.corpus_lock["sources"]["superspeed_hub_lvs"]["revision"] == "Rev 1.15"
    assert retriever.corpus_lock["sources"]["usb4"]["included"] is False
    assert retriever.corpus_lock["benchmark"]["independent_from_corpus"] is True
    assert retriever.qualification_blocked is True
    assert any("sources.usb20_fw" in reason for reason in retriever.qualification_block_reasons)


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
        lock["sources"][source_id]["source_locator"] = str(source_path)
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
