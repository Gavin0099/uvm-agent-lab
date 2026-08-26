"""Regression tests for CorpusSourceResolver (env:// locator resolution).

Covers the fail-closed requirements from the CorpusSourceResolver task:
missing environment variable, missing file, SHA-256 mismatch, blank/empty
relative-path segments, env-root containment (path traversal, absolute
paths, symlink escape), the required-source-set contract for resolve_all(),
and Windows-style path handling (drive letters, backslashes, spaces in
filenames). Also verifies the resolver's output can be plugged directly into
GovernedSpecRetriever's existing source_paths physical-binding path.
"""

from __future__ import annotations

import copy
import hashlib
import os

import pytest

from gv100h.spec_qa.contracts.corpus_source_resolver import (
    CorpusSourceResolver,
    CorpusSourceResolverError,
)
from gv100h.spec_qa.retrieval.governed_retriever import GovernedSpecRetriever


def _lock_with_source(source_id: str, *, locator: str, content_sha256: str) -> dict:
    lock = copy.deepcopy(GovernedSpecRetriever().corpus_lock)
    lock["sources"][source_id]["source_locator"] = locator
    lock["sources"][source_id]["content_sha256"] = content_sha256
    return lock


def _write_source_file(tmp_path, relative_path: str, content: bytes):
    file_path = tmp_path / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(content)
    return file_path


@pytest.mark.unit
def test_resolves_env_locator_to_verified_path(tmp_path):
    content = b"usb32 raw fixture bytes\n"
    file_path = _write_source_file(tmp_path, "usb32/USB 3.2 Revision 1.1.pdf", content)
    content_sha256 = hashlib.sha256(content).hexdigest()
    lock = _lock_with_source(
        "usb32",
        locator="env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf",
        content_sha256=content_sha256,
    )
    resolver = CorpusSourceResolver(
        lock, env={"USB_SPEC_QA_RAW_ROOT": str(tmp_path)}
    )

    resolved = resolver.resolve("usb32")

    assert resolved == file_path.resolve()


@pytest.mark.unit
def test_missing_env_var_fails_closed(tmp_path):
    lock = _lock_with_source(
        "usb32",
        locator="env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf",
        content_sha256="a" * 64,
    )
    resolver = CorpusSourceResolver(lock, env={})

    with pytest.raises(CorpusSourceResolverError, match="USB_SPEC_QA_RAW_ROOT.*to be set"):
        resolver.resolve("usb32")


@pytest.mark.unit
def test_blank_env_var_fails_closed(tmp_path):
    lock = _lock_with_source(
        "usb32",
        locator="env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf",
        content_sha256="a" * 64,
    )
    resolver = CorpusSourceResolver(lock, env={"USB_SPEC_QA_RAW_ROOT": "   "})

    with pytest.raises(CorpusSourceResolverError, match="to be set"):
        resolver.resolve("usb32")


@pytest.mark.unit
def test_missing_file_fails_closed(tmp_path):
    lock = _lock_with_source(
        "usb32",
        locator="env://USB_SPEC_QA_RAW_ROOT/usb32/does_not_exist.pdf",
        content_sha256="a" * 64,
    )
    resolver = CorpusSourceResolver(
        lock, env={"USB_SPEC_QA_RAW_ROOT": str(tmp_path)}
    )

    with pytest.raises(CorpusSourceResolverError, match="does not exist"):
        resolver.resolve("usb32")


@pytest.mark.unit
def test_hash_mismatch_fails_closed(tmp_path):
    _write_source_file(tmp_path, "usb32/usb32.pdf", b"actual bytes\n")
    lock = _lock_with_source(
        "usb32",
        locator="env://USB_SPEC_QA_RAW_ROOT/usb32/usb32.pdf",
        content_sha256=hashlib.sha256(b"different expected bytes\n").hexdigest(),
    )
    resolver = CorpusSourceResolver(
        lock, env={"USB_SPEC_QA_RAW_ROOT": str(tmp_path)}
    )

    with pytest.raises(CorpusSourceResolverError, match="content hash mismatch"):
        resolver.resolve("usb32")


@pytest.mark.unit
@pytest.mark.parametrize(
    "locator",
    [
        "env://USB_SPEC_QA_RAW_ROOT/",
        "env://USB_SPEC_QA_RAW_ROOT/   ",
        "env://USB_SPEC_QA_RAW_ROOT",
    ],
)
def test_blank_filename_fails_closed(tmp_path, locator):
    lock = _lock_with_source("usb32", locator=locator, content_sha256="a" * 64)
    resolver = CorpusSourceResolver(
        lock, env={"USB_SPEC_QA_RAW_ROOT": str(tmp_path)}
    )

    with pytest.raises(CorpusSourceResolverError, match="missing a relative file path"):
        resolver.resolve("usb32")


