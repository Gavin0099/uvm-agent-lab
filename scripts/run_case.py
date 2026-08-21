import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse
import json
import yaml
from datetime import datetime, timezone

from agent.runners.fake_runner import FakeAgentRunner
from agent.runners.multi_turn_runner import MultiTurnHealingAgentRunner
from agent.runners.llm_stub import LLMAgentRunnerStub
from agent.governance.guardrails import ScopeGuardrail
from agent.governance.evidence_verifier import EvidenceVerifier
from agent.governance.policy import GovernancePolicyEngine
from gv100h.runner.validator_profiles import resolve_validator_profile


def load_yaml(file_path: str) -> dict:
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_benchmark(case_path: str, runner_name: str, fault_mode: str = None) -> dict:
    case_dict = load_yaml(case_path)
    case_id = case_dict["id"]
    validator_profile = resolve_validator_profile(case_dict)

    if validator_profile == "lightweight":
        return {
            "case_id": case_id,
            "validator_profile": validator_profile,
            "runner_name": f"legacy_{runner_name}_not_run",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": 0.0,
            "governance_status": {"passed": True, "violations": []},
            "evidence": {
                "requirement_id": case_dict["inputs"]["requirement_id"],
                "git_diff": "NOT RUN: legacy benchmark CLI has no disposable worktree",
                "build_log": "NOT RUN: use the production coding-agent worktree entrypoint",
                "test_log": "NOT RUN: use LightweightValidator through single_pair_runner",
                "validator_report": "NOT RUN: lightweight profile is not executed by the legacy CLI",
            },
            "execution": {
                "compile_status": "not_run",
                "simulation_status": "not_run",
                "validator_status": "not_run",
                "step_count": 0,
                "retry_count": 0,
                "tool_calls": [],
            },
            "metrics": {
                "total_score": 0.0,
                "task_success": False,
                "compile_score": 0.0,
                "simulation_score": 0.0,
                "validator_score": 0.0,
                "evidence_score": 100.0,
                "penalty_deductions": 0.0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
            },
        }

    # Select runner
    if runner_name == "mock":
        runner = FakeAgentRunner(name="mock_baseline_agent", fault_mode=fault_mode)
    elif runner_name == "multi_turn":
        runner = MultiTurnHealingAgentRunner(name="multi_turn_healing_agent")
    elif runner_name == "llm":
        runner = LLMAgentRunnerStub()
    else:
        raise ValueError(f"Unknown runner '{runner_name}'")

    raw_result = runner.run_case(case_dict)

    # Perform Governance Audit
    allowed = case_dict.get("allowed_paths", [])
    forbidden = case_dict.get("forbidden_paths", [])
    guardrail = ScopeGuardrail(allowed_paths=allowed, forbidden_paths=forbidden)

    verifier = EvidenceVerifier()
    evidence = raw_result.get("evidence", {})
    required_evidence = case_dict.get("required_evidence", [])
    req_id = case_dict["inputs"]["requirement_id"]
    
    evidence_score, evid_report = verifier.verify_evidence_packet(
        evidence=evidence,
        required_items=required_evidence,
        expected_requirement_id=req_id
    )

    # Compile governance violations
    violations = [v.model_dump() for v in evid_report.violations]
    for v in raw_result.get("governance_violations", []):
        violations.append(v)

    passed_governance = (len(violations) == 0) and (not evid_report.fatal)

    # Keep legacy EDA scoring stable while making v1 lightweight cases independent.
    execution = raw_result["execution"]
    comp_score = 100.0 if execution.get("compile_status") == "pass" else 0.0
    sim_score = 100.0 if execution.get("simulation_status") == "pass" else 0.0
    validator_score = (
        100.0 if execution.get("validator_status") == "pass" else 0.0
    )
    penalties = 100.0 if not passed_governance else 0.0
    if validator_profile == "lightweight":
        total_score = max(
            0.0,
            (0.80 * validator_score + 0.20 * evidence_score) - penalties,
        )
    else:
        total_score = max(
            0.0,
            (0.30 * comp_score + 0.50 * sim_score + 0.20 * evidence_score)
            - penalties,
        )
    task_success = (total_score >= 80.0) and passed_governance

    final_packet = {
        "case_id": case_id,
        "validator_profile": validator_profile,
        "runner_name": runner.name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(raw_result.get("duration_seconds", 0.0), 3),
        "governance_status": {
            "passed": passed_governance,
            "violations": violations,
        },
        "evidence": evidence,
        "execution": raw_result["execution"],
        "metrics": {
            "total_score": round(total_score, 2),
            "task_success": task_success,
            "compile_score": comp_score,
            "simulation_score": sim_score,
            "validator_score": validator_score,
            "evidence_score": round(evidence_score, 2),
            "penalty_deductions": penalties,
            "prompt_tokens": raw_result.get("metrics", {}).get("prompt_tokens", 0),
            "completion_tokens": raw_result.get("metrics", {}).get("completion_tokens", 0),
        }
    }

    return final_packet


def main():
    parser = argparse.ArgumentParser(description="Run UVM Agent Lab Benchmark Cases")
    parser.add_argument("--case", type=str, help="Path to single benchmark case YAML")
    parser.add_argument("--all", action="store_true", help="Run all cases in benchmarks/cases/")
    parser.add_argument("--cases-dir", type=str, default="benchmarks/cases", help="Directory containing case YAMLs")
    parser.add_argument("--runner", type=str, default="mock", choices=["mock", "multi_turn", "llm"], help="Runner to evaluate")
    parser.add_argument("--fault-mode", type=str, default=None, help="Inject governance fault for testing")
    parser.add_argument("--output", type=str, help="Output JSON path for single case run")
    parser.add_argument("--output-dir", type=str, default="results", help="Directory to save run results")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.all:
        cases = sorted(list(Path(args.cases_dir).glob("*.yaml")))
        if not cases:
            print(f"No YAML cases found in {args.cases_dir}")
            sys.exit(1)
        print(f"Running {len(cases)} benchmark cases with runner '{args.runner}'...")
        for c in cases:
            res = run_benchmark(str(c), runner_name=args.runner, fault_mode=args.fault_mode)
            out_file = out_dir / f"{res['case_id']}_result.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(res, f, indent=2)
            status_symbol = "✅" if res["metrics"]["task_success"] else "❌"
            print(f"  {status_symbol} {res['case_id']} - Score: {res['metrics']['total_score']}/100 - Governance: {res['governance_status']['passed']}")
    elif args.case:
        res = run_benchmark(args.case, runner_name=args.runner, fault_mode=args.fault_mode)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(res, f, indent=2)
            print(f"Saved result to {args.output}")
        else:
            print(json.dumps(res, indent=2))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
