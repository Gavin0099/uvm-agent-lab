"""Six-attempt ledger and executor boundary, independent of question profiles.

The host executor owns retrieval, native runtime, source and semantic checks.
This module enforces lifecycle and UI structure, not claim correctness.
"""
import fcntl
import json
from pathlib import Path
import re
import threading
import time

from gv100h.spec_qa.operator_ui.contract import OperatorQAView
from .storage import persist, read, private_directory, open_private

CAP = 6
ID = re.compile(r"[a-f0-9]{32}\Z")
ACTIVE = {"RESERVED", "STARTING_MODEL", "GENERATING", "VERIFYING"}


class TrialError(ValueError):
    def __init__(self, message, status=409):
        super().__init__(message)
        self.status = status


def validate_question(question):
    if not isinstance(question, str):
        raise TrialError("請輸入文字問題。", 400)
    question = question.strip()
    try:
        size = len(question.encode("utf-8"))
    except UnicodeError as exc:
        raise TrialError("問題包含無法處理的字元。", 400) from exc
    if not question or len(question) > 1000 or size > 3000:
        raise TrialError("請輸入1–1000字的問題（最多3000 UTF-8 bytes）；尚未使用額度。", 400)
    if any(ord(c) < 32 and c not in "\n\t" for c in question):
        raise TrialError("問題包含控制字元；尚未使用額度。", 400)
    if re.search(r"\busb\s*(?:3(?:\.\d+)?|4)(?![\d.])", question, re.I):
        raise TrialError("目前只提供 USB 2.0 規格；此版本沒有對應證據，尚未使用額度。", 422)
    return question


def public_result(result):
    """Project only known UI fields; raw completions/tracebacks stay private."""
    view = result["view"]
    parsed = OperatorQAView.model_validate({k: v for k, v in view.items() if k in OperatorQAView.model_fields})
    if parsed.is_abstain:
        if parsed.status != "abstain" or parsed.claims or parsed.citations or parsed.claim_evidence_ids or not parsed.boundary_reason.strip():
            raise ValueError("Refusal must contain no unsupported claims or citations.")
    else:
        ids = {c.evidence_id for c in parsed.citations}
        if (parsed.status != "answer" or not parsed.claims or not ids
                or len(ids) != len(parsed.citations) or len(parsed.claims) != len(parsed.claim_evidence_ids)
                or any(not c.strip() for c in parsed.claims)
                or any(not c.excerpt.strip() for c in parsed.citations)
                or any(not links or any(i not in ids for i in links) for links in parsed.claim_evidence_ids)):
            raise ValueError("Answer must link each claim to its supplied citations.")
    allowed = {"preview", "mode", "free_question", "label", "question", "saved_date", "elapsed_seconds", "original_response_sha256", "job_id", "refusal_summary"}
    output = {k: v for k, v in result.items() if k in allowed}
    output["view"] = parsed.model_dump(mode="json")
    output["inspection"] = {"stage": result.get("inspection", {}).get("stage")}
    return output


