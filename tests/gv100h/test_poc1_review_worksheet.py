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
    assert text.count("### 這題在問什麼？") == 50
    assert text.count("### 英文原題") == 50
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
    assert "拒絕回答的理由碼（只准這六個）：" + " / ".join(BOUNDARY_CODES) in text
    assert renderer.STATUS_CHECKS["conflict"][0] == (
        "兩邊互相競爭的證據都確實存在於指定規格"
    )
    assert "衝突類型（只准這三個）：" + " / ".join(
        sorted(CONFLICT_BOUNDARY_CODES)
    ) == renderer.reviewer_fields(
        "conflict",
        conflict_list=" / ".join(sorted(CONFLICT_BOUNDARY_CODES)),
        boundary_list=" / ".join(BOUNDARY_CODES),
    )[2]
    assert "衝突類型（只准這三個）：" not in text
    assert "不是正式 acceptance set，也不是 review receipt" in text
    assert "MUST_NOT_CREATE" in text
    assert "這題預期：直接回答" in text
    assert "要查哪份規格？" in text
    assert "這題在問什麼？" in text
    assert "依 USB 2.0 Rev 2.0 第 5 章，`transaction` 與 `transfer` 有什麼差別？" in text
    assert "指定的規格文件與版本正確" in text
    assert "可以從指定規格中找到答案" in text
    assert "這題確實應該直接回答，而不是回報衝突或拒絕回答" in text
    assert "這個問題沒有先把答案透露出來" in text
    assert "這個問題沒有暗示產品已經通過測試或認證" in text
    assert "支持答案的規格原文" in text
    assert "正確答案至少要包含哪些重點" in text
    assert "根據這份證據，哪些結論不能下" in text
    assert "題目可用" in text
    assert "題目需要修改" in text
    assert "這題不適合使用" in text
    assert "題幹" not in text
    assert "棄權理由碼" not in text
    assert "兩邊互相競爭的證據都確實存在於指定規格" not in text
    assert "兩邊談的是同一對象、同一狀態、同一版本脈絡，不是只是範圍不同" not in text
    assert "目前指定的 Phase 1 規格裡，沒有足夠、可接受的證據能回答這題" in text
    assert "不應為了硬答而去引用指定規格以外的來源" in text
    assert "這題不該把規範章節或頁碼當成正式答案" in text
    answer_block = text.split("## DRAFT-L4-043", 1)[0]
    abstain_block = text.split("## DRAFT-L4-043", 1)[1].split("## DRAFT-L4-044", 1)[0]
    l4_039_block = text.split("## DRAFT-L4-039", 1)[1].split("## DRAFT-L4-040", 1)[0]
    l4_041_block = text.split("## DRAFT-L4-041", 1)[1].split("## DRAFT-L4-042", 1)[0]
    l3_037_block = text.split("## DRAFT-L3-037", 1)[1].split("## DRAFT-L3-038", 1)[0]
    l1_001_block = text.split("## DRAFT-L1-001", 1)[1].split("## DRAFT-L1-002", 1)[0]
    assert "可以從指定規格中找到答案" in answer_block
    assert "可以從指定規格中找到答案" not in abstain_block
    assert "指定的規格文件與版本正確" not in abstain_block
    assert "可以從指定規格中找到答案" in l4_039_block
    assert "這題確實應該直接回答，而不是回報衝突或拒絕回答" in l4_039_block
    assert "兩邊互相競爭的證據都確實存在於指定規格" not in l4_039_block
    assert "這兩段是否構成衝突？請分別指出兩段證據描述的對象、" in l4_039_block
    assert "來源 A（`usb20_fw`）" in l4_039_block
    assert "來源 B（`usb32`）" in l4_039_block
    assert "兩者是否同一對象" in l4_039_block
    assert "兩者關係（mapping / conflict / independent scope）" in l4_039_block
    assert "來源 C（`superspeed_hub_lvs`）" in l3_037_block
    assert "三者是否同一對象" in l3_037_block
    assert "來源 A" not in l1_001_block
    assert "規格章節" in l1_001_block
    assert "AUTHORITY_MISMATCH" not in l4_041_block
    assert "目前指定的 Phase 1 規格裡，沒有足夠、可接受的證據能回答這題" not in answer_block
    assert "Contact Capacitance" in text
    assert "TD 10.104 Toggle Port Power" in text
    assert "Programmable Power Supply" in text
    assert "generation-and-field-scope" not in text
    assert "imply different behavior" not in text


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
    assert "這題預期：直接回答" in text
    assert "要查哪份規格？" in text
    assert "這題在問什麼？" in text
    assert "依 USB 2.0 Rev 2.0 第 5 章，`transaction` 與 `transfer` 有什麼差別？" in text
    assert "指定的規格文件與版本正確" in text
    assert "可以從指定規格中找到答案" in text
    assert "這題確實應該直接回答，而不是回報衝突或拒絕回答" in text
    assert "這個問題沒有先把答案透露出來" in text
    assert "這個問題沒有暗示產品已經通過測試或認證" in text
    assert "支持答案的規格原文" in text
    assert "正確答案至少要包含哪些重點" in text
    assert "根據這份證據，哪些結論不能下" in text
    assert "題目可用" in text
    assert "題目需要修改" in text
    assert "這題不適合使用" in text
    assert "機器規則（admission 用，審查時可略過）" in text
    assert "<label class='check'>" in text
    assert "應對規格" not in text
    assert "應能回答" not in text
    assert "題幹" not in text
    assert "棄權理由碼" not in text
    assert (
        "USB 2.0 Rev 2.0 Table 6-7 對 Contact Capacitance 的性能要求是什麼？"
        "必須寫出未插合（unmated）條件與單位。"
    ) in text
    assert "兩邊互相競爭的證據都確實存在於指定規格" not in text
    assert "目前指定的 Phase 1 規格裡，沒有足夠、可接受的證據能回答這題" in text
    l1_card = text.split("id='DRAFT-L1-001'", 1)[1].split("id='DRAFT-L1-002'", 1)[0]
    l4_039 = text.split("id='DRAFT-L4-039'", 1)[1].split("id='DRAFT-L4-040'", 1)[0]
    l4_043 = text.split("id='DRAFT-L4-043'", 1)[1].split("id='DRAFT-L4-044'", 1)[0]
    l3_037 = text.split("id='DRAFT-L3-037'", 1)[1].split("id='DRAFT-L3-038'", 1)[0]
    assert "可以從指定規格中找到答案" in l1_card
    assert "可以從指定規格中找到答案" in l4_039
    assert "可以從指定規格中找到答案" not in l4_043
    assert "指定的規格文件與版本正確" not in l4_043
    assert "兩邊談的是同一對象、同一狀態、同一版本脈絡，不是只是範圍不同" not in l4_039
    assert "來源 A（`usb20_fw`）" in l4_039
    assert "來源 B（`usb32`）" in l4_039
    assert "兩者是否同一對象" in l4_039
    assert "來源 C（`superspeed_hub_lvs`）" in l3_037
    assert "三者是否同一對象" in l3_037
    assert "來源 A" not in l1_card
    assert "規格章節" in l1_card
    assert "這題確實應該直接回答，而不是回報衝突或拒絕回答" in l4_039
    assert "不應為了硬答而去引用指定規格以外的來源" in l4_043
    assert "USB Power Delivery" in text
    assert "TD 10.104 Toggle Port Power" in text


def test_missing_chinese_restatement_fails_closed():
    with pytest.raises(
        renderer.WorksheetRenderError,
        match="missing Chinese restatement for DRAFT-MISSING",
    ):
        renderer.question_plain_zh({"question_id": "DRAFT-MISSING"})
