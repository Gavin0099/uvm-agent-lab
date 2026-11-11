"""Durable, serial, six-attempt trial. Reuses the reviewed candidate pipeline.

Reservations precede startup/transport. No replacement request, automatic
retry or quota reset. A page refresh reads the existing job, never resends it.
"""
from __future__ import annotations

import hashlib
import fcntl
import importlib.metadata
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import threading
import time

from gv100h.spec_qa.contracts.governed_chunk import GovernedChunk
from gv100h.spec_qa.frozen_corpus.receipt_bound_corpus import ReceiptBoundCorpus, _verify_corpus_identity, chunk_identity_sha256
from gv100h.spec_qa.operator_ui.candidate_trial import CandidateTrialAdapter
from gv100h.spec_qa.operator_ui.candidate_trial_server import OneShotCapturedClient, persist, request_bytes

ROOT = Path(__file__).resolve().parents[3]
PRIOR = ROOT / "artifacts/evidence/test-results/typed-claim-b-candidate-integration-20261003"
SEALED = PRIOR.parent / "typed-claim-q005-ab-offline-prep-20261003"
READINESS = PRIOR.parent / "typed-claim-q005-live-readiness-20261003"
CAP = 6
ID = re.compile(r"^[a-f0-9]{32}$")
ACTIVE = {"RESERVED", "STARTING_MODEL", "GENERATING", "VERIFYING"}


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class TrialError(ValueError):
    def __init__(self, message, status=409):
        super().__init__(message)
        self.status = status


def verify_review(directory):
    index = directory / "pre-send-index.json"
    review = read(directory / "pre-send-review.json")
    if review["status"] != "APPROVED" or review["index_sha256"] != sha(index):
        raise RuntimeError("獨立審查未完成或已失效。")
    for name, expected in read(index)["sha256"].items():
        if sha(ROOT / name) != expected:
            raise RuntimeError("已審查的程式或輸入已改變；停止送出。")
    for name, expected in read(directory / "baseline.json")["preserved_sha256"].items():
        if sha(ROOT / name) != expected:
            raise RuntimeError("既有封存結果已改變；停止送出。")


def load_corpus():
    prep = read(PRIOR / "prepared.json")
    if sha(PRIOR / "trusted-corpus.json") != prep["trusted_corpus_sha256"]:
        raise RuntimeError("已核對的來源快照雜湊不同。")
    chunks = tuple(GovernedChunk.model_validate(c) for c in read(PRIOR / "trusted-corpus.json"))
    digest, identity = _verify_corpus_identity(chunks), chunk_identity_sha256(chunks)
    if digest != prep["corpus_sha256"] or identity != prep["chunk_identity_sha256"]:
        raise RuntimeError("來源身分不同。")
    return ReceiptBoundCorpus(chunks, digest, identity, {c.chunk_id: c for c in chunks})


def check_runtime():
    plan = read(SEALED / "runtime-plan.json")
    for name, expected in {**plan["stdlib_source_audit"], **read(READINESS / "runtime-check.json")["config_sha256"]}.items():
        if sha(name) != expected:
            raise RuntimeError("模型或 HTTP runtime 版本不同。")
    if {n: importlib.metadata.version(n) for n in plan["recorded_versions"]} != plan["recorded_versions"]:
        raise RuntimeError("套件版本不同。")
    from mlx_lm import server
    from mlx_lm.models import cache
    if sha(server.__file__) != plan["server_sha256"] or sha(cache.__file__) != plan["cache_implementation_sha256"]:
        raise RuntimeError("模型／cache 實作不同。")
    hub = Path.home() / ".cache/huggingface/hub" / ("models--" + plan["model"].replace("/", "--"))
    if (hub / "refs/main").read_text().strip() != plan["cached_hf_revision"]:
        raise RuntimeError("模型修訂版不同。")
    return plan


def endpoint_closed():
    with socket.socket() as probe:
        return probe.connect_ex(("127.0.0.1", 8080)) != 0


def close_owned(process, job):
    if process.poll() is None:
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    native = job / "runtime/closed.json"
    closed = read(native) if native.exists() else {}
    confirmed = (process.returncode == 0 and endpoint_closed() and closed.get("pid") == process.pid
                 and closed.get("counts", {}).get("network_post_attempts") == 1
                 and closed.get("counts", {}).get("generation_submissions") == 1
                 and not (job / "runtime/unexpected-post.json").exists())
    persist(job / "closure.json", {"owned_pid": process.pid, "exit_code": process.returncode, "confirmed": confirmed})
    if not confirmed:
        raise RuntimeError("模型程序關閉未確認；本輪停止。")


