import pytest
from pathlib import Path
from agent.runners.openai_compatible_runner import OpenAICompatibleLLMRunner
from experiments.gate3.run_gate3_ab import evaluate_model


def test_openai_compatible_runner_mock_mode():
    runner = OpenAICompatibleLLMRunner(name="test_qwen", mock_mode=True)
    cases = list(Path("benchmarks/cases").glob("*.yaml"))
    
    summary = evaluate_model(runner, cases)
    assert summary["model_name"] == "test_qwen"
    assert summary["task_success_rate"] >= 80.0
    assert summary["total_tokens_consumed"] > 0
    assert len(summary["case_details"]) == len(cases)


def test_openai_compatible_runner_live_mode_fails_closed_when_unreachable():
    # Test that runner in live mode fails closed with ConnectionError when server is unreachable
    runner = OpenAICompatibleLLMRunner(name="offline_model", api_base="http://localhost:9999/v1", mock_mode=False)
    with pytest.raises(ConnectionError, match="ENDPOINT_UNAVAILABLE"):
        runner._call_llm_api([{"role": "user", "content": "hello"}])

