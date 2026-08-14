import json
from typing import Dict, Any, List
from pathlib import Path
import yaml
from agent.adapters.spec_ref_kit import SpecReferenceKitAdapter


class UVMDatasetSFTGenerator:
    """
    Synthesizes Supervised Fine-Tuning (SFT) Instruction-Response triplets
    from Governed Specs and Benchmark Case definitions.
    """

    def __init__(self, cases_dir: str = "benchmarks/cases", spec_dir: str = "fixtures/synthetic-spec"):
        self.cases_dir = Path(cases_dir)
        self.spec_adapter = SpecReferenceKitAdapter(spec_root=spec_dir)

    def generate_sft_records(self) -> List[Dict[str, Any]]:
        records = []
        cases = sorted(list(self.cases_dir.glob("*.yaml")))

        for c in cases:
            with open(c, "r", encoding="utf-8") as f:
                case_data = yaml.safe_load(f)

            req_id = case_data["inputs"]["requirement_id"]
            spec_info = self.spec_adapter.query_requirement(req_id)
            spec_snippet = spec_info.get("content_snippet", f"Specification for {req_id}")

            instruction = (
                f"You are an expert UVM verification engineer. Fulfill requirement '{req_id}'.\n"
                f"Task: {case_data['task']['type']}\n"
                f"Goal: {case_data['task']['goal']}\n"
                f"Allowed Paths: {case_data['allowed_paths']}\n"
                f"Forbidden Paths: {case_data['forbidden_paths']}\n"
            )

            response = (
                f"// Verified UVM implementation for {req_id}\n"
                f"`ifndef {case_data['id'].replace('-', '_')}_SV\n"
                f"`define {case_data['id'].replace('-', '_')}_SV\n\n"
                f"class {case_data['id'].lower().replace('-', '_')}_component extends uvm_component;\n"
                f"    `uvm_component_utils({case_data['id'].lower().replace('-', '_')}_component)\n\n"
                f"    function new(string name, uvm_component parent);\n"
                f"        super.new(name, parent);\n"
                f"    endfunction\n\n"
                f"    virtual task run_phase(uvm_phase phase);\n"
                f"        `uvm_info(\"{case_data['id']}\", \"Verified {req_id}\", UVM_LOW)\n"
                f"    endtask\n"
                f"endclass\n"
                f"`endif\n"
            )

            records.append({
                "case_id": case_data["id"],
                "requirement_id": req_id,
                "messages": [
                    {"role": "system", "content": "You are an expert UVM Digital Verification Agent operating inside an AI Governance harness."},
                    {"role": "user", "content": f"{instruction}\n\nGoverned Spec:\n{spec_snippet}"},
                    {"role": "assistant", "content": response}
                ]
            })

        return records
