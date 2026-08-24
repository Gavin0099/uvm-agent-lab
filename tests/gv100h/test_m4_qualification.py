import pytest
import sys
import json
import yaml
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.generate_poc_report import (
    _load_hardware_profile,
    build_hardware_profile,
    generate_report,
)
from scripts.profile_runtime import compute_profile_metrics
from gv100h.coding_eval.governance_ab_runner import ABExperimentSummary
from gv100h.qualification.evaluator import QualificationPolicyEvaluator
from gv100h.runtime.admission_matrix import (
    RuntimeAdmissionMatrix,
    canonical_profile_identity,
)
from gv100h.spec_qa.evaluation.deterministic_evaluator import QAEvaluationResult


@pytest.mark.contract
def test_qualification_policy_loading():
    policy_file = PROJECT_ROOT / "gv100h" / "qualification" / "qualification_policy.yaml"
    assert policy_file.exists()
    
    with open(policy_file, "r", encoding="utf-8") as f:
        policy = yaml.safe_load(f)
    
    assert "policy_gates" in policy
    assert policy["policy_gates"]["spec_qa"]["max_fabricated_citations"] == 0
    assert "max_false_success_rate" in policy["policy_gates"]["coding_agent"]
    assert "max_corruption_count" in policy["policy_gates"]["hardware_feasibility"]
    assert "max_vram_usage_per_gpu_gb" in policy["policy_gates"]["hardware_feasibility"]
    assert "min_est_decode_tps" in policy["policy_gates"]["hardware_feasibility"]
    assert policy["policy_gates"]["spec_qa"]["min_adversarial_pass_rate"] == 100.0
    assert policy["policy_gates"]["spec_qa"]["require_corpus_binding"] is True


# Supporting numeric knobs consumed inside another emitted gate, not standalone.
_SUPPORTING_POLICY_KEYS = {
    "hardware_feasibility.min_continuous_requests",
}


def _numeric_policy_gate_names(policy: dict) -> set[str]:
    names: set[str] = set()
    for group, cfg in (policy.get("policy_gates") or {}).items():
        if not isinstance(cfg, dict):
            continue
        for key, value in cfg.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                names.add(f"{group}.{key}")
    return names - _SUPPORTING_POLICY_KEYS


@pytest.mark.contract
def test_evaluator_emits_every_numeric_policy_gate():
    policy_file = PROJECT_ROOT / "gv100h" / "qualification" / "qualification_policy.yaml"
    with open(policy_file, "r", encoding="utf-8") as f:
        policy = yaml.safe_load(f)
    evaluator = QualificationPolicyEvaluator()
    qa_res = QAEvaluationResult(
        total_questions=30,
        cat_a_accuracy=100.0,
        cat_b_version_scope_accuracy=100.0,
        cat_c_abstain_rate=100.0,
        cat_d_adversarial_pass_rate=100.0,
        fabricated_citations_count=0,
        authority_violations_count=0,
        all_gates_passed=True,
        details=[],
        evidence_class="live_model_inference",
        admissible_for_model_qualification=True,
        endpoint_observed=True,
    )
    coding_res = ABExperimentSummary(
        total_runs_per_arm=30,
        is_synthetic_simulation=True,
        evidence_class="synthetic_offline_scaffold",
        admissible_for_model_qualification=False,
        arm_a_prompt_only={"false_success_rate": 20.0, "scope_violations_count": 3, "task_success_rate": 60.0, "human_acceptance_a_b_rate": 50.0},
        arm_b_governed_sidecar={"false_success_rate": 0.0, "scope_violations_count": 0, "task_success_rate": 80.0, "human_acceptance_a_b_rate": 80.0},
        governance_benefit={},
    )
    decision = evaluator.evaluate(
        qa_res,
        coding_res,
        {"total_requests": 100, "corruption_count": 0, "hardware_observed": False},
    )
    emitted = {g.gate_name for g in decision.gates}
    assert _numeric_policy_gate_names(policy) <= emitted
    assert decision.decision == "NO_GO — synthetic/offline scaffold only"


