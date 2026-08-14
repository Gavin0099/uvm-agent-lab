import re
from typing import Dict, Any, List


class FunctionalCoverageParser:
    """
    Parses simulator functional coverage reports and extracts unhit bins and cross-coverage holes.
    """

    @staticmethod
    def parse_report(report_text: str) -> Dict[str, Any]:
        total_bins = 0
        hit_bins = 0
        unhit_bins_list = []

        lines = report_text.splitlines()
        for line in lines:
            line_str = line.strip()
            # Parse bin pattern: "bin <name> : count = <N>" or "bin <name> [UNHIT]"
            if "bin " in line_str.lower():
                total_bins += 1
                if "unhit" in line_str.lower() or "count = 0" in line_str.lower() or "hits = 0" in line_str.lower():
                    # Extract bin name
                    bin_match = re.search(r"bin\s+([a-zA-Z0-9_]+)", line_str, re.IGNORECASE)
                    bin_name = bin_match.group(1) if bin_match else f"bin_{total_bins}"
                    unhit_bins_list.append(bin_name)
                else:
                    hit_bins += 1

        coverage_pct = (hit_bins / max(1, total_bins)) * 100.0 if total_bins > 0 else 100.0

        return {
            "total_bins": total_bins,
            "hit_bins": hit_bins,
            "unhit_bins": unhit_bins_list,
            "coverage_percentage": round(coverage_pct, 2),
            "is_fully_covered": len(unhit_bins_list) == 0,
        }