@pytest.mark.unit
@pytest.mark.parametrize("locator", ["PENDING_ACQUISITION", "NOT_BOUND", "NOT_APPLICABLE", ""])
def test_pending_or_blank_locator_fails_closed(tmp_path, locator):
    lock = _lock_with_source("usb32", locator=locator, content_sha256="a" * 64)
    resolver = CorpusSourceResolver(
        lock, env={"USB_SPEC_QA_RAW_ROOT": str(tmp_path)}
    )

    with pytest.raises(CorpusSourceResolverError):
        resolver.resolve("usb32")


@pytest.mark.unit
def test_unsupported_locator_scheme_rejected(tmp_path):
    lock = copy.deepcopy(GovernedSpecRetriever().corpus_lock)
    resolver = CorpusSourceResolver(
        lock, env={"USB_SPEC_QA_RAW_ROOT": str(tmp_path)}
    )

    # hub_reference uses repo://, not env:// -- must be explicitly rejected,
    # not silently mis-resolved.
    with pytest.raises(CorpusSourceResolverError, match="not an env:// locator"):
        resolver.resolve("hub_reference")


@pytest.mark.unit
def test_unknown_source_id_fails_closed(tmp_path):
    lock = copy.deepcopy(GovernedSpecRetriever().corpus_lock)
    resolver = CorpusSourceResolver(
        lock, env={"USB_SPEC_QA_RAW_ROOT": str(tmp_path)}
    )

    with pytest.raises(CorpusSourceResolverError, match="no source entry"):
        resolver.resolve("does_not_exist")


@pytest.mark.unit
@pytest.mark.skipif(os.name != "nt", reason="backslash env root is Windows-specific path behavior")
def test_windows_style_env_root_and_spaced_filename_resolves(tmp_path):
    # Simulates a Windows raw-corpus root (drive-letter-style absolute path,
    # as os.environ would actually provide on Windows) combined with a
    # relative path containing a literal space in the filename, exactly as
    # corpus.lock.yaml declares for usb32 ("USB 3.2 Revision 1.1.pdf").
    windows_style_root = str(tmp_path).replace("/", "\\")
    content = b"windows path fixture\n"
    file_path = _write_source_file(tmp_path, "usb32/USB 3.2 Revision 1.1.pdf", content)
    lock = _lock_with_source(
        "usb32",
        locator="env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf",
        content_sha256=hashlib.sha256(content).hexdigest(),
    )
    resolver = CorpusSourceResolver(
        lock, env={"USB_SPEC_QA_RAW_ROOT": windows_style_root}
    )

    resolved = resolver.resolve("usb32")

    assert resolved == file_path.resolve()


@pytest.mark.unit
def test_resolve_all_returns_every_env_locator_source(tmp_path):
    lock = copy.deepcopy(GovernedSpecRetriever().corpus_lock)
    env = {"USB_SPEC_QA_RAW_ROOT": str(tmp_path)}
    for source_id in ("usb20_fw", "usb20_se", "usb32", "superspeed_hub_lvs"):
        content = f"{source_id} bytes\n".encode("utf-8")
        _write_source_file(tmp_path, f"{source_id}.pdf", content)
        lock["sources"][source_id]["source_locator"] = f"env://USB_SPEC_QA_RAW_ROOT/{source_id}.pdf"
        lock["sources"][source_id]["content_sha256"] = hashlib.sha256(content).hexdigest()

    resolver = CorpusSourceResolver(lock, env=env)
    resolved = resolver.resolve_all()

    assert set(resolved) == {"usb20_fw", "usb20_se", "usb32", "superspeed_hub_lvs"}
    assert "hub_reference" not in resolved


@pytest.mark.unit
def test_resolve_all_fails_closed_and_reports_every_failure(tmp_path):
    lock = copy.deepcopy(GovernedSpecRetriever().corpus_lock)
    env = {"USB_SPEC_QA_RAW_ROOT": str(tmp_path)}

    good_content = b"usb20_fw bytes\n"
    _write_source_file(tmp_path, "usb20_fw.pdf", good_content)
    lock["sources"]["usb20_fw"]["source_locator"] = "env://USB_SPEC_QA_RAW_ROOT/usb20_fw.pdf"
    lock["sources"]["usb20_fw"]["content_sha256"] = hashlib.sha256(good_content).hexdigest()

    # usb20_se: file missing entirely.
    lock["sources"]["usb20_se"]["source_locator"] = "env://USB_SPEC_QA_RAW_ROOT/usb20_se_missing.pdf"
    lock["sources"]["usb20_se"]["content_sha256"] = "a" * 64

    # usb32: hash mismatch.
    _write_source_file(tmp_path, "usb32.pdf", b"actual usb32 bytes\n")
    lock["sources"]["usb32"]["source_locator"] = "env://USB_SPEC_QA_RAW_ROOT/usb32.pdf"
    lock["sources"]["usb32"]["content_sha256"] = hashlib.sha256(b"wrong bytes\n").hexdigest()

    # superspeed_hub_lvs left as PENDING_ACQUISITION for this failure case.
    lock["sources"]["superspeed_hub_lvs"]["source_locator"] = "PENDING_ACQUISITION"
    lock["sources"]["superspeed_hub_lvs"]["content_sha256"] = "a" * 64

    resolver = CorpusSourceResolver(lock, env=env)

    with pytest.raises(CorpusSourceResolverError) as excinfo:
        resolver.resolve_all()

    message = str(excinfo.value)
    assert "usb20_se" in message
    assert "usb32" in message
    assert "superspeed_hub_lvs" in message
    assert "usb20_fw" not in message


