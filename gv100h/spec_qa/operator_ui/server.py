"""Local Operator UI server.

Serves the development shell and a fixture-backed /api/qa. Does not replace
dashboard/ and does not implement retrieval.
"""

from __future__ import annotations

import json
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from gv100h.spec_qa.operator_ui.adapter import OperatorQAAdapter, fixture_catalog
from gv100h.spec_qa.operator_ui.contract import CLAIM_CEILING, FROZEN_QA_RESPONSE_FIELDS

UI_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_PORT = 8091


class OperatorUIHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, adapter: Optional[OperatorQAAdapter] = None, **kwargs):
        self.adapter = adapter or OperatorQAAdapter()
        super().__init__(*args, directory=str(UI_DIR), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write("operator-ui: " + (format % args) + "\n")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._json(
                200,
                {
                    "status": "ok",
                    "claim_ceiling": CLAIM_CEILING,
                    "frozen_fields": list(FROZEN_QA_RESPONSE_FIELDS),
                    "fixtures": fixture_catalog(),
                },
            )
            return
        if parsed.path == "/api/fixtures":
            self._json(200, {"fixtures": fixture_catalog()})
            return
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/qa":
            self.send_error(404, "not found")
            return
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "invalid JSON"})
            return
        if not isinstance(payload, dict):
            self._json(400, {"error": "JSON object required"})
            return
        question = str(payload.get("question") or "").strip()
        source = payload.get("source") or "fixture"
        fixture = str(payload.get("fixture") or "answered")
        answer_scope = payload.get("answer_scope") or None
        retrieval_mode = payload.get("retrieval_mode") or "single_scope"
        allowed = payload.get("allowed_evidence_scopes")
        if source not in ("fixture", "service"):
            self._json(400, {"error": "source must be fixture or service"})
            return
        if source == "service" and not question:
            self._json(400, {"error": "question is required when source=service"})
            return
        try:
            view = self.adapter.ask(
                question,
                answer_scope=answer_scope,
                retrieval_mode=retrieval_mode,
                allowed_evidence_scopes=tuple(allowed) if isinstance(allowed, list) else None,
                source=source,
                fixture=fixture,
            )
        except KeyError as exc:
            self._json(404, {"error": str(exc)})
            return
        except ValueError as err:
            self._json(400, {"error": str(err)})
            return
        self._json(200, view.model_dump())

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def run_operator_ui(port: int = DEFAULT_PORT) -> None:
    adapter = OperatorQAAdapter()

    def factory(*args, **kwargs):
        return OperatorUIHandler(*args, adapter=adapter, **kwargs)

    httpd = HTTPServer(("127.0.0.1", port), factory)
    print(f"Operator UI (development shell) http://127.0.0.1:{port}")
    print(CLAIM_CEILING)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    run_operator_ui(port)
