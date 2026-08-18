import json
import time
import uuid
from pathlib import Path
from typing import Optional, Dict, Any

from gv100h.telemetry.schema import TelemetryEvent, FailureClass


class TelemetryLogger:
    """
    Structured Telemetry Logger for GV100H Model Runs.
    Persists events as JSON Lines while keeping sensitive customer data isolated.
    """

    def __init__(self, log_dir: str = "artifacts/telemetry"):
        self.log_dir = Path(log_dir).resolve()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "gv100h_telemetry.jsonl"

    def record_event(self, event: TelemetryEvent):
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event.model_dump(), ensure_ascii=False) + "\n")

    def log_run(
        self,
        model_id: str,
        runtime: str,
        quantization: str,
        context_tokens: int,
        output_tokens: int,
        ttft_ms: float,
        decode_tps: float,
        total_latency_sec: float,
        status: str,
        tool_calls_count: int = 0,
        failure_class: Optional[FailureClass] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TelemetryEvent:
        event = TelemetryEvent(
            request_id=f"req-{uuid.uuid4().hex[:10]}",
            timestamp=time.time(),
            model_id=model_id,
            runtime=runtime,
            quantization=quantization,
            context_tokens=context_tokens,
            output_tokens=output_tokens,
            ttft_ms=ttft_ms,
            decode_tps=decode_tps,
            total_latency_sec=total_latency_sec,
            tool_calls_count=tool_calls_count,
            status=status,
            failure_class=failure_class,
            metadata=metadata or {},
        )
        self.record_event(event)
        return event
