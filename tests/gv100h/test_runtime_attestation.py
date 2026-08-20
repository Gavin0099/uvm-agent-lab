import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

from agent.runners.openai_compatible_runner import OpenAICompatibleLLMRunner
from scripts.run_single_ab_pair import _parse_runtime_command_json
from gv100h.runtime.attestation import (
    finalize_attestation,
    load_attestation_seed,
    RuntimeProcessAttestor,
    sha256_file,
)


def _seed(tmp_path: Path) -> tuple[Path, Path, str]:
    model = tmp_path / "model.gguf"
    model.write_bytes(b"exact-model-bytes")
    model_hash = sha256_file(model)
    executable = Path(sys.executable).resolve()
    seed = {
        "schema_version": "1",
        "runtime": "llama.cpp",
        "runtime_commit": "a" * 40,
        "runtime_version": "llama.cpp test",
        "runtime_executable_path": str(executable),
        "runtime_executable_sha256": sha256_file(executable),
        "server_pid": os.getpid(),
        "launch_argv": ["llama-server", "-m", str(model)],
        "model_id": "Qwen/Qwen3.8-27B",
        "model_path": str(model),
        "model_sha256": model_hash,
        "endpoint_url": "http://127.0.0.1:8000/v1",
        "started_at": "2026-08-20T00:00:00Z",
    }
    seed_path = tmp_path / "runtime_attestation_seed.json"
    seed_path.write_text(json.dumps(seed), encoding="utf-8")
    return seed_path, model, model_hash


def test_cli_runtime_command_json_accepts_non_empty_string_array():
    assert _parse_runtime_command_json('["llama-server", "--model", "model.gguf"]') == [
        "llama-server",
        "--model",
        "model.gguf",
    ]


@pytest.mark.parametrize("value", ['"llama-server"', "{}", "[]", '[""]', "not-json"])
def test_cli_runtime_command_json_rejects_invalid_shape(value):
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_runtime_command_json(value)


def test_attestation_seed_binds_artifact_and_executable(tmp_path):
    seed_path, model, model_hash = _seed(tmp_path)

    seed = load_attestation_seed(
        seed_path,
        expected_runtime="llama.cpp",
        expected_runtime_commit="a" * 40,
        expected_model_id="Qwen/Qwen3.8-27B",
        expected_model_hash=model_hash,
        expected_model_path=model,
        expected_endpoint_url="http://127.0.0.1:8000/v1",
    )

    final = finalize_attestation(
        seed,
        endpoint_url="http://127.0.0.1:8000/v1",
        models_endpoint_response={"data": [{"id": "Qwen/Qwen3.8-27B"}]},
        response_model="Qwen/Qwen3.8-27B",
        observed_at="2026-08-20T00:00:01Z",
    )

    assert final["model_sha256"] == model_hash
    assert final["response_model"] == "Qwen/Qwen3.8-27B"


def test_attestation_rejects_model_hash_mismatch(tmp_path):
    seed_path, model, _model_hash = _seed(tmp_path)

    with pytest.raises(ValueError, match="model hash"):
        load_attestation_seed(
            seed_path,
            expected_runtime="llama.cpp",
            expected_runtime_commit="a" * 40,
            expected_model_id="Qwen/Qwen3.8-27B",
            expected_model_hash="0" * 64,
            expected_model_path=model,
            expected_endpoint_url="http://127.0.0.1:8000/v1",
        )


def test_attestation_rejects_endpoint_model_mismatch(tmp_path):
    seed_path, model, model_hash = _seed(tmp_path)
    seed = load_attestation_seed(
        seed_path,
        expected_runtime="llama.cpp",
        expected_runtime_commit="a" * 40,
        expected_model_id="Qwen/Qwen3.8-27B",
        expected_model_hash=model_hash,
        expected_model_path=model,
        expected_endpoint_url="http://127.0.0.1:8000/v1",
    )

    with pytest.raises(ValueError, match="does not expose"):
        finalize_attestation(
            seed,
            endpoint_url="http://127.0.0.1:8000/v1",
            models_endpoint_response={"data": [{"id": "wrong-model"}]},
            response_model="wrong-model",
            observed_at="2026-08-20T00:00:01Z",
        )


