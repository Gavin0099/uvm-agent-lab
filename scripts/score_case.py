import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse
import json
import yaml
from agent.governance.evidence_verifier import EvidenceVerifier
from agent.governance.policy import GovernancePolicyEngine, GovernanceViolationCode, GovernanceSeverity


def score_result(case_path: str, result_path: str) -> dict:
    with open(case_path, "r", encoding="utf-8") as f:
        case_dict = yaml.safe_load(f)

    with open(result_path, "r", encoding="utf-8") as f:
        result_dict = json.load(f)

    verifier = EvidenceVerifier()
    req_id = case_dict["inputs"]["requirement_id"]
    required_evidence = case_dict.get("required_evidence", [])

    evidence = result_dict.get("evidence", {})
    evid_score, evid_report = verifier.verify_evidence_packet(
        evidence=evidence,
        required_items=required_evidence,
        expected_requirement_id=req_id
    )

    # Check prior recorded violations
    prior_violations = result_dict.get("governance_status", {}).get("violations", [])
    has_fatal_prior = any(v.get("severity") in ["FATAL", "CRITICAL"] for v in prior_violations)

    fatal = evid_report.fatal or has_fatal_prior
    passed_governance = (not fatal) and (len(evid_report.violations) == 0) and (len(prior_violations) == 0)

    # Score breakdown
    compile_pass = result_dict.get("execution", {}).get("compile_status") == "pass"
    sim_pass = result_dict.get("execution", {}).get("simulation_status") == "pass"

    s_comp = 100.0 if compile_pass else 0.0
    s_sim = 100.0 if sim_pass else 0.0
    s_evid = evid_score

    penalties = 100.0 if not passed_governance else 0.0
    total_score = max(0.0, (0.30 * s_comp + 0.50 * s_sim + 0.20 * s_evid) - penalties)
    task_success = (total_score >= 80.0) and passed_governance

    scorecard = {
        "case_id": case_dict["id"],
        "runner_name": result_dict.get("runner_name", "unknown"),
        "total_score": round(total_score, 2),
        "task_success": task_success,
        "breakdown": {
            "compilation_score": s_comp,
            "simulation_score": s_sim,
            "evidence_score": round(s_evid, 2),
            "governance_penalty": penalties,
        },
        "governance_status": {
            "passed": passed_governance,
            "fatal": fatal,
            "violations_count": len(evid_report.violations) + len(prior_violations)
        }
    }

    return scorecard


def main():
    parser = argparse.ArgumentParser(description="Score UVM Benchmark Execution Results")
    parser.add_argument("--case", required=True, type=str, help="Path to benchmark case YAML")
    parser.add_argument("--result", required=True, type=str, help="Path to benchmark run result JSON")
    args = parser.parse_args()

    scorecard = score_result(args.case, args.result)
    print(json.dumps(scorecard, indent=2))


if __name__ == "__main__":
    main()
