#!/usr/bin/env python3
"""
Dataset Export CLI
Exports SFT and DPO training sets in standard JSONL format for fine-tuning LLMs on UVM verification.
"""

import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dataset_gen.sft_generator import UVMDatasetSFTGenerator
from dataset_gen.dpo_generator import UVMDatasetDPOGenerator


def export_datasets(out_dir: str = "dataset_gen/output"):
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # 1. Export SFT
    sft_gen = UVMDatasetSFTGenerator()
    sft_records = sft_gen.generate_sft_records()
    sft_file = out_path / "uvm_sft.jsonl"
    with open(sft_file, "w", encoding="utf-8") as f:
        for r in sft_records:
            f.write(json.dumps(r) + "\n")
    print(f"✅ Exported {len(sft_records)} SFT records to {sft_file}")

    # 2. Export DPO
    dpo_gen = UVMDatasetDPOGenerator()
    dpo_records = dpo_gen.generate_dpo_records()
    dpo_file = out_path / "uvm_dpo.jsonl"
    with open(dpo_file, "w", encoding="utf-8") as f:
        for r in dpo_records:
            f.write(json.dumps(r) + "\n")
    print(f"✅ Exported {len(dpo_records)} DPO preference pairs to {dpo_file}")


def main():
    export_datasets()


if __name__ == "__main__":
    main()
