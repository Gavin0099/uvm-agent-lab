from __future__ import annotations

import datetime as _dt
import hashlib
import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from gv100h.spec_qa.retrieval.governed_retriever import GovernedSpecRetriever


class CorpusBindingReceiptError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        status: Literal["mismatch", "unverified"] = "mismatch",
    ) -> None:
        super().__init__(message)
        self.status = status


class CorpusRuntimeBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["unverified", "verified", "failed"]
    source_locator: str = Field(min_length=1)
    observed_sha256: Optional[str] = Field(
        default=None,
        pattern=r"^[0-9a-fA-F]{64}$",
    )
    observed_commit: Optional[str] = Field(
        default=None,
        pattern=r"^[0-9a-fA-F]{40,64}$",
    )


class CorpusBindingReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"]
    verification_status: Literal["verified"]
    corpus_id: str = Field(min_length=1)
    corpus_lock_path: str = Field(min_length=1)
    corpus_lock_hash: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    corpus_lock_blob_oid: str = Field(pattern=r"^[0-9a-fA-F]{40}$")
    corpus_lock_last_change_commit: str = Field(
        pattern=r"^[0-9a-fA-F]{40,64}$"
    )
    required_source_ids: list[str] = Field(min_length=1)
    observed_source_hashes: Dict[str, str]
    runtime_bindings: Dict[str, CorpusRuntimeBinding]
    physical_binding_verified: Literal[True]
    bound_repo_head_commit: str = Field(pattern=r"^[0-9a-fA-F]{40,64}$")
    bound_repo_files_hash: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    verified_at: str = Field(min_length=1)
    receipt_hash: str = Field(pattern=r"^[0-9a-fA-F]{64}$")


def _run_git(*arguments: str, cwd: Path) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise ValueError("corpus lock Git identity could not be verified")
    return result.stdout.strip()


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    file_path = Path(path).resolve()
    if not file_path.is_file():
        raise ValueError(f"corpus lock does not exist: {file_path}")
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _corpus_lock_identity(
    path: str | Path,
    *,
    repo_root: Optional[str | Path] = None,
) -> Dict[str, str]:
    lock_file = Path(path).resolve()
    if not lock_file.is_file():
        raise ValueError(f"corpus lock does not exist: {lock_file}")

    git_root = Path(
        _run_git("rev-parse", "--show-toplevel", cwd=lock_file.parent)
    ).resolve()
    if repo_root is not None and git_root != Path(repo_root).resolve():
        raise ValueError("corpus lock is outside the requested repository")
    try:
        relative_path = lock_file.relative_to(git_root).as_posix()
    except ValueError as exc:
        raise ValueError("corpus lock is outside its Git repository") from exc

    _run_git("ls-files", "--error-unmatch", "--", relative_path, cwd=git_root)
    if _run_git("status", "--porcelain", "--", relative_path, cwd=git_root):
        raise ValueError("corpus lock must be clean and committed")

    return {
        "relative_path": relative_path,
        "sha256": _sha256_file(lock_file),
        "blob_oid": _run_git(
            "rev-parse",
            f"HEAD:{relative_path}",
            cwd=git_root,
        ),
        "last_change_commit": _run_git(
            "log",
            "-1",
            "--format=%H",
            "--",
            relative_path,
            cwd=git_root,
        ),
    }


def _receipt_hash(receipt: CorpusBindingReceipt) -> str:
    payload = receipt.model_dump(mode="json", exclude={"receipt_hash"})
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _source_locator(
    retriever: "GovernedSpecRetriever",
    source_id: str,
) -> str:
    source = retriever.corpus_lock["sources"][source_id]
    locator = source.get("source_locator")
    if locator in (None, "PENDING_ACQUISITION", "NOT_BOUND"):
        if source_id == "hub_reference":
            return f"repo://{source['repo']}@{source['commit']}"
        raise CorpusBindingReceiptError(
            f"source {source_id} has no portable source locator",
            status="unverified",
        )
    return str(locator)


def _receipt_runtime_binding(
    retriever: "GovernedSpecRetriever",
    source_id: str,
) -> CorpusRuntimeBinding:
    binding = retriever.runtime_bindings[source_id]
    return CorpusRuntimeBinding(
        status=binding["status"],
        source_locator=_source_locator(retriever, source_id),
        observed_sha256=binding.get("observed_sha256"),
        observed_commit=binding.get("observed_commit"),
    )


