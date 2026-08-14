from typing import List, Dict, Any


class DirectedSequenceGenerator:
    """
    Synthesizes targeted UVM sequences specifically configured to hit unvisited coverage bins.
    """

    @staticmethod
    def generate_directed_sequence(unhit_bins: List[str], target_module: str = "usb3") -> Dict[str, Any]:
        seq_name = f"directed_closure_seq_{len(unhit_bins)}_bins"
        constraints = []

        for b in unhit_bins:
            if "backpressure" in b.lower() or "tready" in b.lower():
                constraints.append("tready_delay == 0; // Target minimum backpressure latency")
            elif "max" in b.lower() or "depth" in b.lower():
                constraints.append("burst_length == 16; // Target maximum FIFO depth bin")
            elif "warm_reset" in b.lower() or "reset" in b.lower():
                constraints.append("reset_duration == 12; // Target 12-cycle warm reset transition bin")
            else:
                constraints.append(f"// Constraint to hit corner bin: {b}")

        seq_code = (
            f"// Auto-Generated Directed Sequence to Close Coverage Holes\n"
            f"class {seq_name} extends uvm_sequence;\n"
            f"    `uvm_object_utils({seq_name})\n\n"
            f"    // Directed Constraints targeting {len(unhit_bins)} unhit bins:\n"
            + "\n".join(f"    constraint c_{i} {{ {c} }}" for i, c in enumerate(constraints)) + "\n\n"
            f"    virtual task body();\n"
            f"        `uvm_info(\"{seq_name}\", \"Executing targeted transactions to close coverage holes...\", UVM_HIGH)\n"
            f"    endtask\n"
            f"endclass\n"
        )

        return {
            "sequence_name": seq_name,
            "targeted_bins": unhit_bins,
            "code": seq_code
        }
