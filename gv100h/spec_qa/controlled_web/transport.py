"""Fixed 27B request bytes and captured one-shot loopback transport.

No native engine import/startup. The host must supply the independently checked
owned-runtime/cache admission callback; an absent callback forbids sending.
"""
import fcntl
import hashlib
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import time

from .storage import persist, read, private_directory, open_private

MODEL = "mlx-community/Qwen3.8-27B-4bit"


def request_bytes(messages):
    return json.dumps({"model": MODEL, "messages": messages, "temperature": 0,
        "max_tokens": 2048, "stream": False,
        "chat_template_kwargs": {"enable_thinking": False}}, ensure_ascii=False).encode("utf-8")



class OneShotCapturedClient:
    """No SDK, redirects or retries. Reservation survives uncertain failures.

    A saved call requires explicit local outcome review before another call.
    The candidate UI cannot advance or reset this journal.
    """
    def __init__(self, directory, *, expected_body=None, connection_factory=HTTPConnection, admission_check=None):
        self.directory = Path(directory)
        private_directory(self.directory)
        self.journal_path = self.directory / "requests.json"
        self.expected_body, self.connection_factory = expected_body, connection_factory
        self.admission_check = admission_check
        # Initialization participates in the same ownership as reservation.
        # Recheck existence *inside* the lock: a delayed initializer must not
        # overwrite a journal another client has already reserved or consumed.
        with open_private(self.directory / "transport.lock", "a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if not self.journal_path.exists():
                persist(self.journal_path, {"status": "READY", "count": 0, "cap": 3, "retry": 0, "requests": []})

    def complete(self, messages):
        with open_private(self.directory / "transport.lock", "a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return self._complete(messages)

    def _complete(self, messages):
        body = request_bytes(messages)
        if self.admission_check is None:
            raise RuntimeError("此候選預覽尚未連接已核准的模型執行環境。")
        self.admission_check(body)  # Actual owned/runtime/cache evidence required by the controller.
        if self.expected_body is not None and body != self.expected_body:
            raise RuntimeError("Prepared entry body differs from presealed request; no send")
        journal = read(self.journal_path)
        if (type(journal.get("count")) is not int or not 0 <= journal["count"] <= 3
                or journal.get("cap") != 3 or journal.get("retry") != 0
                or not isinstance(journal.get("requests"), list)
                or len(journal["requests"]) != journal["count"]):
            raise RuntimeError("Existing transport ledger differs; no reset or send")
        if journal["status"] != "READY" or journal["count"] >= 3:
            raise RuntimeError("Model budget/stop state forbids another call")
        number = journal["count"] + 1
        folder = self.directory / f"call-{number}"
        folder.mkdir(mode=0o700, exist_ok=False)
        with open_private(folder / "body.json", "xb") as stream:
            stream.write(body); stream.flush(); os.fsync(stream.fileno())
        entry = {"number": number, "body_sha256": hashlib.sha256(body).hexdigest(), "retry": 0, "status": "RESERVED"}
        journal["requests"].append(entry)
        journal.update(count=number, status="IN_FLIGHT")
        persist(self.journal_path, journal)  # Before connection or uncertain POST.
        connection = None
        started = time.monotonic()
        try:
            connection = self.connection_factory("127.0.0.1", 8080, timeout=900)
            connection.connect()
            connection.auto_open = 0  # No implicit reopen after a lost socket.
            connection.request("POST", "/v1/chat/completions", body=body,
                headers={"Content-Type": "application/json", "Content-Length": str(len(body))})
            response = connection.getresponse()
            raw = response.read()
            with open_private(folder / "raw-http.json", "xb") as stream:
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
            if response.status != 200:
                raise RuntimeError(f"HTTP status {response.status}; no redirect or resend")
            value = json.loads(raw)
            choice = value["choices"][0]
            if value["model"] != MODEL or choice["finish_reason"] != "stop":
                raise RuntimeError("Wrong returned model or incomplete generation")
            content = choice["message"]["content"]
            if not isinstance(content, str):
                raise RuntimeError("No completion string")
            receipt = {"content": content, "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
                "model": value["model"], "finish_reason": choice["finish_reason"], "usage": value.get("usage"),
                "elapsed_seconds": time.monotonic() - started, "request_number": number}
            persist(folder / "completion.json", receipt)
            entry.update(status="SAVED", completion_ref=str(folder / "completion.json"))
            journal["status"] = "AWAITING_REVIEW"
            persist(self.journal_path, journal)
            return content
        except BaseException as exc:
            entry.update(status="FAILED", error=type(exc).__name__ + ": " + str(exc))
            journal["status"] = "STOPPED_FAILURE"
            persist(self.journal_path, journal)
            raise RuntimeError("Local model request failed; attempt consumed, no retry: " + str(exc)) from exc
        finally:
            if connection is not None:
                connection.close()
