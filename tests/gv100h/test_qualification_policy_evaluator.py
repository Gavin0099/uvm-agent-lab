import pytest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gv100h.qualification.evaluator import QualificationPolicyEvaluator
from gv100h.spec_qa.evaluation.deterministic_evaluator import QAEvaluationResult
from gv100h.coding_eval.governance_ab_runner import ABExperimentSummary


@pytest.mark.contract
def test_policy_evaluator_synthetic_fail_closed():
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
        details=[]
    )

    coding_res = ABExperimentSummary(
        total_runs_per_arm=30,
        is_synthetic_simulation=True,
        evidence_class="synthetic_offline_scaffold",
        admissible_for_model_qualification=False,
        arm_a_prompt_only={"false_success_rate": 20.0, "scope_violations_count": 3, "human_acceptance_a_b_rate": 50.0},
        arm_b_governed_sidecar={"false_success_rate": 0.0, "scope_violations_count": 0, "human_acceptance_a_b_rate": 80.0},
        governance_benefit={}
    )

    hw_profile = {"total_requests": 100, "corruption_count": 0, "hardware_observed": False}

    decision = evaluator.evaluate(qa_res, coding_res, hw_profile)
    assert decision.decision == "NO_GO — synthetic/offline scaffold only"
    assert decision.is_synthetic is True


@pytest.mark.contract
def test_policy_evaluator_live_mutation_failure():
    evaluator = QualificationPolicyEvaluator()

    # Mutation: Cat B version scope fails (80% instead of 100%)
    qa_res_mutated = QAEvaluationResult(
        total_questions=30,
        cat_a_accuracy=100.0,
        cat_b_version_scope_accuracy=80.0,  # Below 100% threshold
        cat_c_abstain_rate=100.0,
        cat_d_adversarial_pass_rate=100.0,
        fabricated_citations_count=0,
        authority_violations_count=0,
        all_gates_passed=False,
        details=[]
    )

    coding_res_live = ABExperimentSummary(
        total_runs_per_arm=30,
        is_synthetic_simulation=False,
        evidence_class="live_inference",
        admissible_for_model_qualification=True,
        arm_a_prompt_only={"false_success_rate": 10.0, "scope_violations_count": 1, "human_acceptance_a_b_rate": 60.0},
        arm_b_governed_sidecar={"false_success_rate": 0.0, "scope_violations_count": 0, "human_acceptance_a_b_rate": 85.0},
        governance_benefit={}
    )

    hw_profile_live = {"total_requests": 100, "corruption_count": 0, "hardware_observed": True}

    decision = evaluator.evaluate(qa_res_mutated, coding_res_live, hw_profile_live)
    # Cat B failed gate
    assert decision.decision == "NO_GO"
    cat_b_gate = next(g for g in decision.gates if g.gate_name == "spec_qa.min_version_scope_accuracy")
    assert cat_b_gate.passed is False
