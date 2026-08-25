from __future__ import annotations

import hashlib
import importlib.util
import shutil
import subprocess
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


def _git(*arguments: str, cwd: Path) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _seed_official_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "official-repo"
    draft_rel = Path("gv100h") / "spec_qa" / "golden" / "poc1_acceptance_set.draft.json"
    lock_rel = Path("gv100h") / "spec_qa" / "contracts" / "corpus.lock.yaml"
    renderer_rel = Path("scripts") / "render_poc1_review_worksheet.py"
    (repo / draft_rel.parent).mkdir(parents=True)
    (repo / lock_rel.parent).mkdir(parents=True)
    (repo / renderer_rel.parent).mkdir(parents=True)
    shutil.copy(DRAFT_PATH, repo / draft_rel)
    shutil.copy(LOCK_PATH, repo / lock_rel)
    shutil.copy(RENDERER_PATH, repo / renderer_rel)
    _git("init", cwd=repo)
    _git("add", str(draft_rel), str(lock_rel), str(renderer_rel), cwd=repo)
    _git(
        "-c",
        "user.name=worksheet-test",
        "-c",
        "user.email=worksheet-test@example.invalid",
        "commit",
        "-m",
        "seed official review inputs",
        cwd=repo,
    )
    return repo


def test_worksheet_binds_draft_lock_and_contract_enums(tmp_path: Path):
    repo = _seed_official_repo(tmp_path)
    draft_path = repo / "gv100h" / "spec_qa" / "golden" / "poc1_acceptance_set.draft.json"
    lock_path = repo / "gv100h" / "spec_qa" / "contracts" / "corpus.lock.yaml"
    renderer_path = repo / "scripts" / "render_poc1_review_worksheet.py"
    output = tmp_path / "worksheet.md"
    text = renderer.render_worksheet(
        draft_path=draft_path,
        lock_path=lock_path,
        renderer_path=renderer_path,
        output_path=output,
        generated_at="2026-08-25T00:00:00+00:00",
        repo_root=repo,
    )
    lock = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    usb20_hash = lock["sources"]["usb20_fw"]["content_sha256"]
    usb32_hash = lock["sources"]["usb32"]["content_sha256"]
    lvs_hash = lock["sources"]["superspeed_hub_lvs"]["content_sha256"]
    hub_commit = lock["sources"]["hub_reference"]["commit"]
    lock_blob = _git(
        "rev-parse",
        "HEAD:gv100h/spec_qa/contracts/corpus.lock.yaml",
        cwd=repo,
    )
    draft_blob = _git(
        "rev-parse",
        "HEAD:gv100h/spec_qa/golden/poc1_acceptance_set.draft.json",
        cwd=repo,
    )
    renderer_blob = _git(
        "rev-parse",
        "HEAD:scripts/render_poc1_review_worksheet.py",
        cwd=repo,
    )
    head = _git("rev-parse", "HEAD", cwd=repo)

    assert output.is_file()
    assert text.count("### 題目") == 50
    assert "`source_draft_path`:" in text
    assert f"`source_draft_git_commit`: `{head}`" in text
    assert f"`source_draft_git_blob`: `{draft_blob}`" in text
    assert (
        f"`source_draft_sha256`: `{hashlib.sha256(draft_path.read_bytes()).hexdigest()}`"
        in text
    )
    assert (
        f"`corpus_lock_sha256`: `{hashlib.sha256(lock_path.read_bytes()).hexdigest()}`"
        in text
    )
    assert f"`corpus_lock_git_blob`: `{lock_blob}`" in text
    assert "`renderer_path`:" in text
    assert f"`renderer_git_blob`: `{renderer_blob}`" in text
    assert (
        f"`renderer_sha256`: `{hashlib.sha256(renderer_path.read_bytes()).hexdigest()}`"
        in text
    )
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


