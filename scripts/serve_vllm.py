#!/usr/bin/env python3
"""
vLLM Local Server Launcher and Health Check CLI
Launches or checks health of local OpenAI-compatible inference server on Dual GV100.
"""

import sys
import time
import json
import urllib.request
import urllib.error
from pathlib import Path


def check_vllm_health(api_base: str = "http://localhost:8000/v1") -> bool:
    url = f"{api_base.rstrip('/')}/models"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = data.get("data", [])
            print(f"✅ vLLM Server is Healthy! Available models: {[m.get('id') for m in models]}")
            return True
    except urllib.error.URLError:
        print("❌ vLLM Server is not currently reachable at " + api_base)
        return False


def main():
    api_base = "http://localhost:8000/v1"
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        healthy = check_vllm_health(api_base)
        sys.exit(0 if healthy else 1)

    print("================================================================")
    print("Dual Tesla/Quadro GV100 vLLM Serving Configuration")
    print("================================================================")
    print("To launch server, run via Docker:")
    print("  docker compose -f deploy/docker-compose.vllm.yml up -d")
    print("\nOr natively with Python:")
    print("  python -m vllm.entrypoints.openai.api_server \\")
    print("    --model Qwen/Qwen2.5-Coder-32B-Instruct-AWQ \\")
    print("    --tensor-parallel-size 2 \\")
    print("    --max-model-len 32768 \\")
    print("    --gpu-memory-utilization 0.90 \\")
    print("    --port 8000")
    print("================================================================")


if __name__ == "__main__":
    main()
