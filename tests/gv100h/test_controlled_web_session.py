"""Synthetic lifecycle fixtures, not model/citation-semantic qualification."""
import copy
import json
import os
import stat
import threading

import pytest

from gv100h.spec_qa.controlled_web.session import CAP, ControlledSession, TrialError
from gv100h.spec_qa.controlled_web.storage import persist, read


def fixture_result(refusal=False):
    return {"preview": False, "mode": "controlled_live", "label": "Synthetic only",
            "raw_model_display": "private completion", "inspection": {"stage": "VALID_MODEL_ABSTENTION" if refusal else "CITATION_TEXT_VERIFIED", "private": "trace"},
            "view": {"status": "abstain" if refusal else "answer", "answer": "fixture refusal" if refusal else "fixture answer",
                     "is_abstain": refusal, "boundary": "synthetic", "boundary_reason": "fixture evidence missing" if refusal else "",
                     "scope": "USB_2_0", "claim_ceiling": "Fixture only; no semantic proof",
                     "claims": [] if refusal else ["fixture claim"], "claim_evidence_ids": [] if refusal else [["FIXTURE-1"]],
                     "citations": [] if refusal else [{"evidence_id": "FIXTURE-1", "excerpt": "Synthetic continuous fixture source."}]}}


class FixtureExecutor:
    def __init__(self, *, result=None, error=None, blocking=False):
        self.result = fixture_result() if result is None else result
        self.error, self.calls = error, []
        self.gate, self.entered = threading.Event(), threading.Event()
        if not blocking:
            self.gate.set()

    def __call__(self, question, directory, progress):
        saved = read(directory.parent / "session.json")
        assert saved["count"] == len(saved["jobs"]) and saved["active_job"] == directory.name
        self.calls.append(question)
        progress("STARTING_MODEL")
        progress("GENERATING")
        self.entered.set()
        assert self.gate.wait(4)
        if self.error:
            raise self.error
        progress("VERIFYING")
        return copy.deepcopy(self.result)


def finish(session):
    session.thread.join(5)
    assert not session.thread.is_alive()


@pytest.mark.parametrize("question,key,status", [(None,"a"*32,400), ("","a"*32,400), ("x"*1001,"a"*32,400),
    ("😀"*751,"a"*32,400), ("bad\x01","a"*32,400), ("USB 3.2 question","a"*32,422),
    ("USB4 question","a"*32,422), ("valid", "../x",400), ("valid",None,400)])
def test_invalid_inputs_do_not_reserve_or_execute(tmp_path, question, key, status):
    executor = FixtureExecutor(); session = ControlledSession(tmp_path, executor)
    try:
        with pytest.raises(TrialError) as failure:
            session.submit(question, key)
        assert failure.value.status == status
        assert read(tmp_path/"session.json")["count"] == 0 and not executor.calls
    finally:
        session.close()


def test_active_job_idempotence_and_competing_user_preserve_single_dispatch(tmp_path):
    executor = FixtureExecutor(blocking=True); session = ControlledSession(tmp_path, executor)
    try:
        assert session.submit("USB 2.0 fixture question", "a"*32) == "a"*32
        assert executor.entered.wait(3)
        assert session.job("a"*32)["status"] == "GENERATING"
        assert session.submit("USB 2.0 fixture question", "a"*32) == "a"*32
        for q, key in [("another question","a"*32),("same question","b"*32)]:
            with pytest.raises(TrialError): session.submit(q,key)
        executor.gate.set(); finish(session)
        assert session.job("a"*32)["status"] == "DONE"
        assert session.summary()["count"] == 1 and len(executor.calls) == 1
        public = session.job("a"*32)
        assert "private completion" not in json.dumps(public) and "trace" not in json.dumps(public)
        assert read(tmp_path/("a"*32)/"result.json")["raw_model_display"] == "private completion"
    finally:
        executor.gate.set(); session.close()


def test_six_shared_reservations_survive_restart_and_no_seventh_execution(tmp_path):
    executor = FixtureExecutor(); session = ControlledSession(tmp_path, executor)
    for n in range(CAP):
        session.submit("fixture", f"{n:032x}"); finish(session)
    expected = session.summary(); session.close()
    session = ControlledSession(tmp_path, executor)
    try:
        assert session.summary() == expected and expected["remaining"] == 0 and expected["status"] == "STOPPED"
        assert session.submit("fixture", f"{0:032x}") == f"{0:032x}"
        with pytest.raises(TrialError): session.submit("fixture","f"*32)
        assert len(executor.calls) == 6
    finally: session.close()


def test_valid_refusal_completes_and_next_distinct_question_remains_available(tmp_path):
    executor = FixtureExecutor(result=fixture_result(True)); session = ControlledSession(tmp_path,executor)
    try:
        session.submit("fixture","a"*32); finish(session)
        result = session.job("a"*32)
        assert result["status"] == "DONE" and result["result"]["view"]["is_abstain"]
        assert session.summary()["status"] == "READY" and session.summary()["count"] == 1
        executor.result = fixture_result(); session.submit("second fixture","b"*32); finish(session)
        assert session.summary()["count"] == 2
    finally: session.close()


