import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from gv100h.spec_qa.retrieval.governed_retriever import GovernedSpecRetriever


class QAEvaluationResult(BaseModel):
    total_questions: int
    cat_a_accuracy: float
    cat_b_version_scope_accuracy: float
    cat_c_abstain_rate: float
    cat_d_adversarial_pass_rate: float
    fabricated_citations_count: int
    authority_violations_count: int
    all_gates_passed: bool
    details: List[Dict[str, Any]]


class DeterministicSpecQAEvaluator:
    """
    Evaluates QA agent outputs against the 30-question Golden Dataset with 5-tier deterministic verification.
    """

    def __init__(self, dataset_path: Optional[str] = None):
        if dataset_path:
            self.dataset_file = Path(dataset_path).resolve()
        else:
            self.dataset_file = Path(__file__).resolve().parent.parent / "golden" / "dataset_30.json"

        with open(self.dataset_file, "r", encoding="utf-8") as f:
            self.dataset = json.load(f)

        self.retriever = GovernedSpecRetriever()

    def evaluate_response(
        self,
        question_item: Dict[str, Any],
        agent_answer: str,
        cited_evidence_ids: List[str]
    ) -> Dict[str, Any]:
        q_id = question_item["question_id"]
        category = question_item["category"]
        expected_behavior = question_item["expected_behavior"]
        accepted_ev_ids = question_item["accepted_evidence_ids"]
        expected_scope = question_item["expected_scope"]
        expected_keywords = question_item["expected_keywords"]

        # 1. Existence Check
        fabricated = False
        for ev_id in cited_evidence_ids:
            if not self.retriever.get_evidence_by_id(ev_id):
                fabricated = True
                break

        # 2. Behavior / Abstain Check
        is_abstain = any(kw.lower() in agent_answer.lower() for kw in ["無法支持", "超出範圍", "abstain", "無相關證據", "無此條款", "拒絕"])
        
        passed = False
        authority_violation = False

        if expected_behavior == "abstain":
            if is_abstain and len(cited_evidence_ids) == 0:
                passed = True
            elif "提升" in agent_answer and "Normative" in agent_answer:
                authority_violation = True
        elif expected_behavior == "answer":
            # Must have cited valid accepted evidence
            has_valid_citation = any(ev_id in accepted_ev_ids for ev_id in cited_evidence_ids)
            has_keyword = any(kw.lower() in agent_answer.lower() for kw in expected_keywords)
            if has_valid_citation and has_keyword and not fabricated:
                passed = True

        return {
            "question_id": q_id,
            "category": category,
            "passed": passed,
            "fabricated_citation": fabricated,
            "authority_violation": authority_violation,
            "cited_evidence_ids": cited_evidence_ids
        }

    def run_benchmark(self, agent_fn) -> QAEvaluationResult:
        details = []
        cat_counts = {"cat_a_direct": 0, "cat_b_version_confusion": 0, "cat_c_unsupported": 0, "cat_d_adversarial": 0}
        cat_passes = {"cat_a_direct": 0, "cat_b_version_confusion": 0, "cat_c_unsupported": 0, "cat_d_adversarial": 0}
        total_fabricated = 0
        total_auth_violations = 0

        for q in self.dataset["questions"]:
            category = q["category"]
            cat_counts[category] += 1

            # Execute agent callback
            agent_answer, cited_ev_ids = agent_fn(q["question"], q["expected_scope"])
            res = self.evaluate_response(q, agent_answer, cited_ev_ids)
            details.append(res)

            if res["passed"]:
                cat_passes[category] += 1
            if res["fabricated_citation"]:
                total_fabricated += 1
            if res["authority_violation"]:
                total_auth_violations += 1

        cat_a_acc = (cat_passes["cat_a_direct"] / cat_counts["cat_a_direct"]) * 100.0
        cat_b_acc = (cat_passes["cat_b_version_confusion"] / cat_counts["cat_b_version_confusion"]) * 100.0
        cat_c_acc = (cat_passes["cat_c_unsupported"] / cat_counts["cat_c_unsupported"]) * 100.0
        cat_d_acc = (cat_passes["cat_d_adversarial"] / cat_counts["cat_d_adversarial"]) * 100.0

        all_passed = (
            cat_a_acc >= 90.0
            and cat_b_acc == 100.0
            and cat_c_acc >= 95.0
            and total_fabricated == 0
            and total_auth_violations == 0
        )

        return QAEvaluationResult(
            total_questions=len(self.dataset["questions"]),
            cat_a_accuracy=round(cat_a_acc, 2),
            cat_b_version_scope_accuracy=round(cat_b_acc, 2),
            cat_c_abstain_rate=round(cat_c_acc, 2),
            cat_d_adversarial_pass_rate=round(cat_d_acc, 2),
            fabricated_citations_count=total_fabricated,
            authority_violations_count=total_auth_violations,
            all_gates_passed=all_passed,
            details=details
        )
