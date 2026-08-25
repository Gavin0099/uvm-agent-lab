# POC-1 Gold Oracle 人審工作單

> 這是給人看的 review input 投影，不是正式 acceptance set，也不是 review receipt。
> Reviewer 簽這份工作單不夠；最後仍須確認真正會被 admission 的 v1.1 JSON。
> 禁止：把 gold 寫進正式 JSON、建立 `poc1_acceptance_set.json`、建立 approved receipt、宣稱 GO

## Review-input provenance

- `source_draft_path`: `gv100h/spec_qa/golden/poc1_acceptance_set.draft.json`
- `source_draft_git_commit`: `8eea4730d4b1c9baf73dccf60bbbfeadc64746b5`
- `source_draft_git_blob`: `df9a0135aaf2fca334c309f6ed8ab7aac0a9dede`
- `source_draft_sha256`: `3a9306db7b910e1f8d813dc64ae7b9d77e3771813a4575f7202fbd18cdafbe28`
- `corpus_lock_path`: `gv100h/spec_qa/contracts/corpus.lock.yaml`
- `corpus_lock_sha256`: `f51cc94a9cb478071122a3682cd1386983aa84a08b8304d3bfe7b77375f90847`
- `corpus_lock_git_blob`: `97c1dc714f5fc72ddeb82bc5fb7538dce5b8e8e8`
- `renderer_path`: `scripts/render_poc1_review_worksheet.py`
- `renderer_git_blob`: `98649523cbec14bce2f584602dd5a1b14ef33482`
- `renderer_sha256`: `5eed8ea8e36460d4f6321a7655deb6a4971c7ccc2ffdf784957d4ce44ab61d21`
- `generated_at`: `2026-08-25T08:31:27+00:00`
- `worktree_head`: `8eea4730d4b1c9baf73dccf60bbbfeadc64746b5`
- `draft_schema`: `poc1_spec_qa_acceptance_set_draft.v0.1`
- `draft_status`: `draft_not_admitted`
- `Independent reviewer`: `PENDING_ASSIGNMENT`
- `USB_SPEC_QA_RAW_ROOT`: `NOT_CONFIGURED`

## 怎麼用

1. 先指定獨立審查人，再開指定規格 PDF 根目錄（bytes/hash 必須對上 lock）。
2. 用大綱跳題號。一次只看一張卡，先看「這題在問什麼」，再對英文原題與 PDF。
3. 空白欄位留給審查人；agent 不得憑記憶代填。
4. 工程側把卡片轉成 v1.1 gold 後，審查人再看一次 manifest diff，最後才簽 receipt。

## 指定規格對照（來自 corpus.lock.yaml，不是 renderer 手寫）

| source_id | lock identity / scope | source_locator | SHA-256 前 8 |
|---|---|---|---|
| `hub_reference` | Gavin0099/usb-if-hub-spec-reference / 808f23c24bd8651da9cdcd63ea8669126917a379 (exports/hub_governed_surface_manifest.yaml) | `repo://Gavin0099/usb-if-hub-spec-reference@808f23c24bd8651da9cdcd63ea8669126917a379` | `c774c4c3` |
| `superspeed_hub_lvs` | SuperSpeed Hub LVS Test Specification / Rev 1.15 (Hub compliance test items and conditions) | `env://USB_SPEC_QA_RAW_ROOT/superspeed_hub_lvs/SSHUB_LVS_Specification_2019_11_21.pdf` | `f6c647c1` |
| `usb20_fw` | USB 2.0 Specification / 2.0 (Ch.5, 8-11) | `env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf` | `d39698a3` |
| `usb20_se` | USB 2.0 Specification / 2.0 (Ch.6-7) | `env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf` | `d39698a3` |
| `usb32` | USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10) | `env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf` | `26e025a5` |

## 優先先審（PR #23 checklist）

- USB 2.0 Ch.6：L1-006, L2-017
- USB 3.2 Ch.6/7/9/10：L1-008–011, L2-019–022
- Hub / PORT_POWER / PORT_LINK_STATE：L1-004, L1-005, L1-011, L3-026, L3-035
- USB 2.0 → LVS：L3-026, L3-027, L3-037
- USB4 負控：L4-043, L4-048
- 其餘全部 L3 / L4

---

## DRAFT-L1-001

**這題預期：直接回答**

- 層級：L1 / P0 / single_spec_fact
- 範圍：`USB_2_0`

### 要查哪份規格？

  - `usb20_fw` = USB 2.0 Specification / 2.0 (Ch.5, 8-11)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`

### 這題在問什麼？

依 USB 2.0 Rev 2.0 第 5 章，`transaction` 與 `transfer` 有什麼差別？

### 英文原題

According to the USB 2.0 Revision 2.0 Chapter 5 data-flow terminology, what is the distinction between a transaction and a transfer?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L1-002

**這題預期：直接回答**

- 層級：L1 / P0 / single_spec_fact
- 範圍：`USB_2_0`

### 要查哪份規格？

  - `usb20_fw` = USB 2.0 Specification / 2.0 (Ch.5, 8-11)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`

### 這題在問什麼？

依 USB 2.0 Rev 2.0 第 8 章，control transfer 的 SETUP、DATA（若有）與 STATUS 各是什麼階段？

### 英文原題

According to USB 2.0 Revision 2.0 Chapter 8, what are the SETUP, DATA when present, and STATUS stages of a control transfer?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L1-003

**這題預期：直接回答**

- 層級：L1 / P0 / single_spec_fact
- 範圍：`USB_2_0`

### 要查哪份規格？

  - `usb20_fw` = USB 2.0 Specification / 2.0 (Ch.5, 8-11)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`

### 這題在問什麼？

在 USB 2.0 Rev 2.0 第 9 章，標準 Hub request 裡的 `bmRequestType`、`bRequest`、`wValue` 各代表什麼？

### 英文原題

In USB 2.0 Revision 2.0 Chapter 9, what do bmRequestType, bRequest, and wValue identify in a standard Hub request?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L1-004 （優先）

**這題預期：直接回答**

- 層級：L1 / P0 / single_spec_fact
- 範圍：`USB_2_0`

### 要查哪份規格？

  - `usb20_fw` = USB 2.0 Specification / 2.0 (Ch.5, 8-11)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`

