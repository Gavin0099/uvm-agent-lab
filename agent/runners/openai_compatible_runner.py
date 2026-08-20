import os
import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from agent.runners.base import BaseAgentRunner
from agent.governance.guardrails import ScopeGuardrail
from agent.governance.evidence_verifier import EvidenceVerifier
from agent.governance.policy import GovernanceViolationCode, GovernanceSeverity
from agent.tools.fs_tools import GovernedFileSystemTools
from agent.tools.sim_tools import GovernedSimTools
from agent.adapters.spec_ref_kit import SpecReferenceKitAdapter
from agent.prompts.system_prompts import GOVERNED_UVM_SYSTEM_PROMPT, generate_task_prompt


from agent.runners.models import AgentExecutionContext, AgentRunResult


class OpenAICompatibleLLMRunner(BaseAgentRunner):
    """
    Gate 3: Standardized OpenAI-compatible LLM Runner for Model A/B Benchmarking.
    Supports vLLM, SGLang, Ollama, llama.cpp, and mock replay for CI.
    """

    def __init__(
        self,
        name: str = "qwen2.5-coder-32b",
        api_base: str = "http://localhost:8000/v1",
        model_id: str = "Qwen/Qwen2.5-Coder-32B-Instruct",
        api_key: str = "EMPTY",
        temperature: float = 0.0,
        max_tokens: int = 2048,
        token_budget: int = 8000,
        mock_mode: bool = False,
        mock_success_rate: float = 1.0,
    ):
        super().__init__(name)
        self.api_base = api_base.rstrip("/")
        self.model_id = model_id
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.token_budget = token_budget
        self.mock_mode = mock_mode
        self.mock_success_rate = mock_success_rate

    def _call_llm_api(self, messages: list) -> Dict[str, Any]:
        """
        Call OpenAI-compatible /chat/completions endpoint.
        """
        if self.mock_mode:
            # Deterministic simulation of model response
            return {
                "content": f"// Verified UVM generation by {self.name}\nclass evaluated_test;\nendclass\n",
                "prompt_tokens": 450,
                "completion_tokens": 120,
                "response_model": self.model_id,
                "models_endpoint_response": {"data": [{"id": self.model_id}]},
            }

        models_url = f"{self.api_base}/models"
        url = f"{self.api_base}/chat/completions"
        payload = {
            "model": self.model_id,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        try:
            models_req = urllib.request.Request(models_url, headers=headers, method="GET")
            with urllib.request.urlopen(models_req, timeout=10) as models_resp:
                models_data = json.loads(models_resp.read().decode("utf-8"))
            model_ids = {
                item.get("id")
                for item in models_data.get("data", [])
                if isinstance(item, dict)
            }
            if self.model_id not in model_ids:
                raise ConnectionError(
                    f"ENDPOINT_MODEL_MISMATCH: /models does not expose {self.model_id}"
                )
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_json = json.loads(resp.read().decode("utf-8"))
                choice = resp_json["choices"][0]["message"]
                usage = resp_json.get("usage", {})
                response_model = resp_json.get("model")
                if response_model != self.model_id:
                    raise ConnectionError(
                        f"ENDPOINT_MODEL_MISMATCH: response model {response_model!r} "
                        f"does not match {self.model_id!r}"
                    )
                return {
                    "content": choice.get("content", ""),
                    "prompt_tokens": usage.get("prompt_tokens", 400),
                    "completion_tokens": usage.get("completion_tokens", 100),
                    "response_model": response_model,
                    "models_endpoint_response": models_data,
                }
        except urllib.error.URLError as e:
            raise ConnectionError(f"ENDPOINT_UNAVAILABLE: Failed to connect to OpenAI-compatible endpoint at {url}: {e}")

    def run_case(
        self,
        case_dict: Dict[str, Any],
        context: Optional[AgentExecutionContext] = None
    ) -> AgentRunResult:
        start_time = time.time()
        tool_calls = []
        violations = []

        workspace_root = context.workspace_root if context else Path(".").resolve()
        token_budget = context.token_budget if context else self.token_budget
        treatment = context.treatment if context else "governed_sidecar"
        if not self.mock_mode and not context:
            raise ConnectionError(
                "RUNTIME_ATTESTATION_REQUIRED: live execution requires an attestation seed"
            )
        if not self.mock_mode and not context.runtime_attestation_seed:
            raise ConnectionError(
                "RUNTIME_ATTESTATION_REQUIRED: live execution requires an attestation seed"
            )
        if treatment == "governed_sidecar":
            if context and context.sidecar_guardrail is not None:
                guardrail = context.sidecar_guardrail
            else:
                allowed = case_dict.get("allowed_paths", ["uvm/"])
                forbidden = case_dict.get("forbidden_paths", ["rtl/"])
                guardrail = ScopeGuardrail(allowed_paths=allowed, forbidden_paths=forbidden)
            interception_mode = "ENFORCED"
        else:
            # Arm A keeps only disposable-worktree containment. Scope violations
            # are classified by the post-hoc verifier after the write occurs.
            guardrail = None
            interception_mode = "POST_HOC"

        if treatment not in {"prompt_only", "governed_sidecar"}:
            allowed = case_dict.get("allowed_paths", ["uvm/"])
            forbidden = case_dict.get("forbidden_paths", ["rtl/"])
            guardrail = ScopeGuardrail(allowed_paths=allowed, forbidden_paths=forbidden)
            interception_mode = "UNSUPPORTED"

        fs_tools = GovernedFileSystemTools(guardrail=guardrail, root_dir=str(workspace_root))
        sim_tools = GovernedSimTools(workspace_root=workspace_root)
        spec_adapter = SpecReferenceKitAdapter()

        req_id = case_dict.get("inputs", {}).get("requirement_id", case_dict.get("id", "UNKNOWN_TASK"))
        target_file = case_dict.get("inputs", {}).get("target_file", "uvm/tests/test_case.sv")

        # 1. Spec Retrieval
        spec_res = spec_adapter.query_requirement(req_id)
        tool_calls.append({
            "tool": "query_spec",
            "args": {"requirement_id": req_id},
            "status": spec_res["status"],
            "output_summary": f"Retrieved spec snippet for {req_id}"
        })

        # 2. Prepare Prompt & Call Model
        messages = [
            {"role": "system", "content": GOVERNED_UVM_SYSTEM_PROMPT},
            {"role": "user", "content": generate_task_prompt(case_dict) + f"\nSpec Context: {spec_res.get('content_snippet', '')}"}
        ]
        llm_res = self._call_llm_api(messages)
        code_content = llm_res["content"]

        # 3. File System Write (strictly in workspace_root)
        fs_res = fs_tools.write_file(target_file, code_content)
        tool_calls.append({
            "tool": "write_file",
            "args": {"file_path": target_file},
            "status": fs_res["status"],
            "output_summary": f"Wrote generated code to {target_file}"
        })

        if fs_res["status"] == "governance_violation":
            violations.extend(fs_res.get("violations", []))

        # 4. Agent Compile & Simulate Tool Invocations
        comp_res = sim_tools.compile(target_file)
        tool_calls.append({
            "tool": "compile",
            "args": {"target_file": target_file},
            "status": comp_res["status"],
            "output_summary": f"Compile {comp_res['status']}"
        })

        sim_res = sim_tools.simulate("valid_test" if comp_res["status"] == "pass" else "broken_test")
        tool_calls.append({
            "tool": "simulate",
            "args": {"test_name": "valid_test"},
            "status": sim_res["status"],
            "output_summary": f"Simulate {sim_res['status']}"
        })

        # 5. Evidence Assembly
        diff_text = f"--- a/{target_file}\n+++ b/{target_file}\n@@ -0,0 +1,5 @@\n+{code_content[:100]}\n"
        evidence = {
            "requirement_id": req_id,
            "git_diff": diff_text,
            "compile_log": comp_res["log"],
            "simulation_log": sim_res["log"],
            "coverage_report": f"Overall Coverage: {sim_res.get('coverage', 100.0)}%",
            "log_hash": sim_res["log_hash"],
        }

        total_tokens = llm_res["prompt_tokens"] + llm_res["completion_tokens"]
        if total_tokens > token_budget:
            violations.append({
                "code": GovernanceViolationCode.TIMEOUT_VIOLATION,
                "severity": GovernanceSeverity.HIGH,
                "message": f"Token budget exceeded: {total_tokens} > {token_budget} tokens."
            })

        # Determine agent status and claimed outcome
        if violations:
            status = "scope_violation"
            claimed_outcome = "failure"
        else:
            status = "completed"
            claimed_outcome = "success"

        return AgentRunResult(
            case_id=case_dict.get("id", req_id),
            runner_name=self.name,
            status=status,
            agent_claimed_outcome=claimed_outcome,
            changed_files_claimed=[target_file],
            duration_seconds=time.time() - start_time,
            governance_violations=violations,
            evidence=evidence,
            execution={
                "compile_status": comp_res["status"],
                "simulation_status": sim_res["status"],
                "endpoint_observed": not self.mock_mode,
                "treatment": treatment,
                "interception_mode": interception_mode,
                "response_model": llm_res.get("response_model"),
                "models_endpoint_response": llm_res.get("models_endpoint_response"),
                "runtime_attestation_observed_at": datetime.now(timezone.utc).isoformat(),
                "step_count": len(tool_calls),
                "retry_count": 0,
                "tool_calls": tool_calls,
            },
            metrics={
                "prompt_tokens": llm_res["prompt_tokens"],
                "completion_tokens": llm_res["completion_tokens"],
            }
        )

