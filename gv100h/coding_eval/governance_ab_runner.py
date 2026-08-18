import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from gv100h.manifests.models import GV100HRunManifest
from gv100h.manifests.validator import ManifestValidator, ManifestValidationError


class ABExperimentSummary(BaseModel):
    total_runs_per_arm: int
    is_synthetic_simulation: bool
    evidence_class: str
    admissible_for_model_qualification: bool
    arm_a_prompt_only: Dict[str, Any]
    arm_b_governed_sidecar: Dict[str, Any]
    governance_benefit: Dict[str, Any]


class GovernanceABRunner:
    """
    Executes Governance A/B benchmark comparing Arm A (Prompt Only) vs Arm B (Governed Sidecar)
    under an identical containment sandbox baseline.
    Enforces strict ManifestValidator checks and fails closed on corrupted manifests.
    """

    def __init__(self, tasks_file: Optional[str] = None):
        if tasks_file:
            self.tasks_path = Path(tasks_file).resolve()
        else:
            self.tasks_path = Path(__file__).resolve().parent / "tasks" / "historical_tasks.json"

        with open(self.tasks_path, "r", encoding="utf-8") as f:
            self.task_data = json.load(f)

        self.validator = ManifestValidator()

    def run_ab_benchmark(
        self,
        runs_per_task: int = 3,
        manifest_dir: Optional[str] = None
    ) -> ABExperimentSummary:
        tasks = self.task_data["tasks"]
        total_runs_expected = len(tasks) * runs_per_task

        # If real manifests exist in manifest_dir, strictly validate and aggregate them
        if manifest_dir and Path(manifest_dir).exists():
            manifest_files = sorted(list(Path(manifest_dir).glob("*.json")))
            if manifest_files:
                arm_a_manifests: List[GV100HRunManifest] = []
                arm_b_manifests: List[GV100HRunManifest] = []

                for mf in manifest_files:
                    with open(mf, "r", encoding="utf-8") as f:
                        m_data = json.load(f)
                    
                    # Fail-closed validation on every manifest file
                    validated_m = self.validator.validate_manifest_dict(m_data)

                    if validated_m.experiment_arm == "arm_b_governed_sidecar":
                        arm_b_manifests.append(validated_m)
                    elif validated_m.experiment_arm == "arm_a_prompt_only":
                        arm_a_manifests.append(validated_m)
                    elif validated_m.experiment_arm == "synthetic_replay":
                        pass

                if arm_a_manifests or arm_b_manifests:
                    self.validator.validate_manifest_set(arm_a_manifests + arm_b_manifests)

                    def calc_stats(m_list: List[GV100HRunManifest], name: str):
                        if not m_list:
                            return {
                                "name": name, "total_runs": 0, "passed_runs": 0,
                                "task_success_rate": 0.0, "false_success_rate": 0.0,
                                "scope_violations_count": 0, "human_acceptance_a_b_rate": None,
                                "avg_time_to_correct_sec": 0.0, "hardware_observed": True
                            }
                        passed = sum(1 for m in m_list if m.outcome.status == "pass")
                        false_successes = sum(1 for m in m_list if m.outcome.false_success)
                        scope_violations = sum(1 for m in m_list if m.outcome.status == "scope_violation" or m.outcome.failure_class == "SCOPE_VIOLATION")
                        total_time = sum(m.timing.wall_clock_sec for m in m_list if m.timing and m.timing.wall_clock_sec)

                        # Genuine human acceptance ratings
                        rated = [m.outcome.human_acceptance_rating for m in m_list if m.outcome.human_acceptance_rating]
                        ab_rated = sum(1 for r in rated if r in ["A", "B"])
                        human_acc_pct = round((ab_rated / len(rated)) * 100.0, 2) if rated else None

                        return {
                            "name": name,
                            "evidence_class": "live_inference",
                            "hardware_observed": any(m.hardware.gpu_count > 0 for m in m_list),
                            "total_runs": len(m_list),
                            "passed_runs": passed,
                            "task_success_rate": round((passed / len(m_list)) * 100.0, 2),
                            "false_success_rate": round((false_successes / len(m_list)) * 100.0, 2),
                            "scope_violations_count": scope_violations,
                            "human_acceptance_a_b_rate": human_acc_pct,
                            "avg_time_to_correct_sec": round(total_time / len(m_list), 2)
                        }

                    arm_a_real = calc_stats(arm_a_manifests, "Arm A (Prompt-Only Guidance)")
                    arm_b_real = calc_stats(arm_b_manifests, "Arm B (Governed Sidecar + Git Verifier)")

                    return ABExperimentSummary(
                        total_runs_per_arm=max(len(arm_a_manifests), len(arm_b_manifests)),
                        is_synthetic_simulation=False,
                        evidence_class="live_inference",
                        admissible_for_model_qualification=True,
                        arm_a_prompt_only=arm_a_real,
                        arm_b_governed_sidecar=arm_b_real,
                        governance_benefit={
                            "false_success_reduction": f"{arm_a_real['false_success_rate']}% -> {arm_b_real['false_success_rate']}%",
                            "scope_violation_elimination": f"{arm_a_real['scope_violations_count']} -> {arm_b_real['scope_violations_count']}",
                            "time_saved_per_task_sec": round(arm_a_real['avg_time_to_correct_sec'] - arm_b_real['avg_time_to_correct_sec'], 2)
                        }
                    )

        # Explicitly marked synthetic offline scaffold baseline
        arm_a_results = {
            "name": "Arm A (Prompt-Only Guidance)",
            "evidence_class": "synthetic_offline_scaffold",
            "hardware_observed": False,
            "total_runs": total_runs_expected,
            "passed_runs": 18,
            "task_success_rate": 60.0,
            "first_pass_rate": 50.0,
            "false_success_rate": 20.0,
            "scope_violations_count": 3,
            "human_acceptance_a_b_rate": 56.67,
            "avg_time_to_correct_sec": 185.4
        }

        arm_b_results = {
            "name": "Arm B (Governed Sidecar + Git Verifier)",
            "evidence_class": "synthetic_offline_scaffold",
            "hardware_observed": False,
            "total_runs": total_runs_expected,
            "passed_runs": 24,
            "task_success_rate": 80.0,
            "first_pass_rate": 73.33,
            "false_success_rate": 0.0,
            "scope_violations_count": 0,
            "human_acceptance_a_b_rate": 80.0,
            "avg_time_to_correct_sec": 112.8
        }

        benefit = {
            "false_success_reduction": "100% (20% -> 0%)",
            "scope_violation_elimination": "100% (3 violations -> 0)",
            "human_acceptance_improvement": "+23.33% (56.67% -> 80.0%)",
            "time_saved_per_task_sec": 72.6
        }

        return ABExperimentSummary(
            total_runs_per_arm=total_runs_expected,
            is_synthetic_simulation=True,
            evidence_class="synthetic_offline_scaffold",
            admissible_for_model_qualification=False,
            arm_a_prompt_only=arm_a_results,
            arm_b_governed_sidecar=arm_b_results,
            governance_benefit=benefit
        )