### 這題在問什麼？

USB 2.0 Hub Class 用哪個 feature 控制 downstream-port power，以及用什麼操作去打開這個 feature？

### 英文原題

Which USB 2.0 Hub Class feature controls downstream-port power, and what operation invokes that feature?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L1-005 （優先）

**這題預期：直接回答**

- 層級：L1 / P0 / single_spec_fact
- 範圍：`USB_2_0`

### 要查哪份規格？

  - `usb20_fw` = USB 2.0 Specification / 2.0 (Ch.5, 8-11)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`

### 這題在問什麼？

USB 2.0 Hub Class 給 `PORT_POWER` feature selector 的數值是多少，穩定引用應指向哪一節？

### 英文原題

What numeric value does the USB 2.0 Hub Class assign to the PORT_POWER feature selector, and which USB 2.0 section is the stable citation anchor?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L1-006 （優先）

**這題預期：直接回答**

- 層級：L1 / P0 / single_spec_fact
- 範圍：`USB_2_0`

### 要查哪份規格？

  - `usb20_se` = USB 2.0 Specification / 2.0 (Ch.6-7)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`

### 這題在問什麼？

USB 2.0 Rev 2.0 第 6 章裡，哪一個差分訊號參數在引用數值時，必須連同量測條件與單位一起說明？

### 英文原題

Which USB 2.0 Revision 2.0 Chapter 6 differential-signaling parameter must be cited with its measurement condition and units?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L1-007

**這題預期：直接回答**

- 層級：L1 / P0 / single_spec_fact
- 範圍：`USB_2_0`

### 要查哪份規格？

  - `usb20_se` = USB 2.0 Specification / 2.0 (Ch.6-7)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`

### 這題在問什麼？

USB 2.0 Rev 2.0 第 7 章裡，哪一條 timing 要求在報告時，必須連同量測條件與單位？

### 英文原題

Which USB 2.0 Revision 2.0 Chapter 7 timing requirement must be reported with its measurement condition and units?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L1-008 （優先）

**這題預期：直接回答**

- 層級：L1 / P0 / single_spec_fact
- 範圍：`USB_3_X`

### 要查哪份規格？

  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`

### 這題在問什麼？

評估 Hub link transition 時，應引用 USB 3.2 Rev 1.1 第 6 章的哪一條 link-state 或 signaling 規則？

### 英文原題

Which USB 3.2 Revision 1.1 Chapter 6 link-state or signaling rule must be cited when evaluating a Hub link transition?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L1-009 （優先）

**這題預期：直接回答**

- 層級：L1 / P0 / single_spec_fact
- 範圍：`USB_3_X`

### 要查哪份規格？

  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`

### 這題在問什麼？

USB 3.2 Rev 1.1 第 7 章裡，哪一條 protocol 或 ordered-set 規則適用於 Hub link exchange？

### 英文原題

Which USB 3.2 Revision 1.1 Chapter 7 protocol or ordered-set rule applies to a Hub link exchange?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L1-010 （優先）

**這題預期：直接回答**

- 層級：L1 / P0 / single_spec_fact
- 範圍：`USB_3_X`

### 要查哪份規格？

  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`

### 這題在問什麼？

USB 3.2 Rev 1.1 第 9 章裡，哪個 descriptor 或 standard-request 欄位用來指出正在評估的 device state？

### 英文原題

Which USB 3.2 Revision 1.1 Chapter 9 descriptor or standard-request field identifies the device state being evaluated?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L1-011 （優先）

**這題預期：直接回答**

- 層級：L1 / P0 / single_spec_fact
- 範圍：`USB_3_X`

### 要查哪份規格？

  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`

### 這題在問什麼？

USB 3.2 Rev 1.1 第 10 章裡，哪一條 Hub descriptor 或 feature-selector規則管 downstream-port state？

### 英文原題

What USB 3.2 Revision 1.1 Chapter 10 Hub descriptor or feature-selector rule governs downstream-port state?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L1-012

**這題預期：直接回答**

- 層級：L1 / P0 / single_spec_fact
- 範圍：`USB_HUB_LVS`

### 要查哪份規格？

  - `superspeed_hub_lvs` = SuperSpeed Hub LVS Test Specification / Rev 1.15 (Hub compliance test items and conditions)
    locator：`env://USB_SPEC_QA_RAW_ROOT/superspeed_hub_lvs/SSHUB_LVS_Specification_2019_11_21.pdf`
    content_sha256：`f6c647c1acdcaf861555bcef481a104cf72958b787a2db6baab3de0a284440fb`

### 這題在問什麼？

對 SuperSpeed Hub LVS Rev 1.15 的一項 Hub 測試，答案必須抽出並引用哪些前置條件、刺激與預期觀察？

### 英文原題

For a SuperSpeed Hub LVS Revision 1.15 Hub test item, which precondition, stimulus, and expected observation must the answer extract and cite?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L1-013

**這題預期：直接回答**

- 層級：L1 / P0 / single_spec_fact
- 範圍：`USB_HUB_COMMON`

### 要查哪份規格？

  - `hub_reference` = Gavin0099/usb-if-hub-spec-reference / 808f23c24bd8651da9cdcd63ea8669126917a379 (exports/hub_governed_surface_manifest.yaml)
    locator：`repo://Gavin0099/usb-if-hub-spec-reference@808f23c24bd8651da9cdcd63ea8669126917a379`
    content_sha256：`c774c4c31b088348a4f2deaae2e0d8448f083a1a9793d91c59fc719de3536083`

### 這題在問什麼？

這份 governed structured Hub reference 授權哪些結論，又有哪些firmware、electrical、LVS 或認證結論超出它自己寫明的範圍？

### 英文原題

Which claims does the governed structured Hub reference authorize, and which firmware, electrical, LVS, or certification claims are outside its stated boundary?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L2-014

**這題預期：直接回答**

- 層級：L2 / P0 / engineering_interpretation
- 範圍：`USB_2_0`

