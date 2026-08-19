import pytest
import sys
import yaml
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.generate_poc_report import generate_report, build_hardware_profile
from scripts.profile_runtime import compute_profile_metrics
from gv100h.coding_eval.governance_ab_runner import ABExperimentSummary
from gv100h.qualification.evaluator import QualificationPolicyEvaluator
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
            if isinstance(value, (int, float)):
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
    decision = evaluator.evaluate(qa_res, coding_res, missing)
    vram_gate = next(g for g in decision.gates if g.gate_name == "hardware_feasibility.max_vram_usage_per_gpu_gb")
    tps_gate = next(g for g in decision.gates if g.gate_name == "hardware_feasibility.min_est_decode_tps")
    assert vram_gate.observed == "METRIC_MISSING"
    assert tps_gate.observed == "METRIC_MISSING"
    assert vram_gate.passed is False
    assert tps_gate.passed is False
    assert decision.decision == "NO_GO"