class OwnedExecutor:
    """One fresh owned MLX server for each job; no public inference endpoint."""
    def __init__(self, directory):
        self.directory = Path(directory)
        verify_review(self.directory)
        self.plan = check_runtime()
        self.corpus = load_corpus()
        self.profiles = CandidateTrialAdapter(self.corpus, None).profiles

    def __call__(self, question, job, progress):
        verify_review(self.directory)
        check_runtime()
        if not endpoint_closed():
            raise RuntimeError("模型連接埠已由其他程序使用；不重設或共用。")
        adapter = CandidateTrialAdapter(self.corpus, None)
        prepared = adapter.prepare(question)  # Actual retrieval and unchanged public prompt.
        phase = prepared["question_id"].replace("DRAFT-L1-", "Q")
        body = request_bytes(prepared["messages"])
        if body != (PRIOR / (phase + ".request.json")).read_bytes():
            raise RuntimeError("實際問答組裝與已核對的候選請求不同。")
        (job / (phase + ".request.json")).write_bytes(body)
        persist(job / "prepared.json", prepared)
        process = None

        def admission(actual):
            verify_review(self.directory)
            ready = read(job / "runtime/ready.json")
            if (process is None or process.poll() is not None or actual != body
                    or ready["pid"] != process.pid or ready["ppid"] != os.getpid()
                    or not ready["model_loaded"] or ready["model_key"] != [self.plan["model"], None, None]
                    or ready["cache_entries"] != 0 or ready["cache_bytes"] != 0
                    or ready["pending_generation_queue"] != 0
                    or ready["counts"]["network_post_attempts"] != 0 or ready["counts"]["generation_submissions"] != 0
                    or ready["bound_address"] != ["127.0.0.1", 8080]
                    or ready["cache_class"] != "mlx_lm.models.cache.LRUPromptCache"):
                raise RuntimeError("實際程序、來源或乾淨 cache 前提未通過。")

        command = [sys.executable, "-B", "-u", "-m", "gv100h.spec_qa.operator_ui.trial_runtime_worker", str(job), phase, "--",
                   "--model", self.plan["model"], "--host", "127.0.0.1", "--port", "8080",
                   "--prompt-cache-size", "1", "--prompt-cache-bytes", "1G", "--decode-concurrency", "1",
                   "--prompt-concurrency", "1", "--prefill-step-size", "2048"]
        try:
            progress("STARTING_MODEL")
            with (job / "server.log").open("x") as log:
                process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                    env={**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "PYTHONDONTWRITEBYTECODE": "1"})
                persist(job / "ownership.json", {"pid": process.pid, "ppid": os.getpid(), "command": command})
                deadline = time.monotonic() + 150
                while not (job / "runtime/ready.json").exists():
                    if process.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError("本次模型啟動未完成；不補送。")
                    time.sleep(.1)
                progress("GENERATING")
                client = OneShotCapturedClient(job / "transport", expected_body=body, admission_check=admission)
                raw = client.complete(prepared["messages"])
                progress("VERIFYING")
                view = adapter.present(raw, prepared).model_dump(mode="json")
                persist(job / "execution.json", adapter.last_execution)
                completion = read(job / "transport/call-1/completion.json")
                before = read(job / "runtime/before-generation.json")
                if (body != (job / "runtime/server-body.json").read_bytes()
                        or before["cache_entries"] != 0 or before["cache_bytes"] != 0
                        or before["counts"]["network_post_attempts"] != 1 or before["counts"]["generation_submissions"] != 0
                        or completion["usage"].get("prompt_tokens_details", {}).get("cached_tokens") != 0):
                    raise RuntimeError("實際傳送或 cache 紀錄不符；停止。")
                persist(job / "entry-response.json", view)
                persist(job / "runtime-receipt.json", {"body_sha256": hashlib.sha256(body).hexdigest(),
                    "cache_start": 0, "cached_tokens": 0, "model_posts": 1, "retry": 0,
                    "usage": completion["usage"], "model_elapsed_seconds": completion["elapsed_seconds"]})
        finally:
            if process is not None:
                close_owned(process, job)
        profile = adapter.profile(question)
        return {"preview": False, "mode": "controlled_live", "label": profile["label"], "question": question,
                "saved_date": time.strftime("%Y/%m/%d %H:%M:%S"), "elapsed_seconds": completion["elapsed_seconds"],
                "original_response_sha256": completion["content_sha256"], "view": view,
                "inspection": adapter.last_execution["inspection"], "raw_model_display": raw}


