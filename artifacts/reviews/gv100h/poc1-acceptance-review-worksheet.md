# POC-1 Gold Oracle 人審工作單

> 這是給人看的 review input 投影，不是正式 acceptance set，也不是 review receipt。
> Reviewer 簽這份工作單不夠；最後仍須確認真正會被 admission 的 v1.1 JSON。
> 禁止：把 gold 寫進正式 JSON、建立 `poc1_acceptance_set.json`、建立 approved receipt、宣稱 GO

## Review-input provenance

- `source_draft_path`: `gv100h/spec_qa/golden/poc1_acceptance_set.draft.json`
- `source_draft_git_commit`: `61b19ebfd05b5f0d877e81834104cc76fba70bca`
- `source_draft_git_blob`: `4918b63efd0ad50499a7b3e7095ad039dfe8822e`
- `source_draft_sha256`: `c9099399565cb9b036a32217840c524f7af1d755a10398c3fff4e7e81f2e07ef`
- `corpus_lock_path`: `gv100h/spec_qa/contracts/corpus.lock.yaml`
- `corpus_lock_sha256`: `f51cc94a9cb478071122a3682cd1386983aa84a08b8304d3bfe7b77375f90847`
- `corpus_lock_git_blob`: `97c1dc714f5fc72ddeb82bc5fb7538dce5b8e8e8`
- `renderer_path`: `scripts/render_poc1_review_worksheet.py`
- `renderer_git_blob`: `db90decfce4ee37646870f297b4519c148a179da`
- `renderer_sha256`: `3d098aa30e6a788159e8a18af61d26c27925293ad6e1b995274d7bd77f40d20e`
- `generated_at`: `2026-08-25T10:07:31+00:00`
- `worktree_head`: `61b19ebfd05b5f0d877e81834104cc76fba70bca`
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
- USB4 負控：L4-043；USB PD 負控：L4-048
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

USB 2.0 Rev 2.0 Table 6-7 對 Contact Capacitance 的性能要求是什麼？必須寫出未插合（unmated）條件與單位。

### 英文原題

In USB 2.0 Revision 2.0 Table 6-7, what is the Contact Capacitance performance requirement, including the unmated condition and units?

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

依 USB 2.0 Rev 2.0 Section 7.1.2.2，對 hub 或可拆線裝置，在 A 或 B receptacle 量到的 high-speed 差分 rise/fall（10% 到 90%）最短時間是多少，單位是什麼？

### 英文原題

According to USB 2.0 Revision 2.0 Section 7.1.2.2, what minimum 10%-to-90% high-speed differential rise and fall time applies at the A or B receptacle for a hub or a device with detachable cable, and in what units?

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

依 USB 3.2 Rev 1.1 Section 6.9.3，downstream port 可以在哪些link state 發出 Warm Reset？Table 6-30 給的 tReset 最短與最長是多少？

### 英文原題

According to USB 3.2 Revision 1.1 Section 6.9.3, in which link states may a downstream port issue a Warm Reset, and what tReset minimum and maximum does Table 6-30 specify?

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

依 USB 3.2 Rev 1.1 Table 7-8，x1 與 x2 操作下的 PM_LC_TIMER逾時值各是多少，單位是什麼？

### 英文原題

According to USB 3.2 Revision 1.1 Table 7-8, what are the PM_LC_TIMER timeout values for x1 operation and x2 operation, including units?

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

依 USB 3.2 Rev 1.1 Section 9.4.2 Get Configuration，裝置在Address state 應回什麼 configuration value？在 Configured state 又應回什麼？

### 英文原題

According to USB 3.2 Revision 1.1 Section 9.4.2 Get Configuration, what configuration value shall be returned in the Address state, and what shall be returned in the Configured state?

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

依 USB 3.2 Rev 1.1 Figure 10-10 與 Section 10.3.1.9，PORT_LINK_STATE（PLS）是哪一個 port-status 欄位？哪個 request 會讓 downstream port 進入 DSPORT.Disabled、link 在 eSS.Disabled？

### 英文原題

According to USB 3.2 Revision 1.1 Figure 10-10 and Section 10.3.1.9, which port-status field is PORT_LINK_STATE (PLS), and which request places a downstream port in DSPORT.Disabled with the link in eSS.Disabled?

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

