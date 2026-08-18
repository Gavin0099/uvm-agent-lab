import pytest
import sys
import threading
import urllib.request
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gv100h.gateway.server import create_gateway_server


@pytest.mark.contract
def test_gateway_models_endpoint():
    server = create_gateway_server(host="127.0.0.1", port=8009)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        url = "http://127.0.0.1:8009/v1/models"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["object"] == "list"
            model_ids = [m["id"] for m in data["data"]]
            assert "Qwen/Qwen3.8-35B-A3B" in model_ids
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.contract
def test_gateway_chat_completion_endpoint():
    server = create_gateway_server(host="127.0.0.1", port=8010)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        url = "http://127.0.0.1:8010/v1/chat/completions"
        payload = {
            "model": "Qwen/Qwen3.8-35B-A3B",
            "messages": [{"role": "user", "content": "Hello"}],
            "temperature": 0.0
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert "choices" in data
            assert len(data["choices"]) > 0
            assert "message" in data["choices"][0]
            assert "content" in data["choices"][0]["message"]
    finally:
        server.shutdown()
        server.server_close()