def test_attestation_rejects_endpoint_mismatch(tmp_path):
    seed_path, model, model_hash = _seed(tmp_path)

    with pytest.raises(ValueError, match="endpoint_url"):
        load_attestation_seed(
            seed_path,
            expected_runtime="llama.cpp",
            expected_runtime_commit="a" * 40,
            expected_model_id="Qwen/Qwen3.8-27B",
            expected_model_hash=model_hash,
            expected_model_path=model,
            expected_endpoint_url="http://127.0.0.1:9000/v1",
        )


def test_finalize_attestation_rejects_observed_endpoint_mismatch(tmp_path):
    seed_path, model, model_hash = _seed(tmp_path)
    seed = load_attestation_seed(
        seed_path,
        expected_runtime="llama.cpp",
        expected_runtime_commit="a" * 40,
        expected_model_id="Qwen/Qwen3.8-27B",
        expected_model_hash=model_hash,
        expected_model_path=model,
        expected_endpoint_url="http://127.0.0.1:8000/v1",
    )

    with pytest.raises(ValueError, match="endpoint_url"):
        finalize_attestation(
            seed,
            endpoint_url="http://127.0.0.1:9000/v1",
            models_endpoint_response={"data": [{"id": "Qwen/Qwen3.8-27B"}]},
            response_model="Qwen/Qwen3.8-27B",
            observed_at="2026-08-20T00:00:01Z",
        )


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_runner_rejects_endpoint_models_without_requested_model(monkeypatch):
    def fake_urlopen(request, timeout):
        return _Response({"data": [{"id": "wrong-model"}]})

    monkeypatch.setattr("agent.runners.openai_compatible_runner.urllib.request.urlopen", fake_urlopen)
    runner = OpenAICompatibleLLMRunner(
        model_id="Qwen/Qwen3.8-27B",
        mock_mode=False,
    )

    with pytest.raises(ConnectionError, match="ENDPOINT_MODEL_MISMATCH"):
        runner._call_llm_api([])


def test_runner_rejects_chat_response_for_different_model(monkeypatch):
    def fake_urlopen(request, timeout):
        if request.full_url.endswith("/models"):
            return _Response({"data": [{"id": "Qwen/Qwen3.8-27B"}]})
        return _Response({
            "model": "wrong-model",
            "choices": [{"message": {"content": "answer"}}],
            "usage": {},
        })

    monkeypatch.setattr("agent.runners.openai_compatible_runner.urllib.request.urlopen", fake_urlopen)
    runner = OpenAICompatibleLLMRunner(
        model_id="Qwen/Qwen3.8-27B",
        mock_mode=False,
    )

    with pytest.raises(ConnectionError, match="ENDPOINT_MODEL_MISMATCH"):
        runner._call_llm_api([])


def test_runtime_process_attestor_stops_after_startup_failure(tmp_path, monkeypatch):
    model = tmp_path / "model.gguf"
    model.write_bytes(b"exact-model-bytes")

    class _FakeProcess:
        pid = 12345

        def __init__(self):
            self.returncode = None
            self.terminated = False

        def poll(self):
            return self.returncode

        def terminate(self):
            self.terminated = True
            self.returncode = -15

        def wait(self, timeout):
            return self.returncode

        def kill(self):
            self.returncode = -9

    process = _FakeProcess()
    monkeypatch.setattr(
        "gv100h.runtime.attestation.subprocess.Popen",
        lambda *args, **kwargs: process,
    )
    attestor = RuntimeProcessAttestor(
        [sys.executable],
        runtime="llama.cpp",
        runtime_commit="a" * 40,
        runtime_version="llama.cpp test",
        model_id="Qwen/Qwen3.8-27B",
        model_path=model,
        endpoint_url="http://127.0.0.1:8000/v1",
        startup_timeout_sec=1,
    )
    responses = iter([OSError("endpoint unavailable"), {"data": []}])

    def next_response():
        response = next(responses)
        if isinstance(response, BaseException):
            raise response
        return response

    monkeypatch.setattr(attestor, "_endpoint_models", next_response)
    clock = iter([0.0, 0.0, 2.0])
    monkeypatch.setattr("gv100h.runtime.attestation.time.monotonic", lambda: next(clock))
    monkeypatch.setattr("gv100h.runtime.attestation.time.sleep", lambda _seconds: None)

    with pytest.raises(TimeoutError):
        attestor.start()

    assert process.terminated is True


