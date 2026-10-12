"""Authenticated, bounded HTTPS relay to the unchanged loopback trial.

Only the Cloudflare hostname named by the operator is admitted. Authentication
and public Origin checks precede the only fixed upstream, 127.0.0.1:8094.
Neither credentials nor request bodies are logged; HTTP operations never retry.
"""
from collections import deque
from functools import partial
from http.client import HTTPConnection, HTTPException
from http.cookies import SimpleCookie, CookieError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
from pathlib import Path
import re
import secrets
import threading
import time
from urllib.parse import parse_qs, urlsplit

PUBLIC_ORIGIN = re.compile(r"https://[a-z0-9]+(?:-[a-z0-9]+)*\.trycloudflare\.com\Z")
JOB_PATH = re.compile(r"/api/jobs/[a-f0-9]{32}\Z")
GET_PATHS = {"/", "/index.html", "/styles.css", "/app.js", "/saved-cases.js",
             "/runtime-config.js", "/api/session"}
COOKIE = "__Host-spec_desk"
MAX_BODY = 4096
MAX_RESPONSE = 2 * 1024 * 1024
LIFETIME = 24 * 3600

LOGIN = '''<!doctype html><html lang="zh-Hant"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>USB Spec Desk · 試用登入</title><style>
*{box-sizing:border-box}body{margin:0;background:#f5f7f8;color:#203f40;font:16px/1.7 system-ui,sans-serif;min-height:100vh;display:grid;place-items:center;padding:24px}
main{width:min(100%,440px);padding:36px;background:white;border:1px solid #e2e8e8;border-radius:20px}
small{letter-spacing:.15em;color:#5c7c73}h1{font-size:28px;margin:12px 0}p{color:#667675}label{display:block;font-weight:600;margin-top:24px}
input,button{width:100%;font:inherit;padding:12px 16px;border-radius:10px}input{border:1px solid #ccd8d5;margin:8px 0 18px}button{background:#204c4a;color:white;border:0;font-weight:600;cursor:pointer}
.error{color:#9c3434}footer{font-size:13px;margin-top:24px;color:#71817c}
</style><main><small>USB SPEC DESK</small><h1>進入規格問答工作台</h1>
<p>輸入試用登入碼，即可查看答案與原始引用。</p>__ERROR__
<form method="post" action="/login"><label for="password">試用登入碼</label>
<input id="password" name="password" type="password" required autocomplete="one-time-code" maxlength="128" autofocus>
<button type="submit">進入試用</button></form>
<footer>目前支援兩個完整問句，額度沿用既有試用紀錄。<br>此為臨時試用入口。</footer></main></html>'''


class GatewayPolicy:
    def __init__(self, password, origin_file=None, *, origin=None, clock=time.monotonic):
        if not isinstance(password, str) or len(password) < 20:
            raise ValueError("Trial password must contain at least 20 characters.")
        if origin is not None and not PUBLIC_ORIGIN.fullmatch(origin):
            raise ValueError("Only an exact HTTPS quick-tunnel origin is admitted.")
        self.password = password.encode()
        self.origin_file = Path(origin_file) if origin_file else None
        self._origin = origin
        self.clock = clock
        self.expires = clock() + LIFETIME
        self.sessions = {}
        self.login_times = deque()
        self.lock = threading.Lock()

    def origin(self):
        with self.lock:
            if self.clock() >= self.expires:
                return None
            if self._origin is None and self.origin_file:
                try:
                    value = self.origin_file.read_text().strip()
                except OSError:
                    return None
                if not PUBLIC_ORIGIN.fullmatch(value):
                    return None
                self._origin = value  # Pin the first valid operator-provided hostname.
            return self._origin

    def login(self, password):
        with self.lock:
            now = self.clock()
            while self.login_times and self.login_times[0] <= now - 60:
                self.login_times.popleft()
            if now >= self.expires:
                return 503, None
            if len(self.login_times) >= 12:
                return 429, None
            self.login_times.append(now)
            if not hmac.compare_digest(password.encode(), self.password):
                return 403, None
            self.sessions = {k: v for k, v in self.sessions.items() if v > now}
            if len(self.sessions) >= 64:
                return 429, None
            token = secrets.token_urlsafe(32)
            self.sessions[token] = self.expires
            return 303, token

    def authorized(self, cookie):
        try:
            values = SimpleCookie(cookie or "")
            token = values[COOKIE].value if COOKIE in values else ""
        except CookieError:
            return False
        with self.lock:
            now = self.clock()
            return now < self.expires and self.sessions.get(token, 0) > now


class GatewayHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, policy, upstream_port=8094, **kwargs):
        self.policy = policy
        self.upstream_port = upstream_port
        super().__init__(*args, **kwargs)

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, *_args):
        pass  # Never record login bodies, cookies, arbitrary URLs or query strings.

    def send(self, status, body=b"", kind="application/json; charset=utf-8", headers=()):
        self.send_response(status)
        for name, value in (("Content-Type", kind), ("Content-Length", str(len(body))),
                            ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"),
                            ("Referrer-Policy", "same-origin"), ("X-Frame-Options", "DENY"),
                            ("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"),
                            *headers):
            self.send_header(name, value)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # A browser disconnect never triggers another upstream request.

    def error(self, status, message):
        self.send(status, json.dumps({"error": message}, ensure_ascii=False).encode())

    def guard(self):
        origin = self.policy.origin()
        if origin is None:
            self.error(503, "試用入口尚未啟用或已到期。")
            return None
        hosts = self.headers.get_all("Host", [])
        if hosts != [urlsplit(origin).netloc] or self.headers.get("X-Forwarded-Proto") != "https":
            self.error(403, "請使用指定的 HTTPS 試用網址。")
            return None
        try:
            parts = urlsplit(self.path)
        except ValueError:
            self.error(400, "網址格式不符。")
            return None
        if parts.scheme or parts.netloc or parts.query or parts.fragment or "%" in parts.path:
            self.error(400, "請使用完整的試用網址，不接受額外網址參數。")
            return None
        return parts.path

    def login_page(self, failed=False):
        error = '<p class="error" role="alert">登入碼不正確，請重新確認。</p>' if failed else ""
        self.send(403 if failed else 200, LOGIN.replace("__ERROR__", error).encode(), "text/html; charset=utf-8")

    def read_body(self, kind):
        values = self.headers.get_all("Content-Length", [])
        if self.headers.get("Transfer-Encoding") or len(values) != 1 or not re.fullmatch(r"[0-9]{1,4}", values[0]):
            raise ValueError("invalid HTTP body framing")
        length = int(values[0])
        if not 0 < length <= MAX_BODY or self.headers.get("Content-Type") != kind:
            raise ValueError("invalid body size/type")
        body = self.rfile.read(length)
        if len(body) != length:
            raise ValueError("incomplete request body")
        return body

    def do_GET(self):
        path = self.guard()
        if path is None:
            return
        if path == "/login":
            return self.login_page()
        if not self.policy.authorized(self.headers.get("Cookie")):
            if path in {"/", "/index.html"}:
                return self.send(303, headers=(("Location", "/login"),))
            return self.error(401, "請先輸入試用登入碼。")
        if path not in GET_PATHS and not JOB_PATH.fullmatch(path):
            return self.error(404, "此入口不提供此操作。")
        self.forward("GET", path)

    def do_POST(self):
        path = self.guard()
        if path is None:
            return
        origins = self.headers.get_all("Origin", [])
        if origins != [self.policy.origin()]:
            return self.error(403, "請由同一個試用網頁送出。")
        if path == "/login":
            try:
                fields = parse_qs(self.read_body("application/x-www-form-urlencoded").decode(), strict_parsing=True)
                if set(fields) != {"password"} or len(fields["password"]) != 1 or len(fields["password"][0]) > 128:
                    raise ValueError("invalid login fields")
                status, token = self.policy.login(fields["password"][0])
            except (ValueError, UnicodeError, OSError):
                return self.error(400, "登入格式不符。")
            if token:
                return self.send(303, headers=(("Location", "/"), ("Set-Cookie", f"{COOKIE}={token}; Path=/; Max-Age={LIFETIME}; Secure; HttpOnly; SameSite=Strict")))
            if status == 403:
                return self.login_page(failed=True)
            return self.error(status, "登入次數過多或試用已到期，請稍後再試。")
        if not self.policy.authorized(self.headers.get("Cookie")):
            return self.error(401, "請先輸入試用登入碼。")
        if path != "/api/jobs":
            return self.error(404, "此入口不提供此操作。")
        try:
            body = self.read_body("application/json")
        except (ValueError, OSError):
            return self.error(400, "請求格式不符。")
        self.forward("POST", path, body)

    def forward(self, method, path, body=None):
        # Caller-selected URL, forwarded headers and credentials never choose upstream.
        connection = HTTPConnection("127.0.0.1", self.upstream_port, timeout=15)
        local_origin = f"http://127.0.0.1:{self.upstream_port}"
        headers = {"Host": f"127.0.0.1:{self.upstream_port}"}
        if method == "POST":
            headers.update({"Origin": local_origin, "Content-Type": "application/json"})
        try:
            connection.request(method, path, body=body, headers=headers)  # Exactly once.
            response = connection.getresponse()
            data = response.read(MAX_RESPONSE + 1)
            if len(data) > MAX_RESPONSE:
                raise HTTPException("upstream response exceeds limit")
            self.send(response.status, data, response.getheader("Content-Type", "application/json"))
        except (OSError, HTTPException):
            self.error(502, "服務連線中斷，請重新整理以查詢原請求；不會自動重送。")
        finally:
            connection.close()


def external_gateway(policy, port=8095, *, upstream_port=8094):
    server = ThreadingHTTPServer(("127.0.0.1", port), partial(GatewayHandler, policy=policy, upstream_port=upstream_port))
    server.daemon_threads = True
    return server
