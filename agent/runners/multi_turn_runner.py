import time
from typing import Dict, Any, List, Optional
from agent.runners.base import BaseAgentRunner
from agent.governance.guardrails import ScopeGuardrail
from agent.governance.evidence_verifier import EvidenceVerifier
from agent.governance.policy import GovernanceViolationCode, GovernanceSeverity, GovernanceReport
from agent.tools.fs_tools import GovernedFileSystemTools
from agent.tools.sim_tools import GovernedSimTools
from agent.adapters.spec_ref_kit import SpecReferenceKitAdapter
from scripts.sim_stub import SimStubEngine


class MultiTurnHealingAgentRunner(BaseAgentRunner):
    """
    Gate 2: Multi-Turn Autonomous State Machine Agent Runner.
    Simulates realistic verification agent behavior:
    1. Query governed spec.
    2. Author initial UVM testbench / sequence.
    3. Compile -> If errors encountered, parse compiler log and auto-patch syntax.
    4. Simulate -> If scoreboard mismatch or UVM_ERROR, parse sim log and adjust sampling/timing.
    5. Terminate and submit validated evidence packet.
    """

    def __init__(self, name: str = "multi_turn_healing_agent", max_retries: int = 3):
        super().__init__(name)
        self.max_retries = max_retries

    def run_case(self, case_dict: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        tool_calls = []
        turn_count = 0
        tokens_consumed = 0

        allowed = case_dict.get("allowed_paths", ["uvm/"])
        forbidden = case_dict.get("forbidden_paths", ["rtl/"])
        guardrail = ScopeGuardrail(allowed_paths=allowed, forbidden_paths=forbidden)
        fs_tools = GovernedFileSystemTools(guardrail=guardrail)
        sim_tools = GovernedSimTools()
        spec_adapter = SpecReferenceKitAdapter()

        req_id = case_dict["inputs"]["requirement_id"]
        target_file = case_dict["inputs"].get("target_file", "uvm/tests/test_case.sv")

        # Step 1: Spec Ingestion
        spec_res = spec_adapter.query_requirement(req_id)
        tokens_consumed += 250
        tool_calls.append({
            "turn": turn_count,
            "tool": "query_spec",
            "args": {"requirement_id": req_id},
            "status": spec_res["status"],
            "output_summary": f"Ingested authoritative spec clause for {req_id}"
        })

        # Step 2: Initial Draft (Simulate initial syntax or timing glitch on task UVM-003 or UVM-004)
        has_initial_compile_bug = (case_dict["task"]["type"] == "fix_compile_error")
        has_initial_sim_bug = (case_dict["task"]["type"] == "debug_simulation_mismatch")

        initial_content = f"// Draft 0 UVM verification component for {req_id}\n"
        if has_initial_compile_bug:
            initial_content += "// Syntax error intentionally present in initial draft\nclass broken_test;\n"
        else:
            initial_content += f"class valid_component;\n  // Verified for {req_id}\nendclass\n"

        fs_res = fs_tools.write_file(target_file, initial_content)
        tokens_consumed += 180
        tool_calls.append({
            "turn": turn_count,
            "tool": "write_file",
            "args": {"file_path": target_file},
            "status": fs_res["status"],
            "output_summary": f"Authored initial draft in {target_file}"
        })

        # Step 3: Compilation Loop (with Auto-Patching)
        comp_target = "broken_test.sv" if has_initial_compile_bug else target_file
        comp_res = sim_tools.compile(comp_target)
        tool_calls.append({
            "turn": turn_count,
            "tool": "compile",
            "args": {"target_file": comp_target},
            "status": comp_res["status"],
            "output_summary": f"Compile initial draft: {comp_res['status']}"
        })

        if comp_res["status"] == "fail":
            # Auto-healing Turn 1
            turn_count += 1
            tokens_consumed += 320
            # Parse error and patch file
            fixed_content = f"// Healed UVM component for {req_id}\nclass fixed_test;\n  // Syntax resolved\nendclass\n"
            fs_tools.write_file(target_file, fixed_content)
            comp_res = sim_tools.compile(target_file)
            tool_calls.append({
                "turn": turn_count,
                "tool": "compile",
                "args": {"target_file": target_file},
                "status": comp_res["status"],
                "output_summary": f"Re-compiled after auto-patch: {comp_res['status']}"
            })

        # Step 4: Simulation Loop (with Auto-Patching)
        sim_target = "broken_test" if has_initial_sim_bug else "valid_test"
        sim_res = sim_tools.simulate(sim_target)
        tool_calls.append({
            "turn": turn_count,
            "tool": "simulate",
            "args": {"test_name": sim_target},
            "status": sim_res["status"],
            "output_summary": f"Simulation draft: {sim_res['status']}"
        })

        if sim_res["status"] == "fail":
            # Auto-healing Turn 2
            turn_count += 1
            tokens_consumed += 410
            # Fix sampling clock skew
            fixed_timing_content = f"// Fixed sampling skew for {req_id}\nclass fixed_timing_test;\n  // Clocking block skew fixed\nendclass\n"
            fs_tools.write_file(target_file, fixed_timing_content)
            sim_res = sim_tools.simulate("valid_test")
            tool_calls.append({
                "turn": turn_count,
                "tool": "simulate",
                "args": {"test_name": "valid_test"},
                "status": sim_res["status"],
                "output_summary": f"Re-simulated after timing fix: {sim_res['status']}"
            })

        # Step 5: Final Validated Evidence Packet
        diff_text = f"--- a/{target_file}\n+++ b/{target_file}\n@@ -0,0 +1,5 @@\n+// Final verified UVM implementation for {req_id}\n"
        evidence = {
            "requirement_id": req_id,
            "git_diff": diff_text,
            "compile_log": comp_res["log"],
            "simulation_log": sim_res["log"],
            "coverage_report": f"Overall Coverage: {sim_res.get('coverage', 100.0)}%",
            "log_hash": sim_res["log_hash"],
        }

        # Check retry budget penalty
        violations = []
        if turn_count > self.max_retries:
            violations.append({
                "code": GovernanceViolationCode.TOOL_RETRY_EXCESS,
                "severity": GovernanceSeverity.MEDIUM,
                "message": f"Agent exceeded retry budget: {turn_count} > {self.max_retries} turns."
            })

        return {
            "case_id": case_dict["id"],
            "runner_name": self.name,
            "duration_seconds": time.time() - start_time,
            "governance_violations": violations,
            "evidence": evidence,
            "execution": {
                "compile_status": comp_res["status"],
                "simulation_status": sim_res["status"],
                "step_count": len(tool_calls),
                "retry_count": turn_count,
                "tool_calls": tool_calls,
            },
            "metrics": {
                "prompt_tokens": tokens_consumed,
                "completion_tokens": int(tokens_consumed * 0.45),
            }
        }
