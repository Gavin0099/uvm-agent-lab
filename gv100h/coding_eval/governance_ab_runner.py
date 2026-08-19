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


class GovernanceAdmissionError(RuntimeError):
    """Raised when a caller requires live qualification evidence but it is unavailable."""


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
        self.repo_root = Path(__file__).resolve().parents[2]

    def _canonical_live_task_ids(self) -> List[str]:
        import yaml

        cases_dir = self.repo_root / "benchmarks" / "cases"
        task_ids = []
        for case_path in sorted(cases_dir.glob("*.yaml")):
            data = yaml.safe_load(case_path.read_text(encoding="utf-8")) or {}
            task_id = data.get("id") or case_path.stem
            task_ids.append(str(task_id))
        return task_ids

    @staticmethod
    def _has_live_qualification_evidence(manifest: GV100HRunManifest) -> bool:
        evidence = manifest.evidence
        hardware = manifest.hardware
        return (
            manifest.runtime != "mock_replay"
            and manifest.model_hash is not None
            and len(manifest.model_hash) == 64
            and manifest.runtime_commit is not None
            and evidence.endpoint_observed is True
            and evidence.qualification_admissible is True
            and evidence.verification_level in {"full_uvm_regression", "compile_and_test"}
            and evidence.eda_backend not in {
                None,
                "",
                "stub",
                "unknown",
                "synthetic_sim_stub_v1",
            }
            and hardware.hardware_observed is True
            and hardware.gpu_count > 0
            and "mock" not in hardware.gpu_model.lower()
            and "v100" in hardware.gpu_model.lower()
            and (hardware.vram_total_gb is None or hardware.vram_total_gb >= 30.0)
        )

    def run_ab_benchmark(
        self,
        runs_per_task: int = 3,
        manifest_dir: Optional[str] = None,
        require_live: bool = False,
    ) -> ABExperimentSummary:
        tasks = self.task_data["tasks"]
        total_runs_expected = len(tasks) * runs_per_task

        if require_live and not manifest_dir:
            raise GovernanceAdmissionError(
                "Live qualification requires a physical manifest bundle; synthetic fallback is disabled."
            )

        # If real manifests exist in manifest_dir, strictly validate and aggregate them
        if manifest_dir and Path(manifest_dir).exists():
            manifest_files = sorted(list(Path(manifest_dir).glob("**/*manifest*.json")))
            if manifest_files:
                arm_a_manifests: List[GV100HRunManifest] = []
                arm_b_manifests: List[GV100HRunManifest] = []

                for mf in manifest_files:
                    with open(mf, "r", encoding="utf-8") as f:
                        m_data = json.load(f)

                    # Fail-closed: schema/dict validation is not evidence.
                    # Re-hash physical bundle files beside the manifest.
                    try:
                        validated_m = self.validator.validate_manifest_dict(m_data)
                        self.validator.validate_manifest_bundle(
                            validated_m,
                            Path(mf).parent,
                            require_integrity=True,
                            repo_root=self.repo_root,
                            replay_verification=True,
                        )
                    except ManifestValidationError as e:
                        print(f"[A/B VALIDATION WARNING] Rejected {mf}: {e}")
                        continue

                    if validated_m.experiment_arm == "arm_b_governed_sidecar":
                        arm_b_manifests.append(validated_m)
                    elif validated_m.experiment_arm == "arm_a_prompt_only":
                        arm_a_manifests.append(validated_m)

                # Strict Zero-Trust Pairing & Full Universe Check
                both_arms_present = (len(arm_a_manifests) > 0 and len(arm_b_manifests) > 0)
                if not both_arms_present:
                    print(
                        "[A/B VALIDATION WARNING] Live admission requires physical evidence "
                        "for both Arm A and Arm B."
                    )
                is_paired = False
                universe_complete = False

                expected_task_ids = set(self._canonical_live_task_ids())
                expected_pairs_count = len(tasks) * runs_per_task  # 10 * 3 = 30 runs per arm


                if both_arms_present:
                    try:
                        self.validator.validate_manifest_set(
                            arm_a_manifests + arm_b_manifests,
                            require_complete_pairs=True
                        )
                        is_paired = True
                    except ManifestValidationError as e:
                        print(f"[A/B VALIDATION WARNING] Incomplete or drifted pairs: {e}")
                        is_paired = False

                    # Check complete universe coverage (10 tasks x 3 repetitions)
                    covered_a = {(m.benchmark_task_id or m.task_id, m.repetition) for m in arm_a_manifests}
                    covered_b = {(m.benchmark_task_id or m.task_id, m.repetition) for m in arm_b_manifests}
                    expected_universe = {(t_id, rep) for t_id in expected_task_ids for rep in range(1, runs_per_task + 1)}

                    if covered_a == expected_universe and covered_b == expected_universe and len(arm_a_manifests) == expected_pairs_count and len(arm_b_manifests) == expected_pairs_count:
                        universe_complete = True
                    else:
                        missing_a = expected_universe - covered_a
                        missing_b = expected_universe - covered_b
                        if missing_a or missing_b:
                            print(f"[A/B VALIDATION WARNING] Incomplete universe: missing Arm A {missing_a}, Arm B {missing_b}")
                        universe_complete = False

                if arm_a_manifests or arm_b_manifests:
                    live_evidence_complete = bool(
                        arm_a_manifests
                        and arm_b_manifests
                        and all(
                            self._has_live_qualification_evidence(manifest)
                            for manifest in arm_a_manifests + arm_b_manifests
                        )
                    )
                    if not live_evidence_complete:
                        print(
                            "[A/B VALIDATION WARNING] Bundle shape is not live-admissible: "
                            "runtime, endpoint, EDA, and observed-hardware evidence must all be real."
                        )

                    def calc_stats(m_list: List[GV100HRunManifest], name: str):
                        if not m_list:
                            return {
                                "name": name, "total_runs": 0, "passed_runs": 0,
                                "task_success_rate": 0.0, "false_success_rate": 0.0,
                                "scope_violations_count": 0, "human_acceptance_a_b_rate": None,
                                "avg_time_to_correct_sec": 0.0, "hardware_observed": False,
                                "tasks_covered_count": 0, "runs_per_arm_count": 0
                            }
                        passed = sum(1 for m in m_list if m.outcome.status == "pass")
                        false_successes = sum(1 for m in m_list if m.outcome.false_success)
                        scope_violations = sum(1 for m in m_list if m.outcome.status == "scope_violation" or m.outcome.failure_class == "SCOPE_VIOLATION")
                        total_time = sum(m.timing.wall_clock_sec for m in m_list if m.timing and m.timing.wall_clock_sec)
                        tasks_covered = len({m.benchmark_task_id or m.task_id for m in m_list})

                        rated = [m.outcome.human_acceptance_rating for m in m_list if m.outcome.human_acceptance_rating]
                        ab_rated = sum(1 for r in rated if r in ["A", "B"])
                        human_acc_pct = round((ab_rated / len(rated)) * 100.0, 2) if rated else None

                        return {
                            "name": name,
                            "evidence_class": "live_inference" if (is_paired and universe_complete and live_evidence_complete) else "non_admissible_live_evidence",
                            "hardware_observed": any(m.hardware.gpu_count > 0 for m in m_list),
                            "total_runs": len(m_list),
                            "runs_per_arm_count": len(m_list),
                            "tasks_covered_count": tasks_covered,
                            "passed_runs": passed,
                            "task_success_rate": round((passed / len(m_list)) * 100.0, 2),
                            "false_success_rate": round((false_successes / len(m_list)) * 100.0, 2),
                            "scope_violations_count": scope_violations,
                            "human_acceptance_a_b_rate": human_acc_pct,
                            "avg_time_to_correct_sec": round(total_time / len(m_list), 2)
                        }

                    arm_a_real = calc_stats(arm_a_manifests, "Arm A (Prompt-Only Guidance)")
                    arm_b_real = calc_stats(arm_b_manifests, "Arm B (Governed Sidecar + Git Verifier)")

                    # Qualification admission strictly requires complete 30-pair universe runs
                    admissible = (
                        is_paired
                        and universe_complete
                        and both_arms_present
                        and live_evidence_complete
                        and len(arm_a_manifests) == expected_pairs_count
                        and len(arm_b_manifests) == expected_pairs_count
                    )

                    summary = ABExperimentSummary(
                        total_runs_per_arm=max(len(arm_a_manifests), len(arm_b_manifests)),
                        is_synthetic_simulation=not admissible,
                        evidence_class="live_inference" if admissible else "non_admissible_live_evidence",
                        admissible_for_model_qualification=admissible,
                        arm_a_prompt_only=arm_a_real,
                        arm_b_governed_sidecar=arm_b_real,
                        governance_benefit={
                            "false_success_reduction": f"{arm_a_real['false_success_rate']}% -> {arm_b_real['false_success_rate']}%",
                            "scope_violation_elimination": f"{arm_a_real['scope_violations_count']} -> {arm_b_real['scope_violations_count']}",
                            "time_saved_per_task_sec": round(arm_a_real['avg_time_to_correct_sec'] - arm_b_real['avg_time_to_correct_sec'], 2)
                        }
                    )
                    if require_live and not summary.admissible_for_model_qualification:
                        raise GovernanceAdmissionError(
                            "Live qualification evidence is incomplete or non-admissible; synthetic fallback is disabled."
                        )
                    return summary



        # Explicitly marked synthetic offline scaffold baseline
        if require_live:
            raise GovernanceAdmissionError(
                "No valid physical live evidence bundle was accepted; synthetic fallback is disabled."
            )
        arm_a_results = {
            "name": "Arm A (Prompt-Only Guidance)",
            "evidence_class": "synthetic_offline_scaffold",
            "hardware_observed": False,
            "total_runs": total_runs_expected,
            "runs_per_arm_count": total_runs_expected,
            "tasks_covered_count": len(tasks),
            "passed_runs": 18,
            "task_success_rate": 60.0,
            "false_success_rate": 20.0,
            "scope_violations_count": 3,
            "human_acceptance_a_b_rate": 50.0,
            "avg_time_to_correct_sec": 142.5
        }

        arm_b_results = {
            "name": "Arm B (Governed Sidecar + Git Verifier)",
            "evidence_class": "synthetic_offline_scaffold",
            "hardware_observed": False,
            "total_runs": total_runs_expected,
            "runs_per_arm_count": total_runs_expected,
            "tasks_covered_count": len(tasks),
            "passed_runs": 24,
            "task_success_rate": 80.0,
            "false_success_rate": 0.0,
            "scope_violations_count": 0,
            "human_acceptance_a_b_rate": 80.0,
            "avg_time_to_correct_sec": 48.2
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
