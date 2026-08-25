from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

from gv100h.spec_qa.contracts.poc1_acceptance_contract import (
    BOUNDARY_CODES,
    CONFLICT_BOUNDARY_CODES,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RENDERER_PATH = PROJECT_ROOT / "scripts" / "render_poc1_review_worksheet.py"
DRAFT_PATH = (
    PROJECT_ROOT / "gv100h" / "spec_qa" / "golden" / "poc1_acceptance_set.draft.json"
)
LOCK_PATH = PROJECT_ROOT / "gv100h" / "spec_qa" / "contracts" / "corpus.lock.yaml"


def _load_renderer():
    spec = importlib.util.spec_from_file_location(
        "render_poc1_review_worksheet",
        RENDERER_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


renderer = _load_renderer()


def test_worksheet_binds_draft_lock_and_contract_enums(tmp_path: Path):
    output = tmp_path / "worksheet.md"
    text = renderer.render_worksheet(
        output_path=output,
        generated_at="2026-08-25T00:00:00+00:00",
    )
    lock = yaml.safe_load(LOCK_PATH.read_text(encoding="utf-8"))
    usb20_hash = lock["sources"]["usb20_fw"]["content_sha256"]
    usb32_hash = lock["sources"]["usb32"]["content_sha256"]
    lvs_hash = lock["sources"]["superspeed_hub_lvs"]["content_sha256"]
    hub_commit = lock["sources"]["hub_reference"]["commit"]

    assert output.is_file()
    assert text.count("### 題目") == 50
    assert "`source_draft_path`:" in text
    assert "`source_draft_git_commit`:" in text
    assert f"`source_draft_sha256`: `{hashlib.sha256(DRAFT_PATH.read_bytes()).hexdigest()}`" in text
    assert f"`corpus_lock_sha256`: `{hashlib.sha256(LOCK_PATH.read_bytes()).hexdigest()}`" in text
    assert "`corpus_lock_git_blob`:" in text
    assert "`renderer_path`:" in text
    assert f"`renderer_sha256`: `{hashlib.sha256(RENDERER_PATH.read_bytes()).hexdigest()}`" in text
    assert "`generated_at`: `2026-08-25T00:00:00+00:00`" in text
    assert usb20_hash[:8] in text
    assert usb32_hash[:8] in text
    assert lvs_hash[:8] in text
    assert hub_commit in text
    assert lock["sources"]["usb20_fw"]["source_locator"] in text
    assert "其他" not in text
    assert "棄權理由碼（只准這六個）：" + " / ".join(BOUNDARY_CODES) in text
    assert "衝突類型（只准這三個）：" + " / ".join(sorted(CONFLICT_BOUNDARY_CODES)) in text
    assert "不是正式 acceptance set，也不是 review receipt" in text
    assert "MUST_NOT_CREATE" in text


def test_worksheet_follows_lock_bytes_not_hardcoded_hashes(tmp_path: Path):
    lock = yaml.safe_load(LOCK_PATH.read_text(encoding="utf-8"))
    old_hash = lock["sources"]["usb32"]["content_sha256"]
    new_hash = "aa" * 32
    lock["sources"]["usb32"]["content_sha256"] = new_hash
    tampered_lock = tmp_path / "corpus.lock.yaml"
    tampered_lock.write_text(
        yaml.safe_dump(lock, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    text = renderer.render_worksheet(
        lock_path=tampered_lock,
        output_path=tmp_path / "worksheet.md",
        generated_at="2026-08-25T00:00:00+00:00",
    )
    assert new_hash[:8] in text
    assert old_hash[:8] not in text


def test_worksheet_fails_closed_when_required_source_missing(tmp_path: Path):
    lock = yaml.safe_load(LOCK_PATH.read_text(encoding="utf-8"))
    del lock["sources"]["usb32"]
    broken_lock = tmp_path / "corpus.lock.yaml"
    broken_lock.write_text(
        yaml.safe_dump(lock, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    with pytest.raises(renderer.WorksheetRenderError, match="usb32"):
        renderer.render_worksheet(
            lock_path=broken_lock,
            output_path=tmp_path / "worksheet.md",
        )