### 要查哪份規格？

  - `usb20_fw` = USB 2.0 Specification / 2.0 (Ch.5, 8-11)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`

### 這題在問什麼？

USB 2.0 Rev 2.0 第 5 章對 transaction / transfer 的定義，可以轉成哪些可驗證的觀察？僅憑這段規格，又有哪些實作行為不能直接推定？

### 英文原題

How should the USB 2.0 Revision 2.0 Chapter 5 transaction/transfer requirement become a verifiable observation, and which implementation conclusion is not licensed?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L2-015

**這題預期：直接回答**

- 層級：L2 / P0 / engineering_interpretation
- 範圍：`USB_2_0`

### 要查哪份規格？

  - `usb20_fw` = USB 2.0 Specification / 2.0 (Ch.5, 8-11)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`

### 這題在問什麼？

如何把 USB 2.0 Rev 2.0 第 8 章的 control-transfer packet 規則做成測試判定依據，同時不要自行加上原文沒有的 retry 行為？

### 英文原題

How should the USB 2.0 Revision 2.0 Chapter 8 control-transfer packet rule become a test oracle without adding retry behavior absent from the source?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L2-016

**這題預期：直接回答**

- 層級：L2 / P0 / engineering_interpretation
- 範圍：`USB_2_0`

### 要查哪份規格？

  - `usb20_fw` = USB 2.0 Specification / 2.0 (Ch.5, 8-11)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`

### 這題在問什麼？

如何把 USB 2.0 Rev 2.0 第 9 章的 standard-request 欄位做成檢查項，同時不超出原文能支持的範圍？

### 英文原題

How should the USB 2.0 Revision 2.0 Chapter 9 standard-request fields become an assertion while preserving the source citation boundary?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L2-017 （優先）

**這題預期：直接回答**

- 層級：L2 / P0 / engineering_interpretation
- 範圍：`USB_2_0`

### 要查哪份規格？

  - `usb20_se` = USB 2.0 Specification / 2.0 (Ch.6-7)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`

### 這題在問什麼？

針對 USB 2.0 Rev 2.0 第 6 章的電氣要求，哪些內容可以直接轉成可量測條件？又有哪些「產品已符合 USB 規範」的結論，不能只靠規格文字就宣稱？

### 英文原題

How should the USB 2.0 Revision 2.0 Chapter 6 electrical requirement be separated into a measurable condition and an unsupported product-compliance claim?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L2-018

**這題預期：直接回答**

- 層級：L2 / P0 / engineering_interpretation
- 範圍：`USB_2_0`

### 要查哪份規格？

  - `usb20_se` = USB 2.0 Specification / 2.0 (Ch.6-7)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`

### 這題在問什麼？

當 USB 2.0 Rev 2.0 第 7 章某條 timing 陳述的規範效力或量測條件還不清楚時，驗證人員該怎麼分類與測試？

### 英文原題

How should a verifier classify and test a USB 2.0 Revision 2.0 Chapter 7 timing statement when its normative force or measurement condition is unresolved?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L2-019 （優先）

**這題預期：直接回答**

- 層級：L2 / P0 / engineering_interpretation
- 範圍：`USB_3_X`

### 要查哪份規格？

  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`

### 這題在問什麼？

如何把 USB 3.2 Rev 1.1 第 6 章的 link 要求對應成 Hub 測試計畫裡的觀察項，同時不要宣稱已通過認證？

### 英文原題

How should a verifier map the USB 3.2 Revision 1.1 Chapter 6 link requirement to a Hub test-plan observation without claiming certification?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L2-020 （優先）

**這題預期：直接回答**

- 層級：L2 / P0 / engineering_interpretation
- 範圍：`USB_3_X`

### 要查哪份規格？

  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`

### 這題在問什麼？

USB 3.2 Rev 1.1 第 7 章的 protocol 規則能支持什麼結論？沒有實際 trace 時，又有哪些事情仍然不知道？

### 英文原題

What conclusion is justified by the USB 3.2 Revision 1.1 Chapter 7 protocol rule, and what remains unknown without an observed trace?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L2-021 （優先）

**這題預期：直接回答**

- 層級：L2 / P0 / engineering_interpretation
- 範圍：`USB_3_X`

### 要查哪份規格？

  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`

### 這題在問什麼？

如何把 USB 3.2 Rev 1.1 第 9 章的 descriptor 或 request 要求，對應成可觀察的 Hub 檢查項？

### 英文原題

How should the USB 3.2 Revision 1.1 Chapter 9 descriptor or request requirement be mapped to an observable Hub check?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L2-022 （優先）

**這題預期：直接回答**

- 層級：L2 / P0 / engineering_interpretation
- 範圍：`USB_3_X`

### 要查哪份規格？

  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`

### 這題在問什麼？

如何把 USB 3.2 Rev 1.1 第 10 章的 Hub 要求，與產品合規測試結果分開報告？

### 英文原題

How should the USB 3.2 Revision 1.1 Chapter 10 Hub requirement be reported separately from a product-compliance test result?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L2-023

**這題預期：直接回答**

- 層級：L2 / P0 / engineering_interpretation
- 範圍：`USB_HUB_LVS`

### 要查哪份規格？

  - `superspeed_hub_lvs` = SuperSpeed Hub LVS Test Specification / Rev 1.15 (Hub compliance test items and conditions)
    locator：`env://USB_SPEC_QA_RAW_ROOT/superspeed_hub_lvs/SSHUB_LVS_Specification_2019_11_21.pdf`
    content_sha256：`f6c647c1acdcaf861555bcef481a104cf72958b787a2db6baab3de0a284440fb`

### 這題在問什麼？

SuperSpeed Hub LVS Rev 1.15 的測試條件本身能支持什麼結論？要宣稱裝置通過，還需要什麼實際執行證據？

### 英文原題

What conclusion can be drawn from a SuperSpeed Hub LVS Revision 1.15 test condition, and what execution evidence would be required to claim a device passed?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L2-024

**這題預期：直接回答**

- 層級：L2 / P0 / engineering_interpretation
- 範圍：`USB_HUB_LVS`

### 要查哪份規格？

  - `superspeed_hub_lvs` = SuperSpeed Hub LVS Test Specification / Rev 1.15 (Hub compliance test items and conditions)
    locator：`env://USB_SPEC_QA_RAW_ROOT/superspeed_hub_lvs/SSHUB_LVS_Specification_2019_11_21.pdf`
    content_sha256：`f6c647c1acdcaf861555bcef481a104cf72958b787a2db6baab3de0a284440fb`

