#!/usr/bin/env python3
"""
UVM Verification Model DPO Fine-Tuning Pipeline.
Prepares LoRA / QLoRA / Full DPO training configurations targeting Dual GV100 (64GB VRAM).
Configured for: Qwen/Qwen2.5-Coder-32B-Instruct or Mistral-NeMo-15B.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def get_training_config(
    model_name_or_path: str = "Qwen/Qwen2.5-Coder-32B-Instruct",
    dataset_dir: str = "datasets",
    output_dir: str = "checkpoints/qwen-32b-uvm-dpo",
    use_qlora: bool = True,
    tensor_parallel_size: int = 2,
    learning_rate: float = 5e-6,
    beta: float = 0.1,
    max_seq_length: int = 4096,
) -> dict[str, Any]:
    """
    Returns high-performance DPO training hyperparameters optimized for 2× GV100 32GB cards.
    """
    return {
        "model": {
            "model_name_or_path": model_name_or_path,
            "torch_dtype": "bfloat16" if not use_qlora else "float16",
            "load_in_4bit": use_qlora,
            "bnb_4bit_quant_type": "nf4",
            "bnb_4bit_compute_dtype": "float16",
            "use_flash_attention_2": False,  # GV100 (Volta) uses standard scaled dot-product / SDPA
            "tensor_parallel_size": tensor_parallel_size,
        },
        "lora": {
            "r": 64,
            "lora_alpha": 128,
            "lora_dropout": 0.05,
            "bias": "none",
            "target_modules": [
                "q_proj",
                "k_proj",
                "v_proj",
                "o_proj",
                "gate_proj",
                "up_proj",
                "down_proj",
            ],
            "task_type": "CAUSAL_LM",
        },
        "dpo_hyperparameters": {
            "beta": beta,
            "learning_rate": learning_rate,
            "lr_scheduler_type": "cosine",
            "warmup_ratio": 0.1,
            "per_device_train_batch_size": 1,
            "gradient_accumulation_steps": 8,
            "num_train_epochs": 3,
            "max_length": max_seq_length,
            "max_prompt_length": 1536,
            "max_target_length": 2560,
            "gradient_checkpointing": True,
            "optim": "paged_adamw_8bit" if use_qlora else "adamw_torch",
            "evaluation_strategy": "steps",
            "eval_steps": 50,
            "save_strategy": "steps",
            "save_steps": 50,
            "save_total_limit": 3,
            "logging_steps": 10,
            "report_to": "tensorboard",
        },
        "dataset": {
            "train_file": str(Path(dataset_dir) / "dpo_train.jsonl"),
            "eval_file": str(Path(dataset_dir) / "dpo_eval.jsonl"),
        },
        "output": {
            "output_dir": output_dir,
            "save_merged_model": True,
            "export_awq": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="UVM DPO Training Pipeline Configurator")
    parser.add_argument("--model", default="Qwen/Qwen2.5-Coder-32B-Instruct", help="Base model identifier")
    parser.add_argument("--dataset-dir", default="datasets", help="Directory containing DPO jsonl datasets")
    parser.add_argument("--output-dir", default="checkpoints/qwen-32b-uvm-dpo", help="Output checkpoint directory")
    parser.add_argument("--no-qlora", action="store_true", help="Disable QLoRA and use FP16 full/LoRA")
    parser.add_argument("--dry-run", action="store_true", help="Validate config without training execution")
    args = parser.parse_args()

    # Step 1: Ensure dataset exists or generate sample dataset
    dataset_path = Path(args.dataset_dir)
    train_file = dataset_path / "dpo_train.jsonl"
    if not train_file.exists():
        print(f"Dataset not found at {train_file}. Generating fresh DPO dataset...")
        from dataset_gen.export_dataset import main as export_main
        import sys
        old_argv = sys.argv
        sys.argv = ["export_dataset.py", "--output-dir", str(dataset_path), "--dpo-count", "20", "--sft-count", "20"]
        export_main()
        sys.argv = old_argv

    # Step 2: Build configuration
    config = get_training_config(
        model_name_or_path=args.model,
        dataset_dir=args.dataset_dir,
        output_dir=args.output_dir,
        use_qlora=not args.no_qlora,
    )

    out_cfg_path = Path(args.output_dir) / "dpo_training_config.json"
    out_cfg_path.parent.mkdir(parents=True, exist_ok=True)
    out_cfg_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    print("=" * 70)
    print("🚀 UVM Agent Lab — DPO Fine-Tuning Recipe Generated")
    print(f"• Model: {config['model']['model_name_or_path']}")
    print(f"• Quantization: {'4-bit NF4 (QLoRA)' if config['model']['load_in_4bit'] else '16-bit'}")
    print(f"• Hardware Target: Dual GV100 (64GB Total VRAM, TP=2)")
    print(f"• DPO Dataset: {config['dataset']['train_file']}")
    print(f"• Config File Saved: {out_cfg_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
