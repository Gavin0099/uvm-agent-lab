import pytest
from pathlib import Path
import json

from scripts.generate_leaderboard import generate_leaderboard_data, calculate_composite_score
from scripts.train_dpo_qwen import get_training_config


def test_leaderboard_composite_score_calculation():
    perfect_cfg = {
        "config_name": "Perfect",
        "compilation_rate": 100.0,
        "simulation_pass_rate": 100.0,
        "coverage_score": 100.0,
        "mean_turns": 1.0,
        "scope_violation_rate": 0.0,
    }
    score = calculate_composite_score(perfect_cfg)
    assert score >= 89.0  # 20 + 40 + 30 - 0 = 90.0

    violating_cfg = {
        "config_name": "Violator",
        "compilation_rate": 100.0,
        "simulation_pass_rate": 100.0,
        "coverage_score": 100.0,
        "mean_turns": 1.0,
        "scope_violation_rate": 10.0,
    }
    fatal_score = calculate_composite_score(violating_cfg)
    assert fatal_score == 0.0


def test_leaderboard_generation_output():
    results = generate_leaderboard_data()
    assert len(results) >= 4
    # Top rank should be fine-tuned or governed runner
    assert results[0].composite_score > results[-1].composite_score


def test_dpo_training_config_structure():
    cfg = get_training_config(
        model_name_or_path="Qwen/Qwen2.5-Coder-32B-Instruct",
        use_qlora=True,
        tensor_parallel_size=2,
    )
    assert cfg["model"]["tensor_parallel_size"] == 2
    assert cfg["model"]["load_in_4bit"] is True
    assert "q_proj" in cfg["lora"]["target_modules"]
    assert cfg["dpo_hyperparameters"]["gradient_checkpointing"] is True