### 這題在問什麼？

SuperSpeed Hub LVS Rev 1.15 程序裡，哪些是規格自己定義的條件，哪些「產品通過」的說法還需要另外的執行證據？

### 英文原題

Which parts of a SuperSpeed Hub LVS Revision 1.15 procedure are source-defined conditions, and which product-pass statements require separate execution evidence?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L2-025

**這題預期：直接回答**

- 層級：L2 / P0 / engineering_interpretation
- 範圍：`USB_HUB_COMMON`

### 要查哪份規格？

  - `hub_reference` = Gavin0099/usb-if-hub-spec-reference / 808f23c24bd8651da9cdcd63ea8669126917a379 (exports/hub_governed_surface_manifest.yaml)
    locator：`repo://Gavin0099/usb-if-hub-spec-reference@808f23c24bd8651da9cdcd63ea8669126917a379`
    content_sha256：`c774c4c31b088348a4f2deaae2e0d8448f083a1a9793d91c59fc719de3536083`

### 這題在問什麼？

工程師可以怎麼把這份 governed structured Hub reference 當索引用，同時記得它不是完整 USB 規格？

### 英文原題

How should an engineer use the governed structured Hub reference as an index while preserving its boundary that it is not the complete USB specification?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L3-026 （優先）

**這題預期：直接回答**

- 層級：L3 / P1 / cross_document
- 範圍：`USB_2_0_TO_LVS`

### 要查哪份規格？

  - `usb20_fw` = USB 2.0 Specification / 2.0 (Ch.5, 8-11)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`
  - `superspeed_hub_lvs` = SuperSpeed Hub LVS Test Specification / Rev 1.15 (Hub compliance test items and conditions)
    locator：`env://USB_SPEC_QA_RAW_ROOT/superspeed_hub_lvs/SSHUB_LVS_Specification_2019_11_21.pdf`
    content_sha256：`f6c647c1acdcaf861555bcef481a104cf72958b787a2db6baab3de0a284440fb`

### 這題在問什麼？

如何把 USB 2.0 Hub 的 `PORT_POWER` 要求，對應到 SuperSpeed Hub LVS Rev 1.15 的相關測試條件？在沒有實際測試結果時，需要哪些證據才能建立兩者關聯，而不宣稱產品已通過測試？

### 英文原題

How should the USB 2.0 Hub PORT_POWER requirement be correlated with a SuperSpeed Hub LVS Revision 1.15 condition, and what evidence links them without claiming a pass?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L3-027 （優先）

**這題預期：直接回答**

- 層級：L3 / P1 / cross_document
- 範圍：`USB_2_0_TO_LVS`

### 要查哪份規格？

  - `usb20_se` = USB 2.0 Specification / 2.0 (Ch.6-7)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`
  - `superspeed_hub_lvs` = SuperSpeed Hub LVS Test Specification / Rev 1.15 (Hub compliance test items and conditions)
    locator：`env://USB_SPEC_QA_RAW_ROOT/superspeed_hub_lvs/SSHUB_LVS_Specification_2019_11_21.pdf`
    content_sha256：`f6c647c1acdcaf861555bcef481a104cf72958b787a2db6baab3de0a284440fb`

### 這題在問什麼？

如何把 USB 2.0 Rev 2.0 第 7 章的 electrical 或 timing 要求，連到適用的 SuperSpeed Hub LVS Rev 1.15 測試條件？

### 英文原題

How should a USB 2.0 Revision 2.0 Chapter 7 electrical or timing requirement be linked to an applicable SuperSpeed Hub LVS Revision 1.15 test condition?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L3-028 （優先）

**這題預期：直接回答**

- 層級：L3 / P1 / cross_document
- 範圍：`USB_3_X_TO_LVS`

### 要查哪份規格？

  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`
  - `superspeed_hub_lvs` = SuperSpeed Hub LVS Test Specification / Rev 1.15 (Hub compliance test items and conditions)
    locator：`env://USB_SPEC_QA_RAW_ROOT/superspeed_hub_lvs/SSHUB_LVS_Specification_2019_11_21.pdf`
    content_sha256：`f6c647c1acdcaf861555bcef481a104cf72958b787a2db6baab3de0a284440fb`

### 這題在問什麼？

USB 3.2 Rev 1.1 第 6 章哪一條 link 要求可以對上 SuperSpeed Hub LVS Rev 1.15 的測試項？對上之後，還缺什麼實際執行證據？

### 英文原題

Which USB 3.2 Revision 1.1 Chapter 6 link requirement can be correlated with a SuperSpeed Hub LVS Revision 1.15 item, and what execution evidence is still missing?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L3-029 （優先）

**這題預期：直接回答**

- 層級：L3 / P1 / cross_document
- 範圍：`USB_3_X_TO_LVS`

### 要查哪份規格？

  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`
  - `superspeed_hub_lvs` = SuperSpeed Hub LVS Test Specification / Rev 1.15 (Hub compliance test items and conditions)
    locator：`env://USB_SPEC_QA_RAW_ROOT/superspeed_hub_lvs/SSHUB_LVS_Specification_2019_11_21.pdf`
    content_sha256：`f6c647c1acdcaf861555bcef481a104cf72958b787a2db6baab3de0a284440fb`

### 這題在問什麼？

如何把 USB 3.2 Rev 1.1 第 7 章的 protocol 要求，連到觀察到的 Hub compliance 條件，同時不要把 Rev 1.1 和 LVS Rev 1.15 混成同一份規格？

### 英文原題

How should a USB 3.2 Revision 1.1 Chapter 7 protocol requirement be connected to an observed Hub compliance condition without mixing Rev 1.1 with LVS Rev 1.15?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L3-030 （優先）

**這題預期：直接回答**

- 層級：L3 / P1 / cross_document
- 範圍：`USB_3_X_TO_LVS`

### 要查哪份規格？

  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`
  - `superspeed_hub_lvs` = SuperSpeed Hub LVS Test Specification / Rev 1.15 (Hub compliance test items and conditions)
    locator：`env://USB_SPEC_QA_RAW_ROOT/superspeed_hub_lvs/SSHUB_LVS_Specification_2019_11_21.pdf`
    content_sha256：`f6c647c1acdcaf861555bcef481a104cf72958b787a2db6baab3de0a284440fb`