@pytest.mark.unit
def test_resolve_all_required_pending_source_is_not_silently_skipped(tmp_path):
    # Regression for the resolve_all() default-set bug: a required Phase 1
    # official-raw source left at a pending marker (no env:// prefix) must
    # still surface as a resolve_all() failure, not be silently dropped from
    # the default source_ids just because its locator isn't env://.
    lock = copy.deepcopy(GovernedSpecRetriever().corpus_lock)
    env = {"USB_SPEC_QA_RAW_ROOT": str(tmp_path)}

    for source_id in ("usb20_fw", "usb20_se", "usb32"):
        content = f"{source_id} bytes\n".encode("utf-8")
        _write_source_file(tmp_path, f"{source_id}.pdf", content)
        lock["sources"][source_id]["source_locator"] = f"env://USB_SPEC_QA_RAW_ROOT/{source_id}.pdf"
        lock["sources"][source_id]["content_sha256"] = hashlib.sha256(content).hexdigest()

    lock["sources"]["superspeed_hub_lvs"]["source_locator"] = "PENDING_ACQUISITION"

    resolver = CorpusSourceResolver(lock, env=env)

    with pytest.raises(CorpusSourceResolverError, match="superspeed_hub_lvs"):
        resolver.resolve_all()


@pytest.mark.unit
def test_resolve_all_required_unsupported_scheme_source_is_not_silently_skipped(tmp_path):
    # A required Phase 1 official-raw source mis-typed with an unsupported
    # locator scheme (e.g. file://) must also surface as a resolve_all()
    # failure rather than being excluded from the default source_ids.
    lock = copy.deepcopy(GovernedSpecRetriever().corpus_lock)
    env = {"USB_SPEC_QA_RAW_ROOT": str(tmp_path)}

    for source_id in ("usb20_fw", "usb20_se", "superspeed_hub_lvs"):
        content = f"{source_id} bytes\n".encode("utf-8")
        _write_source_file(tmp_path, f"{source_id}.pdf", content)
        lock["sources"][source_id]["source_locator"] = f"env://USB_SPEC_QA_RAW_ROOT/{source_id}.pdf"
        lock["sources"][source_id]["content_sha256"] = hashlib.sha256(content).hexdigest()

    lock["sources"]["usb32"]["source_locator"] = "file:///usb32/usb32.pdf"

    resolver = CorpusSourceResolver(lock, env=env)

    with pytest.raises(CorpusSourceResolverError, match="usb32"):
        resolver.resolve_all()


@pytest.mark.unit
@pytest.mark.parametrize(
    "relative_path",
    [
        "../outside.pdf",
        "usb32/../../outside.pdf",
    ],
)
def test_env_root_dotdot_traversal_escape_fails_closed(tmp_path, relative_path):
    root_dir = tmp_path / "raw_root"
    root_dir.mkdir()
    outside_content = b"outside root bytes\n"
    (tmp_path / "outside.pdf").write_bytes(outside_content)
    lock = _lock_with_source(
        "usb32",
        locator=f"env://USB_SPEC_QA_RAW_ROOT/{relative_path}",
        content_sha256=hashlib.sha256(outside_content).hexdigest(),
    )
    resolver = CorpusSourceResolver(lock, env={"USB_SPEC_QA_RAW_ROOT": str(root_dir)})

    with pytest.raises(CorpusSourceResolverError, match="escapes its source root"):
        resolver.resolve("usb32")


