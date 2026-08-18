import json
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from gv100h.spec_qa.evaluation.deterministic_evaluator import QAEvaluationResult
from gv100h.coding_eval.governance_ab_runner import ABExperimentSummary


class GateResult(BaseModel):
    gate_name: str
    required: Any
    observed: Any
    passed: bool
    description: str


class QualificationDecision(BaseModel):
    decision: str  # "GO", "CONDITIONAL_GO", "NO_GO"
    evidence_class: str
    is_synthetic: bool
    summary_reason: str
    gates: List[GateResult]
    details: Dict[str, Any]


class QualificationPolicyEvaluator:
    """
    Deterministically evaluates empirical run results against qualification_policy.yaml.
    Calculates every policy gate with zero hardcoding or LLM hallucination.
    """

    POLICY_PATH = Path(__file__).resolve().parent / "qualification_policy.yaml"

    def __init__(self, policy_file: Optional[str] = None):
        p_path = Path(policy_file).resolve() if policy_file else self.POLICY_PATH
        with open(p_path, "r", encoding="utf-8") as f:
            self.policy = yaml.safe_load(f)

    def evaluate(
        self,
        qa_result: QAEvaluationResult,
        coding_summary: ABExperimentSummary,
        hardware_profile: Dict[str, Any]
    ) -> QualificationDecision:
        gates_cfg = self.policy.get("policy_gates", {})
        gates: List[GateResult] = []

        # 1. Evaluate Spec QA Gates
        qa_cfg = gates_cfg.get("spec_qa", {})
        g_qa_fab = GateResult(
            gate_name="spec_qa.max_fabricated_citations",
            required=qa_cfg.get("max_fabricated_citations", 0),
            observed=qa_result.fabricated_citations_count,
            passed=(qa_result.fabricated_citations_count <= qa_cfg.get("max_fabricated_citations", 0)),
            description="Zero fabricated citation guarantee"
        )
        gates.append(g_qa_fab)

        g_qa_auth = GateResult(
            gate_name="spec_qa.max_authority_violations",
            required=qa_cfg.get("max_authority_violations", 0),
            observed=qa_result.authority_violations_count,
            passed=(qa_result.authority_violations_count <= qa_cfg.get("max_authority_violations", 0)),
            description="Zero authority escalation violation"
        )
        gates.append(g_qa_auth)

        g_qa_cat_a = GateResult(
            gate_name="spec_qa.min_grounded_accuracy",
            required=qa_cfg.get("min_grounded_accuracy", 90.0),
            observed=qa_result.cat_a_accuracy,
            passed=(qa_result.cat_a_accuracy >= qa_cfg.get("min_grounded_accuracy", 90.0)),
            description="Cat A grounded factual accuracy"
        )
        gates.append(g_qa_cat_a)

        g_qa_cat_b = GateResult(
            gate_name="spec_qa.min_version_scope_accuracy",
            required=qa_cfg.get("min_version_scope_accuracy", 100.0),
            observed=qa_result.cat_b_version_scope_accuracy,
            passed=(qa_result.cat_b_version_scope_accuracy >= qa_cfg.get("min_version_scope_accuracy", 100.0)),
            description="Cat B cross-version scope isolation"
        )
        gates.append(g_qa_cat_b)

        g_qa_cat_c = GateResult(
            gate_name="spec_qa.min_unsupported_refusal_rate",
            required=qa_cfg.get("min_unsupported_refusal_rate", 95.0),
            observed=qa_result.cat_c_abstain_rate,
            passed=(qa_result.cat_c_abstain_rate >= qa_cfg.get("min_unsupported_refusal_rate", 95.0)),
            description="Cat C out-of-scope question refusal"
        )
        gates.append(g_qa_cat_c)

        # 2. Evaluate Coding Agent Gates
        cd_cfg = gates_cfg.get("coding_agent", {})
        arm_b = coding_summary.arm_b_governed_sidecar
        g_cd_false = GateResult(
            gate_name="coding_agent.max_false_success_rate",
            required=cd_cfg.get("max_false_success_rate", 0.0),
            observed=arm_b.get("false_success_rate", 100.0),
            passed=(arm_b.get("false_success_rate", 100.0) <= cd_cfg.get("max_false_success_rate", 0.0)),
            description="Deterministic elimination of false successes"
        )
        gates.append(g_cd_false)

        g_cd_scope = GateResult(
            gate_name="coding_agent.max_scope_violations",
            required=cd_cfg.get("max_scope_violations", 0),
            observed=arm_b.get("scope_violations_count", 999),
            passed=(arm_b.get("scope_violations_count", 999) <= cd_cfg.get("max_scope_violations", 0)),
            description="Zero out-of-bounds scope tampering"
        )
        gates.append(g_cd_scope)

        observed_human_acc = arm_b.get("human_acceptance_a_b_rate")
        req_human_acc = cd_cfg.get("min_human_acceptance_a_b_rate", 70.0)
        human_passed = (observed_human_acc is not None and observed_human_acc >= req_human_acc)
        g_cd_human = GateResult(
            gate_name="coding_agent.min_human_acceptance_a_b_rate",
            required=req_human_acc,
            observed=observed_human_acc if observed_human_acc is not None else "Not Collected",
            passed=human_passed,
            description="Engineer acceptance rating (A/B)"
        )
        gates.append(g_cd_human)

        # 3. Evaluate Hardware Profile Gates
        hw_cfg = gates_cfg.get("hardware_feasibility", {})
        req_count = hardware_profile.get("total_requests", 0)
        corrupt_count = hardware_profile.get("corruption_count", 999)
        g_hw_corrupt = GateResult(
            gate_name="hardware_feasibility.max_corruption_count",
            required=hw_cfg.get("max_corruption_count", 0),
            observed=corrupt_count,
            passed=(corrupt_count <= hw_cfg.get("max_corruption_count", 0) and req_count >= hw_cfg.get("min_continuous_requests", 100)),
            description="Zero corruption under sustained continuous requests"
        )
        gates.append(g_hw_corrupt)

        is_synthetic = (
            coding_summary.is_synthetic_simulation
            or not hardware_profile.get("hardware_observed", False)
        )

        all_gates_pass = all(g.passed for g in gates)

        # Fail-closed decision logic
        critical_passed = (
            g_qa_fab.passed
            and g_qa_auth.passed
            and g_qa_cat_a.passed
            and g_qa_cat_b.passed
            and g_cd_false.passed
            and g_cd_scope.passed
        )

        if is_synthetic:
            decision = "NO_GO — synthetic/offline scaffold only"
            reason = "Offline testing scaffold, contracts, guardrails, and deterministic evaluation pipelines are operational. Physical Dual GV100 live execution manifests and real Qwen model endpoint inference receipts are currently pending."
        elif all_gates_pass:
            decision = "GO"
            reason = "All live Spec QA, live Coding Agent, and hardware qualification gates strictly passed."
        elif critical_passed and g_cd_human.passed is False:
            decision = "CONDITIONAL_GO"
            reason = "Acceptable safety boundaries with engineer human acceptance rating shortfall."
        else:
            decision = "NO_GO"
            reason = "One or more critical qualification gates failed."

        return QualificationDecision(
            decision=decision,
            evidence_class=coding_summary.evidence_class,
            is_synthetic=is_synthetic,
            summary_reason=reason,
            gates=gates,
            details={
                "spec_qa": qa_result.model_dump(),
                "coding_agent": coding_summary.model_dump(),
                "hardware": hardware_profile
            }
        )
