"""Local Operator UI server.

Serves the development shell and a fixture-backed /api/qa. Does not replace
dashboard/ and does not implement retrieval.
"""

from __future__ import annotations

import json
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any, Iterable, Optional
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
                    "source_modes": ["fixture", "service", "real_local_rag"],
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
        if parsed.path not in ("/api/qa", "/api/qa/stream"):
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
        if parsed.path == "/api/qa/stream":
            self._stream_real_local_rag(payload)
            return
        question = str(payload.get("question") or "").strip()
        source = payload.get("source") or "fixture"
        fixture = str(payload.get("fixture") or "answered")
        answer_scope = payload.get("answer_scope") or None
        retrieval_mode = payload.get("retrieval_mode") or "single_scope"
        allowed = payload.get("allowed_evidence_scopes")
        if source not in ("fixture", "service", "real_local_rag"):
            self._json(
                400,
                {"error": "source must be fixture, service, or real_local_rag"},
            )
            return
        if source in ("service", "real_local_rag") and not question:
            self._json(
                400,
                {"error": f"question is required when source={source}"},
            )
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
        except RuntimeError as err:
            self._json(502, {"error": str(err)})
            return
        self._json(200, view.model_dump())

    def _stream_real_local_rag(self, payload: dict[str, Any]) -> None:
        source = payload.get("source") or "fixture"
        if source != "real_local_rag":
            self._json(
                400,
                {"error": "stream endpoint requires source=real_local_rag"},
            )
            return
        question = str(payload.get("question") or "").strip()
        if not question:
            self._json(400, {"error": "question is required for real_local_rag"})
            return
        answer_scope = payload.get("answer_scope") or None
        retrieval_mode = payload.get("retrieval_mode") or "single_scope"
        allowed = payload.get("allowed_evidence_scopes")
        try:
            events = self.adapter.stream_real_local_rag(
                question,
                answer_scope=answer_scope,
                retrieval_mode=retrieval_mode,
                allowed_evidence_scopes=(
                    tuple(allowed) if isinstance(allowed, list) else None
                ),
            )
        except ValueError as err:
            self._json(400, {"error": str(err)})
            return
        except RuntimeError as err:
            self._json(502, {"error": str(err)})
            return
        self._ndjson_stream(events)

    def _ndjson_stream(self, events: Iterable[dict[str, Any]]) -> None:
        """Write one flushed JSON event per line so fetch() can render tokens."""
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        try:
            for event in events:
                body = (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")
                self.wfile.write(body)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as exc:
            try:
                body = (
                    json.dumps(
                        {"type": "error", "error": str(exc)},
                        ensure_ascii=False,
                    )
                    + "\n"
                ).encode("utf-8")
                self.wfile.write(body)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                return

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
