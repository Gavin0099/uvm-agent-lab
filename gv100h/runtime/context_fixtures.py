from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ContextLength = Literal[32768, 65536, 131072, 196608, 262144]
MIN_CONTEXT_COVERAGE = 0.9


class ContextPromptFixture(BaseModel):
    """Deterministic prompt/answer binding for one Gate 4 context cell."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1", pattern=r"^1$")
    context_length: ContextLength
    prompt: str = Field(min_length=1)
    prompt_hash: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    actual_prompt_tokens: int = Field(gt=0)
    expected_response_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")

    def validate_prompt(self) -> None:
        actual_hash = hashlib.sha256(self.prompt.encode("utf-8")).hexdigest()
        if actual_hash.lower() != self.prompt_hash.lower():
            raise ValueError(
                "context fixture prompt_hash does not match prompt bytes: "
                f"expected {self.prompt_hash}, got {actual_hash}"
            )
        minimum_tokens = int(self.context_length * MIN_CONTEXT_COVERAGE)
        if self.actual_prompt_tokens < minimum_tokens:
            raise ValueError(
                "context fixture actual_prompt_tokens does not exercise the "
                f"declared context slot: {self.actual_prompt_tokens} < {minimum_tokens}"
            )
        if self.actual_prompt_tokens > self.context_length:
            raise ValueError(
                "context fixture actual_prompt_tokens exceeds context_length"
            )


def load_context_fixture(path: str | Path) -> ContextPromptFixture:
    fixture_path = Path(path).resolve()
    try:
        raw = json.loads(fixture_path.read_text(encoding="utf-8"))
        fixture = ContextPromptFixture.model_validate(raw)
        fixture.validate_prompt()
        return fixture
    except Exception as exc:
        raise ValueError(f"invalid Gate 4 context fixture: {exc}") from exc
