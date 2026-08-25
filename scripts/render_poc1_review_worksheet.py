"""Render a human review worksheet from the POC-1 authoring draft.

This is a projection of review input only. It does not admit the draft,
invent gold, or create a review receipt.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gv100h.spec_qa.contracts.poc1_acceptance_contract import (
    BOUNDARY_CODES,
    CONFLICT_BOUNDARY_CODES,
    REQUIRED_POC1_SOURCE_IDS,
)
DRAFT_PATH = ROOT / "gv100h" / "spec_qa" / "golden" / "poc1_acceptance_set.draft.json"
LOCK_PATH = ROOT / "gv100h" / "spec_qa" / "contracts" / "corpus.lock.yaml"
OUT_PATH = (
    ROOT / "artifacts" / "reviews" / "gv100h" / "poc1-acceptance-review-worksheet.md"
)

PRIORITY_IDS = {
    "DRAFT-L1-004",
    "DRAFT-L1-005",
    "DRAFT-L1-006",
    "DRAFT-L1-008",
    "DRAFT-L1-009",
    "DRAFT-L1-010",
    "DRAFT-L1-011",
    "DRAFT-L2-017",
    "DRAFT-L2-019",
    "DRAFT-L2-020",
    "DRAFT-L2-021",
    "DRAFT-L2-022",
    "DRAFT-L3-026",
    "DRAFT-L3-027",
    "DRAFT-L3-035",
    "DRAFT-L3-037",
    "DRAFT-L4-043",
    "DRAFT-L4-048",
}
STATUS_ZH = {
    "answer": "應能回答",
    "conflict": "應報衝突、不要硬解",
    "abstain": "應拒絕回答 / 棄權",
}
STATUS_GOLD_RULES = {
    "answer": (
        "accepted evidence + 至少 1 條 required claim + required facts + "
        "section anchors；不可有 competing/boundary evidence 或 boundary_code"
    ),
    "conflict": (
        "至少 2 個 competing evidence + 至少 2 條 required claims + "
        "至少 2 個 section anchors；boundary_code 限 "
        + " / ".join(sorted(CONFLICT_BOUNDARY_CODES))
    ),
    "abstain": (
        "boundary evidence + 至少 1 條 required boundary claim；"
        "不可有 accepted/competing evidence，也不可填 normative section anchors"
    ),
}


class WorksheetRenderError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*arguments: str, cwd: Path) -> str | None:
    result = subprocess.run(
        ["git", *arguments],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _repo_relative(path: Path, repo_root: Path = ROOT) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(repo_root.resolve()).as_posix()
    except ValueError as exc:
        raise WorksheetRenderError(
            f"{resolved.as_posix()} is outside the repository"
        ) from exc


def _require_tracked_and_clean(path: Path, repo_root: Path) -> str:
    rel = _repo_relative(path, repo_root)
    listed = _git("ls-files", "--error-unmatch", "--", rel, cwd=repo_root)
    if listed is None:
        raise WorksheetRenderError(f"{rel} is not tracked")
    status = _git("status", "--porcelain", "--", rel, cwd=repo_root)
    # Clean tracked files yield empty porcelain output, which _git maps to None.
    if status:
        raise WorksheetRenderError(f"{rel} is dirty")
    return rel


def _head_blob(rel: str, repo_root: Path) -> str:
    blob = _git("rev-parse", f"HEAD:{rel}", cwd=repo_root)
    if blob is None:
        raise WorksheetRenderError(f"HEAD:{rel} is not retrievable")
    return blob


def collect_provenance(
    *,
    draft_path: Path,
    lock_path: Path,
    renderer_path: Path,
    generated_at: str,
    repo_root: Path = ROOT,
) -> dict[str, str]:
    draft_rel = _require_tracked_and_clean(draft_path, repo_root)
    lock_rel = _require_tracked_and_clean(lock_path, repo_root)
    renderer_rel = _require_tracked_and_clean(renderer_path, repo_root)
    head = _git("rev-parse", "HEAD", cwd=repo_root)
    if head is None:
        raise WorksheetRenderError("HEAD is not retrievable")
    return {
        "source_draft_path": draft_rel,
        "source_draft_git_commit": head,
        "source_draft_git_blob": _head_blob(draft_rel, repo_root),
        "source_draft_sha256": sha256_file(draft_path),
        "corpus_lock_path": lock_rel,
        "corpus_lock_sha256": sha256_file(lock_path),
        "corpus_lock_git_blob": _head_blob(lock_rel, repo_root),
        "renderer_path": renderer_rel,
        "renderer_git_blob": _head_blob(renderer_rel, repo_root),
        "renderer_sha256": sha256_file(renderer_path),
        "generated_at": generated_at,
        "worktree_head": head,
    }


def load_corpus_lock(lock_path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise WorksheetRenderError(f"corpus lock could not be loaded: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("sources"), dict):
        raise WorksheetRenderError("corpus lock is missing sources")
    return payload


def required_sources_from_lock(lock: Mapping[str, Any]) -> dict[str, Any]:
    sources = lock["sources"]
    if not isinstance(sources, dict):
        raise WorksheetRenderError("corpus lock is missing sources")
    missing = sorted(REQUIRED_POC1_SOURCE_IDS - set(sources))
    if missing:
        raise WorksheetRenderError(
            "corpus lock is missing required POC-1 sources: " + ", ".join(missing)
        )
    return sources


def _scope_text(source: Mapping[str, Any]) -> str:
    chapters = source.get("included_chapters")
    if isinstance(chapters, list) and chapters:
        return "Ch." + ", ".join(str(item) for item in chapters)
    scope = source.get("included_scope")
    if isinstance(scope, str) and scope.strip():
        return scope.strip()
    entry = source.get("canonical_entrypoint")
    if isinstance(entry, str) and entry.strip():
        return entry.strip()
    return "NOT_DECLARED"


def source_row(source_id: str, source: Mapping[str, Any]) -> tuple[str, str, str, str]:
    locator = str(source.get("source_locator") or "NOT_DECLARED")
    revision = str(source.get("revision") or source.get("commit") or "NOT_DECLARED")
    digest = str(source.get("content_sha256") or "NOT_DECLARED")
    short_hash = (
        digest[:8] if digest not in {"NOT_DECLARED", "NOT_APPLICABLE"} else digest
    )
    label = f"{source.get('document') or source.get('repo') or source_id} / {revision}"
    return source_id, f"{label} ({_scope_text(source)})", locator, short_hash


def source_card_lines(source_id: str, source: Mapping[str, Any]) -> list[str]:
    _, label, locator, _digest = source_row(source_id, source)
    digest = str(source.get("content_sha256") or "NOT_DECLARED")
    return [
        f"  - `{source_id}` = {label}",
        f"    locator：`{locator}`",
        f"    content_sha256：`{digest}`",
    ]


def render_worksheet(
    *,
    draft_path: Path = DRAFT_PATH,
    lock_path: Path = LOCK_PATH,
    renderer_path: Path | None = None,
    output_path: Path | None = None,
    generated_at: str | None = None,
    repo_root: Path = ROOT,
) -> str:
    renderer = renderer_path or Path(__file__).resolve()
    if not draft_path.is_file():
        raise WorksheetRenderError(f"draft does not exist: {draft_path}")
    if not lock_path.is_file():
        raise WorksheetRenderError(f"corpus lock does not exist: {lock_path}")

    stamp = generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    provenance = collect_provenance(
        draft_path=draft_path,
        lock_path=lock_path,
        renderer_path=renderer,
        generated_at=stamp,
        repo_root=repo_root,
    )
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    lock = load_corpus_lock(lock_path)
    sources = required_sources_from_lock(lock)
    boundary_list = " / ".join(BOUNDARY_CODES)
    conflict_list = " / ".join(sorted(CONFLICT_BOUNDARY_CODES))

    lines: list[str] = []
    add = lines.append
    add("# POC-1 Gold Oracle 人審工作單")
    add("")
    add("> 這是給人看的 review input 投影，不是正式 acceptance set，也不是 review receipt。")
    add("> Reviewer 簽這份工作單不夠；最後仍須確認真正會被 admission 的 v1.1 JSON。")
    add(
        "> 禁止：把 gold 寫進正式 JSON、建立 `poc1_acceptance_set.json`、"
        "建立 approved receipt、宣稱 GO"
    )
    add("")
    add("## Review-input provenance")
    add("")
    for key, value in provenance.items():
        add(f"- `{key}`: `{value}`")
    add(f"- `draft_schema`: `{draft.get('draft_schema')}`")
    add(f"- `draft_status`: `{draft.get('status')}`")
    add("- `Independent reviewer`: `PENDING_ASSIGNMENT`")
    add("- `USB_SPEC_QA_RAW_ROOT`: `NOT_CONFIGURED`")
    add("")
    add("## 怎麼用")
    add("")
    add("1. 先指定獨立審查人，再開已鎖定 PDF 根目錄（bytes/hash 必須對上 lock）。")
    add("2. 用大綱跳題號。一次只看一張卡，打開對應 PDF，找 section / page，再勾選。")
    add("3. 空白欄位留給審查人；agent 不得憑記憶代填。")
    add("4. 工程側把卡片轉成 v1.1 gold 後，審查人再看一次 manifest diff，最後才簽 receipt。")
    add("")
    add("## 鎖定來源對照（來自 corpus.lock.yaml，不是 renderer 手寫）")
    add("")
    add("| source_id | lock identity / scope | source_locator | SHA-256 前 8 |")
    add("|---|---|---|---|")
    for source_id in sorted(REQUIRED_POC1_SOURCE_IDS):
        row = source_row(source_id, sources[source_id])
        add(f"| `{row[0]}` | {row[1]} | `{row[2]}` | `{row[3]}` |")
    add("")
    add("## 優先先審（PR #23 checklist）")
    add("")
    add("- USB 2.0 Ch.6：L1-006, L2-017")
    add("- USB 3.2 Ch.6/7/9/10：L1-008–011, L2-019–022")
    add("- Hub / PORT_POWER / PORT_LINK_STATE：L1-004, L1-005, L1-011, L3-026, L3-035")
    add("- USB 2.0 → LVS：L3-026, L3-027, L3-037")
    add("- USB4 負控：L4-043, L4-048")
    add("- 其餘全部 L3 / L4")
    add("")

    for question in draft["questions"]:
        qid = question["question_id"]
        extra = []
        if qid in PRIORITY_IDS or question["layer"] in {"L3", "L4"}:
            extra.append("優先")
        if question.get("usb4_negative_control"):
            extra.append("USB4負控")
        suffix = f" （{' · '.join(extra)}）" if extra else ""
        source_ids = question.get("accepted_source_ids") or []
        status = question["expected_status"]
        add("---")
        add("")
        add(f"## {qid}{suffix}")
        add("")
        add(
            f"- 層級：{question['layer']} / {question['priority']} / "
            f"{question['category']}"
        )
        add(f"- 預期行為：{STATUS_ZH[status]} （`{status}`）")
        add(f"- 範圍標籤：`{question['expected_scope']}`")
        add(f"- v1.1 gold 規則：{STATUS_GOLD_RULES[status]}")
        if source_ids:
            add("- 應對規格：")
            for source_id in source_ids:
                lines.extend(source_card_lines(source_id, sources[source_id]))
        else:
            add("- 應對規格：無（棄權題不該引用 Phase 1 正式來源）")
        add("")
        add("### 題目")
        add("")
        add(question["question"])
        add("")
        add("### 審查人勾選")
        add("")
        add("- [ ] 題幹能對到鎖定原文（不是憑印象）")
        add("- [ ] 來源身分 / revision 正確")
        add("- [ ] expected_status 正確（回答 / 衝突 / 棄權）")
        add("- [ ] 題幹沒有暗示不該有的答案或認證結論")
        add("")
        if status == "answer":
            add("請填（answer）：")
            add("")
            add("- 文件 / revision：")
            add("- section：")
            add("- page 或穩定錨點：")
            add("- 原文摘錄（短）：")
            add("- 必答事實（1–3 條）：")
            add("- 禁止宣稱：")
        elif status == "conflict":
            add("請填（conflict，至少兩造）：")
            add("")
            add("- 來源 A 文件 / section / page / 主張：")
            add("- 來源 B 文件 / section / page / 主張：")
            add(f"- 衝突類型（只准這三個）：{conflict_list}")
            add("- 為何不能硬解：")
        else:
            add("請填（abstain）：")
            add("")
            add(f"- 棄權理由碼（只准這六個）：{boundary_list}")
            add("- 為何 Phase 1 corpus 不能答：")
            add("- 不可把 section/page 當成正式答案")
        add("")
        add("- 判定：PASS / REWORD / REJECT")
        add("- 備註：")
        add("")

    add("---")
    add("")
    add("## 封面紀錄（全部審完才填）")
    add("")
    add("- 審查人：PENDING_ASSIGNMENT")
    add("- USB_SPEC_QA_RAW_ROOT：NOT_CONFIGURED")
    add("- 通過題數：0 / 50")
    add("- 正式 receipt：MUST_NOT_CREATE")
    add("- 最終仍須確認：`poc1_acceptance_set.json` v1.1 manifest diff")
    add("")
    text = "\n".join(lines)
    target = output_path or OUT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return text


def main() -> None:
    text = render_worksheet()
    print(OUT_PATH)
    print(f"cards={text.count('### 題目')}")


if __name__ == "__main__":
    main()
