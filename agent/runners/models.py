from pathlib import Path
from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict

from agent.governance.guardrails import ScopeGuardrail


class AgentExecutionContext(BaseModel):
    """
    Standardized execution context injected into any BaseAgentRunner.
    Guarantees strict workspace isolation and distinguishes invariant containment
    from experiment treatments (Arm A Prompt-Only vs Arm B Governed Sidecar).
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    workspace_root: Path
    sidecar_guardrail: Optional[ScopeGuardrail] = None
    eda_router: Optional[Any] = None
    treatment: Literal["prompt_only", "governed_sidecar"] = "governed_sidecar"
    token_budget: int = 8000
    tool_budget: int = 20
    timeout_sec: int = 120


class AgentRunResult(BaseModel):
    """
    Strongly-typed execution result capturing Agent claims, tool traces,
    governance intercepts, and token metrics.
    Note: agent_claimed_outcome represents the Agent's self-assertion;
    final qualification truth is strictly evaluated by IndependentVerifier.
    """
    case_id: str
    runner_name: str
    status: Literal["completed", "error", "scope_violation", "timeout"]
    agent_claimed_outcome: Literal["success", "failure", "inconclusive"]
    changed_files_claimed: List[str] = Field(default_factory=list)
    duration_seconds: float
    governance_violations: List[Dict[str, Any]] = Field(default_factory=list)
    evidence: Dict[str, Any] = Field(default_factory=dict)
    execution: Dict[str, Any] = Field(default_factory=dict)

    metrics: Dict[str, Any] = Field(default_factory=dict)