class TrialSession:
    def __init__(self, directory, executor):
        self.directory, self.executor = Path(directory), executor
        self.directory.mkdir(parents=True, exist_ok=True)
        self.process_lock = (self.directory / "session.lock").open("a+")
        try:
            fcntl.flock(self.process_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self.process_lock.close()
            raise RuntimeError("同一輪服務已在執行；不能重設額度或接管。") from exc
        self.path = self.directory / "session.json"
        self.lock = threading.Lock()
        self.thread = None
        if self.path.exists():
            self.state = read(self.path)
            if (self.state.get("cap") != CAP or self.state.get("retry") != 0
                    or not isinstance(self.state.get("count"), int) or not 0 <= self.state["count"] <= CAP
                    or self.state["count"] != len(self.state.get("jobs", {}))):
                raise RuntimeError("既有額度紀錄不符；不能重建。")
            if self.state["active_job"]:
                key = self.state["active_job"]
                self.state["jobs"][key].update(status="FAILED", error="服務曾中斷；未知請求仍計入額度，不補送。")
                self.state.update(active_job=None, status="STOPPED")
                persist(self.path, self.state)
        else:
            self.state = {"status": "READY", "count": 0, "cap": CAP, "retry": 0, "active_job": None, "last_job": None, "jobs": {}}
            persist(self.path, self.state)

    def close(self):
        if self.thread is not None:
            self.thread.join()
        self.process_lock.close()

    def summary(self):
        with self.lock:
            return {k: self.state[k] for k in ("status", "count", "cap", "retry", "active_job", "last_job")} | {"remaining": CAP - self.state["count"]}

    def job(self, key):
        with self.lock:
            if key not in self.state["jobs"]:
                raise TrialError("找不到本次請求。", 404)
            return json.loads(json.dumps(self.state["jobs"][key]))

    def submit(self, question, key):
        if not isinstance(key, str) or not ID.fullmatch(key):
            raise TrialError("請求識別碼格式不符。", 400)
        if not isinstance(question, str) or not any(p["question"] == question for p in self.executor.profiles):
            raise TrialError("此入口僅支援列出的兩個完整問句；未呼叫模型。", 400)
        with self.lock:
            if key in self.state["jobs"]:
                if self.state["jobs"][key]["question"] != question:
                    raise TrialError("請求識別碼不能改用另一題。")
                return key  # Existing job only; never a replacement request.
            if self.state["status"] != "READY" or self.state["active_job"] or self.state["count"] >= CAP:
                raise TrialError("本輪正在處理、已停止或額度已用完；沒有追加請求。")
            (self.directory / key).mkdir(exist_ok=False)
            self.state["jobs"][key] = {"id": key, "question": question, "status": "RESERVED", "started_at": time.time()}
            self.state.update(count=self.state["count"] + 1, active_job=key, last_job=key)
            persist(self.path, self.state)  # Durable before startup or network attempt.
            self.thread = threading.Thread(target=self._run, args=(key,), daemon=False)
            try:
                self.thread.start()
            except BaseException:
                self.state["jobs"][key].update(status="FAILED", error="背景工作未啟動；本次額度保留，不重送。")
                self.state.update(active_job=None, status="STOPPED")
                persist(self.path, self.state)
                raise
        return key

    def _run(self, key):
        def progress(status):
            with self.lock:
                self.state["jobs"][key]["status"] = status
                persist(self.path, self.state)
        try:
            result = self.executor(self.state["jobs"][key]["question"], self.directory / key, progress)
            result["job_id"] = key
            persist(self.directory / key / "result.json", result)
            stopped = result["view"]["is_abstain"]
            with self.lock:
                self.state["jobs"][key].update(status="DONE", result=result)
                self.state.update(active_job=None, status="STOPPED" if stopped or self.state["count"] >= CAP else "READY")
                persist(self.path, self.state)
        except BaseException as exc:
            persist(self.directory / key / "failure.json", {"type": type(exc).__name__, "message": str(exc), "retry": 0})
            with self.lock:
                self.state["jobs"][key].update(status="FAILED", error="本次執行未通過，本輪已停止；額度已計入，沒有自動重試。")
                self.state.update(active_job=None, status="STOPPED")
                persist(self.path, self.state)
