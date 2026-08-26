"""Render a human review worksheet from the POC-1 authoring draft.

This is a projection of review input only. It does not admit the draft,
invent gold, or create a review receipt.
"""

from __future__ import annotations

import hashlib
import html
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
    POC1_CORPUS_SOURCE_IDS,
)
DRAFT_PATH = ROOT / "gv100h" / "spec_qa" / "golden" / "poc1_acceptance_set.draft.json"
LOCK_PATH = ROOT / "gv100h" / "spec_qa" / "contracts" / "corpus.lock.yaml"
OUT_PATH = (
    ROOT / "artifacts" / "reviews" / "gv100h" / "poc1-acceptance-review-worksheet.md"
)
HTML_OUT_PATH = (
    ROOT / "artifacts" / "reviews" / "gv100h" / "poc1-acceptance-review-worksheet.html"
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
    "answer": "直接回答",
    "conflict": "回報衝突，不應自行裁決",
    "abstain": "拒絕回答",
}
REVIEWER_CHECKS_COMMON = (
    "這個問題沒有先把答案透露出來",
    "這個問題沒有暗示產品已經通過測試或認證",
)
STATUS_CHECKS = {
    "answer": (
        "指定的規格文件與版本正確",
        "可以從指定規格中找到答案",
        "這題確實應該直接回答，而不是回報衝突或拒絕回答",
    ),
    "conflict": (
        "兩邊互相競爭的證據都確實存在於指定規格",
        "兩邊談的是同一對象、同一狀態、同一版本脈絡，不是只是範圍不同",
        "兩邊主張無法同時成立，所以這題應該回報衝突，而不是自行給出單一答案",
    ),
    "abstain": (
        "目前指定的 Phase 1 規格裡，沒有足夠、可接受的證據能回答這題",
        "不應為了硬答而去引用指定規格以外的來源",
        "拒絕回答的理由，和實際缺什麼證據相符",
        "這題不該把規範章節或頁碼當成正式答案",
        "這題確實應該拒絕回答，而不是硬答",
    ),
}
VERDICT_LABELS = (
    ("UNSET", "未判定"),
    ("PASS", "題目可用"),
    ("REWORD", "題目需要修改"),
    ("REJECT", "這題不適合使用"),
)
QUESTION_ZH = {
    "DRAFT-L1-001": (
        "依 USB 2.0 Rev 2.0 第 5 章，`transaction` 與 `transfer` 有什麼差別？"
    ),
    "DRAFT-L1-002": (
        "依 USB 2.0 Rev 2.0 第 8 章，control transfer 的 SETUP、DATA（若有）"
        "與 STATUS 各是什麼階段？"
    ),
    "DRAFT-L1-003": (
        "在 USB 2.0 Rev 2.0 第 9 章，標準 Hub request 裡的 `bmRequestType`、"
        "`bRequest`、`wValue` 各代表什麼？"
    ),
    "DRAFT-L1-004": (
        "USB 2.0 Hub Class 用哪個 feature 控制 downstream-port power，"
        "以及用什麼操作去打開這個 feature？"
    ),
    "DRAFT-L1-005": (
        "USB 2.0 Hub Class 給 `PORT_POWER` feature selector 的數值是多少，"
        "穩定引用應指向哪一節？"
    ),
    "DRAFT-L1-006": (
        "USB 2.0 Rev 2.0 Table 6-7 對 Contact Capacitance 的性能要求是什麼？"
        "必須寫出未插合（unmated）條件與單位。"
    ),
    "DRAFT-L1-007": (
        "依 USB 2.0 Rev 2.0 Section 7.1.2.2，對 hub 或可拆線裝置，"
        "在 A 或 B receptacle 量到的 high-speed 差分 rise/fall（10% 到 90%）"
        "最短時間是多少，單位是什麼？"
    ),
    "DRAFT-L1-008": (
        "依 USB 3.2 Rev 1.1 Section 6.9.3，downstream port 可以在哪些"
        "link state 發出 Warm Reset？Table 6-30 給的 tReset 最短與最長是多少？"
    ),
    "DRAFT-L1-009": (
        "依 USB 3.2 Rev 1.1 Table 7-8，x1 與 x2 操作下的 PM_LC_TIMER"
        "逾時值各是多少，單位是什麼？"
    ),
    "DRAFT-L1-010": (
        "依 USB 3.2 Rev 1.1 Section 9.4.2 Get Configuration，裝置在"
        "Address state 應回什麼 configuration value？在 Configured state 又應回什麼？"
    ),
    "DRAFT-L1-011": (
        "依 USB 3.2 Rev 1.1 Figure 10-10 與 Section 10.3.1.9，"
        "PORT_LINK_STATE（PLS）是哪一個 port-status 欄位？"
        "哪個 request 會讓 downstream port 進入 DSPORT.Disabled、link 在 eSS.Disabled？"
    ),
    "DRAFT-L1-012": (
        "在 SuperSpeed Hub LVS Rev 1.15 TD 10.104 Toggle Port Power 中，"
        "先 ClearPortFeature(PORT_POWER)，再在最短 tReset（80 ms）內"
        "SetPortFeature(PORT_POWER) 之後，最長 tReset（120 ms）時"
        "GetPortStatus 必須看到什麼？"
    ),
    "DRAFT-L1-013": (
        "依 USB 2.0 Rev 2.0 Section 11.5.1.2，成功執行 ClearPortFeature"
        "（PORT_POWER）後，Hub port 進入什麼狀態？是哪個 request 造成這個轉換？"
    ),
    "DRAFT-L2-014": (
        "USB 2.0 Rev 2.0 第 5 章對 transaction / transfer 的定義，"
        "可以轉成哪些可驗證的觀察？僅憑這段規格，又有哪些實作行為不能直接推定？"
    ),
    "DRAFT-L2-015": (
        "如何把 USB 2.0 Rev 2.0 第 8 章的 control-transfer packet 規則"
        "做成測試判定依據，同時不要自行加上原文沒有的 retry 行為？"
    ),
    "DRAFT-L2-016": (
        "如何把 USB 2.0 Rev 2.0 第 9 章的 standard-request 欄位做成檢查項，"
        "同時不超出原文能支持的範圍？"
    ),
    "DRAFT-L2-017": (
        "針對 USB 2.0 Rev 2.0 第 6 章的電氣要求，哪些內容可以直接轉成"
        "可量測條件？又有哪些「產品已符合 USB 規範」的結論，不能只靠規格文字就宣稱？"
    ),
    "DRAFT-L2-018": (
        "當 USB 2.0 Rev 2.0 第 7 章某條 timing 陳述的規範效力或量測條件"
        "還不清楚時，驗證人員該怎麼分類與測試？"
    ),
    "DRAFT-L2-019": (
        "如何把 USB 3.2 Rev 1.1 第 6 章的 link 要求對應成 Hub 測試計畫裡的"
        "觀察項，同時不要宣稱已通過認證？"
    ),
    "DRAFT-L2-020": (
        "USB 3.2 Rev 1.1 第 7 章的 protocol 規則能支持什麼結論？"
        "沒有實際 trace 時，又有哪些事情仍然不知道？"
    ),
    "DRAFT-L2-021": (
        "如何把 USB 3.2 Rev 1.1 第 9 章的 descriptor 或 request 要求，"
        "對應成可觀察的 Hub 檢查項？"
    ),
    "DRAFT-L2-022": (
        "如何把 USB 3.2 Rev 1.1 第 10 章的 Hub 要求，與產品合規測試結果分開報告？"
    ),
    "DRAFT-L2-023": (
        "SuperSpeed Hub LVS Rev 1.15 的測試條件本身能支持什麼結論？"
        "要宣稱裝置通過，還需要什麼實際執行證據？"
    ),
    "DRAFT-L2-024": (
        "SuperSpeed Hub LVS Rev 1.15 TD 10.105 Disconnect Device Test"
        "在 U0–U3 disconnect 後要求的 GetPortStatus 觀察，可以怎麼當測試判定？"
        "為什麼寫在程序裡的條件，還不能直接當成產品已通過？"
    ),
    "DRAFT-L2-025": (
        "如何把 USB 2.0 Rev 2.0 Section 11.5.1.2 在 ClearPortFeature"
        "（PORT_POWER）後進入 Powered-off 的要求，轉成可驗證觀察？"
        "僅憑這條要求，又不能宣稱產品已通過？"
    ),
    "DRAFT-L3-026": (
        "如何把 USB 2.0 Hub 的 `PORT_POWER` 要求，對應到 SuperSpeed Hub LVS"
        " Rev 1.15 的相關測試條件？在沒有實際測試結果時，需要哪些證據才能"
        "建立兩者關聯，而不宣稱產品已通過測試？"
    ),
    "DRAFT-L3-027": (
        "如何把 USB 2.0 Rev 2.0 第 7 章的 electrical 或 timing 要求，"
        "連到適用的 SuperSpeed Hub LVS Rev 1.15 測試條件？"
    ),
    "DRAFT-L3-028": (
        "USB 3.2 Rev 1.1 第 6 章哪一條 link 要求可以對上 SuperSpeed Hub LVS"
        " Rev 1.15 的測試項？對上之後，還缺什麼實際執行證據？"
    ),
    "DRAFT-L3-029": (
        "如何把 USB 3.2 Rev 1.1 第 7 章的 protocol 要求，連到觀察到的 Hub"
        " compliance 條件，同時不要把 Rev 1.1 和 LVS Rev 1.15 混成同一份規格？"
    ),
    "DRAFT-L3-030": (
        "如何把 USB 3.2 Rev 1.1 第 9 章的 descriptor 或 request 要求，"
        "連到 Hub descriptor 觀察或 LVS 測試項？"
    ),
    "DRAFT-L3-031": (
        "要組成完整的「規格要求 → 測試條件」證據鏈，需要 USB 3.2 Rev 1.1"
        " 第 10 章的哪一條 Hub 要求，以及 SuperSpeed Hub LVS Rev 1.15 的哪一項條件？"
    ),
    "DRAFT-L3-032": (
        "USB 3.2 Rev 1.1 第 6.9.3 節規定 downstream port 可以在 Table 6-30 的"
        " tReset 區間內發出 Warm Reset；第 10.3.1.9 節把 PORT_LINK_STATE（PLS）"
        "定義成該轉換期間 GetPortStatus 要回報的欄位。哪一項 SuperSpeed Hub LVS"
        " Rev 1.15 測試條件，能把 Warm Reset 要求與觀察到的 PLS 值串成實際執行"
        "證據？要補齊這條證據鏈，還缺什麼？"
    ),
    "DRAFT-L3-033": (
        "USB 2.0 Rev 2.0 Table 11-17 把 Hub Class PORT_POWER feature-selector"
        " 訂成 8，供 ClearPortFeature/SetPortFeature 使用；Table 6-7 則是同一個"
        " connector 的 Contact Capacitance 效能要求。當合規報告用 Table 11-17"
        " 支撐一項 PORT_POWER 控制轉換測試時，Table 6-7 的電容要求是否也是這項"
        "測試的必要證據？還是它屬於另一個獨立範圍的電氣或機械測試？請指出"
        " PORT_POWER 這項主張實際需要哪些引用。"
    ),
    "DRAFT-L3-034": (
        "一項同時涵蓋控制行為與 signaling 的要求，需要哪一對 USB 2.0"
        " firmware-scope 與 signal/electrical-scope 證據？"
    ),
    "DRAFT-L3-035": (
        "如何比較 USB 2.0 與 USB 3.2 的 `PORT_POWER` 要求，同時保留各自文件、"
        "版本與權威來源，而不是把 selector 數值等同於完整行為？"
    ),
    "DRAFT-L3-036": (
        "在同一組跨規格答案與引用裡，如何把 USB 2.0 signal/electrical 證據"
        "與 USB 3.2 protocol 證據分開寫？"
    ),
    "DRAFT-L3-037": (
        "把 USB 2.0 firmware 要求、USB 2.0 signal/electrical 條件，以及"
        " SuperSpeed Hub LVS Rev 1.15 測試條件連起來，需要哪三截證據？"
    ),
    "DRAFT-L3-038": (
        "某 Hub 廠商只因為 SuperSpeed Hub LVS Rev 1.15 TD 10.104 通過，就宣稱"
        "完全符合 USB 3.2 Rev 1.1 第 10.3.1.11 節的 Powered-off-reset 要求。"
        "請完成三個明確步驟：(1) 說明第 10.3.1.11 節在收到 ClearPortFeature"
        "(PORT_POWER) 後實際要求的轉換是什麼；(2) 說明 TD 10.104 實際施加的"
        " stimulus 與觀察的 response 是什麼；(3) 指出第 10.3.1.11 節要求中，"
        "TD 10.104 的執行證據沒有涵蓋到的部分。這個廠商的合規主張是否成立？"
        "為什麼？"
    ),
    "DRAFT-L4-039": (
        "USB 2.0 Table 11-17 把 PORT_POWER 的 Hub Class feature-selector 訂成 8。"
        "USB 3.2 第 10 章把 PORT_POWER（PP）當成與 PORT_LINK_STATE（PLS）不同的"
        "port-status 欄位。這兩段是否構成衝突？請分別指出兩段證據描述的對象、"
        "範圍與權威角色，並說明判斷理由。"
    ),
    "DRAFT-L4-040": (
        "USB 2.0 Section 7.1.2.2 寫 high-speed 差分 rise/fall（10% 到 90%）最短 500 ps。"
        "USB 3.2 Section 10.3.1.9 用 SetPortFeature(PORT_LINK_STATE) eSS.Disabled"
        "進入 DSPORT.Disabled。這兩段是否構成衝突？請分別指出兩段證據描述的對象、"
        "範圍與權威角色，並說明判斷理由。"
    ),
    "DRAFT-L4-041": (
        "SuperSpeed Hub LVS Rev 1.15 TD 10.104 把 ClearPortFeature(PORT_POWER)"
        "當測試刺激。USB 2.0 Section 11.5.1.2 寫規範性的 Powered-off 轉換。"
        "這兩段是否構成衝突？請分別指出兩段證據描述的對象、範圍與權威角色，"
        "並說明判斷理由。"
    ),
    "DRAFT-L4-042": (
        "USB 3.2 Section 10.3.1.11 說收到 ClearPortFeature(PORT_POWER) 時，"
        "downstream port 進入 DSPORT.Powered-off-reset。SuperSpeed Hub LVS"
        " TD 10.104 把同一個 request 當測試刺激。這兩段是否構成衝突？"
        "請分別指出兩段證據描述的對象、範圍與權威角色，並說明判斷理由。"
    ),
    "DRAFT-L4-043": (
        "USB4 Router 完成成功的 Phase 2 連線後，啟用 USB4 tunnel 前必須滿足"
        "哪一條 Router 要求？"
    ),
    "DRAFT-L4-044": (
        "當請求的 USB Hub 行為引用不存在的 99.99 節，且對不到任何已指定規格"
        "章節時，應該回什麼？"
    ),
    "DRAFT-L4-045": (
        "當擬議的 USB Hub 答案依賴目前指定規格裡沒有的權威或檔案時，應該怎麼回？"
    ),
    "DRAFT-L4-046": (
        "當請求的 USB 2.0 主張在指定規格裡找不到章節、頁碼或穩定引用位置時，"
        "應該回什麼？"
    ),
    "DRAFT-L4-047": (
        "對超出目前五類 Phase 1 指定規格的廠商專屬 Hub firmware 問題，"
        "正確回應是什麼？"
    ),
    "DRAFT-L4-048": (
        "USB Power Delivery 來源要支援 20 V / 5 A 合約時，必須在"
        "Programmable Power Supply（PPS）APDO 裡廣告哪些欄位？"
    ),
    "DRAFT-L4-049": (
        "USB 2.0 Section 11.5.1.2 描述 ClearPortFeature(PORT_POWER) 後進入"
        " Powered-off。Section 7.1.2.2 寫 high-speed 差分 rise/fall"
        "（10% 到 90%）最短 500 ps。這兩段是否構成衝突？請分別指出兩段證據"
        "描述的對象、範圍與權威角色，並說明判斷理由。"
    ),
    "DRAFT-L4-050": (
        "當使用者要求把 informative note 提升成規範性 USB Hub 要求，"
        "卻沒有規範原文支持時，應該怎麼做？"
    ),
}
STATUS_GOLD_RULES = {
    "answer": (
        "accepted evidence + 至少 1 條 required claim + required facts + "
        "section anchors；每個 accepted_source_id 至少 1 筆 accepted evidence "
        "與 1 個 section anchor（兩個以上來源時，ID/anchor 須以 source_id: 綁定）；"
        "不可有 competing/boundary evidence 或 boundary_code"
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
    missing = sorted(POC1_CORPUS_SOURCE_IDS - set(sources))
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


def question_plain_zh(question: Mapping[str, Any]) -> str:
    qid = str(question.get("question_id") or "")
    text = QUESTION_ZH.get(qid)
    if not text:
        raise WorksheetRenderError(f"missing Chinese restatement for {qid}")
    return text


def reviewer_checks(status: str) -> tuple[str, ...]:
    try:
        status_items = STATUS_CHECKS[status]
    except KeyError as exc:
        raise WorksheetRenderError(f"unknown expected_status: {status}") from exc
    return status_items + REVIEWER_CHECKS_COMMON


def _source_slot_label(index: int) -> str:
    labels = ("來源 A", "來源 B", "來源 C", "來源 D", "來源 E")
    if 0 <= index < len(labels):
        return labels[index]
    return f"來源 {index + 1}"


def reviewer_fields(
    status: str,
    *,
    conflict_list: str,
    boundary_list: str,
    accepted_source_ids: list[str] | tuple[str, ...] = (),
) -> list[str]:
    if status == "answer":
        source_ids = [
            str(item).strip() for item in accepted_source_ids if str(item).strip()
        ]
        if len(source_ids) >= 2:
            fields: list[str] = []
            for index, source_id in enumerate(source_ids):
                prefix = f"{_source_slot_label(index)}（`{source_id}`）"
                fields.extend(
                    [
                        f"{prefix} 文件",
                        f"{prefix} 章節",
                        f"{prefix} 頁碼",
                        f"{prefix} 支持答案的規格原文",
                        f"{prefix} 這份證據支持的主張",
                    ]
                )
            if len(source_ids) == 2:
                relation = "兩者"
            elif len(source_ids) == 3:
                relation = "三者"
            else:
                relation = "各來源"
            fields.extend(
                [
                    f"{relation}是否同一對象",
                    f"{relation}是否同一適用範圍",
                    f"{relation}權威角色是否相同",
                    f"{relation}關係（mapping / conflict / independent scope）",
                    "根據這份證據，哪些結論不能下",
                ]
            )
            return fields
        return [
            "規格章節",
            "頁碼",
            "支持答案的規格原文",
            "正確答案至少要包含哪些重點",
            "根據這份證據，哪些結論不能下",
        ]
    if status == "conflict":
        return [
            "來源 A 文件 / 章節 / 頁碼 / 主張",
            "來源 B 文件 / 章節 / 頁碼 / 主張",
            f"衝突類型（只准這三個）：{conflict_list}",
            "為什麼不能自己選一邊當答案",
        ]
    return [
        f"拒絕回答的理由碼（只准這六個）：{boundary_list}",
        "為什麼目前指定的規格答不了",
        "不要把章節或頁碼當成正式答案",
    ]


def verdict_line() -> str:
    human = " / ".join(label for _code, label in VERDICT_LABELS)
    machine = " / ".join(code for code, _label in VERDICT_LABELS)
    return f"結果：{human}（機器值 {machine}）"


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
    add("1. 先指定獨立審查人，再開指定規格 PDF 根目錄（bytes/hash 必須對上 lock）。")
    add("2. 用大綱跳題號。一次只看一張卡，先看「這題在問什麼」，再對英文原題與 PDF。")
    add("3. 空白欄位留給審查人；agent 不得憑記憶代填。")
    add("4. 工程側把卡片轉成 v1.1 gold 後，審查人再看一次 manifest diff，最後才簽 receipt。")
    add("")
    add("## 指定規格對照（來自 corpus.lock.yaml，不是 renderer 手寫）")
    add("")
    add("| source_id | lock identity / scope | source_locator | SHA-256 前 8 |")
    add("|---|---|---|---|")
    for source_id in sorted(POC1_CORPUS_SOURCE_IDS):
        row = source_row(source_id, sources[source_id])
        add(f"| `{row[0]}` | {row[1]} | `{row[2]}` | `{row[3]}` |")
    add("")
    add("## 優先先審（PR #23 checklist）")
    add("")
    add("- USB 2.0 Ch.6：L1-006, L2-017")
    add("- USB 3.2 Ch.6/7/9/10：L1-008–011, L2-019–022")
    add("- Hub / PORT_POWER / PORT_LINK_STATE：L1-004, L1-005, L1-011, L3-026, L3-035")
    add("- USB 2.0 → LVS：L3-026, L3-027, L3-037")
    add("- USB4 負控：L4-043；USB PD 負控：L4-048")
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
        add(f"**這題預期：{STATUS_ZH[status]}**")
        add("")
        add(
            f"- 層級：{question['layer']} / {question['priority']} / "
            f"{question['category']}"
        )
        add(f"- 範圍：`{question['expected_scope']}`")
        add("")
        add("### 要查哪份規格？")
        add("")
        if source_ids:
            for source_id in source_ids:
                lines.extend(source_card_lines(source_id, sources[source_id]))
        else:
            add("- 無。這題不該引用目前指定的 Phase 1 正式來源")
        add("")
        add("### 這題在問什麼？")
        add("")
        add(question_plain_zh(question))
        add("")
        add("### 英文原題")
        add("")
        add(question["question"])
        add("")
        add("### 請確認")
        add("")
        for check in reviewer_checks(status):
            add(f"- [ ] {check}")
        add("")
        add("### 請填")
        add("")
        for field in reviewer_fields(
            status,
            conflict_list=conflict_list,
            boundary_list=boundary_list,
            accepted_source_ids=source_ids,
        ):
            add(f"- {field}：")
        add(f"- {verdict_line()}")
        add("- 備註：")
        add("")
        add("<details>")
        add("<summary>機器規則（admission 用，審查時可略過）</summary>")
        add("")
        add(f"- expected_status：`{status}`")
        add(f"- v1.1 gold 規則：{STATUS_GOLD_RULES[status]}")
        add("</details>")
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


def _h(value: Any) -> str:
    return html.escape(str(value), quote=True)


def render_html_worksheet(
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
    questions = draft["questions"]

    nav_items: list[str] = []
    cards: list[str] = []
    for question in questions:
        qid = question["question_id"]
        status = question["expected_status"]
        extra = []
        if qid in PRIORITY_IDS or question["layer"] in {"L3", "L4"}:
            extra.append("優先")
        if question.get("usb4_negative_control"):
            extra.append("USB4負控")
        source_ids = question.get("accepted_source_ids") or []
        nav_items.append(
            f'<a href="#{_h(qid)}" class="nav-{_h(status)}">{_h(qid)}</a>'
        )
        source_html = ["<ul class='sources'>"]
        if source_ids:
            for source_id in source_ids:
                _, label, locator, _digest = source_row(source_id, sources[source_id])
                digest = str(sources[source_id].get("content_sha256") or "NOT_DECLARED")
                source_html.append(
                    "<li>"
                    f"<code>{_h(source_id)}</code> = {_h(label)}<br>"
                    f"locator：<code>{_h(locator)}</code><br>"
                    f"content_sha256：<code>{_h(digest)}</code>"
                    "</li>"
                )
        else:
            source_html.append("<li>無。這題不該引用目前指定的 Phase 1 正式來源</li>")
        source_html.append("</ul>")
        fields = reviewer_fields(
            status,
            conflict_list=conflict_list,
            boundary_list=boundary_list,
            accepted_source_ids=source_ids,
        )
        field_html = "".join(
            "<label>"
            f"<span>{_h(field)}</span>"
            "<textarea rows='2'></textarea>"
            "</label>"
            for field in fields
        )
        verdict_html = "".join(
            f"<option value='{_h(code)}'>{_h(label)}</option>"
            for code, label in VERDICT_LABELS
        )
        cards.append(
            "<article class='card' id='"
            + _h(qid)
            + "' data-status='"
            + _h(status)
            + "' data-layer='"
            + _h(question["layer"])
            + "'>"
            "<header>"
            f"<h2>{_h(qid)}</h2>"
            + "".join(f"<span class='tag'>{_h(item)}</span>" for item in extra)
            + f"<span class='status status-{_h(status)}'>這題預期：{_h(STATUS_ZH[status])}</span>"
            "</header>"
            "<dl>"
            f"<div><dt>層級</dt><dd>{_h(question['layer'])} / {_h(question['priority'])} / {_h(question['category'])}</dd></div>"
            f"<div><dt>範圍</dt><dd><code>{_h(question['expected_scope'])}</code></dd></div>"
            "</dl>"
            "<h3>要查哪份規格？</h3>"
            + "".join(source_html)
            + "<h3>這題在問什麼？</h3>"
            f"<p class=\"plain\">{_h(question_plain_zh(question))}</p>"
            "<h3>英文原題</h3>"
            f"<p class=\"question\">{_h(question['question'])}</p>"
            "<h3>請確認</h3>"
            "<div class='checks'>"
            + "".join(
                f"<label class='check'><input type='checkbox'> <span>{_h(check)}</span></label>"
                for check in reviewer_checks(status)
            )
            + "</div>"
            "<h3>請填</h3>"
            f"<form>{field_html}"
            "<label><span>結果</span>"
            f"<select>{verdict_html}</select></label>"
            "<label><span>備註</span><textarea rows='3'></textarea></label>"
            "</form>"
            "<details class='machine'>"
            "<summary>機器規則（admission 用，審查時可略過）</summary>"
            f"<p><code>expected_status</code> = <code>{_h(status)}</code></p>"
            f"<p>{_h(STATUS_GOLD_RULES[status])}</p>"
            "</details>"
            "</article>"
        )

    source_rows = []
    for source_id in sorted(POC1_CORPUS_SOURCE_IDS):
        row = source_row(source_id, sources[source_id])
        source_rows.append(
            "<tr>"
            f"<td><code>{_h(row[0])}</code></td>"
            f"<td>{_h(row[1])}</td>"
            f"<td><code>{_h(row[2])}</code></td>"
            f"<td><code>{_h(row[3])}</code></td>"
            "</tr>"
        )
    provenance_rows = "".join(
        f"<tr><th><code>{_h(key)}</code></th><td><code>{_h(value)}</code></td></tr>"
        for key, value in provenance.items()
    )
    extra_rows = (
        ("draft_schema", draft.get("draft_schema")),
        ("draft_status", draft.get("status")),
        ("Independent reviewer", "PENDING_ASSIGNMENT"),
        ("USB_SPEC_QA_RAW_ROOT", "NOT_CONFIGURED"),
    )
    provenance_rows += "".join(
        f"<tr><th><code>{_h(key)}</code></th><td><code>{_h(value)}</code></td></tr>"
        for key, value in extra_rows
    )

    page = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>POC-1 Gold Oracle 人審工作單</title>
<style>
:root {{
  --bg: #f4f1ea;
  --ink: #1f2430;
  --muted: #5c6573;
  --card: #fffdf8;
  --line: #d8d0c4;
  --answer: #1f6b4a;
  --conflict: #9a4a12;
  --abstain: #5b4b8a;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  color: var(--ink);
  background: var(--bg);
  font: 16px/1.55 "Iwanami", "Source Han Serif TC", "Noto Serif TC", "PMingLiU", serif;
}}
.wrap {{ display: grid; grid-template-columns: 220px 1fr; min-height: 100vh; }}
nav {{
  position: sticky; top: 0; height: 100vh; overflow: auto;
  padding: 1rem 0.8rem; background: #ece6db; border-right: 1px solid var(--line);
}}
nav a {{ display: block; color: inherit; text-decoration: none; padding: 0.18rem 0.4rem; font-size: 0.86rem; }}
nav a.nav-answer {{ border-left: 3px solid var(--answer); }}
nav a.nav-conflict {{ border-left: 3px solid var(--conflict); }}
nav a.nav-abstain {{ border-left: 3px solid var(--abstain); }}
main {{ padding: 1.4rem 1.6rem 4rem; max-width: 980px; }}
.banner, .card, table {{
  background: var(--card); border: 1px solid var(--line); border-radius: 10px;
}}
.banner {{ padding: 1rem 1.1rem; margin-bottom: 1rem; }}
.banner p {{ margin: 0.3rem 0; color: var(--muted); }}
h1, h2, h3 {{ font-family: "Iwanami", "Source Han Sans TC", "Noto Sans TC", "Microsoft JhengHei", sans-serif; }}
h1 {{ margin-top: 0; font-size: 1.7rem; }}
table {{ width: 100%; border-collapse: collapse; margin: 0.8rem 0 1.2rem; font-size: 0.92rem; }}
th, td {{ border-bottom: 1px solid var(--line); padding: 0.4rem 0.5rem; text-align: left; vertical-align: top; }}
.card {{ padding: 1rem 1.1rem; margin: 1.1rem 0; }}
.card header {{ display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: center; }}
.card h2 {{ margin: 0 0.4rem 0 0; }}
.tag, .status {{
  font-family: "Source Han Sans TC", "Noto Sans TC", "Microsoft JhengHei", sans-serif;
  font-size: 0.78rem; padding: 0.15rem 0.45rem; border-radius: 999px; border: 1px solid var(--line);
}}
.status-answer {{ color: var(--answer); border-color: var(--answer); }}
.status-conflict {{ color: var(--conflict); border-color: var(--conflict); }}
.status-abstain {{ color: var(--abstain); border-color: var(--abstain); }}
.plain {{ font-size: 1.12rem; }}
.question {{ color: var(--muted); font-size: 0.98rem; }}
.checks, form {{ display: grid; gap: 0.55rem; }}
.checks .check {{ display: flex; align-items: flex-start; gap: 0.45rem; }}
.checks .check input {{ margin-top: 0.28rem; flex: 0 0 auto; }}
form label {{ display: grid; gap: 0.2rem; }}
.machine {{ margin-top: 0.9rem; color: var(--muted); font-size: 0.92rem; }}
textarea, select {{ width: 100%; font: inherit; padding: 0.4rem; }}
code {{ font-family: Consolas, "Sarasa Mono TC", monospace; font-size: 0.86em; }}
@media print {{
  nav {{ display: none; }}
  .wrap {{ display: block; }}
  .card {{ break-inside: avoid; }}
}}
</style>
</head>
<body>
<div class="wrap">
<nav>
<strong>50 題目錄</strong>
{"".join(nav_items)}
</nav>
<main>
<section class="banner">
<h1>POC-1 Gold Oracle 人審工作單</h1>
<p>每題先看中文「這題在問什麼」，英文原題仍是正式題目。USB 專有名詞不硬翻。</p>
<p>這是給人看的 review input 投影，不是正式 acceptance set，也不是 review receipt。</p>
<p>Reviewer 簽這份工作單不夠；最後仍須確認真正會被 admission 的 v1.1 JSON。</p>
<p>禁止：把 gold 寫進正式 JSON、建立 poc1_acceptance_set.json、建立 approved receipt、宣稱 GO。</p>
<p>瀏覽器勾選只留在本機頁面，不會寫回倉庫。</p>
</section>
<h2>Review-input provenance</h2>
<table>{provenance_rows}</table>
<h2>指定規格對照</h2>
<table>
<tr><th>source_id</th><th>lock identity / scope</th><th>source_locator</th><th>SHA-256 前 8</th></tr>
{"".join(source_rows)}
</table>
<h2>優先先審</h2>
<ul>
<li>USB 2.0 Ch.6：L1-006, L2-017</li>
<li>USB 3.2 Ch.6/7/9/10：L1-008–011, L2-019–022</li>
<li>Hub / PORT_POWER / PORT_LINK_STATE：L1-004, L1-005, L1-011, L3-026, L3-035</li>
<li>USB 2.0 → LVS：L3-026, L3-027, L3-037</li>
<li>USB4 負控：L4-043；USB PD 負控：L4-048</li>
<li>其餘全部 L3 / L4</li>
</ul>
{"".join(cards)}
<section class="card">
<h2>封面紀錄（全部審完才填）</h2>
<p>審查人：PENDING_ASSIGNMENT</p>
<p>USB_SPEC_QA_RAW_ROOT：NOT_CONFIGURED</p>
<p>通過題數：0 / 50</p>
<p>正式 receipt：MUST_NOT_CREATE</p>
<p>最終仍須確認：poc1_acceptance_set.json v1.1 manifest diff</p>
</section>
</main>
</div>
</body>
</html>
"""
    target = output_path or HTML_OUT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page, encoding="utf-8")
    return page


def main() -> None:
    text = render_worksheet()
    html_text = render_html_worksheet()
    print(OUT_PATH)
    print(HTML_OUT_PATH)
    print(f"cards={text.count('### 這題在問什麼？')}")
    print(f"html_cards={html_text.count('class=\"question\"')}")


if __name__ == "__main__":
    main()
