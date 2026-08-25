from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

from agent.prompts.system_prompts import (
    GOVERNED_CODING_SYSTEM_PROMPT,
    GOVERNED_UVM_SYSTEM_PROMPT,
    generate_coding_task_prompt,
    generate_task_prompt,
)


AgentProfile = Literal["lightweight", "eda"]


class AgentExecutionStrategy(ABC):
    profile: AgentProfile
    requires_spec_retrieval: bool
    requires_eda_tools: bool

    @abstractmethod
    def build_messages(
        self,
        case_dict: dict[str, Any],
        spec_context: str = "",
        target_context: str = "",
    ) -> list[dict[str, str]]:
        raise NotImplementedError


class LightweightCodingStrategy(AgentExecutionStrategy):
    profile: AgentProfile = "lightweight"
    requires_spec_retrieval = False
    requires_eda_tools = False

    def build_messages(
        self,
        case_dict: dict[str, Any],
        spec_context: str = "",
        target_context: str = "",
    ) -> list[dict[str, str]]:
        del spec_context
        return [
            {"role": "system", "content": GOVERNED_CODING_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": generate_coding_task_prompt(case_dict, target_context),
            },
        ]


class EDAUVMStrategy(AgentExecutionStrategy):
    profile: AgentProfile = "eda"
    requires_spec_retrieval = True
    requires_eda_tools = True

    def build_messages(
        self,
        case_dict: dict[str, Any],
        spec_context: str = "",
        target_context: str = "",
    ) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": GOVERNED_UVM_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": generate_task_prompt(case_dict)
                + f"\nSpec Context: {spec_context}",
            },
        ]


def create_execution_strategy(profile: str) -> AgentExecutionStrategy:
    if profile == "lightweight":
        return LightweightCodingStrategy()
    if profile == "eda":
        return EDAUVMStrategy()
    raise ValueError(f"unknown agent execution profile: {profile}")