def test_runtime_process_attestor_stop_does_not_raise_cleanup_error():
    class _UnstoppableProcess:
        def poll(self):
            return None

        def terminate(self):
            raise OSError("terminate failed")

    attestor = RuntimeProcessAttestor(
        [sys.executable],
        runtime="llama.cpp",
        runtime_commit="a" * 40,
        runtime_version="llama.cpp test",
        model_id="Qwen/Qwen3.8-27B",
        model_path=Path(sys.executable),
        endpoint_url="http://127.0.0.1:8000/v1",
    )
    attestor.process = _UnstoppableProcess()

    attestor.stop()


def test_runtime_process_attestor_captures_started_process(tmp_path, monkeypatch):
    model = tmp_path / "model.gguf"
    model.write_bytes(b"exact-model-bytes")

    class _FakeProcess:
        pid = 12345
        returncode = None

        def poll(self):
            return None

        def terminate(self):
            self.returncode = -15

        def wait(self, timeout):
            return self.returncode

    process = _FakeProcess()
    monkeypatch.setattr(
        "gv100h.runtime.attestation.subprocess.Popen",
        lambda *args, **kwargs: process,
    )
    attestor = RuntimeProcessAttestor(
        [sys.executable],
        runtime="llama.cpp",
        runtime_commit="a" * 40,
        runtime_version="llama.cpp test",
        model_id="Qwen/Qwen3.8-27B",
        model_path=model,
        endpoint_url="http://127.0.0.1:8000/v1",
    )
    responses = iter([
        OSError("endpoint unavailable"),
        {"data": [{"id": "Qwen/Qwen3.8-27B"}]},
    ])

    def next_response():
        response = next(responses)
        if isinstance(response, BaseException):
            raise response
        return response

    monkeypatch.setattr(attestor, "_endpoint_models", next_response)

    seed = attestor.start()

    assert seed["server_pid"] == 12345
    assert seed["launch_argv"] == [sys.executable]
    assert seed["model_sha256"] == "76e2328f2eedf89c41124f02a920851ef8d6f7dbbec2fb3a7573f062a557e44a"
    assert seed["models_endpoint_response"] == {"data": [{"id": "Qwen/Qwen3.8-27B"}]}
    attestor.stop()


def test_runtime_process_attestor_rejects_existing_endpoint(tmp_path, monkeypatch):
    model = tmp_path / "model.gguf"
    model.write_bytes(b"exact-model-bytes")
    attestor = RuntimeProcessAttestor(
        [sys.executable],
        runtime="llama.cpp",
        runtime_commit="a" * 40,
        runtime_version="llama.cpp test",
        model_id="Qwen/Qwen3.8-27B",
        model_path=model,
        endpoint_url="http://127.0.0.1:8000/v1",
    )
    monkeypatch.setattr(
        attestor,
        "_endpoint_models",
        lambda: {"data": [{"id": "Qwen/Qwen3.8-27B"}]},
    )
    monkeypatch.setattr(
        "gv100h.runtime.attestation.subprocess.Popen",
        lambda *args, **kwargs: pytest.fail("existing endpoint must block launch"),
    )

    with pytest.raises(RuntimeError, match="already available"):
        attestor.start()


def test_runtime_process_attestor_rejects_early_exit(tmp_path, monkeypatch):
    model = tmp_path / "model.gguf"
    model.write_bytes(b"exact-model-bytes")

    class _ExitedProcess:
        pid = 12345
        returncode = 7

        def poll(self):
            return self.returncode

    monkeypatch.setattr(
        "gv100h.runtime.attestation.subprocess.Popen",
        lambda *args, **kwargs: _ExitedProcess(),
    )
    attestor = RuntimeProcessAttestor(
        [sys.executable],
        runtime="llama.cpp",
        runtime_commit="a" * 40,
        runtime_version="llama.cpp test",
        model_id="Qwen/Qwen3.8-27B",
        model_path=model,
        endpoint_url="http://127.0.0.1:8000/v1",
    )
    def endpoint_unavailable():
        raise OSError("endpoint unavailable")

    monkeypatch.setattr(attestor, "_endpoint_models", endpoint_unavailable)

    with pytest.raises(RuntimeError, match="exited before endpoint"):
        attestor.start()