@pytest.mark.parametrize("error", [TimeoutError("private timeout"), RuntimeError("private model error")])
def test_uncertain_error_stops_and_consumes_without_resend(tmp_path,error):
    executor=FixtureExecutor(error=error); session=ControlledSession(tmp_path,executor)
    session.submit("fixture","a"*32); finish(session)
    assert session.job("a"*32)["status"] == "FAILED"
    assert "private" not in json.dumps(session.job("a"*32))
    assert session.summary()["status"] == "STOPPED" and session.summary()["remaining"] == 5
    assert read(tmp_path/("a"*32)/"failure.json")["message"] == str(error)
    session.close(); session=ControlledSession(tmp_path,executor)
    try:
        assert session.submit("fixture","a"*32) == "a"*32
        with pytest.raises(TrialError): session.submit("fixture","b"*32)
        assert executor.calls == ["fixture"]
    finally: session.close()


@pytest.mark.parametrize("mutation", ["rejected", "missing_quote", "missing_links", "refusal_with_claim"])
def test_unaccepted_answer_never_exposed_as_done(tmp_path,mutation):
    result=fixture_result(mutation=="refusal_with_claim")
    if mutation=="rejected": result["inspection"]["stage"]="REJECTED_ANSWER"
    if mutation=="missing_quote": result["view"]["citations"][0]["excerpt"]=""
    if mutation=="missing_links": result["view"]["claim_evidence_ids"]=[[]]
    if mutation=="refusal_with_claim": result["view"]["claims"]=["unsupported"]
    executor=FixtureExecutor(result=result); session=ControlledSession(tmp_path,executor)
    try:
        session.submit("fixture","a"*32); finish(session)
        assert session.job("a"*32)["status"] == "FAILED" and "result" not in session.job("a"*32)
        assert session.summary()["remaining"] == 5 and session.summary()["status"] == "STOPPED"
    finally: session.close()


def test_interrupted_active_job_restart_is_failed_without_dispatch(tmp_path):
    executor=FixtureExecutor(); session=ControlledSession(tmp_path,executor)
    state=copy.deepcopy(session.state); session.close()
    state.update(count=1,active_job="a"*32,last_job="a"*32)
    state["jobs"]["a"*32]={"id":"a"*32,"question":"fixture","status":"GENERATING"}
    persist(tmp_path/"session.json",state)
    session=ControlledSession(tmp_path,executor)
    try:
        assert session.job("a"*32)["status"] == "FAILED"
        assert session.summary()["remaining"] == 5 and session.summary()["status"] == "STOPPED"
        assert not executor.calls
    finally: session.close()


def test_exclusive_owner_and_closed_session_cannot_execute(tmp_path):
    executor=FixtureExecutor(); session=ControlledSession(tmp_path,executor)
    with pytest.raises(BlockingIOError): ControlledSession(tmp_path,executor)
    session.close()
    with pytest.raises(TrialError): session.submit("fixture","a"*32)
    assert not executor.calls


@pytest.mark.parametrize("change", [{"count":True},{"cap":7},{"retry":1},{"count":1},{"active_job":"a"*32},{"last_job":"a"*32}])
def test_corrupt_ledger_is_not_reset_and_failed_init_releases_lock(tmp_path,change):
    executor=FixtureExecutor(); session=ControlledSession(tmp_path,executor); original=copy.deepcopy(session.state); session.close()
    invalid=copy.deepcopy(original); invalid.update(change); persist(tmp_path/"session.json",invalid)
    with pytest.raises(RuntimeError): ControlledSession(tmp_path,executor)
    assert read(tmp_path/"session.json") == invalid and not executor.calls
    persist(tmp_path/"session.json",original)
    session=ControlledSession(tmp_path,executor); session.close()


def test_public_projection_omits_unvalidated_typed_extras_but_retains_internal(tmp_path):
    result=fixture_result()
    result["view"]["typed_claims"]={"claims":[{"value":{"raw_model_content":"private typed trace"}}],"private_trace":"private nested trace"}
    executor=FixtureExecutor(result=result); session=ControlledSession(tmp_path,executor)
    try:
        session.submit("fixture","a"*32); finish(session)
        public=session.job("a"*32)["result"]
        assert "typed_claims" not in public["view"] and "private" not in json.dumps(public)
        assert public["view"]["claims"]==["fixture claim"] and public["view"]["claim_evidence_ids"]==[["FIXTURE-1"]]
        saved=read(tmp_path/("a"*32)/"result.json")
        assert saved["view"]["typed_claims"]==result["view"]["typed_claims"]
    finally: session.close()


def test_new_ledger_job_and_raw_records_are_private_under_public_umask(tmp_path):
    old=os.umask(0o022)
    session=None
    try:
        ledger=tmp_path/"new-ledger"; session=ControlledSession(ledger,FixtureExecutor())
        session.submit("fixture","a"*32); finish(session)
        for path in (ledger,ledger/("a"*32)):
            assert stat.S_IMODE(path.stat().st_mode)==0o700
        for path in (ledger/"session.json",ledger/("a"*32)/"result.json"):
            assert stat.S_IMODE(path.stat().st_mode)==0o600
    finally:
        if session is not None: session.close()
        os.umask(old)


def test_unsafe_existing_ledger_is_rejected_without_chmod_or_reset(tmp_path):
    ledger=tmp_path/"shared"; ledger.mkdir(mode=0o755); ledger.chmod(0o755)
    original=b'{"private":"preserved original"}\n'; (ledger/"session.json").write_bytes(original)
    with pytest.raises(ValueError,match="0700"):
        ControlledSession(ledger,FixtureExecutor())
    assert (ledger/"session.json").read_bytes()==original
    assert stat.S_IMODE(ledger.stat().st_mode)==0o755
