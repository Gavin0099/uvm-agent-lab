"""Explicitly enabled loopback adapter; no generation, ledger or file routes."""
from base64 import b64decode
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import BoundedSemaphore, Lock, Timer
from urllib.parse import parse_qs, urlsplit
import hashlib
import hmac
import re
import socket

from .service import EvidenceService
from .search import SCOPES
import json

STATIC = Path(__file__).parent / 'static'
PREVIEW_STYLE = Path(__file__).resolve().parents[1] / 'operator_ui/evidence_preview_static/styles.css'

# Local preview limits, not query-quality Gates. A slow client must not hold
# the accept loop or the service's mutable lazy index / PDF cache.
MAX_CONNECTIONS = 16
HEADER_TIMEOUT_SECONDS = 5.0
IO_TIMEOUT_SECONDS = 5.0
QUERY_WAIT_SECONDS = 5.0
MIN_ACCESS_CODE_LENGTH = 16
PUBLIC_HOST_PATTERN = re.compile(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+')
REALM = 'USB Spec Desk'


def validate_public_settings(public_host, access_code):
    if public_host is None:
        return
    if not PUBLIC_HOST_PATTERN.fullmatch(public_host) or public_host in {'localhost', '127.0.0.1'}:
        raise ValueError('public_host must be a bare DNS name')
    if not access_code or len(access_code) < MIN_ACCESS_CODE_LENGTH:
        raise ValueError(f'access code must be at least {MIN_ACCESS_CODE_LENGTH} characters')


class _LocalHTTPServer(ThreadingHTTPServer):
    def __init__(self, address, handler):
        self.connection_slots = BoundedSemaphore(MAX_CONNECTIONS)
        super().__init__(address, handler)

    def process_request(self, request, client_address):
        if not self.connection_slots.acquire(blocking=False):
            # Do not parse or emit source data on an over-capacity connection.
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.connection_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.connection_slots.release()


def make_server(*, port=8769, service=None, public_host=None, access_code=None, audit_log=None):
    """Binds loopback only; public_host adds an access-code gate for an HTTPS front."""
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError('Invalid port')
    validate_public_settings(public_host, access_code)
    service = EvidenceService() if service is None else service
    service_lock = Lock()
    audit_guard = Lock()

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            self.request.settimeout(IO_TIMEOUT_SECONDS)
            super().setup()

        def handle(self):
            self._header_guard = Lock()
            self._reading_headers = True
            self._header_timer = Timer(HEADER_TIMEOUT_SECONDS, self._expire_headers)
            self._header_timer.daemon = True
            self._header_timer.start()
            try:
                # One response per connection: no unbounded keep-alive waiter.
                self.close_connection = True
                self.handle_one_request()
            except OSError:
                # Client timeout/disconnect is isolated from other requests.
                pass
            finally:
                self._finish_headers()

        def _expire_headers(self):
            with self._header_guard:
                if self._reading_headers:
                    self._reading_headers = False
                    try:
                        self.connection.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass

        def _finish_headers(self):
            with self._header_guard:
                timely = self._reading_headers
                self._reading_headers = False
                self._header_timer.cancel()
                return timely

        def parse_request(self):
            parsed = super().parse_request()
            # Cancel the absolute deadline before any query starts. If expiry
            # won the race, this connection cannot enter the source service.
            timely = self._finish_headers()
            return parsed and timely

        def log_message(self, *_args):
            pass  # Questions and source text are not persisted in access logs.

        def send(self, status, body, kind='application/json; charset=utf-8', headers=()):
            raw = json.dumps(body, ensure_ascii=False).encode() if isinstance(body, dict) else body
            self.send_response(status)
            self.send_header('Content-Type', kind)
            for name, value in headers:
                self.send_header(name, value)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Connection', 'close')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'self'; script-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(raw)

        def admitted(self):
            port = self.server.server_port
            origins = {f'127.0.0.1:{port}': f'http://127.0.0.1:{port}',
                       f'localhost:{port}': f'http://localhost:{port}'}
            if public_host is not None:
                origins[public_host] = 'https://' + public_host
            host = self.headers.get('Host', '')
            origin = self.headers.get('Origin')
            if any(len(self.headers.get_all(name) or ()) > 1 for name in ('Host', 'Origin', 'Sec-Fetch-Site')):
                return False
            return (host in origins and (origin is None or origin == origins[host])
                    and self.headers.get('Sec-Fetch-Site', 'none') in {'none', 'same-origin'})

        def authorized(self):
            if public_host is None:
                return True
            values = self.headers.get_all('Authorization') or ()
            if len(values) != 1:
                return False
            scheme, _, token = values[0].partition(' ')
            if scheme.lower() != 'basic':
                return False
            try:
                user_password = b64decode(token, validate=True).decode('utf-8')
            except (ValueError, UnicodeDecodeError):
                return False
            _, separator, password = user_password.partition(':')
            return bool(separator) and hmac.compare_digest(password.encode('utf-8'), access_code.encode('utf-8'))

        def audit(self, status, reason, question, scope):
            if audit_log is None:
                return True
            record = {'ts': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                      'client': self.client_address[0], 'status': status, 'reason': reason, 'scope': scope,
                      'question_len': None if question is None else len(question),
                      'question_sha256': None if question is None else hashlib.sha256(question.encode('utf-8')).hexdigest()}
            try:
                with audit_guard, open(audit_log, 'a', encoding='utf-8') as handle:
                    handle.write(json.dumps(record, ensure_ascii=False) + '\n')
            except (OSError, ValueError):
                self.send(503, {'status': 'error', 'reason': 'audit_unavailable', 'answer': None})
                return False
            return True

        def do_GET(self):
            if not self.admitted():
                self.send(403, {'status': 'error', 'reason': 'local_same_origin_only'})
                return
            if not self.authorized():
                self.send(401, {'status': 'error', 'reason': 'access_code_required'},
                          headers=[('WWW-Authenticate', f'Basic realm="{REALM}", charset="UTF-8"')])
                return
            if len(self.path) > 16384:
                self.send(414, {'status': 'error', 'reason': 'request_too_long'})
                return
            try:
                url = urlsplit(self.path)
            except ValueError:
                self.send(400, {'status': 'error', 'reason': 'invalid_url'})
                return
            routes = {'/': (STATIC/'index.html', 'text/html; charset=utf-8'),
                      '/app.js': (STATIC/'app.js', 'text/javascript; charset=utf-8'),
                      '/preview.css': (STATIC/'preview.css', 'text/css; charset=utf-8'),
                      '/styles.css': (PREVIEW_STYLE, 'text/css; charset=utf-8')}
            if url.path in routes and not url.query:
                path, kind = routes[url.path]
                try:
                    content = path.read_bytes()
                except OSError:
                    self.send(503, {'status': 'error', 'reason': 'preview_asset_unavailable'})
                    return
                self.send(200, content, kind)
                return
            if url.path != '/api/search':
                self.send(404, {'status': 'error', 'reason': 'route_not_found'})
                return
            question = scope = None
            try:
                params = parse_qs(url.query, keep_blank_values=True, strict_parsing=True)
                if set(params) != {'question', 'scope'} or any(len(v) != 1 for v in params.values()):
                    raise ValueError('Only question and scope are accepted')
                if params['scope'][0] not in SCOPES:
                    raise ValueError('Unknown scope')
                question, scope = params['question'][0], params['scope'][0]
                if not service_lock.acquire(timeout=QUERY_WAIT_SECONDS):
                    if self.audit(503, 'source_service_busy', question, scope):
                        self.send(503, {'status': 'error', 'reason': 'source_service_busy', 'answer': None})
                    return
                try:
                    result = service.query(question, scope=scope)
                finally:
                    service_lock.release()
            except ValueError:
                if self.audit(400, 'input_or_source_verification_failed', question, scope):
                    self.send(400, {'status': 'error', 'reason': 'input_or_source_verification_failed', 'answer': None})
                return
            except (OSError, RuntimeError, KeyError):
                if self.audit(503, 'source_service_unavailable', question, scope):
                    self.send(503, {'status': 'error', 'reason': 'source_service_unavailable', 'answer': None})
                return
            if self.audit(200, 'ok', question, scope):
                self.send(200, result)

        def do_POST(self):
            self.send(405, {'status': 'error', 'reason': 'read_only'})

        do_PUT = do_POST
        do_DELETE = do_POST
        do_OPTIONS = do_POST

    # Connection work is independent; only complete, admitted queries acquire
    # the lock. Slow request readers and response consumers never hold it.
    return _LocalHTTPServer(('127.0.0.1', port), Handler)


def serve(*, port=8769, public_host=None, access_code=None, audit_log=None):
    with make_server(port=port, public_host=public_host, access_code=access_code, audit_log=audit_log) as server:
        print(f'Evidence-only local preview: http://127.0.0.1:{server.server_port}', flush=True)
        if public_host is not None:
            print(f'Public mode: https://{public_host} (HTTPS front and access code required)', flush=True)
        try:
            server.serve_forever(poll_interval=0.25)
        except KeyboardInterrupt:
            pass