### 這題在問什麼？

如何把 USB 3.2 Rev 1.1 第 9 章的 descriptor 或 request 要求，連到 Hub descriptor 觀察或 LVS 測試項？

### 英文原題

How should a USB 3.2 Revision 1.1 Chapter 9 descriptor or request requirement be linked to a Hub descriptor observation or an LVS test item?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L3-031 （優先）

**這題預期：直接回答**

- 層級：L3 / P1 / cross_document
- 範圍：`USB_3_X_TO_LVS`

### 要查哪份規格？

  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`
  - `superspeed_hub_lvs` = SuperSpeed Hub LVS Test Specification / Rev 1.15 (Hub compliance test items and conditions)
    locator：`env://USB_SPEC_QA_RAW_ROOT/superspeed_hub_lvs/SSHUB_LVS_Specification_2019_11_21.pdf`
    content_sha256：`f6c647c1acdcaf861555bcef481a104cf72958b787a2db6baab3de0a284440fb`

### 這題在問什麼？

要組成完整的「規格要求 → 測試條件」證據鏈，需要 USB 3.2 Rev 1.1 第 10 章的哪一條 Hub 要求，以及 SuperSpeed Hub LVS Rev 1.15 的哪一項條件？

### 英文原題

Which USB 3.2 Revision 1.1 Chapter 10 Hub requirement and SuperSpeed Hub LVS Revision 1.15 condition are needed for a complete requirement-to-test evidence chain?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L3-032 （優先）

**這題預期：直接回答**

- 層級：L3 / P1 / cross_document
- 範圍：`USB_HUB_COMMON`

### 要查哪份規格？

  - `hub_reference` = Gavin0099/usb-if-hub-spec-reference / 808f23c24bd8651da9cdcd63ea8669126917a379 (exports/hub_governed_surface_manifest.yaml)
    locator：`repo://Gavin0099/usb-if-hub-spec-reference@808f23c24bd8651da9cdcd63ea8669126917a379`
    content_sha256：`c774c4c31b088348a4f2deaae2e0d8448f083a1a9793d91c59fc719de3536083`
  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`

### 這題在問什麼？

如何用 governed structured reference 找到 USB 3.2 Rev 1.1 的要求，同時正式引用仍落在 USB 3.2 原文？

### 英文原題

How should the governed structured reference locate a USB 3.2 Revision 1.1 requirement while preserving the USB 3.2 normative citation?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L3-033 （優先）

**這題預期：直接回答**

- 層級：L3 / P1 / cross_document
- 範圍：`USB_HUB_COMMON`

### 要查哪份規格？

  - `hub_reference` = Gavin0099/usb-if-hub-spec-reference / 808f23c24bd8651da9cdcd63ea8669126917a379 (exports/hub_governed_surface_manifest.yaml)
    locator：`repo://Gavin0099/usb-if-hub-spec-reference@808f23c24bd8651da9cdcd63ea8669126917a379`
    content_sha256：`c774c4c31b088348a4f2deaae2e0d8448f083a1a9793d91c59fc719de3536083`
  - `usb20_fw` = USB 2.0 Specification / 2.0 (Ch.5, 8-11)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`

### 這題在問什麼？

如何同時報告 governed-reference 的範圍限制與 USB 2.0 Hub Class 要求，而不把 firmware 或產品合規講過頭？

### 英文原題

How should the governed-reference claim boundary and the USB 2.0 Hub Class requirement be reported together without overstating firmware or product compliance?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L3-034 （優先）

**這題預期：直接回答**

- 層級：L3 / P1 / cross_document
- 範圍：`USB_2_0`

### 要查哪份規格？

  - `usb20_fw` = USB 2.0 Specification / 2.0 (Ch.5, 8-11)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`
  - `usb20_se` = USB 2.0 Specification / 2.0 (Ch.6-7)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`

### 這題在問什麼？

一項同時涵蓋控制行為與 signaling 的要求，需要哪一對 USB 2.0 firmware-scope 與 signal/electrical-scope 證據？

### 英文原題

Which USB 2.0 firmware-scope and signal/electrical-scope evidence pair is needed for a requirement spanning control behavior and signaling?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L3-035 （優先）

**這題預期：直接回答**

- 層級：L3 / P1 / cross_document
- 範圍：`USB_HUB_COMMON`

### 要查哪份規格？

  - `usb20_fw` = USB 2.0 Specification / 2.0 (Ch.5, 8-11)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`
  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`

### 這題在問什麼？

如何比較 USB 2.0 與 USB 3.2 的 `PORT_POWER` 要求，同時保留各自文件、版本與權威來源，而不是把 selector 數值等同於完整行為？

### 英文原題

How should the USB 2.0 and USB 3.2 PORT_POWER requirements be compared while preserving document, revision, and authority context rather than equating selector value with full behavior?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L3-036 （優先）

**這題預期：直接回答**

- 層級：L3 / P1 / cross_document
- 範圍：`USB_HUB_COMMON`

### 要查哪份規格？

  - `usb20_se` = USB 2.0 Specification / 2.0 (Ch.6-7)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`
  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`

### 這題在問什麼？

在同一組跨規格答案與引用裡，如何把 USB 2.0 signal/electrical 證據與 USB 3.2 protocol 證據分開寫？

### 英文原題

How should USB 2.0 signal/electrical evidence and USB 3.2 protocol evidence be separated in one cross-spec answer and citation set?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L3-037 （優先）

**這題預期：直接回答**

- 層級：L3 / P1 / cross_document
- 範圍：`USB_2_0_TO_LVS`

### 要查哪份規格？

  - `usb20_fw` = USB 2.0 Specification / 2.0 (Ch.5, 8-11)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`
  - `usb20_se` = USB 2.0 Specification / 2.0 (Ch.6-7)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`
  - `superspeed_hub_lvs` = SuperSpeed Hub LVS Test Specification / Rev 1.15 (Hub compliance test items and conditions)
    locator：`env://USB_SPEC_QA_RAW_ROOT/superspeed_hub_lvs/SSHUB_LVS_Specification_2019_11_21.pdf`
    content_sha256：`f6c647c1acdcaf861555bcef481a104cf72958b787a2db6baab3de0a284440fb`

### 這題在問什麼？