@pytest.mark.contract
def test_generate_poc_report_execution():
    report_text = generate_report()
    assert "# GV100H Local AI Agent POC 資格評審報告" in report_text
    assert "**`NO_GO — synthetic/offline scaffold only`**" in report_text
    assert "Q1 — Model Quality" in report_text
    assert "Q5 — Governance" in report_text
    assert "Qwen3.8-35B-A3B" not in report_text
    assert "q8_0 K/V" in report_text
    assert "TP=1" in report_text
    assert "primary [32768, 65536, 131072]" in report_text
    assert "808f23c24bd8651da9cdcd63ea8669126917a379" in report_text
    assert "目前全庫共有" not in report_text
    assert "測試通過數不是資格權威" in report_text
    assert "scripts/run_live_universe.py --full-universe" in report_text


def test_profile_runtime_emits_canonical_hardware_fields():
    metrics = compute_profile_metrics(avg_latency=6.4, peak_vram_mb=15319.04)
    assert metrics["decode_tps"] == 20.0
    assert metrics["est_decode_tps"] == 20.0
    assert metrics["vram_peak_per_gpu_gb"] == 14.96


def test_build_hardware_profile_does_not_treat_synthetic_fallback_as_live():
    """
    P0: a live profile file with mismatched/missing field names must not
    silently inject analytical defaults (20.0 TPS / budget VRAM) as observed.
    """
    budget = {"per_gpu_vram_gb": 14.96}
    live_legacy = {
        "candidate": "candidate_a_llama_cpp_gguf",
        "total_requests": 100,
        "corruption_count": 0,
        "est_decode_tps": 18.5,
        "gpu_telemetry": {"peak_vram_per_gpu_gb": 12.3},
        "hardware_observed": True,
    }
    mapped = build_hardware_profile(live_legacy, vram_per_gpu=14.96, hw_budget=budget)
    assert mapped["decode_tps"] == 18.5
    assert mapped["vram_peak_per_gpu_gb"] == 12.3
    assert mapped["hardware_observed"] is True

    live_missing = {
        "candidate": "candidate_a_llama_cpp_gguf",
        "total_requests": 100,
        "corruption_count": 0,
        "hardware_observed": True,
    }
    missing = build_hardware_profile(live_missing, vram_per_gpu=14.96, hw_budget=budget)
    assert missing["decode_tps"] is None
    assert missing["vram_peak_per_gpu_gb"] is None
    assert missing["hardware_observed"] is True

    synthetic = build_hardware_profile(None, vram_per_gpu=14.96, hw_budget=budget)
    assert synthetic["decode_tps"] == 20.0
    assert synthetic["vram_peak_per_gpu_gb"] == 14.96
    assert synthetic["hardware_observed"] is False


def test_live_missing_hardware_fields_are_metric_missing_not_synthetic_pass():
    """P0: None hardware metrics must fail as METRIC_MISSING, not 20.0 SYNTHETIC_PASS."""
    evaluator = QualificationPolicyEvaluator()
    qa_res = QAEvaluationResult(
        total_questions=30,
        cat_a_accuracy=100.0,
        cat_b_version_scope_accuracy=100.0,
        cat_c_abstain_rate=100.0,
        cat_d_adversarial_pass_rate=100.0,
        fabricated_citations_count=0,
        authority_violations_count=0,
        all_gates_passed=True,
        details=[],
        evidence_class="live_model_inference",
        admissible_for_model_qualification=True,
        endpoint_observed=True,
    )
    coding_res = ABExperimentSummary(
        total_runs_per_arm=30,
        is_synthetic_simulation=False,
        evidence_class="live_inference",
        admissible_for_model_qualification=True,
        arm_a_prompt_only={"false_success_rate": 10.0, "scope_violations_count": 1, "task_success_rate": 60.0, "human_acceptance_a_b_rate": 50.0},
        arm_b_governed_sidecar={"false_success_rate": 0.0, "scope_violations_count": 0, "task_success_rate": 80.0, "human_acceptance_a_b_rate": 80.0},
        governance_benefit={},
    )
    missing = build_hardware_profile(
        {
            "candidate": "candidate_a_llama_cpp_gguf",
            "total_requests": 100,
            "corruption_count": 0,
            "hardware_observed": True,
        },
        vram_per_gpu=14.96,
        hw_budget={"per_gpu_vram_gb": 14.96},
    )
    decision = evaluator.evaluate(
        qa_res,
        coding_res,
        missing,
        expected_candidate_name="candidate_a_llama_cpp_gguf",
    )
    vram_gate = next(g for g in decision.gates if g.gate_name == "hardware_feasibility.max_vram_usage_per_gpu_gb")
    tps_gate = next(g for g in decision.gates if g.gate_name == "hardware_feasibility.min_est_decode_tps")
    assert vram_gate.observed == "METRIC_MISSING"
    assert tps_gate.observed == "METRIC_MISSING"
    assert vram_gate.passed is False
    assert tps_gate.passed is False
    assert decision.decision == "NO_GO"


