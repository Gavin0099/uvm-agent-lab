import time
from typing import Dict, Any, Optional
from agent.runners.base import BaseAgentRunner
from agent.governance.guardrails import ScopeGuardrail
from agent.governance.policy import GovernanceReport
from agent.tools.fs_tools import GovernedFileSystemTools
from agent.tools.sim_tools import GovernedSimTools
from agent.adapters.spec_ref_kit import SpecReferenceKitAdapter


class FakeAgentRunner(BaseAgentRunner):
    """
    Deterministic Mock Agent Runner for harness testing and baseline evaluation.
    Supports injecting controlled governance faults for test verification.
    """

    def __init__(self, name: str = "mock_baseline_agent", fault_mode: Optional[str] = None):
        super().__init__(name)
        self.fault_mode = fault_mode  # None | "scope_violation" | "missing_evidence" | "hallucinated_evidence" | "sim_error"

    def run_case(self, case_dict: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        tool_calls = []

        allowed = case_dict.get("allowed_paths", ["uvm/"])
        forbidden = case_dict.get("forbidden_paths", ["rtl/"])
        guardrail = ScopeGuardrail(allowed_paths=allowed, forbidden_paths=forbidden)
        fs_tools = GovernedFileSystemTools(guardrail=guardrail)
        sim_tools = GovernedSimTools()
        spec_adapter = SpecReferenceKitAdapter()

        # Step 1: Spec Lookup
        req_id = case_dict["inputs"]["requirement_id"]
        spec_res = spec_adapter.query_requirement(req_id)
        tool_calls.append({
            "tool": "query_spec",
            "args": {"requirement_id": req_id},
            "status": spec_res.get("status", "success"),
            "output_summary": f"Retrieved spec snippet for {req_id}"
        })

        # Step 2: Handle simulated Fault Modes
        if self.fault_mode == "scope_violation":
            # Attempt to write to forbidden path (e.g. rtl/fake.sv)
            write_res = fs_tools.write_file("rtl/illegal_patch.sv", "// Illegal RTL touch\n")
            tool_calls.append({
                "tool": "write_file",
                "args": {"file_path": "rtl/illegal_patch.sv"},
                "status": write_res.get("status", "governance_violation"),
                "output_summary": write_res.get("message", "Scope violation")
            })

            return {
                "case_id": case_dict["id"],
                "runner_name": self.name,
                "duration_seconds": time.time() - start_time,
                "governance_violations": write_res.get("violations", []),
                "evidence": {},
                "execution": {
                    "compile_status": "not_run",
                    "simulation_status": "not_run",
                    "step_count": len(tool_calls),
                    "tool_calls": tool_calls,
                },
                "metrics": {
                    "prompt_tokens": 150,
                    "completion_tokens": 50,
                }
            }

        # Step 3: Normal compliant execution
        target_file = case_dict["inputs"].get("target_file", "uvm/tests/test_case.sv")
        synthetic_code = f"// Governed verification implementation for {req_id}\nclass generated_test;\nendclass\n"
        
        # Write to allowed path
        fs_res = fs_tools.write_file(target_file, synthetic_code)
        tool_calls.append({
            "tool": "write_file",
            "args": {"file_path": target_file},
            "status": fs_res.get("status", "success"),
            "output_summary": f"Generated code for {target_file}"
        })

        # Step 4: Compile & Simulate
        comp_res = sim_tools.compile(target_file)
        tool_calls.append({
            "tool": "compile",
            "args": {"target_file": target_file},
            "status": comp_res["status"],
            "output_summary": f"Compile {comp_res['status']}"
        })

        test_name = "broken_test" if self.fault_mode == "sim_error" else "valid_test"
        sim_res = sim_tools.simulate(test_name)
        tool_calls.append({
            "tool": "simulate",
            "args": {"test_name": test_name},
            "status": sim_res["status"],
            "output_summary": f"Simulation {sim_res['status']}"
        })

        # Step 5: Package Evidence
        diff_text = f"--- a/{target_file}\n+++ b/{target_file}\n@@ -0,0 +1,3 @@\n+// Governed verification implementation for {req_id}\n"
        
        evidence = {
            "requirement_id": req_id,
            "git_diff": diff_text,
            "compile_log": comp_res["log"],
            "simulation_log": sim_res["log"],
            "coverage_report": "Overall Coverage: 100.0%",
            "log_hash": sim_res["log_hash"],
        }

        if self.fault_mode == "missing_evidence":
            evidence.pop("simulation_log", None)
            evidence.pop("git_diff", None)

        if self.fault_mode == "hallucinated_evidence":
            evidence["requirement_id"] = "WRONG-REQ-999"
            evidence["log_hash"] = "fabricated_hash_000000000000"

        return {
            "case_id": case_dict["id"],
            "runner_name": self.name,
            "duration_seconds": time.time() - start_time,
            "governance_violations": [],
            "evidence": evidence,
            "execution": {
                "compile_status": comp_res["status"],
                "simulation_status": sim_res["status"],
                "step_count": len(tool_calls),
                "tool_calls": tool_calls,
            },
            "metrics": {
                "prompt_tokens": 420,
                "completion_tokens": 180,
            }
        }
