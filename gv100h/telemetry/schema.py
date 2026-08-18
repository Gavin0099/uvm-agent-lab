from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class FailureClass(str, Enum):
    MODEL_REASONING_FAIL = "MODEL_REASONING_FAIL"
    TOOL_CALL_FAIL = "TOOL_CALL_FAIL"
    CONTEXT_FAIL = "CONTEXT_FAIL"
    BUILD_FAIL = "BUILD_FAIL"
    TEST_FAIL = "TEST_FAIL"
    HALLUCINATED_SUCCESS = "HALLUCINATED_SUCCESS"
    SCOPE_VIOLATION = "SCOPE_VIOLATION"
    TIMEOUT = "TIMEOUT"
    ENDPOINT_UNAVAILABLE = "ENDPOINT_UNAVAILABLE"


class TelemetryEvent(BaseModel):
    request_id: str
    timestamp: float
    model_id: str
    runtime: str
    quantization: str
    context_tokens: int
    output_tokens: int
    ttft_ms: float
    decode_tps: float
    total_latency_sec: float
    tool_calls_count: int = 0
    status: str
    failure_class: Optional[FailureClass] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