class ControlledSession:
    """One ledger owner, one active job, persisted reservation before execution.

    Supply the *reviewed* executor explicitly. There is no implicit model,
    imported experiment code, reset endpoint, retry or automatic recovery.
    """
    def __init__(self, directory, executor, *, question_validator=validate_question):
        self.directory = Path(directory).resolve()
        private_directory(self.directory)
        self.executor, self.question_validator = executor, question_validator
        self.process_lock = open_private(self.directory / "session.lock", "a+")
        self.lock, self.thread, self.closed = threading.Lock(), None, False
        self.path = self.directory / "session.json"
        try:
            fcntl.flock(self.process_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if self.path.exists():
                self.state = read(self.path)
                self._validate_state()
                if self.state["active_job"]:
                    key = self.state["active_job"]
                    self.state["jobs"][key].update(status="FAILED", error="服務曾中斷；未知請求仍計入額度，不補送。")
                    self.state.update(active_job=None, status="STOPPED")
                    persist(self.path, self.state)
            else:
                self.state = {"status": "READY", "count": 0, "cap": CAP, "retry": 0,
                              "active_job": None, "last_job": None, "jobs": {}}
                persist(self.path, self.state)
        except BaseException:
            self.process_lock.close()
            raise

    def _validate_state(self):
        s = self.state
        if (s.get("cap") != CAP or s.get("retry") != 0 or type(s.get("count")) is not int
                or not 0 <= s["count"] <= CAP or not isinstance(s.get("jobs"), dict)
                or s["count"] != len(s["jobs"]) or s.get("status") not in {"READY", "STOPPED"}
                or "active_job" not in s or "last_job" not in s):
            raise RuntimeError("既有額度紀錄不符；不能重建。")
        for key, job in s["jobs"].items():
            if (not isinstance(key, str) or not ID.fullmatch(key) or not isinstance(job, dict)
                    or job.get("id") != key or not isinstance(job.get("question"), str)
                    or job.get("status") not in ACTIVE | {"DONE", "FAILED"}):
                raise RuntimeError("既有工作紀錄不符；不能重建。")
        active = [k for k, v in s["jobs"].items() if v["status"] in ACTIVE]
        if (s["active_job"] is not None and s["active_job"] not in s["jobs"]
                or s["last_job"] is not None and s["last_job"] not in s["jobs"]
                or active != ([] if s["active_job"] is None else [s["active_job"]])
                or bool(s["count"]) != (s["last_job"] is not None)
                or s["count"] == CAP and not active and s["status"] != "STOPPED"):
            raise RuntimeError("既有工作與額度關聯不符；不能重建。")

    def close(self):
        with self.lock:
            self.closed = True
        if self.thread is not None:
            self.thread.join()
        self.process_lock.close()

    def summary(self):
        with self.lock:
            return {k: self.state[k] for k in ("status", "count", "cap", "retry", "active_job", "last_job")} | {"remaining": CAP - self.state["count"]}

    def job(self, key):
        with self.lock:
            if not isinstance(key, str) or not ID.fullmatch(key) or key not in self.state["jobs"]:
                raise TrialError("找不到本次請求。", 404)
            job = self.state["jobs"][key]
            value = json.loads(json.dumps({k: v for k, v in job.items() if k in {"id", "question", "status", "started_at", "result", "error"}}, allow_nan=False))
            if "result" in value:
                value["result"] = public_result(value["result"])
            return value

    def submit(self, question, key):
        if not isinstance(key, str) or not ID.fullmatch(key):
            raise TrialError("請求識別碼格式不符。", 400)
        question = self.question_validator(question)
        with self.lock:
            if self.closed:
                raise TrialError("本輪服務已關閉。")
            if key in self.state["jobs"]:
                if self.state["jobs"][key]["question"] != question:
                    raise TrialError("請求識別碼不能改用另一題。")
                return key
            if self.state["status"] != "READY" or self.state["active_job"] or self.state["count"] >= CAP:
                raise TrialError("本輪正在處理、已停止或額度已用完；沒有追加請求。")
            (self.directory / key).mkdir(mode=0o700, exist_ok=False)
            self.state["jobs"][key] = {"id": key, "question": question, "status": "RESERVED", "started_at": time.time()}
            self.state.update(count=self.state["count"] + 1, active_job=key, last_job=key)
            persist(self.path, self.state)
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
            if status not in ACTIVE:
                raise ValueError("Unknown executor progress state.")
            with self.lock:
                self.state["jobs"][key]["status"] = status
                persist(self.path, self.state)
        try:
            result = self.executor(self.state["jobs"][key]["question"], self.directory / key, progress)
            stage = result.get("inspection", {}).get("stage")
            refusal = result["view"]["is_abstain"]
            if (refusal and stage != "VALID_MODEL_ABSTENTION"
                    or not refusal and stage not in {"SOURCE_SUPPORTED_ANSWER", "CITATION_TEXT_VERIFIED"}
                    or result.get("preview") is not False or result.get("mode") != "controlled_live"):
                raise ValueError("Executor result has no accepted answer/refusal validation.")
            result.update(job_id=key, question=self.state["jobs"][key]["question"])
            public_result(result)
            persist(self.directory / key / "result.json", result)
            with self.lock:
                self.state["jobs"][key].update(status="DONE", result=result)
                self.state.update(active_job=None, status="STOPPED" if self.state["count"] >= CAP else "READY")
                persist(self.path, self.state)
        except BaseException as exc:
            persist(self.directory / key / "failure.json", {"type": type(exc).__name__, "message": str(exc), "retry": 0})
            with self.lock:
                message = "模型執行超過等待期限，未取得完整回應。" if isinstance(exc, TimeoutError) else "本次執行未通過，本輪已停止；額度已計入，沒有自動重試。"
                self.state["jobs"][key].update(status="FAILED", error=message)
                self.state.update(active_job=None, status="STOPPED")
                persist(self.path, self.state)
