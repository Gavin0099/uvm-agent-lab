"""Transport fixtures observe body/journal effects; no MLX executions."""
import json
from pathlib import Path
import fcntl
import threading

import pytest

from gv100h.spec_qa.controlled_web.storage import read
from gv100h.spec_qa.controlled_web.transport import MODEL, OneShotCapturedClient, request_bytes

MESSAGES=[{"role":"system","content":"fixture instruction"},{"role":"user","content":"fixture 問題"}]


class Connection:
    def __init__(self, status=200, error=None, model=MODEL, finish="stop"):
        self.status,self.error,self.model,self.finish=status,error,model,finish
        self.records=[]; self.closed=False; self.auto_open=1
    def connect(self): pass
    def request(self,*args,**kwargs):
        self.records.append((args,kwargs,self.auto_open))
        if self.error: raise self.error
    def getresponse(self): return self
    def read(self):
        return json.dumps({"model":self.model,"choices":[{"finish_reason":self.finish,"message":{"content":"fixture completion"}}],"usage":{"prompt_tokens":4,"completion_tokens":2}}).encode()
    def close(self): self.closed=True


def test_actual_body_config_saved_before_one_post_and_never_replayed(tmp_path):
    connection=Connection(); observed=[]
    def factory(host,port,timeout):
        assert (host,port,timeout)==("127.0.0.1",8080,900)
        journal=read(tmp_path/"requests.json")
        assert journal["status"]=="IN_FLIGHT" and journal["count"]==1
        assert (tmp_path/"call-1/body.json").read_bytes()==request_bytes(MESSAGES)
        return connection
    client=OneShotCapturedClient(tmp_path,connection_factory=factory,admission_check=observed.append)
    assert client.complete(MESSAGES)=="fixture completion"
    body=json.loads(observed[0]); assert body=={"model":MODEL,"messages":MESSAGES,"temperature":0,"max_tokens":2048,"stream":False,"chat_template_kwargs":{"enable_thinking":False}}
    assert connection.records[0][0]==("POST","/v1/chat/completions")
    assert connection.records[0][1]["body"]==observed[0] and connection.records[0][2]==0
    assert read(tmp_path/"requests.json")["status"]=="AWAITING_REVIEW"
    assert read(tmp_path/"call-1/completion.json")["content"]=="fixture completion"
    with pytest.raises(RuntimeError): client.complete(MESSAGES)
    assert len(connection.records)==1 and connection.closed


@pytest.mark.parametrize("kind", ["timeout","disconnect","redirect","truncated","wrong_model"])
def test_failed_or_uncertain_response_counts_once_and_stops(tmp_path,kind):
    connection=Connection(status=302 if kind=="redirect" else 200,
                          error=TimeoutError("fixture") if kind=="timeout" else ConnectionResetError("fixture") if kind=="disconnect" else None,
                          finish="length" if kind=="truncated" else "stop",model="wrong" if kind=="wrong_model" else MODEL)
    client=OneShotCapturedClient(tmp_path,connection_factory=lambda *_a,**_k:connection,admission_check=lambda _b:None)
    with pytest.raises(RuntimeError): client.complete(MESSAGES)
    assert read(tmp_path/"requests.json")["status"]=="STOPPED_FAILURE"
    assert read(tmp_path/"requests.json")["count"]==1
    with pytest.raises(RuntimeError): client.complete(MESSAGES)
    assert len(connection.records)==1 and connection.closed
    assert not (tmp_path/"call-2").exists()


@pytest.mark.parametrize("failure", ["missing_admission","failed_admission","body_drift"])
def test_unmet_execution_precondition_has_no_connection_or_reservation(tmp_path,failure):
    calls=[]
    def rejected(_body): raise RuntimeError("fixture admission rejected")
    callback=None if failure=="missing_admission" else rejected if failure=="failed_admission" else lambda _b:None
    client=OneShotCapturedClient(tmp_path,admission_check=callback,expected_body=b"wrong" if failure=="body_drift" else None,
                                connection_factory=lambda *_a,**_k:calls.append(1))
    with pytest.raises(RuntimeError): client.complete(MESSAGES)
    assert not calls and read(tmp_path/"requests.json")["count"]==0


def test_second_client_cannot_reopen_consumed_journal(tmp_path):
    connection=Connection(error=TimeoutError("fixture uncertain"))
    first=OneShotCapturedClient(tmp_path,connection_factory=lambda *_a,**_k:connection,admission_check=lambda _b:None)
    with pytest.raises(RuntimeError): first.complete(MESSAGES)
    calls=[]
    second=OneShotCapturedClient(tmp_path,connection_factory=lambda *_a,**_k:calls.append(1),admission_check=lambda _b:None)
    with pytest.raises(RuntimeError): second.complete(MESSAGES)
    assert read(tmp_path/"requests.json")["count"]==1 and not calls


def test_initialization_cannot_overwrite_a_concurrently_consumed_journal(tmp_path,monkeypatch):
    import gv100h.spec_qa.controlled_web.transport as module
    original=module.persist
    init_entered,release_init,other_ready=threading.Event(),threading.Event(),threading.Event()
    errors=[]; posted=[]
    def delayed(path,value):
        if threading.current_thread().name=="delayed-init" and value.get("count")==0:
            init_entered.set()
            assert release_init.wait(4)
        original(path,value)
    monkeypatch.setattr(module,"persist",delayed)
    def first():
        try: OneShotCapturedClient(tmp_path)
        except BaseException as error: errors.append(error)
    def second():
        try:
            connection=Connection()
            client=OneShotCapturedClient(tmp_path,connection_factory=lambda *_a,**_k:connection,admission_check=lambda _b:None)
            client.complete(MESSAGES); posted.extend(connection.records)
        except BaseException as error: errors.append(error)
        finally: other_ready.set()
    a=threading.Thread(target=first,name="delayed-init"); b=threading.Thread(target=second,name="other-client")
    a.start(); assert init_entered.wait(3)
    # Observe ownership rather than depend on thread scheduling/a short sleep.
    with (tmp_path/"transport.lock").open("a+") as probe:
        try:
            fcntl.flock(probe,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: initialization_owned=True
        else:
            initialization_owned=False
            fcntl.flock(probe,fcntl.LOCK_UN)
    b.start()
    try:
        if not initialization_owned:
            assert other_ready.wait(3)  # Deterministically complete before stale write.
    finally:
        release_init.set(); a.join(4); b.join(4)
    assert not a.is_alive() and not b.is_alive() and not errors
    assert len(posted)==1
    journal=read(tmp_path/"requests.json")
    assert journal["count"]==1 and journal["status"]=="AWAITING_REVIEW" and len(journal["requests"])==1
    assert read(tmp_path/"call-1/completion.json")["content"]=="fixture completion"