def build_corpus_binding_receipt(
    retriever: "GovernedSpecRetriever",
    *,
    repo_root: Optional[str | Path] = None,
) -> CorpusBindingReceipt:
    if (
        not retriever.physical_binding_verified
        or retriever.runtime_binding_status != "verified"
        or retriever.qualification_blocked
    ):
        raise CorpusBindingReceiptError(
            "cannot build a verified receipt from an unverified corpus binding",
            status="unverified",
        )

    lock_identity = _corpus_lock_identity(
        retriever.corpus_lock_path,
        repo_root=repo_root,
    )
    required_source_ids = list(retriever.REQUIRED_PHASE1_SOURCES)
    runtime_bindings = {
        source_id: _receipt_runtime_binding(retriever, source_id)
        for source_id in required_source_ids
    }
    observed_source_hashes = {
        source_id: binding.observed_sha256
        for source_id, binding in runtime_bindings.items()
    }
    if any(value is None for value in observed_source_hashes.values()):
        raise CorpusBindingReceiptError(
            "verified corpus binding is missing an observed source hash",
            status="unverified",
        )
    if not retriever.bound_repo_head_commit or not retriever.bound_repo_files_hash:
        raise CorpusBindingReceiptError(
            "verified corpus binding is missing governed reference identity",
            status="unverified",
        )

    receipt = CorpusBindingReceipt(
        schema_version="1",
        verification_status="verified",
        corpus_id=retriever.corpus_id,
        corpus_lock_path=lock_identity["relative_path"],
        corpus_lock_hash=lock_identity["sha256"],
        corpus_lock_blob_oid=lock_identity["blob_oid"],
        corpus_lock_last_change_commit=lock_identity["last_change_commit"],
        required_source_ids=required_source_ids,
        observed_source_hashes={
            source_id: str(source_hash)
            for source_id, source_hash in observed_source_hashes.items()
        },
        runtime_bindings=runtime_bindings,
        physical_binding_verified=True,
        bound_repo_head_commit=retriever.bound_repo_head_commit,
        bound_repo_files_hash=retriever.bound_repo_files_hash,
        verified_at=_dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        receipt_hash="0" * 64,
    )
    return receipt.model_copy(update={"receipt_hash": _receipt_hash(receipt)})


def verify_corpus_binding_receipt(
    receipt: CorpusBindingReceipt,
    retriever: "GovernedSpecRetriever",
    *,
    repo_root: Optional[str | Path] = None,
) -> Dict[str, Any]:
    if _receipt_hash(receipt).lower() != receipt.receipt_hash.lower():
        raise CorpusBindingReceiptError("corpus binding receipt hash does not match")

    if (
        not retriever.physical_binding_verified
        or retriever.runtime_binding_status != "verified"
        or retriever.qualification_blocked
    ):
        raise CorpusBindingReceiptError(
            "retriever corpus binding is not verified",
            status="unverified",
        )

    lock_identity = _corpus_lock_identity(
        retriever.corpus_lock_path,
        repo_root=repo_root,
    )
    expected_source_ids = list(retriever.REQUIRED_PHASE1_SOURCES)
    if receipt.corpus_id != retriever.corpus_id:
        raise CorpusBindingReceiptError("corpus binding receipt corpus_id does not match")
    if receipt.corpus_lock_path != lock_identity["relative_path"]:
        raise CorpusBindingReceiptError("corpus binding receipt lock path does not match")
    if receipt.corpus_lock_hash.lower() != lock_identity["sha256"].lower():
        raise CorpusBindingReceiptError("corpus binding receipt lock hash does not match")
    if receipt.corpus_lock_blob_oid != lock_identity["blob_oid"]:
        raise CorpusBindingReceiptError("corpus binding receipt lock blob does not match")
    if receipt.corpus_lock_last_change_commit != lock_identity["last_change_commit"]:
        raise CorpusBindingReceiptError(
            "corpus binding receipt lock last-change commit does not match"
        )
    if receipt.required_source_ids != expected_source_ids:
        raise CorpusBindingReceiptError("corpus binding receipt source IDs do not match")
    if receipt.physical_binding_verified is not True:
        raise CorpusBindingReceiptError("corpus binding receipt is not physically verified")
    if receipt.bound_repo_head_commit != retriever.bound_repo_head_commit:
        raise CorpusBindingReceiptError("corpus binding receipt governed head does not match")
    if receipt.bound_repo_files_hash.lower() != str(
        retriever.bound_repo_files_hash
    ).lower():
        raise CorpusBindingReceiptError("corpus binding receipt governed hash does not match")

    expected_bindings = {
        source_id: _receipt_runtime_binding(retriever, source_id)
        for source_id in expected_source_ids
    }
    if receipt.runtime_bindings != expected_bindings:
        raise CorpusBindingReceiptError("corpus binding receipt runtime bindings do not match")
    expected_hashes = {
        source_id: str(binding.observed_sha256)
        for source_id, binding in expected_bindings.items()
    }
    if receipt.observed_source_hashes != expected_hashes:
        raise CorpusBindingReceiptError(
            "corpus binding receipt observed source hashes do not match"
        )
    return receipt.model_dump(mode="json")


def load_corpus_binding_receipt(path: str | Path) -> CorpusBindingReceipt:
    receipt_path = Path(path).resolve()
    try:
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        return CorpusBindingReceipt.model_validate(payload)
    except Exception as exc:
        raise ValueError(f"invalid corpus binding receipt: {exc}") from exc