def test_source_table_follows_lock_bytes_not_hardcoded_hashes():
    lock = yaml.safe_load(LOCK_PATH.read_text(encoding="utf-8"))
    old_hash = lock["sources"]["usb32"]["content_sha256"]
    new_hash = "aa" * 32
    lock["sources"]["usb32"]["content_sha256"] = new_hash
    row = renderer.source_row("usb32", lock["sources"]["usb32"])
    assert row[3] == new_hash[:8]
    assert old_hash[:8] not in row[3]


def test_required_sources_fail_when_usb32_missing():
    lock = yaml.safe_load(LOCK_PATH.read_text(encoding="utf-8"))
    del lock["sources"]["usb32"]
    with pytest.raises(renderer.WorksheetRenderError, match="usb32"):
        renderer.required_sources_from_lock(lock)


def test_official_render_fails_when_lock_dirty(tmp_path: Path):
    repo = _seed_official_repo(tmp_path)
    lock_path = repo / "gv100h" / "spec_qa" / "contracts" / "corpus.lock.yaml"
    lock_path.write_text(
        lock_path.read_text(encoding="utf-8") + "\n# dirty\n",
        encoding="utf-8",
    )
    with pytest.raises(renderer.WorksheetRenderError, match="corpus.lock.yaml is dirty"):
        renderer.render_worksheet(
            draft_path=repo
            / "gv100h"
            / "spec_qa"
            / "golden"
            / "poc1_acceptance_set.draft.json",
            lock_path=lock_path,
            renderer_path=repo / "scripts" / "render_poc1_review_worksheet.py",
            output_path=tmp_path / "worksheet.md",
            repo_root=repo,
        )


def test_official_render_fails_when_draft_dirty(tmp_path: Path):
    repo = _seed_official_repo(tmp_path)
    draft_path = repo / "gv100h" / "spec_qa" / "golden" / "poc1_acceptance_set.draft.json"
    draft_path.write_text(draft_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(
        renderer.WorksheetRenderError,
        match="poc1_acceptance_set.draft.json is dirty",
    ):
        renderer.render_worksheet(
            draft_path=draft_path,
            lock_path=repo / "gv100h" / "spec_qa" / "contracts" / "corpus.lock.yaml",
            renderer_path=repo / "scripts" / "render_poc1_review_worksheet.py",
            output_path=tmp_path / "worksheet.md",
            repo_root=repo,
        )


def test_html_worksheet_has_fifty_cards_and_lock_hashes(tmp_path: Path):
    repo = _seed_official_repo(tmp_path)
    draft_path = repo / "gv100h" / "spec_qa" / "golden" / "poc1_acceptance_set.draft.json"
    lock_path = repo / "gv100h" / "spec_qa" / "contracts" / "corpus.lock.yaml"
    renderer_path = repo / "scripts" / "render_poc1_review_worksheet.py"
    output = tmp_path / "worksheet.html"
    text = renderer.render_html_worksheet(
        draft_path=draft_path,
        lock_path=lock_path,
        renderer_path=renderer_path,
        output_path=output,
        generated_at="2026-08-25T00:00:00+00:00",
        repo_root=repo,
    )
    lock = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    assert output.is_file()
    assert text.count('class="question"') == 50
    assert text.count("<article class='card'") == 50
    assert lock["sources"]["usb20_fw"]["content_sha256"][:8] in text
    assert lock["sources"]["usb32"]["content_sha256"][:8] in text
    assert "MUST_NOT_CREATE" in text
    assert "PENDING_ASSIGNMENT" in text
    assert "瀏覽器勾選只留在本機頁面" in text
    assert "預期處理：直接回答" in text
    assert "本題應查閱的規格" in text
    assert "可在鎖定來源中找到足以支持本題的依據" in text
    assert "題目引用的規格與版本正確" in text
    assert "預期處理類型（回答／衝突／棄權）分類正確" in text
    assert "題幹沒有洩漏預期答案" in text
    assert "題幹沒有暗示產品已通過認證" in text
    assert "答案必須包含" in text
    assert "不得延伸宣稱" in text
    assert "機器規則（admission 用，審查時可略過）" in text
    assert "<label class='check'>" in text
    assert "應對規格" not in text
    assert "應能回答" not in text