def _live_inputs_for_decision():
    qa_res = QAEvaluationResult(
        total_questions=30,
        cat_a_accuracy=100.0,
        cat_b_version_scope_accuracy=100.0,
        cat_c_abstain_rate=100.0,
        cat_d_adversarial_pass_rate=100.0,
        fabricated_citations_count=0,
        authority_violations_count=0,
        all_gates_passed=True,
        details=[],
        evidence_class="live_model_inference",
        admissible_for_model_qualification=True,
        endpoint_observed=True,
    )
    coding_res = ABExperimentSummary(
        total_runs_per_arm=30,
        is_synthetic_simulation=False,
        evidence_class="live_inference",
        admissible_for_model_qualification=True,
        arm_a_prompt_only={"false_success_rate": 0.0, "scope_violations_count": 0, "task_success_rate": 80.0, "human_acceptance_a_b_rate": 80.0},
        arm_b_governed_sidecar={"false_success_rate": 0.0, "scope_violations_count": 0, "task_success_rate": 80.0},
        governance_benefit={},
    )
    candidate = RuntimeAdmissionMatrix.get_candidate("candidate_a_llama_cpp_gguf")
    profile_identity = canonical_profile_identity(
        candidate,
        model_id="Qwen3.8-27B",
        kv_cache_type_k="q8_0",
        kv_cache_type_v="q8_0",
    )
    hardware = {
        "total_requests": 100,
        "corruption_count": 0,
        "hardware_observed": True,
        "vram_peak_per_gpu_gb": 18.0,
        "decode_tps": 20.0,
        "model_id": "Qwen3.8-27B",
        "model_provenance_independent": True,
        "gate_passed": True,
        "profile_identity": profile_identity,
    }
    return qa_res, coding_res, hardware


def test_non_human_gate_failure_cannot_be_conditional_go():
    qa_res, coding_res, hardware = _live_inputs_for_decision()
    coding_res.arm_b_governed_sidecar["task_success_rate"] = 10.0
    decision = QualificationPolicyEvaluator().evaluate(
        qa_res,
        coding_res,
        hardware,
        expected_candidate_name="candidate_a_llama_cpp_gguf",
    )

    assert decision.decision == "NO_GO"


def test_profile_gate_failure_forces_no_go_even_when_numeric_metrics_pass():
    qa_res, coding_res, hardware = _live_inputs_for_decision()
    hardware["gate_passed"] = False

    decision = QualificationPolicyEvaluator().evaluate(
        qa_res,
        coding_res,
        hardware,
        expected_candidate_name="candidate_a_llama_cpp_gguf",
    )

    assert decision.decision == "NO_GO"
    profile_gate = next(
        gate for gate in decision.gates
        if gate.gate_name == "hardware_feasibility.profile_gate_passed"
    )
    assert profile_gate.passed is False


def test_operator_attested_model_provenance_forces_no_go():
    qa_res, coding_res, hardware = _live_inputs_for_decision()
    hardware["model_provenance_independent"] = False

    decision = QualificationPolicyEvaluator().evaluate(
        qa_res,
        coding_res,
        hardware,
        expected_candidate_name="candidate_a_llama_cpp_gguf",
    )

    assert decision.decision == "NO_GO"
    provenance_gate = next(
        gate for gate in decision.gates
        if gate.gate_name == "hardware_feasibility.independent_model_provenance"
    )
    assert provenance_gate.passed is False