在 SuperSpeed Hub LVS Rev 1.15 TD 10.104 Toggle Port Power 中，先 ClearPortFeature(PORT_POWER)，再在最短 tReset（80 ms）內SetPortFeature(PORT_POWER) 之後，最長 tReset（120 ms）時GetPortStatus 必須看到什麼？

### 英文原題

In SuperSpeed Hub LVS Revision 1.15 TD 10.104 Toggle Port Power, after ClearPortFeature(PORT_POWER) then SetPortFeature(PORT_POWER) within min tReset (80 ms), what GetPortStatus observation is required after max tReset (120 ms)?

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

SuperSpeed Hub LVS Rev 1.15 TD 10.105 Disconnect Device Test在 U0–U3 disconnect 後要求的 GetPortStatus 觀察，可以怎麼當測試判定？為什麼寫在程序裡的條件，還不能直接當成產品已通過？

### 英文原題

How should SuperSpeed Hub LVS Revision 1.15 TD 10.105 Disconnect Device Test's required GetPortStatus observation after a U0-U3 disconnect be used as a test oracle, without treating the written procedure as a device-pass result?

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

**這題預期：直接回答**

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

USB 2.0 Table 11-17 把 PORT_POWER 的 Hub Class feature-selector 訂成 8。USB 3.2 第 10 章把 PORT_POWER（PP）當成與 PORT_LINK_STATE（PLS）不同的port-status 欄位。這兩段是否構成衝突？請分別指出兩段證據描述的對象、範圍與權威角色，並說明判斷理由。

### 英文原題

USB 2.0 Table 11-17 assigns PORT_POWER the Hub Class feature-selector value 8. USB 3.2 Chapter 10 treats PORT_POWER (PP) as a port-status field distinct from PORT_LINK_STATE (PLS). Do these two statements constitute a conflict? Identify the object, scope, and authority role described by each excerpt, and justify the determination.

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

## DRAFT-L4-040 （優先）

**這題預期：直接回答**

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

USB 2.0 Section 7.1.2.2 寫 high-speed 差分 rise/fall（10% 到 90%）最短 500 ps。USB 3.2 Section 10.3.1.9 用 SetPortFeature(PORT_LINK_STATE) eSS.Disabled進入 DSPORT.Disabled。這兩段是否構成衝突？請分別指出兩段證據描述的對象、範圍與權威角色，並說明判斷理由。

### 英文原題

USB 2.0 Section 7.1.2.2 states a high-speed 10%-to-90% differential rise/fall minimum of 500 ps. USB 3.2 Section 10.3.1.9 uses SetPortFeature(PORT_LINK_STATE) eSS.Disabled to enter DSPORT.Disabled. Do these two statements constitute a conflict? Identify the object, scope, and authority role described by each excerpt, and justify the determination.

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

## DRAFT-L4-041 （優先）

**這題預期：直接回答**

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

governed Hub reference 的 claim_ceiling 是 spec_reference_only，且 cannot_establish firmware_behavior。USB 2.0 Section 11.5.1.2 寫規範性的 Powered-off 轉換。這兩段是否構成衝突？請分別指出兩段證據描述的對象、範圍與權威角色，並說明判斷理由。

### 英文原題

The governed Hub reference claim_ceiling is spec_reference_only and cannot_establish firmware_behavior. USB 2.0 Section 11.5.1.2 states a normative Powered-off transition. Do these two statements constitute a conflict? Identify the object, scope, and authority role described by each excerpt, and justify the determination.

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

## DRAFT-L4-042 （優先）

**這題預期：直接回答**

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

USB 3.2 Section 10.3.1.11 說收到 ClearPortFeature(PORT_POWER) 時，downstream port 進入 DSPORT.Powered-off-reset。SuperSpeed Hub LVS TD 10.104 把同一個 request 當測試刺激。這兩段是否構成衝突？請分別指出兩段證據描述的對象、範圍與權威角色，並說明判斷理由。

### 英文原題

USB 3.2 Section 10.3.1.11 says a downstream port transitions to DSPORT.Powered-off-reset when it receives ClearPortFeature(PORT_POWER). SuperSpeed Hub LVS TD 10.104 uses that same request as a test stimulus. Do these two statements constitute a conflict? Identify the object, scope, and authority role described by each excerpt, and justify the determination.

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

