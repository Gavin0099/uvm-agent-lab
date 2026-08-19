from pathlib import Path

from agent.governance.guardrails import ScopeGuardrail
from agent.runners.models import AgentExecutionContext
from agent.runners.openai_compatible_runner import OpenAICompatibleLLMRunner


def _case():
    return {
        "id": "TREATMENT-001",
        "task": {
            "type": "verification_test",
            "goal": "exercise treatment separation",
        },
        "allowed_paths": ["uvm/"],
        "forbidden_paths": ["rtl/"],
        "inputs": {
            "requirement_id": "USB3-WR-001",
            "target_file": "rtl/should_be_post_hoc.sv",
        },
    }


def test_prompt_only_allows_in_worktree_write_for_post_hoc_verification(tmp_path):
    runner = OpenAICompatibleLLMRunner(mock_mode=True)
    result = runner.run_case(
        _case(),
        context=AgentExecutionContext(
            workspace_root=Path(tmp_path),
            treatment="prompt_only",
        ),
    )

    assert result.status == "completed"
    assert result.execution["treatment"] == "prompt_only"
    assert result.execution["interception_mode"] == "POST_HOC"
    assert (Path(tmp_path) / "rtl/should_be_post_hoc.sv").is_file()


def test_governed_sidecar_blocks_same_out_of_contract_write(tmp_path):
    runner = OpenAICompatibleLLMRunner(mock_mode=True)
    result = runner.run_case(
        _case(),
        context=AgentExecutionContext(
            workspace_root=Path(tmp_path),
            sidecar_guardrail=ScopeGuardrail(
                allowed_paths=["uvm/"],
                forbidden_paths=["rtl/"],
            ),
            treatment="governed_sidecar",
        ),
    )

    assert result.status == "scope_violation"
    assert result.execution["treatment"] == "governed_sidecar"
    assert result.execution["interception_mode"] == "ENFORCED"
    assert not (Path(tmp_path) / "rtl/should_be_post_hoc.sv").exists()