@pytest.mark.unit
def test_env_root_absolute_relative_path_escape_fails_closed(tmp_path):
    root_dir = tmp_path / "raw_root"
    root_dir.mkdir()
    outside_content = b"outside root bytes\n"
    outside_file = tmp_path / "outside.pdf"
    outside_file.write_bytes(outside_content)
    # "env://ROOT//outside.pdf" parses to an absolute relative_path segment
    # (a leading "/"), which must not be allowed to override the env root.
    absolute_relative_path = str(outside_file)
    if not absolute_relative_path.startswith("/"):
        # Force a POSIX-style absolute segment regardless of host platform
        # path separator conventions, matching the locator's forward-slash
        # convention.
        absolute_relative_path = "/" + absolute_relative_path.replace("\\", "/").lstrip("/")
    lock = _lock_with_source(
        "usb32",
        locator=f"env://USB_SPEC_QA_RAW_ROOT{absolute_relative_path}",
        content_sha256=hashlib.sha256(outside_content).hexdigest(),
    )
    resolver = CorpusSourceResolver(lock, env={"USB_SPEC_QA_RAW_ROOT": str(root_dir)})

    with pytest.raises(CorpusSourceResolverError, match="absolute|escapes its source root"):
        resolver.resolve("usb32")


@pytest.mark.unit
def test_env_root_symlink_escape_fails_closed(tmp_path):
    root_dir = tmp_path / "raw_root"
    root_dir.mkdir()
    outside_content = b"outside root bytes via symlink\n"
    outside_file = tmp_path / "outside.pdf"
    outside_file.write_bytes(outside_content)
    link_path = root_dir / "link.pdf"
    try:
        os.symlink(outside_file, link_path)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is not permitted in this test environment")

    lock = _lock_with_source(
        "usb32",
        locator="env://USB_SPEC_QA_RAW_ROOT/link.pdf",
        content_sha256=hashlib.sha256(outside_content).hexdigest(),
    )
    resolver = CorpusSourceResolver(lock, env={"USB_SPEC_QA_RAW_ROOT": str(root_dir)})

    with pytest.raises(CorpusSourceResolverError, match="escapes its source root"):
        resolver.resolve("usb32")


@pytest.mark.contract
def test_resolved_paths_satisfy_governed_retriever_physical_binding(tmp_path):
    # Integration: CorpusSourceResolver's output plugs directly into
    # GovernedSpecRetriever(source_paths=...) without any additional
    # manual path bookkeeping, for the four env:// official-raw sources.
    # hub_reference (repo://) is bound separately via knowledge_repo_path,
    # matching its existing, unrelated binding mechanism.
    import subprocess

    lock = copy.deepcopy(GovernedSpecRetriever().corpus_lock)
    lock["status"] = "phase1_bound"
    env = {"USB_SPEC_QA_RAW_ROOT": str(tmp_path)}

    for source_id in ("usb20_fw", "usb20_se", "usb32", "superspeed_hub_lvs"):
        source = lock["sources"][source_id]
        source["binding_status"] = "locked"
        content = f"{source_id} bound bytes\n".encode("utf-8")
        _write_source_file(tmp_path, f"{source_id}.pdf", content)
        source["source_locator"] = f"env://USB_SPEC_QA_RAW_ROOT/{source_id}.pdf"
        source["content_sha256"] = hashlib.sha256(content).hexdigest()

    repo_path = tmp_path / "reference"
    (repo_path / "exports").mkdir(parents=True)
    (repo_path / "exports" / "hub_governed_surface_manifest.yaml").write_text(
        "manifest_id: test\n", encoding="utf-8"
    )
    subprocess.run(["git", "init", "--quiet", str(repo_path)], check=True)
    subprocess.run(["git", "-C", str(repo_path), "config", "user.name", "Test"], check=True)
    subprocess.run(
        ["git", "-C", str(repo_path), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    subprocess.run(["git", "-C", str(repo_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo_path), "commit", "--quiet", "-m", "bind fixture"], check=True)
    commit = subprocess.check_output(
        ["git", "-C", str(repo_path), "rev-parse", "HEAD"], text=True
    ).strip()
    content_hash, _file_count = GovernedSpecRetriever._compute_knowledge_repo_content_hash(repo_path)
    lock["sources"]["hub_reference"]["commit"] = commit
    lock["sources"]["hub_reference"]["content_sha256"] = content_hash
    lock["sources"]["hub_reference"]["binding_status"] = "locked"

    lock_path = tmp_path / "corpus.lock.yaml"
    import yaml

    lock_path.write_text(yaml.safe_dump(lock, sort_keys=False), encoding="utf-8")

    resolver = CorpusSourceResolver(lock, env=env)
    source_paths = resolver.resolve_all()
    source_paths["hub_reference"] = repo_path

    retriever = GovernedSpecRetriever(
        source_paths=source_paths,
        corpus_lock_path=str(lock_path),
        require_physical_binding=True,
    )

    assert retriever.physical_binding_verified is True
    assert retriever.qualification_blocked is False