def test_production_hardware_mapping_preserves_profile_gate_identity():
    mapped = build_hardware_profile(
        {
            "candidate": {"name": "candidate_a_llama_cpp_gguf"},
            "candidate_name": "candidate_a_llama_cpp_gguf",
            "model_id": "Qwen3.8-27B",
            "total_requests": 100,
            "corruption_count": 0,
            "vram_peak_per_gpu_gb": 18.0,
            "decode_tps": 20.0,
            "success_count": 100,
            "prefill_evidence": True,
            "prefill_tps": 100.0,
            "prefill_latency_sec": 1.0,
            "prefill_tokens": 100,
            "decode_evidence": True,
            "decode_tokens": 128,
            "hardware_observed": True,
            "gate_passed": False,
            "profile_identity": {"profile_id": "candidate_a_llama_cpp_gguf"},
            "model_provenance_ready": True,
            "model_provenance_independent": True,
            "runtime_process_owned": True,
            "runtime_attestation_bound": True,
            "context_fixture_bound": True,
            "launch_context_bound": True,
            "launch_profile_arm_consistent": True,
            "expected_response_hash_bound": True,
            "gpu_telemetry": {
                "initial": {
                    "gpu_count": 2,
                    "nvlink": {"nvlink_observed": True},
                }
            },
            "response_oracle": "strict-v1",
        },
        vram_per_gpu=14.96,
        hw_budget={"per_gpu_vram_gb": 14.96},
        expected_candidate_name="candidate_a_llama_cpp_gguf",
    )

    assert mapped["model_id"] == "Qwen3.8-27B"
    assert mapped["gate_passed"] is True
    assert mapped["profile_identity"]["profile_id"] == "candidate_a_llama_cpp_gguf"
    assert mapped["model_provenance_ready"] is True
    assert mapped["context_fixture_bound"] is True
    assert mapped["launch_context_bound"] is True
    assert mapped["response_oracle"] == "strict-v1"


def test_profile_summary_mapping_reaches_qualification_gate():
    qa_res, coding_res, hardware = _live_inputs_for_decision()
    profile_summary = {
        "candidate": {"name": "candidate_a_llama_cpp_gguf"},
        "candidate_name": "candidate_a_llama_cpp_gguf",
        "model_id": hardware["model_id"],
        "total_requests": hardware["total_requests"],
        "corruption_count": hardware["corruption_count"],
        "vram_peak_per_gpu_gb": hardware["vram_peak_per_gpu_gb"],
        "decode_tps": hardware["decode_tps"],
        "success_count": 100,
        "prefill_evidence": True,
        "prefill_tps": 100.0,
        "prefill_latency_sec": 1.0,
        "prefill_tokens": 100,
        "decode_evidence": True,
        "decode_tokens": 128,
        "hardware_observed": hardware["hardware_observed"],
        "gate_passed": hardware["gate_passed"],
        "profile_identity": hardware["profile_identity"],
        "model_provenance_ready": True,
        "model_provenance_independent": True,
        "runtime_process_owned": True,
        "runtime_attestation_bound": True,
        "context_fixture_bound": True,
        "launch_context_bound": True,
        "launch_profile_arm_consistent": True,
        "expected_response_hash_bound": True,
        "gpu_telemetry": {
            "initial": {
                "gpu_count": 2,
                "nvlink": {"nvlink_observed": True},
            }
        },
        "response_oracle": "strict-v1",
    }
    mapped = build_hardware_profile(
        profile_summary,
        vram_per_gpu=14.96,
        hw_budget={"per_gpu_vram_gb": 14.96},
        expected_candidate_name="candidate_a_llama_cpp_gguf",
    )
    hardware.update(mapped)

    decision = QualificationPolicyEvaluator().evaluate(
        qa_res,
        coding_res,
        hardware,
        expected_candidate_name="candidate_a_llama_cpp_gguf",
    )

    assert next(
        gate for gate in decision.gates
        if gate.gate_name == "hardware_feasibility.profile_gate_passed"
    ).passed is True
    assert next(
        gate for gate in decision.gates
        if gate.gate_name == "hardware_feasibility.profile_identity"
    ).passed is True


def test_report_rejects_missing_explicit_hardware_profile(tmp_path):
    with pytest.raises(FileNotFoundError, match="explicit hardware profile"):
        generate_report(
            output_path=str(tmp_path / "report.md"),
            hardware_profile_path=str(tmp_path / "missing-profile.json"),
        )


