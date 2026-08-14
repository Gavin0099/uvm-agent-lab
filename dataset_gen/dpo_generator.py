import json
from typing import Dict, Any, List
from pathlib import Path
import yaml
from agent.adapters.spec_ref_kit import SpecReferenceKitAdapter


class UVMDatasetDPOGenerator:
    """
    Synthesizes Direct Preference Optimization (DPO) Chosen / Rejected pairs
    to align LLMs on UVM syntax accuracy, protocol correctness, and Scope Governance.
    """

    def __init__(self, cases_dir: str = "benchmarks/cases", spec_dir: str = "fixtures/synthetic-spec"):
        self.cases_dir = Path(cases_dir)
        self.spec_adapter = SpecReferenceKitAdapter(spec_root=spec_dir)

    def generate_dpo_records(self) -> List[Dict[str, Any]]:
        records = []
        cases = sorted(list(self.cases_dir.glob("*.yaml")))

        for c in cases:
            with open(c, "r", encoding="utf-8") as f:
                case_data = yaml.safe_load(f)

            req_id = case_data["inputs"]["requirement_id"]
            spec_info = self.spec_adapter.query_requirement(req_id)
            spec_snippet = spec_info.get("content_snippet", f"Specification for {req_id}")

            prompt = (
                f"You are a UVM verification agent. Implement {case_data['task']['goal']} for requirement {req_id}.\n"
                f"Allowed Paths: {case_data['allowed_paths']}\n"
                f"Forbidden Paths: {case_data['forbidden_paths']}\n"
                f"Spec Reference:\n{spec_snippet}"
            )

            # Positive (Chosen): Compliant UVM code in allowed path
            chosen = (
                f"// Compliant UVM verification component for {req_id}\n"
                f"class {case_data['id'].lower().replace('-', '_')}_verified extends uvm_test;\n"
                f"    `uvm_component_utils({case_data['id'].lower().replace('-', '_')}_verified)\n"
                f"    // Properly scoped and free of RTL modifications\n"
                f"endclass\n"
            )

            # Negative (Rejected): Scope violation (touching RTL) or broken macro
            rejected = (
                f"// VIOLATION: Agent improperly modified RTL to force a pass\n"
                f"module rtl_patch_hack;\n"
                f"  assign rtl_state = 4'h1; // Illegal RTL modification in forbidden path rtl/\n"
                f"endmodule\n"
            )

            records.append({
                "case_id": case_data["id"],
                "requirement_id": req_id,
                "prompt": prompt,
                "chosen": chosen,
                "rejected": rejected,
                "rejection_reason": "SCOPE_VIOLATION_FORBIDDEN_PATH: Modified RTL source instead of authoring UVM testbench."
            })

        return records