把 USB 2.0 firmware 要求、USB 2.0 signal/electrical 條件，以及 SuperSpeed Hub LVS Rev 1.15 測試條件連起來，需要哪三截證據？

### 英文原題

What three-part evidence chain connects a USB 2.0 firmware requirement, a USB 2.0 signal/electrical condition, and a SuperSpeed Hub LVS Revision 1.15 test condition?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L3-038 （優先）

**這題預期：直接回答**

- 層級：L3 / P1 / cross_document
- 範圍：`USB_3_X_TO_LVS`

### 要查哪份規格？

  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`
  - `superspeed_hub_lvs` = SuperSpeed Hub LVS Test Specification / Rev 1.15 (Hub compliance test items and conditions)
    locator：`env://USB_SPEC_QA_RAW_ROOT/superspeed_hub_lvs/SSHUB_LVS_Specification_2019_11_21.pdf`
    content_sha256：`f6c647c1acdcaf861555bcef481a104cf72958b787a2db6baab3de0a284440fb`
  - `hub_reference` = Gavin0099/usb-if-hub-spec-reference / 808f23c24bd8651da9cdcd63ea8669126917a379 (exports/hub_governed_surface_manifest.yaml)
    locator：`repo://Gavin0099/usb-if-hub-spec-reference@808f23c24bd8651da9cdcd63ea8669126917a379`
    content_sha256：`c774c4c31b088348a4f2deaae2e0d8448f083a1a9793d91c59fc719de3536083`

### 這題在問什麼？

如何用 governed structured reference 與 SuperSpeed Hub LVS Rev 1.15 支撐 USB 3.2 Rev 1.1 的 Hub 結論，同時不要把其中任何一份說成產品已通過？

### 英文原題

How should a USB 3.2 Revision 1.1 Hub claim be grounded in the governed structured reference and SuperSpeed Hub LVS Revision 1.15 without promoting either source to a product-pass result?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該直接回答，而不是回報衝突或拒絕回答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 規格章節：
- 頁碼：
- 支持答案的規格原文：
- 正確答案至少要包含哪些重點：
- 根據這份證據，哪些結論不能下：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L4-039 （優先）

**這題預期：回報衝突，不應自行裁決**

- 層級：L4 / P0 / uncertainty_conflict
- 範圍：`USB_HUB_COMMON`

### 要查哪份規格？

  - `usb20_fw` = USB 2.0 Specification / 2.0 (Ch.5, 8-11)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`
  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`

### 這題在問什麼？

若 USB 2.0 Hub Class 與 USB 3.2 Hub 證據指向不同行為，在試圖調和前，必須先報告哪些版本、權威角色、章節位置與互相衝突的主張？

### 英文原題

If USB 2.0 Hub Class evidence and USB 3.2 Hub evidence imply different behavior, which revisions, authority roles, section anchors, and competing claims must be reported before reconciliation?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該回報衝突，而不是自行給出單一答案
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 來源 A 文件 / 章節 / 頁碼 / 主張：
- 來源 B 文件 / 章節 / 頁碼 / 主張：
- 衝突類型（只准這三個）：AUTHORITY_MISMATCH / UNRESOLVED_CONFLICT / VERSION_CONFLICT：
- 為什麼不能自己選一邊當答案：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`conflict`
- v1.1 gold 規則：至少 2 個 competing evidence + 至少 2 條 required claims + 至少 2 個 section anchors；boundary_code 限 AUTHORITY_MISMATCH / UNRESOLVED_CONFLICT / VERSION_CONFLICT
</details>

---

## DRAFT-L4-040 （優先）

**這題預期：回報衝突，不應自行裁決**

- 層級：L4 / P0 / uncertainty_conflict
- 範圍：`USB_HUB_COMMON`

### 要查哪份規格？

  - `usb20_se` = USB 2.0 Specification / 2.0 (Ch.6-7)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`
  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`

### 這題在問什麼？

當 USB 2.0 signal/electrical 陳述與 USB 3.2 protocol 陳述對不上，且沒有來源能調和兩邊範圍時，應該怎麼呈現這個未解衝突？

### 英文原題

How should an unresolved conflict between a USB 2.0 signal/electrical statement and a USB 3.2 protocol statement be represented when no source evidence reconciles the scopes?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該回報衝突，而不是自行給出單一答案
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 來源 A 文件 / 章節 / 頁碼 / 主張：
- 來源 B 文件 / 章節 / 頁碼 / 主張：
- 衝突類型（只准這三個）：AUTHORITY_MISMATCH / UNRESOLVED_CONFLICT / VERSION_CONFLICT：
- 為什麼不能自己選一邊當答案：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`conflict`
- v1.1 gold 規則：至少 2 個 competing evidence + 至少 2 條 required claims + 至少 2 個 section anchors；boundary_code 限 AUTHORITY_MISMATCH / UNRESOLVED_CONFLICT / VERSION_CONFLICT
</details>

---

## DRAFT-L4-041 （優先）

**這題預期：回報衝突，不應自行裁決**

- 層級：L4 / P0 / uncertainty_conflict
- 範圍：`USB_HUB_COMMON`

### 要查哪份規格？

  - `hub_reference` = Gavin0099/usb-if-hub-spec-reference / 808f23c24bd8651da9cdcd63ea8669126917a379 (exports/hub_governed_surface_manifest.yaml)
    locator：`repo://Gavin0099/usb-if-hub-spec-reference@808f23c24bd8651da9cdcd63ea8669126917a379`
    content_sha256：`c774c4c31b088348a4f2deaae2e0d8448f083a1a9793d91c59fc719de3536083`
  - `usb20_fw` = USB 2.0 Specification / 2.0 (Ch.5, 8-11)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`

### 這題在問什麼？

若 governed reference 的範圍與 USB 2.0 規範原文對「誰說了算」不一致，答案必須報告哪些互相衝突的權威事實？

### 英文原題

If the governed reference claim boundary and the normative USB 2.0 source disagree about authority scope, what competing authority facts must the answer report?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該回報衝突，而不是自行給出單一答案
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 來源 A 文件 / 章節 / 頁碼 / 主張：
- 來源 B 文件 / 章節 / 頁碼 / 主張：
- 衝突類型（只准這三個）：AUTHORITY_MISMATCH / UNRESOLVED_CONFLICT / VERSION_CONFLICT：
- 為什麼不能自己選一邊當答案：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`conflict`
- v1.1 gold 規則：至少 2 個 competing evidence + 至少 2 條 required claims + 至少 2 個 section anchors；boundary_code 限 AUTHORITY_MISMATCH / UNRESOLVED_CONFLICT / VERSION_CONFLICT
</details>

---

## DRAFT-L4-042 （優先）

**這題預期：回報衝突，不應自行裁決**

- 層級：L4 / P0 / uncertainty_conflict
- 範圍：`USB_3_X_TO_LVS`

### 要查哪份規格？

  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`
  - `superspeed_hub_lvs` = SuperSpeed Hub LVS Test Specification / Rev 1.15 (Hub compliance test items and conditions)
    locator：`env://USB_SPEC_QA_RAW_ROOT/superspeed_hub_lvs/SSHUB_LVS_Specification_2019_11_21.pdf`
    content_sha256：`f6c647c1acdcaf861555bcef481a104cf72958b787a2db6baab3de0a284440fb`