## DRAFT-L4-043 （優先 · USB4負控）

**這題預期：拒絕回答**

- 層級：L4 / P0 / uncertainty_conflict
- 範圍：`USB4_SPEC`

### 要查哪份規格？

- 無。這題不該引用目前指定的 Phase 1 正式來源

### 這題在問什麼？

USB4 Router 完成成功的 Phase 2 連線後，啟用 USB4 tunnel 前必須滿足哪一條 Router 要求？

### 英文原題

After a USB4 Router completes a successful Phase 2 connection, what Router requirement must be satisfied before a USB4 tunnel can be enabled?

### 請確認

- [ ] 目前指定的 Phase 1 規格裡，沒有足夠、可接受的證據能回答這題
- [ ] 不應為了硬答而去引用指定規格以外的來源
- [ ] 拒絕回答的理由，和實際缺什麼證據相符
- [ ] 這題不該把規範章節或頁碼當成正式答案
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

- [ ] 目前指定的 Phase 1 規格裡，沒有足夠、可接受的證據能回答這題
- [ ] 不應為了硬答而去引用指定規格以外的來源
- [ ] 拒絕回答的理由，和實際缺什麼證據相符
- [ ] 這題不該把規範章節或頁碼當成正式答案
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

- [ ] 目前指定的 Phase 1 規格裡，沒有足夠、可接受的證據能回答這題
- [ ] 不應為了硬答而去引用指定規格以外的來源
- [ ] 拒絕回答的理由，和實際缺什麼證據相符
- [ ] 這題不該把規範章節或頁碼當成正式答案
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

- [ ] 目前指定的 Phase 1 規格裡，沒有足夠、可接受的證據能回答這題
- [ ] 不應為了硬答而去引用指定規格以外的來源
- [ ] 拒絕回答的理由，和實際缺什麼證據相符
- [ ] 這題不該把規範章節或頁碼當成正式答案
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

- [ ] 目前指定的 Phase 1 規格裡，沒有足夠、可接受的證據能回答這題
- [ ] 不應為了硬答而去引用指定規格以外的來源
- [ ] 拒絕回答的理由，和實際缺什麼證據相符
- [ ] 這題不該把規範章節或頁碼當成正式答案
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

## DRAFT-L4-048 （優先）

**這題預期：拒絕回答**

- 層級：L4 / P0 / uncertainty_conflict
- 範圍：`USB_PD_SPEC`

### 要查哪份規格？

- 無。這題不該引用目前指定的 Phase 1 正式來源

### 這題在問什麼？

USB Power Delivery 來源要支援 20 V / 5 A 合約時，必須在Programmable Power Supply（PPS）APDO 裡廣告哪些欄位？

### 英文原題

What Programmable Power Supply (PPS) APDO fields must a USB Power Delivery source advertise to support a 20 V / 5 A contract?

### 請確認

- [ ] 目前指定的 Phase 1 規格裡，沒有足夠、可接受的證據能回答這題
- [ ] 不應為了硬答而去引用指定規格以外的來源
- [ ] 拒絕回答的理由，和實際缺什麼證據相符
- [ ] 這題不該把規範章節或頁碼當成正式答案
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

**這題預期：直接回答**

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

USB 2.0 Section 11.5.1.2 描述 ClearPortFeature(PORT_POWER) 後進入 Powered-off。Section 7.1.2.2 寫 high-speed 差分 rise/fall（10% 到 90%）最短 500 ps。這兩段是否構成衝突？請分別指出兩段證據描述的對象、範圍與權威角色，並說明判斷理由。

### 英文原題

USB 2.0 Section 11.5.1.2 describes Powered-off after ClearPortFeature(PORT_POWER). USB 2.0 Section 7.1.2.2 states a high-speed 10%-to-90% differential rise/fall minimum of 500 ps. Do these two statements constitute a conflict? Identify the object, scope, and authority role described by each excerpt, and justify the determination.

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

- [ ] 目前指定的 Phase 1 規格裡，沒有足夠、可接受的證據能回答這題
- [ ] 不應為了硬答而去引用指定規格以外的來源
- [ ] 拒絕回答的理由，和實際缺什麼證據相符
- [ ] 這題不該把規範章節或頁碼當成正式答案
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
