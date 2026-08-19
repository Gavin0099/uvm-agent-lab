import time
import uuid
import json
from typing import Dict, Any, List, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from gv100h.gateway.contract import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatMessage,
    UsageInfo
)


class ModelGatewayHandler(BaseHTTPRequestHandler):
    SUPPORTED_MODELS = [
        "Qwen/Qwen3.8-27B",
        "Qwen/Qwen3.8-35B-A3B",
        "Qwen/Qwen2.5-Coder-32B-Instruct"
    ]

    def _send_json(self, status: int, data: Dict[str, Any]):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ["/v1/models", "/models"]:
            models_data = {
                "object": "list",
                "data": [
                    {"id": m, "object": "model", "owned_by": "gv100h-local"}
                    for m in self.SUPPORTED_MODELS
                ]
            }
            self._send_json(200, models_data)
        elif parsed.path == "/health":
            self._send_json(200, {"status": "healthy", "gpu": "Dual GV100"})
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path in ["/v1/chat/completions", "/chat/completions"]:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            
            try:
                req_json = json.loads(body)
                req = ChatCompletionRequest(**req_json)
            except Exception as e:
                self._send_json(400, {"error": f"Invalid request body or schema mismatch: {str(e)}"})
                return

            # Simulate or route to local runtime
            resp = ChatCompletionResponse(
                id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
                created=int(time.time()),
                model=req.model,
                choices=[
                    ChatCompletionChoice(
                        index=0,
                        message=ChatMessage(
                            role="assistant",
                            content=f"Response from {req.model} via GV100H Model Gateway."
                        ),
                        finish_reason="stop"
                    )
                ],
                usage=UsageInfo(prompt_tokens=150, completion_tokens=50, total_tokens=200)
            )
            self._send_json(200, resp.model_dump())
        else:
            self._send_json(404, {"error": "Not found"})


def create_gateway_server(host: str = "127.0.0.1", port: int = 8000) -> HTTPServer:
    return HTTPServer((host, port), ModelGatewayHandler)