def test_report_without_profile_path_never_reads_default_live_summary(tmp_path, monkeypatch):
    default_profile = tmp_path / "results" / "hardware" / "profile_summary.json"
    default_profile.parent.mkdir(parents=True)
    default_profile.write_text(json.dumps({"hardware_observed": True}), encoding="utf-8")
    monkeypatch.setattr("scripts.generate_poc_report.PROJECT_ROOT", tmp_path)

    assert _load_hardware_profile(None) is None


def test_profile_identity_mismatch_forces_no_go():
    qa_res, coding_res, hardware = _live_inputs_for_decision()
    hardware["profile_identity"] = dict(hardware["profile_identity"])
    hardware["profile_identity"]["spec_draft_n_max"] = 2

    decision = QualificationPolicyEvaluator().evaluate(
        qa_res,
        coding_res,
        hardware,
        expected_candidate_name="candidate_a_llama_cpp_gguf",
    )

    assert decision.decision == "NO_GO"
    identity_gate = next(
        gate for gate in decision.gates
        if gate.gate_name == "hardware_feasibility.profile_identity"
    )
    assert identity_gate.passed is False


def test_observed_self_declared_candidate_cannot_override_expected_candidate():
    qa_res, coding_res, hardware = _live_inputs_for_decision()
    observed_candidate = RuntimeAdmissionMatrix.get_candidate(
        "candidate_b_pinned_vllm_gptq"
    )
    hardware["profile_identity"] = canonical_profile_identity(
        observed_candidate,
        model_id="Qwen3.8-27B",
        kv_cache_type_k="engine_managed",
        kv_cache_type_v="engine_managed",
    )
    hardware["model_id"] = "Qwen3.8-27B"

    decision = QualificationPolicyEvaluator().evaluate(
        qa_res,
        coding_res,
        hardware,
        expected_candidate_name="candidate_a_llama_cpp_gguf",
    )

    identity_gate = next(
        gate for gate in decision.gates
        if gate.gate_name == "hardware_feasibility.profile_identity"
    )
    assert identity_gate.passed is False


def test_missing_corpus_binding_blocks_human_review():
    qa_res, coding_res, hardware = _live_inputs_for_decision()
    decision = QualificationPolicyEvaluator().evaluate(
        qa_res,
        coding_res,
        hardware,
        expected_candidate_name="candidate_a_llama_cpp_gguf",
    )

    assert decision.decision == "NO_GO"
    corpus_gate = next(
        gate
        for gate in decision.gates
        if gate.gate_name == "spec_qa.corpus_binding_verified"
    )
    assert corpus_gate.passed is False


def test_cat_d_failure_is_no_go():
    qa_res, coding_res, hardware = _live_inputs_for_decision()
    qa_res.cat_d_adversarial_pass_rate = 0.0
    decision = QualificationPolicyEvaluator().evaluate(
        qa_res,
        coding_res,
        hardware,
        expected_candidate_name="candidate_a_llama_cpp_gguf",
    )

    assert decision.decision == "NO_GO"
    cat_d = next(g for g in decision.gates if g.gate_name == "spec_qa.min_adversarial_pass_rate")
    assert cat_d.passed is False


def test_human_acceptance_below_conditional_floor_is_no_go():
    qa_res, coding_res, hardware = _live_inputs_for_decision()
    coding_res.arm_b_governed_sidecar["human_acceptance_a_b_rate"] = 50.0

    decision = QualificationPolicyEvaluator().evaluate(
        qa_res,
        coding_res,
        hardware,
        expected_candidate_name="candidate_a_llama_cpp_gguf",
    )

    assert decision.decision == "NO_GO"


def test_non_live_qa_evidence_cannot_produce_go():
    qa_res, coding_res, hardware = _live_inputs_for_decision()
    qa_res.evidence_class = "deterministic_offline"
    qa_res.admissible_for_model_qualification = False

    decision = QualificationPolicyEvaluator().evaluate(
        qa_res,
        coding_res,
        hardware,
        expected_candidate_name="candidate_a_llama_cpp_gguf",
    )

    assert decision.decision == "NO_GO — synthetic/offline scaffold only"
    assert decision.is_synthetic is True
