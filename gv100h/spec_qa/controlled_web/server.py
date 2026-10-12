"""Fixed loopback routes with caller-owned assets and executor session."""
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
from urllib.parse import urlsplit

from gv100h.spec_qa.source_binding.strict_json import strict_object
from .config import ASSETS
from .session import TrialError

JOB = re.compile(r"/api/jobs/[a-f0-9]{32}\Z")


class ControlledHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, session, paths, **kwargs):
        self.session, self.paths = session, paths
        super().__init__(*args, **kwargs)

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, *_args):
        pass

    def send(self, status, body, kind="application/json"):
        self.send_response(status)
        for key, value in (("Content-Type", kind + "; charset=utf-8"),
                           ("Content-Length", str(len(body))), ("Cache-Control", "no-store"),
                           ("X-Content-Type-Options", "nosniff"), ("Referrer-Policy", "same-origin")):
            self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # Disconnect never restarts or cancels the already-reserved job.

    def json(self, status, value):
        self.send(status, json.dumps(value, ensure_ascii=False, allow_nan=False).encode())

    def guard(self):
        allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        if len(self.headers.get_all("Host", [])) != 1 or self.headers["Host"] not in allowed:
            raise TrialError("僅接受本機網址。", 403)
        try:
            path = urlsplit(self.path)
        except ValueError as exc:
            raise TrialError("網址格式不符。", 400) from exc
        if path.scheme or path.netloc or path.query or path.fragment or "%" in path.path:
            raise TrialError("網址格式不符。", 400)
        return path.path

    def do_GET(self):
        try:
            path = self.guard()
            if path in ASSETS:
                name, kind = ASSETS[path]
                return self.send(200, (self.paths.assets / name).read_bytes(), kind)
            if path == "/runtime-config.js":
                return self.send(200, b'window.SPEC_DESK_RUNTIME={mode:"controlled_live",live_enabled:true,free_question:true,max_question_length:1000};', "text/javascript")
            if path == "/api/session":
                return self.json(200, self.session.summary())
            if JOB.fullmatch(path):
                return self.json(200, self.session.job(path.removeprefix("/api/jobs/")))
            return self.json(404, {"error": "找不到此頁。"})
        except TrialError as exc:
            self.json(exc.status, {"error": str(exc)})
        except OSError:
            self.json(503, {"error": "網頁資料暫時無法讀取。"})

    def do_POST(self):
        try:
            path = self.guard()
            origins = {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}
            if len(self.headers.get_all("Origin", [])) != 1 or self.headers["Origin"] not in origins:
                raise TrialError("請由同一個本機網頁送出。", 403)
            if path != "/api/jobs":
                raise TrialError("此入口不提供其他操作。", 404)
            values = self.headers.get_all("Content-Length", [])
            if (self.headers.get("Transfer-Encoding") or len(values) != 1
                    or re.fullmatch(r"[0-9]{1,4}", values[0]) is None
                    or not 0 < int(values[0]) <= 4096
                    or self.headers.get("Content-Type") != "application/json"):
                raise TrialError("請求格式不符。", 400)
            raw = self.rfile.read(int(values[0]))
            if len(raw) != int(values[0]):
                raise TrialError("請求未完整送達。", 400)
            value = strict_object(raw.decode("utf-8"))
            if set(value) != {"question", "request_id"}:
                raise TrialError("請求只接受問句與識別碼。", 400)
            return self.json(202, {"job_id": self.session.submit(value["question"], value["request_id"])})
        except TrialError as exc:
            self.json(exc.status, {"error": str(exc)})
        except (ValueError, UnicodeError, TypeError, OSError):
            self.json(400, {"error": "請求不是完整有效的 JSON。"})


def create_backend(session, paths, port=8094):
    """Callable entry, portable from any cwd; the host retains session ownership.

    Not a native inference launcher. Use the external gateway for public HTTPS.
    """
    if session.directory != paths.ledger:
        raise ValueError("Server and session must use the same explicit ledger.")
    return ThreadingHTTPServer(("127.0.0.1", port), partial(ControlledHandler, session=session, paths=paths))
