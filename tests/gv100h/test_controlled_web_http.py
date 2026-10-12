"""Real loopback HTTP tests with an explicit fake trial backend; zero model calls."""
from contextlib import contextmanager
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from urllib.parse import urlencode

import pytest

from gv100h.spec_qa.controlled_web.gateway import GatewayPolicy, external_gateway

ORIGIN = "https://usb-desk-test.trycloudflare.com"
PASSWORD = "fixture-only-trial-password-2026"
BODY = b'{"question":"fixture-only question","request_id":"0123456789abcdef0123456789abcdef"}'


class FakeTrial(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        self.server.records.append(("GET", self.path, dict(self.headers), b""))
        body = b'{"count":2,"remaining":4}' if self.path == "/api/session" else b"fixture original asset bytes"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        self.server.records.append(("POST", self.path, dict(self.headers), body))
        self.server.reservations += 1
        if self.server.drop_post:
            self.close_connection = True
            return
        data = b'{"job_id":"0123456789abcdef0123456789abcdef"}'
        self.send_response(202)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@contextmanager
def started(server):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.fixture
def relay():
    backend = ThreadingHTTPServer(("127.0.0.1", 0), FakeTrial)
    backend.records, backend.reservations, backend.drop_post = [], 2, False
    policy = GatewayPolicy(PASSWORD, origin=ORIGIN)
    with started(backend), started(external_gateway(policy, 0, upstream_port=backend.server_port)) as gateway:
        yield gateway, backend, policy


def request(relay, method, path, body=None, *, cookie=None, headers=None):
    gateway, _, _ = relay
    base = {"Host": "usb-desk-test.trycloudflare.com", "X-Forwarded-Proto": "https"}
    if method == "POST":
        base["Origin"] = ORIGIN
        base["Content-Type"] = "application/json"
    if cookie:
        base["Cookie"] = cookie
    base.update(headers or {})
    client = HTTPConnection("127.0.0.1", gateway.server_port, timeout=3)
    try:
        client.request(method, path, body=body, headers=base)
        response = client.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        client.close()


def login(relay):
    status, headers, _ = request(relay, "POST", "/login", urlencode({"password": PASSWORD}),
                                  headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert status == 303 and headers["Location"] == "/"
    return headers["Set-Cookie"].split(";", 1)[0], headers


@contextmanager
def controlled_application(tmp_path, *, refusal=False, fail=False, drop_reply=False):
    """Actual auth -> backend -> ledger -> executor -> GET; no native model."""
    from functools import partial
    from gv100h.spec_qa.controlled_web.config import WebPaths
    from gv100h.spec_qa.controlled_web.session import ControlledSession
    from gv100h.spec_qa.controlled_web.server import ControlledHandler, create_backend

    assets=tmp_path/"assets"; assets.mkdir()
    for name in ["index.html","styles.css","app.js","saved-cases.js"]:
        (assets/name).write_bytes(b"synthetic reviewed UI fixture")
    paths=WebPaths(tmp_path/"ledger",assets)
    calls=[]; gate=threading.Event(); entered=threading.Event()
    def executor(question, folder, progress):
        saved=json.loads((paths.ledger/"session.json").read_text())
        assert saved["count"]==1 and saved["active_job"]==folder.name
        calls.append(question); progress("GENERATING"); entered.set()
        assert gate.wait(4)
        if fail: raise TimeoutError("private fixture timeout")
        progress("VERIFYING")
        return {"preview":False,"mode":"controlled_live","raw_model_display":"private raw fixture",
                "inspection":{"stage":"VALID_MODEL_ABSTENTION" if refusal else "CITATION_TEXT_VERIFIED"},
                "view":{"status":"abstain" if refusal else "answer","is_abstain":refusal,
                        "answer":"synthetic refusal" if refusal else "synthetic answer",
                        "boundary":"synthetic","boundary_reason":"synthetic missing evidence" if refusal else "","scope":"USB_2_0",
                        "claims":[] if refusal else ["synthetic claim"],"claim_evidence_ids":[] if refusal else [["FIXTURE-1"]],
                        "citations":[] if refusal else [{"evidence_id":"FIXTURE-1","excerpt":"Synthetic continuous fixture source."}]}}
    session=ControlledSession(paths.ledger,executor)
    backend=create_backend(session,paths,0)
    if drop_reply:
        class DropReply(ControlledHandler):
            def send(self,status,body,kind="application/json"):
                if status==202:
                    self.close_connection=True
                    return  # Request reserved, downstream reply lost: no extra dispatch.
                return super().send(status,body,kind)
        backend.RequestHandlerClass=partial(DropReply,session=session,paths=paths)
    policy=GatewayPolicy(PASSWORD,origin=ORIGIN)
    try:
        with started(backend),started(external_gateway(policy,0,upstream_port=backend.server_port)) as gateway:
            yield (gateway,backend,policy),session,calls,gate,entered,paths
    finally:
        gate.set(); session.close()


@pytest.mark.parametrize("outcome",["answer","refusal","timeout"])
def test_authenticated_job_progress_refresh_and_terminal_result(tmp_path,outcome):
    with controlled_application(tmp_path,refusal=outcome=="refusal",fail=outcome=="timeout") as app:
        relay,session,calls,gate,entered,paths=app
        one,_=login(relay); two,_=login(relay)
        value=json.dumps({"question":"USB 2.0 fixture question","request_id":"a"*32}).encode()
        assert request(relay,"POST","/api/jobs",value,cookie=one)[0]==202
        assert entered.wait(3)
        status,_,data=request(relay,"GET","/api/jobs/"+"a"*32,cookie=two)
        assert status==200 and json.loads(data)["status"]=="GENERATING"
        assert request(relay,"POST","/api/jobs",value,cookie=two)[0]==202
        other=json.dumps({"question":"competing fixture question","request_id":"b"*32}).encode()
        assert request(relay,"POST","/api/jobs",other,cookie=two)[0]==409
        assert json.loads(request(relay,"GET","/api/session",cookie=two)[2])["count"]==1
        gate.set(); session.thread.join(4); assert not session.thread.is_alive()
        status,_,data=request(relay,"GET","/api/jobs/"+"a"*32,cookie=one)
        result=json.loads(data)
        assert result["status"]==("FAILED" if outcome=="timeout" else "DONE")
        assert b"private" not in data
        if outcome!="timeout": assert result["result"]["view"]["is_abstain"]==(outcome=="refusal")
        assert calls==["USB 2.0 fixture question"]
        assert json.loads((paths.ledger/"session.json").read_text())["count"]==1
        assert request(relay,"GET","/session.json",cookie=one)[0]==404
        assert request(relay,"GET","/trusted-corpus.json",cookie=one)[0]==404


def test_unknown_browser_post_is_recovered_by_get_without_model_resend(tmp_path):
    with controlled_application(tmp_path,drop_reply=True) as app:
        relay,session,calls,gate,entered,_paths=app
        cookie,_=login(relay)
        body=json.dumps({"question":"fixture question","request_id":"a"*32}).encode()
        assert request(relay,"POST","/api/jobs",body,cookie=cookie)[0]==502
        assert entered.wait(3)
        saved=json.loads(request(relay,"GET","/api/session",cookie=cookie)[2])
        assert saved["active_job"]=="a"*32 and saved["count"]==1
        gate.set(); session.thread.join(4)
        recovered=json.loads(request(relay,"GET","/api/jobs/"+saved["active_job"],cookie=cookie)[2])
        assert recovered["status"]=="DONE" and calls==["fixture question"]


def test_explicit_paths_work_from_other_cwd_and_never_serve_private_directory(tmp_path,monkeypatch):
    from gv100h.spec_qa.controlled_web.config import WebPaths, read_secret
    assets=tmp_path/"assets"; assets.mkdir()
    for name in ["index.html","app.js","styles.css","saved-cases.js"]:
        (assets/name).write_text("fixture")
    unrelated=tmp_path/"unrelated"; unrelated.mkdir(); monkeypatch.chdir(unrelated)
    paths=WebPaths(tmp_path/"state",assets)
    assert paths.assets==assets and paths.ledger==tmp_path/"state"
    with pytest.raises(ValueError): WebPaths(assets/"private",assets)
    with pytest.raises(ValueError): WebPaths(tmp_path/"state",tmp_path/"missing-assets")
    secret=tmp_path/"secret"; secret.write_text(PASSWORD); secret.chmod(0o600)
    assert read_secret(secret)==PASSWORD
    secret.chmod(0o644)
    with pytest.raises(ValueError): read_secret(secret)
    alias=tmp_path/"alias"; alias.symlink_to(secret)
    with pytest.raises(ValueError): read_secret(alias)


def test_unauthenticated_page_redirects_and_api_cannot_reach_backend(relay):
    status, headers, _ = request(relay, "GET", "/")
    assert status == 303 and headers["Location"] == "/login"
    assert request(relay, "GET", "/api/session")[0] == 401
    assert request(relay, "POST", "/api/jobs", BODY)[0] == 401
    assert relay[1].records == [] and relay[1].reservations == 2


def test_login_page_has_no_saved_answer_or_model_controls(relay):
    status, _, body = request(relay, "GET", "/login")
    assert status == 200 and '試用登入碼'.encode() in body
    assert b'PORT_POWER' not in body and b'2 pF' not in body and b'/api/jobs' not in body
    assert PASSWORD.encode() not in body and relay[1].records == []


def test_login_policy_preserves_same_origin_browser_form_origin(relay):
    # Fetch Standard, Origin header algorithm: no-referrer makes a form POST's
    # Origin null; same-origin preserves it here and suppresses cross-site referrers.
    status, headers, _ = request(relay, "GET", "/login")
    assert status == 200 and headers["Referrer-Policy"] == "same-origin"
    assert relay[1].records == []


@pytest.mark.parametrize("origin", ["null", "", "https://evil.example", "http://usb-desk-test.trycloudflare.com"])
def test_login_with_correct_password_cannot_mint_session_from_wrong_origin(relay, origin):
    status, headers, _ = request(relay, "POST", "/login", urlencode({"password": PASSWORD}),
                                  headers={"Content-Type": "application/x-www-form-urlencoded", "Origin": origin})
    assert status == 403 and "Set-Cookie" not in headers
    assert relay[2].sessions == {} and relay[1].records == []


def test_login_cookie_and_original_asset_and_session_bytes(relay):
    cookie, headers = login(relay)
    for flag in ["__Host-spec_desk=", "Secure", "HttpOnly", "SameSite=Strict", "Path=/"]:
        assert flag in headers["Set-Cookie"]
    assert "Domain=" not in headers["Set-Cookie"]
    assert request(relay, "GET", "/app.js", cookie=cookie)[2] == b"fixture original asset bytes"
    assert request(relay, "GET", "/api/session", cookie=cookie)[2] == b'{"count":2,"remaining":4}'
    assert relay[1].reservations == 2


def test_wrong_password_and_tampered_cookie_never_forward(relay):
    status, _, body = request(relay, "POST", "/login", b"password=wrong-test-value", headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert status == 403 and b"wrong-test-value" not in body
    assert request(relay, "GET", "/api/session", cookie="__Host-spec_desk=forged")[0] == 401
    assert relay[1].records == [] and relay[1].reservations == 2


@pytest.mark.parametrize("headers", [{"Host": "evil.example"}, {"Host": "usb-desk-test.trycloudflare.com.evil.example"}, {"X-Forwarded-Proto": "http"}, {"X-Forwarded-Proto": ""}])
def test_exact_host_and_https_required_before_backend(relay, headers):
    cookie, _ = login(relay)
    assert request(relay, "GET", "/api/session", cookie=cookie, headers=headers)[0] == 403
    assert relay[1].records == []


@pytest.mark.parametrize("origin", ["https://evil.example", "null", "", "http://usb-desk-test.trycloudflare.com"])
def test_post_requires_exact_public_origin_even_with_valid_cookie(relay, origin):
    cookie, _ = login(relay)
    assert request(relay, "POST", "/api/jobs", BODY, cookie=cookie, headers={"Origin": origin})[0] == 403
    assert relay[1].records == [] and relay[1].reservations == 2


@pytest.mark.parametrize("path", ["/v1/chat/completions", "/artifacts/evidence.json", "/../PLAN.md", "/%2e%2e/PLAN.md", "/api/jobs/invalid", "/api/jobs/" + "f"*32 + "/x", "/app.js?password=never-log-this", "http://127.0.0.1:8080/v1/models"])
def test_only_exact_trial_routes_are_reachable(relay, path):
    cookie, _ = login(relay)
    assert request(relay, "GET", path, cookie=cookie)[0] in {400, 404}
    assert relay[1].records == []


def test_authenticated_post_forwards_bytes_once_and_reauthors_only_local_headers(relay):
    cookie, _ = login(relay)
    status, _, data = request(relay, "POST", "/api/jobs", BODY, cookie=cookie, headers={"Authorization": "spoof", "X-Forwarded-Host": "evil.example"})
    assert status == 202 and json.loads(data)["job_id"] == "0123456789abcdef0123456789abcdef"
    assert len(relay[1].records) == 1 and relay[1].reservations == 3
    method, path, headers, body = relay[1].records[0]
    assert (method, path, body) == ("POST", "/api/jobs", BODY)
    assert headers["Host"] == f"127.0.0.1:{relay[1].server_port}"
    assert headers["Origin"] == f"http://127.0.0.1:{relay[1].server_port}"
    assert "Cookie" not in headers and "Authorization" not in headers and "X-Forwarded-Host" not in headers


def test_uncertain_upstream_post_is_never_retried(relay):
    cookie, _ = login(relay)
    relay[1].drop_post = True
    assert request(relay, "POST", "/api/jobs", BODY, cookie=cookie)[0] == 502
    assert len(relay[1].records) == 1 and relay[1].reservations == 3


@pytest.mark.parametrize("body,headers", [(b"x"*4097, {}), (b"", {}), (BODY, {"Content-Type": "text/plain"}), (BODY, {"Transfer-Encoding": "chunked"})])
def test_body_boundaries_and_framing_fail_before_forward(relay, body, headers):
    cookie, _ = login(relay)
    assert request(relay, "POST", "/api/jobs", body, cookie=cookie, headers=headers)[0] == 400
    assert relay[1].records == [] and relay[1].reservations == 2


def test_maximum_body_size_is_forwarded_unchanged(relay):
    cookie, _ = login(relay)
    body = b"x"*4096
    assert request(relay, "POST", "/api/jobs", body, cookie=cookie)[0] == 202
    assert relay[1].records[0][3] == body


def test_expiry_boundary_denies_old_cookie_and_login(relay):
    cookie, _ = login(relay)
    policy = relay[2]
    policy.clock = lambda: policy.expires
    assert not policy.authorized(cookie)
    assert request(relay, "GET", "/api/session", cookie=cookie)[0] == 503
    assert relay[1].records == []


def test_login_rate_limit_and_recovery_without_backend(relay):
    for _ in range(12):
        assert request(relay, "POST", "/login", b"password=wrong", headers={"Content-Type": "application/x-www-form-urlencoded"})[0] == 403
    assert request(relay, "POST", "/login", b"password=wrong", headers={"Content-Type": "application/x-www-form-urlencoded"})[0] == 429
    now = relay[2].clock()
    relay[2].clock = lambda: now + 61
    login(relay)
    assert relay[1].records == []


def test_origin_file_fail_closed_then_pins_first_valid_hostname(tmp_path):
    file = tmp_path / "public-url"
    policy = GatewayPolicy(PASSWORD, file)
    assert policy.origin() is None
    file.write_text("https://attacker.example")
    assert policy.origin() is None
    file.write_text(ORIGIN)
    assert policy.origin() == ORIGIN
    file.write_text("https://changed.trycloudflare.com")
    assert policy.origin() == ORIGIN


def test_short_password_and_ambiguous_origin_are_rejected():
    with pytest.raises(ValueError):
        GatewayPolicy("short", origin=ORIGIN)
    with pytest.raises(ValueError):
        GatewayPolicy(PASSWORD, origin="https://usb-desk-test.trycloudflare.com.evil.example")