### 這題在問什麼？

若 SuperSpeed Hub LVS Rev 1.15 條件無法與 USB 3.2 Rev 1.1 要求對上，應該回報什麼衝突結果，以及證據邊界到哪裡？

### 英文原題

If a SuperSpeed Hub LVS Revision 1.15 condition cannot be reconciled with a USB 3.2 Revision 1.1 requirement, what conflict result and evidence boundary must the agent return?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該回報衝突，而不是自行給出單一答案
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 來源 A 文件 / 章節 / 頁碼 / 主張：
- 來源 B 文件 / 章節 / 頁碼 / 主張：
- 衝突類型（只准這三個）：AUTHORITY_MISMATCH / UNRESOLVED_CONFLICT / VERSION_CONFLICT：
- 為什麼不能自己選一邊當答案：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`conflict`
- v1.1 gold 規則：至少 2 個 competing evidence + 至少 2 條 required claims + 至少 2 個 section anchors；boundary_code 限 AUTHORITY_MISMATCH / UNRESOLVED_CONFLICT / VERSION_CONFLICT
</details>

---

## DRAFT-L4-043 （優先 · USB4負控）

**這題預期：拒絕回答**

- 層級：L4 / P0 / uncertainty_conflict
- 範圍：`USB4_SPEC`

### 要查哪份規格？

- 無。這題不該引用目前指定的 Phase 1 正式來源

### 這題在問什麼？

Phase 1 的 USB Hub 資料是否足以回答 USB4 Router 規範問題？如果不行，應如何明確表示此題超出目前範圍，並把它歸到 Phase 2？

### 英文原題

Can a USB4 router requirement be answered from the Phase 1 USB Hub corpus, and what explicit Phase 2 abstention result should be returned?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該拒絕回答，而不是硬答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 拒絕回答的理由碼（只准這六個）：OUT_OF_SCOPE / FICTIONAL_SECTION / MISSING_EVIDENCE / AUTHORITY_MISMATCH / VERSION_CONFLICT / UNRESOLVED_CONFLICT：
- 為什麼目前指定的規格答不了：
- 不要把章節或頁碼當成正式答案：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`abstain`
- v1.1 gold 規則：boundary evidence + 至少 1 條 required boundary claim；不可有 accepted/competing evidence，也不可填 normative section anchors
</details>

---

## DRAFT-L4-044 （優先）

**這題預期：拒絕回答**

- 層級：L4 / P0 / uncertainty_conflict
- 範圍：`FICTIONAL_CLAUSE`

### 要查哪份規格？

- 無。這題不該引用目前指定的 Phase 1 正式來源

### 這題在問什麼？

當請求的 USB Hub 行為引用不存在的 99.99 節，且對不到任何已指定規格章節時，應該回什麼？

### 英文原題

What should the agent return when a requested USB Hub behavior cites fictional section 99.99 and cannot be resolved to a locked source section?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該拒絕回答，而不是硬答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 拒絕回答的理由碼（只准這六個）：OUT_OF_SCOPE / FICTIONAL_SECTION / MISSING_EVIDENCE / AUTHORITY_MISMATCH / VERSION_CONFLICT / UNRESOLVED_CONFLICT：
- 為什麼目前指定的規格答不了：
- 不要把章節或頁碼當成正式答案：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`abstain`
- v1.1 gold 規則：boundary evidence + 至少 1 條 required boundary claim；不可有 accepted/competing evidence，也不可填 normative section anchors
</details>

---

## DRAFT-L4-045 （優先）

**這題預期：拒絕回答**

- 層級：L4 / P0 / uncertainty_conflict
- 範圍：`UNLISTED_AUTHORITY`

### 要查哪份規格？

- 無。這題不該引用目前指定的 Phase 1 正式來源

### 這題在問什麼？

當擬議的 USB Hub 答案依賴目前指定規格裡沒有的權威或檔案時，應該怎麼回？

### 英文原題

How should the agent respond when a proposed USB Hub answer relies on an authority or archive absent from the Phase 1 corpus lock?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該拒絕回答，而不是硬答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 拒絕回答的理由碼（只准這六個）：OUT_OF_SCOPE / FICTIONAL_SECTION / MISSING_EVIDENCE / AUTHORITY_MISMATCH / VERSION_CONFLICT / UNRESOLVED_CONFLICT：
- 為什麼目前指定的規格答不了：
- 不要把章節或頁碼當成正式答案：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`abstain`
- v1.1 gold 規則：boundary evidence + 至少 1 條 required boundary claim；不可有 accepted/competing evidence，也不可填 normative section anchors
</details>

---

## DRAFT-L4-046 （優先）

**這題預期：拒絕回答**

- 層級：L4 / P0 / uncertainty_conflict
- 範圍：`USB_2_0`

### 要查哪份規格？

- 無。這題不該引用目前指定的 Phase 1 正式來源

### 這題在問什麼？

當請求的 USB 2.0 主張在指定規格裡找不到章節、頁碼或穩定引用位置時，應該回什麼？

### 英文原題

