from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field


class RuntimeAttestation(BaseModel):
    """Launcher-produced runtime identity plus endpoint identity observation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1"
    runtime: str
    runtime_commit: str
    runtime_version: str
    runtime_executable_path: str
    runtime_executable_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    server_pid: int = Field(gt=0)
    launch_argv: List[str] = Field(min_length=1)
    model_id: str
    model_path: str
    model_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    endpoint_url: str
    models_endpoint_response: Optional[Dict[str, Any]] = None
    response_model: Optional[str] = None
    started_at: str
    observed_at: Optional[str] = None


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    file_path = Path(path).resolve()
    if not file_path.is_file():
        raise ValueError(f"attestation file does not exist: {file_path}")
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_attestation_seed(
    path: str | Path,
    *,
    expected_runtime: str,
    expected_runtime_commit: str,
    expected_model_id: str,
    expected_model_hash: str,
    expected_model_path: str | Path,
    expected_endpoint_url: str,
) -> Dict[str, Any]:
    seed_path = Path(path).resolve()
    try:
        raw = json.loads(seed_path.read_text(encoding="utf-8"))
        attestation = RuntimeAttestation.model_validate(raw)
    except Exception as exc:
        raise ValueError(f"invalid runtime attestation seed: {exc}") from exc

    if attestation.runtime != expected_runtime:
        raise ValueError("runtime attestation runtime does not match requested runtime")
    if attestation.runtime_commit != expected_runtime_commit:
        raise ValueError("runtime attestation commit does not match requested runtime commit")
    if attestation.model_id != expected_model_id:
        raise ValueError("runtime attestation model_id does not match requested model")
    if attestation.endpoint_url.rstrip("/") != expected_endpoint_url.rstrip("/"):
        raise ValueError("runtime attestation endpoint_url does not match requested endpoint")
    if attestation.model_sha256.lower() != expected_model_hash.lower():
        raise ValueError("runtime attestation model hash does not match requested model hash")

    expected_path = Path(expected_model_path).resolve()
    if Path(attestation.model_path).resolve() != expected_path:
        raise ValueError("runtime attestation model path does not match requested artifact")
    if sha256_file(expected_path).lower() != expected_model_hash.lower():
        raise ValueError("requested model artifact hash does not match artifact bytes")
    if sha256_file(attestation.runtime_executable_path).lower() != attestation.runtime_executable_sha256.lower():
        raise ValueError("runtime executable hash does not match executable bytes")

    return attestation.model_dump()


def finalize_attestation(
    seed: Dict[str, Any],
    *,
    endpoint_url: str,
    models_endpoint_response: Dict[str, Any],
    response_model: str,
    observed_at: str,
) -> Dict[str, Any]:
    if seed["endpoint_url"].rstrip("/") != endpoint_url.rstrip("/"):
        raise ValueError("runtime attestation endpoint_url does not match observed endpoint")
    models = models_endpoint_response.get("data", [])
    model_ids = {item.get("id") for item in models if isinstance(item, dict)}
    if seed["model_id"] not in model_ids:
        raise ValueError("runtime endpoint /models does not expose the attested model")
    if response_model != seed["model_id"]:
        raise ValueError("runtime chat response model does not match the attested model")

    final = dict(seed)
    final.update(
        {
            "endpoint_url": endpoint_url,
            "models_endpoint_response": models_endpoint_response,
            "response_model": response_model,
            "observed_at": observed_at,
        }
    )
    RuntimeAttestation.model_validate(final)
    return final


class RuntimeProcessAttestor:
    """Launch a runtime and capture process/executable/model provenance."""

    def __init__(
        self,
        command: Sequence[str],
        *,
        runtime: str,
        runtime_commit: str,
        runtime_version: str,
        model_id: str,
        model_path: str | Path,
        endpoint_url: str,
        cwd: str | Path | None = None,
        startup_timeout_sec: int = 60,
    ):
        self.command = [str(item) for item in command]
        self.runtime = runtime
        self.runtime_commit = runtime_commit
        self.runtime_version = runtime_version
        self.model_id = model_id
        self.model_path = Path(model_path).resolve()
        self.endpoint_url = endpoint_url.rstrip("/")
        self.cwd = Path(cwd).resolve() if cwd else None
        self.startup_timeout_sec = startup_timeout_sec
        self.process: Optional[subprocess.Popen] = None

    def _endpoint_models(self) -> Dict[str, Any]:
        request = urllib.request.Request(f"{self.endpoint_url}/models", method="GET")
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    def start(self) -> Dict[str, Any]:
        if not self.command:
            raise ValueError("runtime command must not be empty")
        executable = shutil.which(self.command[0]) or str(Path(self.command[0]).resolve())
        executable_path = Path(executable).resolve()
        if not executable_path.is_file():
            raise ValueError(f"runtime executable does not exist: {executable_path}")
        if not self.model_path.is_file():
            raise ValueError(f"model artifact does not exist: {self.model_path}")
        if not self.runtime_commit or not self.runtime_version:
            raise ValueError("runtime commit and version are required for attestation")

        try:
            self._endpoint_models()
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                "runtime endpoint responded before harness launch"
            ) from exc
        except (OSError, urllib.error.URLError):
            pass
        except ValueError as exc:
            raise RuntimeError(
                "runtime endpoint returned invalid preflight data"
            ) from exc
        else:
            raise RuntimeError("runtime endpoint is already available before harness launch")

        self.process = subprocess.Popen(
            self.command,
            cwd=str(self.cwd) if self.cwd else None,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.monotonic() + self.startup_timeout_sec
            models_data = None
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise RuntimeError(
                        f"runtime exited before endpoint became ready: {self.process.returncode}"
                    )
                try:
                    models_data = self._endpoint_models()
                    model_ids = {
                        item.get("id")
                        for item in models_data.get("data", [])
                        if isinstance(item, dict)
                    }
                    if self.model_id in model_ids:
                        break
                except (OSError, ValueError, urllib.error.URLError):
                    pass
                if self.process.poll() is not None:
                    raise RuntimeError(
                        f"runtime exited before endpoint became ready: {self.process.returncode}"
                    )
                time.sleep(0.25)
            else:
                raise TimeoutError("runtime endpoint did not expose the attested model")

            if self.process.poll() is not None:
                raise RuntimeError(
                    f"runtime exited before attestation completed: {self.process.returncode}"
                )

            return {
                "schema_version": "1",
                "runtime": self.runtime,
                "runtime_commit": self.runtime_commit,
                "runtime_version": self.runtime_version,
                "runtime_executable_path": str(executable_path),
                "runtime_executable_sha256": sha256_file(executable_path),
                "server_pid": self.process.pid,
                "launch_argv": self.command,
                "model_id": self.model_id,
                "model_path": str(self.model_path),
                "model_sha256": sha256_file(self.model_path),
                "endpoint_url": self.endpoint_url,
                "models_endpoint_response": models_data,
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
        except BaseException:
            self.stop()
            raise

    def stop(self) -> None:
        process = self.process
        if process is None or process.poll() is not None:
            return
        try:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        except (OSError, subprocess.SubprocessError):
            return