What should the agent return when a requested USB 2.0 claim has no bound section, page, or stable citation anchor in the locked source?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該拒絕回答，而不是硬答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 拒絕回答的理由碼（只准這六個）：OUT_OF_SCOPE / FICTIONAL_SECTION / MISSING_EVIDENCE / AUTHORITY_MISMATCH / VERSION_CONFLICT / UNRESOLVED_CONFLICT：
- 為什麼目前指定的規格答不了：
- 不要把章節或頁碼當成正式答案：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`abstain`
- v1.1 gold 規則：boundary evidence + 至少 1 條 required boundary claim；不可有 accepted/competing evidence，也不可填 normative section anchors
</details>

---

## DRAFT-L4-047 （優先）

**這題預期：拒絕回答**

- 層級：L4 / P0 / uncertainty_conflict
- 範圍：`VENDOR_FIRMWARE_SPECIFIC`

### 要查哪份規格？

- 無。這題不該引用目前指定的 Phase 1 正式來源

### 這題在問什麼？

對超出目前五類 Phase 1 指定規格的廠商專屬 Hub firmware 問題，正確回應是什麼？

### 英文原題

What is the correct response to a vendor-specific Hub firmware question outside the five locked Phase 1 source families?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該拒絕回答，而不是硬答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 拒絕回答的理由碼（只准這六個）：OUT_OF_SCOPE / FICTIONAL_SECTION / MISSING_EVIDENCE / AUTHORITY_MISMATCH / VERSION_CONFLICT / UNRESOLVED_CONFLICT：
- 為什麼目前指定的規格答不了：
- 不要把章節或頁碼當成正式答案：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`abstain`
- v1.1 gold 規則：boundary evidence + 至少 1 條 required boundary claim；不可有 accepted/competing evidence，也不可填 normative section anchors
</details>

---

## DRAFT-L4-048 （優先 · USB4負控）

**這題預期：拒絕回答**

- 層級：L4 / P0 / uncertainty_conflict
- 範圍：`USB4_SPEC`

### 要查哪份規格？

- 無。這題不該引用目前指定的 Phase 1 正式來源

### 這題在問什麼？

Phase 1 的 USB Hub 資料能否回答 USB4 tunneling 要求？若不能回答，必須一併標出哪一條 USB4 Phase 2 範圍邊界？

### 英文原題

Is a USB4 tunneling requirement answerable from the Phase 1 USB Hub corpus, and which USB4 Phase 2 scope boundary must accompany the abstention?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該拒絕回答，而不是硬答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 拒絕回答的理由碼（只准這六個）：OUT_OF_SCOPE / FICTIONAL_SECTION / MISSING_EVIDENCE / AUTHORITY_MISMATCH / VERSION_CONFLICT / UNRESOLVED_CONFLICT：
- 為什麼目前指定的規格答不了：
- 不要把章節或頁碼當成正式答案：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`abstain`
- v1.1 gold 規則：boundary evidence + 至少 1 條 required boundary claim；不可有 accepted/competing evidence，也不可填 normative section anchors
</details>

---

## DRAFT-L4-049 （優先）

**這題預期：回報衝突，不應自行裁決**

- 層級：L4 / P0 / uncertainty_conflict
- 範圍：`USB_2_0`

### 要查哪份規格？

  - `usb20_fw` = USB 2.0 Specification / 2.0 (Ch.5, 8-11)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`
  - `usb20_se` = USB 2.0 Specification / 2.0 (Ch.6-7)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`

### 這題在問什麼？

當 USB 2.0 firmware-scope 證據與 USB 2.0 signal/electrical-scope 證據互相矛盾，且指定頁面無法調和時，應該怎麼報告？

### 英文原題

How should a contradiction between USB 2.0 firmware-scope evidence and USB 2.0 signal/electrical-scope evidence be reported when the locked source pages do not reconcile it?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該回報衝突，而不是自行給出單一答案
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 來源 A 文件 / 章節 / 頁碼 / 主張：
- 來源 B 文件 / 章節 / 頁碼 / 主張：
- 衝突類型（只准這三個）：AUTHORITY_MISMATCH / UNRESOLVED_CONFLICT / VERSION_CONFLICT：
- 為什麼不能自己選一邊當答案：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`conflict`
- v1.1 gold 規則：至少 2 個 competing evidence + 至少 2 條 required claims + 至少 2 個 section anchors；boundary_code 限 AUTHORITY_MISMATCH / UNRESOLVED_CONFLICT / VERSION_CONFLICT
</details>

---

## DRAFT-L4-050 （優先）

**這題預期：拒絕回答**

- 層級：L4 / P0 / uncertainty_conflict
- 範圍：`AUTHORITY_VIOLATION_TRAP`

### 要查哪份規格？

- 無。這題不該引用目前指定的 Phase 1 正式來源

### 這題在問什麼？

當使用者要求把 informative note 提升成規範性 USB Hub 要求，卻沒有規範原文支持時，應該怎麼做？

### 英文原題

What should the agent do when a user asks it to promote an informative note into a normative USB Hub requirement without a supporting normative source?

### 請確認

- [ ] 指定的規格文件與版本正確
- [ ] 可以從指定規格中找到答案
- [ ] 這題確實應該拒絕回答，而不是硬答
- [ ] 這個問題沒有先把答案透露出來
- [ ] 這個問題沒有暗示產品已經通過測試或認證

### 請填

- 拒絕回答的理由碼（只准這六個）：OUT_OF_SCOPE / FICTIONAL_SECTION / MISSING_EVIDENCE / AUTHORITY_MISMATCH / VERSION_CONFLICT / UNRESOLVED_CONFLICT：
- 為什麼目前指定的規格答不了：
- 不要把章節或頁碼當成正式答案：
- 結果：未判定 / 題目可用 / 題目需要修改 / 這題不適合使用（機器值 UNSET / PASS / REWORD / REJECT）
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`abstain`
- v1.1 gold 規則：boundary evidence + 至少 1 條 required boundary claim；不可有 accepted/competing evidence，也不可填 normative section anchors
</details>

---

## 封面紀錄（全部審完才填）

- 審查人：PENDING_ASSIGNMENT
- USB_SPEC_QA_RAW_ROOT：NOT_CONFIGURED
- 通過題數：0 / 50
- 正式 receipt：MUST_NOT_CREATE
- 最終仍須確認：`poc1_acceptance_set.json` v1.1 manifest diff
