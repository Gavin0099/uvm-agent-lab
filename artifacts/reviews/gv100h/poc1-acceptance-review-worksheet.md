# POC-1 Gold Oracle 人審工作單

> 這是給人看的 review input 投影，不是正式 acceptance set，也不是 review receipt。
> Reviewer 簽這份工作單不夠；最後仍須確認真正會被 admission 的 v1.1 JSON。
> 禁止：把 gold 寫進正式 JSON、建立 `poc1_acceptance_set.json`、建立 approved receipt、宣稱 GO

## Review-input provenance

- `source_draft_path`: `gv100h/spec_qa/golden/poc1_acceptance_set.draft.json`
- `source_draft_git_commit`: `b964c72a210a6e8a38146bbe887b99ed977ea8dc`
- `source_draft_git_blob`: `df9a0135aaf2fca334c309f6ed8ab7aac0a9dede`
- `source_draft_sha256`: `3a9306db7b910e1f8d813dc64ae7b9d77e3771813a4575f7202fbd18cdafbe28`
- `corpus_lock_path`: `gv100h/spec_qa/contracts/corpus.lock.yaml`
- `corpus_lock_sha256`: `f51cc94a9cb478071122a3682cd1386983aa84a08b8304d3bfe7b77375f90847`
- `corpus_lock_git_blob`: `97c1dc714f5fc72ddeb82bc5fb7538dce5b8e8e8`
- `renderer_path`: `scripts/render_poc1_review_worksheet.py`
- `renderer_git_blob`: `6a8ecc536aca333a444d717db290144590e720f5`
- `renderer_sha256`: `7e3de1ac3ab79a360e2cb138bb043246cd43b4151eb435fd39a7836056265379`
- `generated_at`: `2026-08-25T08:18:07+00:00`
- `worktree_head`: `b964c72a210a6e8a38146bbe887b99ed977ea8dc`
- `draft_schema`: `poc1_spec_qa_acceptance_set_draft.v0.1`
- `draft_status`: `draft_not_admitted`
- `Independent reviewer`: `PENDING_ASSIGNMENT`
- `USB_SPEC_QA_RAW_ROOT`: `NOT_CONFIGURED`

## 怎麼用

1. 先指定獨立審查人，再開已鎖定 PDF 根目錄（bytes/hash 必須對上 lock）。
2. 用大綱跳題號。一次只看一張卡，打開對應 PDF，找 section / page，再勾選。
3. 空白欄位留給審查人；agent 不得憑記憶代填。
4. 工程側把卡片轉成 v1.1 gold 後，審查人再看一次 manifest diff，最後才簽 receipt。

## 鎖定來源對照（來自 corpus.lock.yaml，不是 renderer 手寫）

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

- 層級：L1 / P0 / single_spec_fact
- 預期處理：直接回答
- 範圍：`USB_2_0`
- 本題應查閱的規格：
  - `usb20_fw` = USB 2.0 Specification / 2.0 (Ch.5, 8-11)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`

### 題目

According to the USB 2.0 Revision 2.0 Chapter 5 data-flow terminology, what is the distinction between a transaction and a transfer?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L1-002

- 層級：L1 / P0 / single_spec_fact
- 預期處理：直接回答
- 範圍：`USB_2_0`
- 本題應查閱的規格：
  - `usb20_fw` = USB 2.0 Specification / 2.0 (Ch.5, 8-11)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`

### 題目

According to USB 2.0 Revision 2.0 Chapter 8, what are the SETUP, DATA when present, and STATUS stages of a control transfer?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L1-003

- 層級：L1 / P0 / single_spec_fact
- 預期處理：直接回答
- 範圍：`USB_2_0`
- 本題應查閱的規格：
  - `usb20_fw` = USB 2.0 Specification / 2.0 (Ch.5, 8-11)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`

### 題目

In USB 2.0 Revision 2.0 Chapter 9, what do bmRequestType, bRequest, and wValue identify in a standard Hub request?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L1-004 （優先）

- 層級：L1 / P0 / single_spec_fact
- 預期處理：直接回答
- 範圍：`USB_2_0`
- 本題應查閱的規格：
  - `usb20_fw` = USB 2.0 Specification / 2.0 (Ch.5, 8-11)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`

### 題目

Which USB 2.0 Hub Class feature controls downstream-port power, and what operation invokes that feature?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L1-005 （優先）

- 層級：L1 / P0 / single_spec_fact
- 預期處理：直接回答
- 範圍：`USB_2_0`
- 本題應查閱的規格：
  - `usb20_fw` = USB 2.0 Specification / 2.0 (Ch.5, 8-11)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`

### 題目

What numeric value does the USB 2.0 Hub Class assign to the PORT_POWER feature selector, and which USB 2.0 section is the stable citation anchor?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L1-006 （優先）

- 層級：L1 / P0 / single_spec_fact
- 預期處理：直接回答
- 範圍：`USB_2_0`
- 本題應查閱的規格：
  - `usb20_se` = USB 2.0 Specification / 2.0 (Ch.6-7)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`

### 題目

Which USB 2.0 Revision 2.0 Chapter 6 differential-signaling parameter must be cited with its measurement condition and units?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L1-007

- 層級：L1 / P0 / single_spec_fact
- 預期處理：直接回答
- 範圍：`USB_2_0`
- 本題應查閱的規格：
  - `usb20_se` = USB 2.0 Specification / 2.0 (Ch.6-7)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`

### 題目

Which USB 2.0 Revision 2.0 Chapter 7 timing requirement must be reported with its measurement condition and units?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L1-008 （優先）

- 層級：L1 / P0 / single_spec_fact
- 預期處理：直接回答
- 範圍：`USB_3_X`
- 本題應查閱的規格：
  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`

### 題目

Which USB 3.2 Revision 1.1 Chapter 6 link-state or signaling rule must be cited when evaluating a Hub link transition?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L1-009 （優先）

- 層級：L1 / P0 / single_spec_fact
- 預期處理：直接回答
- 範圍：`USB_3_X`
- 本題應查閱的規格：
  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`

### 題目

Which USB 3.2 Revision 1.1 Chapter 7 protocol or ordered-set rule applies to a Hub link exchange?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L1-010 （優先）

- 層級：L1 / P0 / single_spec_fact
- 預期處理：直接回答
- 範圍：`USB_3_X`
- 本題應查閱的規格：
  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`

### 題目

Which USB 3.2 Revision 1.1 Chapter 9 descriptor or standard-request field identifies the device state being evaluated?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L1-011 （優先）

- 層級：L1 / P0 / single_spec_fact
- 預期處理：直接回答
- 範圍：`USB_3_X`
- 本題應查閱的規格：
  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`

### 題目

What USB 3.2 Revision 1.1 Chapter 10 Hub descriptor or feature-selector rule governs downstream-port state?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L1-012

- 層級：L1 / P0 / single_spec_fact
- 預期處理：直接回答
- 範圍：`USB_HUB_LVS`
- 本題應查閱的規格：
  - `superspeed_hub_lvs` = SuperSpeed Hub LVS Test Specification / Rev 1.15 (Hub compliance test items and conditions)
    locator：`env://USB_SPEC_QA_RAW_ROOT/superspeed_hub_lvs/SSHUB_LVS_Specification_2019_11_21.pdf`
    content_sha256：`f6c647c1acdcaf861555bcef481a104cf72958b787a2db6baab3de0a284440fb`

### 題目

For a SuperSpeed Hub LVS Revision 1.15 Hub test item, which precondition, stimulus, and expected observation must the answer extract and cite?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L1-013

- 層級：L1 / P0 / single_spec_fact
- 預期處理：直接回答
- 範圍：`USB_HUB_COMMON`
- 本題應查閱的規格：
  - `hub_reference` = Gavin0099/usb-if-hub-spec-reference / 808f23c24bd8651da9cdcd63ea8669126917a379 (exports/hub_governed_surface_manifest.yaml)
    locator：`repo://Gavin0099/usb-if-hub-spec-reference@808f23c24bd8651da9cdcd63ea8669126917a379`
    content_sha256：`c774c4c31b088348a4f2deaae2e0d8448f083a1a9793d91c59fc719de3536083`

### 題目

Which claims does the governed structured Hub reference authorize, and which firmware, electrical, LVS, or certification claims are outside its stated boundary?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L2-014

- 層級：L2 / P0 / engineering_interpretation
- 預期處理：直接回答
- 範圍：`USB_2_0`
- 本題應查閱的規格：
  - `usb20_fw` = USB 2.0 Specification / 2.0 (Ch.5, 8-11)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`

### 題目

How should the USB 2.0 Revision 2.0 Chapter 5 transaction/transfer requirement become a verifiable observation, and which implementation conclusion is not licensed?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L2-015

- 層級：L2 / P0 / engineering_interpretation
- 預期處理：直接回答
- 範圍：`USB_2_0`
- 本題應查閱的規格：
  - `usb20_fw` = USB 2.0 Specification / 2.0 (Ch.5, 8-11)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`

### 題目

How should the USB 2.0 Revision 2.0 Chapter 8 control-transfer packet rule become a test oracle without adding retry behavior absent from the source?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L2-016

- 層級：L2 / P0 / engineering_interpretation
- 預期處理：直接回答
- 範圍：`USB_2_0`
- 本題應查閱的規格：
  - `usb20_fw` = USB 2.0 Specification / 2.0 (Ch.5, 8-11)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`

### 題目

How should the USB 2.0 Revision 2.0 Chapter 9 standard-request fields become an assertion while preserving the source citation boundary?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L2-017 （優先）

- 層級：L2 / P0 / engineering_interpretation
- 預期處理：直接回答
- 範圍：`USB_2_0`
- 本題應查閱的規格：
  - `usb20_se` = USB 2.0 Specification / 2.0 (Ch.6-7)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`

### 題目

How should the USB 2.0 Revision 2.0 Chapter 6 electrical requirement be separated into a measurable condition and an unsupported product-compliance claim?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L2-018

- 層級：L2 / P0 / engineering_interpretation
- 預期處理：直接回答
- 範圍：`USB_2_0`
- 本題應查閱的規格：
  - `usb20_se` = USB 2.0 Specification / 2.0 (Ch.6-7)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`

### 題目

How should a verifier classify and test a USB 2.0 Revision 2.0 Chapter 7 timing statement when its normative force or measurement condition is unresolved?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L2-019 （優先）

- 層級：L2 / P0 / engineering_interpretation
- 預期處理：直接回答
- 範圍：`USB_3_X`
- 本題應查閱的規格：
  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`

### 題目

How should a verifier map the USB 3.2 Revision 1.1 Chapter 6 link requirement to a Hub test-plan observation without claiming certification?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L2-020 （優先）

- 層級：L2 / P0 / engineering_interpretation
- 預期處理：直接回答
- 範圍：`USB_3_X`
- 本題應查閱的規格：
  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`

### 題目

What conclusion is justified by the USB 3.2 Revision 1.1 Chapter 7 protocol rule, and what remains unknown without an observed trace?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L2-021 （優先）

- 層級：L2 / P0 / engineering_interpretation
- 預期處理：直接回答
- 範圍：`USB_3_X`
- 本題應查閱的規格：
  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`

### 題目

How should the USB 3.2 Revision 1.1 Chapter 9 descriptor or request requirement be mapped to an observable Hub check?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L2-022 （優先）

- 層級：L2 / P0 / engineering_interpretation
- 預期處理：直接回答
- 範圍：`USB_3_X`
- 本題應查閱的規格：
  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`

### 題目

How should the USB 3.2 Revision 1.1 Chapter 10 Hub requirement be reported separately from a product-compliance test result?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L2-023

- 層級：L2 / P0 / engineering_interpretation
- 預期處理：直接回答
- 範圍：`USB_HUB_LVS`
- 本題應查閱的規格：
  - `superspeed_hub_lvs` = SuperSpeed Hub LVS Test Specification / Rev 1.15 (Hub compliance test items and conditions)
    locator：`env://USB_SPEC_QA_RAW_ROOT/superspeed_hub_lvs/SSHUB_LVS_Specification_2019_11_21.pdf`
    content_sha256：`f6c647c1acdcaf861555bcef481a104cf72958b787a2db6baab3de0a284440fb`

### 題目

What conclusion can be drawn from a SuperSpeed Hub LVS Revision 1.15 test condition, and what execution evidence would be required to claim a device passed?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L2-024

- 層級：L2 / P0 / engineering_interpretation
- 預期處理：直接回答
- 範圍：`USB_HUB_LVS`
- 本題應查閱的規格：
  - `superspeed_hub_lvs` = SuperSpeed Hub LVS Test Specification / Rev 1.15 (Hub compliance test items and conditions)
    locator：`env://USB_SPEC_QA_RAW_ROOT/superspeed_hub_lvs/SSHUB_LVS_Specification_2019_11_21.pdf`
    content_sha256：`f6c647c1acdcaf861555bcef481a104cf72958b787a2db6baab3de0a284440fb`

### 題目

Which parts of a SuperSpeed Hub LVS Revision 1.15 procedure are source-defined conditions, and which product-pass statements require separate execution evidence?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L2-025

- 層級：L2 / P0 / engineering_interpretation
- 預期處理：直接回答
- 範圍：`USB_HUB_COMMON`
- 本題應查閱的規格：
  - `hub_reference` = Gavin0099/usb-if-hub-spec-reference / 808f23c24bd8651da9cdcd63ea8669126917a379 (exports/hub_governed_surface_manifest.yaml)
    locator：`repo://Gavin0099/usb-if-hub-spec-reference@808f23c24bd8651da9cdcd63ea8669126917a379`
    content_sha256：`c774c4c31b088348a4f2deaae2e0d8448f083a1a9793d91c59fc719de3536083`

### 題目

How should an engineer use the governed structured Hub reference as an index while preserving its boundary that it is not the complete USB specification?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L3-026 （優先）

- 層級：L3 / P1 / cross_document
- 預期處理：直接回答
- 範圍：`USB_2_0_TO_LVS`
- 本題應查閱的規格：
  - `usb20_fw` = USB 2.0 Specification / 2.0 (Ch.5, 8-11)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`
  - `superspeed_hub_lvs` = SuperSpeed Hub LVS Test Specification / Rev 1.15 (Hub compliance test items and conditions)
    locator：`env://USB_SPEC_QA_RAW_ROOT/superspeed_hub_lvs/SSHUB_LVS_Specification_2019_11_21.pdf`
    content_sha256：`f6c647c1acdcaf861555bcef481a104cf72958b787a2db6baab3de0a284440fb`

### 題目

How should the USB 2.0 Hub PORT_POWER requirement be correlated with a SuperSpeed Hub LVS Revision 1.15 condition, and what evidence links them without claiming a pass?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L3-027 （優先）

- 層級：L3 / P1 / cross_document
- 預期處理：直接回答
- 範圍：`USB_2_0_TO_LVS`
- 本題應查閱的規格：
  - `usb20_se` = USB 2.0 Specification / 2.0 (Ch.6-7)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`
  - `superspeed_hub_lvs` = SuperSpeed Hub LVS Test Specification / Rev 1.15 (Hub compliance test items and conditions)
    locator：`env://USB_SPEC_QA_RAW_ROOT/superspeed_hub_lvs/SSHUB_LVS_Specification_2019_11_21.pdf`
    content_sha256：`f6c647c1acdcaf861555bcef481a104cf72958b787a2db6baab3de0a284440fb`

### 題目

How should a USB 2.0 Revision 2.0 Chapter 7 electrical or timing requirement be linked to an applicable SuperSpeed Hub LVS Revision 1.15 test condition?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L3-028 （優先）

- 層級：L3 / P1 / cross_document
- 預期處理：直接回答
- 範圍：`USB_3_X_TO_LVS`
- 本題應查閱的規格：
  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`
  - `superspeed_hub_lvs` = SuperSpeed Hub LVS Test Specification / Rev 1.15 (Hub compliance test items and conditions)
    locator：`env://USB_SPEC_QA_RAW_ROOT/superspeed_hub_lvs/SSHUB_LVS_Specification_2019_11_21.pdf`
    content_sha256：`f6c647c1acdcaf861555bcef481a104cf72958b787a2db6baab3de0a284440fb`

### 題目

Which USB 3.2 Revision 1.1 Chapter 6 link requirement can be correlated with a SuperSpeed Hub LVS Revision 1.15 item, and what execution evidence is still missing?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L3-029 （優先）

- 層級：L3 / P1 / cross_document
- 預期處理：直接回答
- 範圍：`USB_3_X_TO_LVS`
- 本題應查閱的規格：
  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`
  - `superspeed_hub_lvs` = SuperSpeed Hub LVS Test Specification / Rev 1.15 (Hub compliance test items and conditions)
    locator：`env://USB_SPEC_QA_RAW_ROOT/superspeed_hub_lvs/SSHUB_LVS_Specification_2019_11_21.pdf`
    content_sha256：`f6c647c1acdcaf861555bcef481a104cf72958b787a2db6baab3de0a284440fb`

### 題目

How should a USB 3.2 Revision 1.1 Chapter 7 protocol requirement be connected to an observed Hub compliance condition without mixing Rev 1.1 with LVS Rev 1.15?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L3-030 （優先）

- 層級：L3 / P1 / cross_document
- 預期處理：直接回答
- 範圍：`USB_3_X_TO_LVS`
- 本題應查閱的規格：
  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`
  - `superspeed_hub_lvs` = SuperSpeed Hub LVS Test Specification / Rev 1.15 (Hub compliance test items and conditions)
    locator：`env://USB_SPEC_QA_RAW_ROOT/superspeed_hub_lvs/SSHUB_LVS_Specification_2019_11_21.pdf`
    content_sha256：`f6c647c1acdcaf861555bcef481a104cf72958b787a2db6baab3de0a284440fb`

### 題目

How should a USB 3.2 Revision 1.1 Chapter 9 descriptor or request requirement be linked to a Hub descriptor observation or an LVS test item?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L3-031 （優先）

- 層級：L3 / P1 / cross_document
- 預期處理：直接回答
- 範圍：`USB_3_X_TO_LVS`
- 本題應查閱的規格：
  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`
  - `superspeed_hub_lvs` = SuperSpeed Hub LVS Test Specification / Rev 1.15 (Hub compliance test items and conditions)
    locator：`env://USB_SPEC_QA_RAW_ROOT/superspeed_hub_lvs/SSHUB_LVS_Specification_2019_11_21.pdf`
    content_sha256：`f6c647c1acdcaf861555bcef481a104cf72958b787a2db6baab3de0a284440fb`

### 題目

Which USB 3.2 Revision 1.1 Chapter 10 Hub requirement and SuperSpeed Hub LVS Revision 1.15 condition are needed for a complete requirement-to-test evidence chain?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L3-032 （優先）

- 層級：L3 / P1 / cross_document
- 預期處理：直接回答
- 範圍：`USB_HUB_COMMON`
- 本題應查閱的規格：
  - `hub_reference` = Gavin0099/usb-if-hub-spec-reference / 808f23c24bd8651da9cdcd63ea8669126917a379 (exports/hub_governed_surface_manifest.yaml)
    locator：`repo://Gavin0099/usb-if-hub-spec-reference@808f23c24bd8651da9cdcd63ea8669126917a379`
    content_sha256：`c774c4c31b088348a4f2deaae2e0d8448f083a1a9793d91c59fc719de3536083`
  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`

### 題目

How should the governed structured reference locate a USB 3.2 Revision 1.1 requirement while preserving the USB 3.2 normative citation?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L3-033 （優先）

- 層級：L3 / P1 / cross_document
- 預期處理：直接回答
- 範圍：`USB_HUB_COMMON`
- 本題應查閱的規格：
  - `hub_reference` = Gavin0099/usb-if-hub-spec-reference / 808f23c24bd8651da9cdcd63ea8669126917a379 (exports/hub_governed_surface_manifest.yaml)
    locator：`repo://Gavin0099/usb-if-hub-spec-reference@808f23c24bd8651da9cdcd63ea8669126917a379`
    content_sha256：`c774c4c31b088348a4f2deaae2e0d8448f083a1a9793d91c59fc719de3536083`
  - `usb20_fw` = USB 2.0 Specification / 2.0 (Ch.5, 8-11)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`

### 題目

How should the governed-reference claim boundary and the USB 2.0 Hub Class requirement be reported together without overstating firmware or product compliance?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L3-034 （優先）

- 層級：L3 / P1 / cross_document
- 預期處理：直接回答
- 範圍：`USB_2_0`
- 本題應查閱的規格：
  - `usb20_fw` = USB 2.0 Specification / 2.0 (Ch.5, 8-11)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`
  - `usb20_se` = USB 2.0 Specification / 2.0 (Ch.6-7)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`

### 題目

Which USB 2.0 firmware-scope and signal/electrical-scope evidence pair is needed for a requirement spanning control behavior and signaling?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L3-035 （優先）

- 層級：L3 / P1 / cross_document
- 預期處理：直接回答
- 範圍：`USB_HUB_COMMON`
- 本題應查閱的規格：
  - `usb20_fw` = USB 2.0 Specification / 2.0 (Ch.5, 8-11)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`
  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`

### 題目

How should the USB 2.0 and USB 3.2 PORT_POWER requirements be compared while preserving document, revision, and authority context rather than equating selector value with full behavior?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L3-036 （優先）

- 層級：L3 / P1 / cross_document
- 預期處理：直接回答
- 範圍：`USB_HUB_COMMON`
- 本題應查閱的規格：
  - `usb20_se` = USB 2.0 Specification / 2.0 (Ch.6-7)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`
  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`

### 題目

How should USB 2.0 signal/electrical evidence and USB 3.2 protocol evidence be separated in one cross-spec answer and citation set?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L3-037 （優先）

- 層級：L3 / P1 / cross_document
- 預期處理：直接回答
- 範圍：`USB_2_0_TO_LVS`
- 本題應查閱的規格：
  - `usb20_fw` = USB 2.0 Specification / 2.0 (Ch.5, 8-11)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`
  - `usb20_se` = USB 2.0 Specification / 2.0 (Ch.6-7)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`
  - `superspeed_hub_lvs` = SuperSpeed Hub LVS Test Specification / Rev 1.15 (Hub compliance test items and conditions)
    locator：`env://USB_SPEC_QA_RAW_ROOT/superspeed_hub_lvs/SSHUB_LVS_Specification_2019_11_21.pdf`
    content_sha256：`f6c647c1acdcaf861555bcef481a104cf72958b787a2db6baab3de0a284440fb`

### 題目

What three-part evidence chain connects a USB 2.0 firmware requirement, a USB 2.0 signal/electrical condition, and a SuperSpeed Hub LVS Revision 1.15 test condition?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L3-038 （優先）

- 層級：L3 / P1 / cross_document
- 預期處理：直接回答
- 範圍：`USB_3_X_TO_LVS`
- 本題應查閱的規格：
  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`
  - `superspeed_hub_lvs` = SuperSpeed Hub LVS Test Specification / Rev 1.15 (Hub compliance test items and conditions)
    locator：`env://USB_SPEC_QA_RAW_ROOT/superspeed_hub_lvs/SSHUB_LVS_Specification_2019_11_21.pdf`
    content_sha256：`f6c647c1acdcaf861555bcef481a104cf72958b787a2db6baab3de0a284440fb`
  - `hub_reference` = Gavin0099/usb-if-hub-spec-reference / 808f23c24bd8651da9cdcd63ea8669126917a379 (exports/hub_governed_surface_manifest.yaml)
    locator：`repo://Gavin0099/usb-if-hub-spec-reference@808f23c24bd8651da9cdcd63ea8669126917a379`
    content_sha256：`c774c4c31b088348a4f2deaae2e0d8448f083a1a9793d91c59fc719de3536083`

### 題目

How should a USB 3.2 Revision 1.1 Hub claim be grounded in the governed structured reference and SuperSpeed Hub LVS Revision 1.15 without promoting either source to a product-pass result?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 規格文件：
- 章節：
- 頁碼：
- 關鍵原文：
- 答案必須包含：
- 不得延伸宣稱：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`answer`
- v1.1 gold 規則：accepted evidence + 至少 1 條 required claim + required facts + section anchors；不可有 competing/boundary evidence 或 boundary_code
</details>

---

## DRAFT-L4-039 （優先）

- 層級：L4 / P0 / uncertainty_conflict
- 預期處理：回報衝突，不應自行裁決
- 範圍：`USB_HUB_COMMON`
- 本題應查閱的規格：
  - `usb20_fw` = USB 2.0 Specification / 2.0 (Ch.5, 8-11)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`
  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`

### 題目

If USB 2.0 Hub Class evidence and USB 3.2 Hub evidence imply different behavior, which revisions, authority roles, section anchors, and competing claims must be reported before reconciliation?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 來源 A 文件 / 章節 / 頁碼 / 主張：
- 來源 B 文件 / 章節 / 頁碼 / 主張：
- 衝突類型（只准這三個）：AUTHORITY_MISMATCH / UNRESOLVED_CONFLICT / VERSION_CONFLICT：
- 為何不能自行裁決：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`conflict`
- v1.1 gold 規則：至少 2 個 competing evidence + 至少 2 條 required claims + 至少 2 個 section anchors；boundary_code 限 AUTHORITY_MISMATCH / UNRESOLVED_CONFLICT / VERSION_CONFLICT
</details>

---

## DRAFT-L4-040 （優先）

- 層級：L4 / P0 / uncertainty_conflict
- 預期處理：回報衝突，不應自行裁決
- 範圍：`USB_HUB_COMMON`
- 本題應查閱的規格：
  - `usb20_se` = USB 2.0 Specification / 2.0 (Ch.6-7)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`
  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`

### 題目

How should an unresolved conflict between a USB 2.0 signal/electrical statement and a USB 3.2 protocol statement be represented when no source evidence reconciles the scopes?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 來源 A 文件 / 章節 / 頁碼 / 主張：
- 來源 B 文件 / 章節 / 頁碼 / 主張：
- 衝突類型（只准這三個）：AUTHORITY_MISMATCH / UNRESOLVED_CONFLICT / VERSION_CONFLICT：
- 為何不能自行裁決：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`conflict`
- v1.1 gold 規則：至少 2 個 competing evidence + 至少 2 條 required claims + 至少 2 個 section anchors；boundary_code 限 AUTHORITY_MISMATCH / UNRESOLVED_CONFLICT / VERSION_CONFLICT
</details>

---

## DRAFT-L4-041 （優先）

- 層級：L4 / P0 / uncertainty_conflict
- 預期處理：回報衝突，不應自行裁決
- 範圍：`USB_HUB_COMMON`
- 本題應查閱的規格：
  - `hub_reference` = Gavin0099/usb-if-hub-spec-reference / 808f23c24bd8651da9cdcd63ea8669126917a379 (exports/hub_governed_surface_manifest.yaml)
    locator：`repo://Gavin0099/usb-if-hub-spec-reference@808f23c24bd8651da9cdcd63ea8669126917a379`
    content_sha256：`c774c4c31b088348a4f2deaae2e0d8448f083a1a9793d91c59fc719de3536083`
  - `usb20_fw` = USB 2.0 Specification / 2.0 (Ch.5, 8-11)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`

### 題目

If the governed reference claim boundary and the normative USB 2.0 source disagree about authority scope, what competing authority facts must the answer report?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 來源 A 文件 / 章節 / 頁碼 / 主張：
- 來源 B 文件 / 章節 / 頁碼 / 主張：
- 衝突類型（只准這三個）：AUTHORITY_MISMATCH / UNRESOLVED_CONFLICT / VERSION_CONFLICT：
- 為何不能自行裁決：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`conflict`
- v1.1 gold 規則：至少 2 個 competing evidence + 至少 2 條 required claims + 至少 2 個 section anchors；boundary_code 限 AUTHORITY_MISMATCH / UNRESOLVED_CONFLICT / VERSION_CONFLICT
</details>

---

## DRAFT-L4-042 （優先）

- 層級：L4 / P0 / uncertainty_conflict
- 預期處理：回報衝突，不應自行裁決
- 範圍：`USB_3_X_TO_LVS`
- 本題應查閱的規格：
  - `usb32` = USB 3.2 Specification / Rev 1.1 (Ch.6, 7, 9, 10)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb32/USB 3.2 Revision 1.1.pdf`
    content_sha256：`26e025a56ce0352f4f91fcaaca67b622d8e9e030ca429804bf7da98f52e674fd`
  - `superspeed_hub_lvs` = SuperSpeed Hub LVS Test Specification / Rev 1.15 (Hub compliance test items and conditions)
    locator：`env://USB_SPEC_QA_RAW_ROOT/superspeed_hub_lvs/SSHUB_LVS_Specification_2019_11_21.pdf`
    content_sha256：`f6c647c1acdcaf861555bcef481a104cf72958b787a2db6baab3de0a284440fb`

### 題目

If a SuperSpeed Hub LVS Revision 1.15 condition cannot be reconciled with a USB 3.2 Revision 1.1 requirement, what conflict result and evidence boundary must the agent return?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 來源 A 文件 / 章節 / 頁碼 / 主張：
- 來源 B 文件 / 章節 / 頁碼 / 主張：
- 衝突類型（只准這三個）：AUTHORITY_MISMATCH / UNRESOLVED_CONFLICT / VERSION_CONFLICT：
- 為何不能自行裁決：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`conflict`
- v1.1 gold 規則：至少 2 個 competing evidence + 至少 2 條 required claims + 至少 2 個 section anchors；boundary_code 限 AUTHORITY_MISMATCH / UNRESOLVED_CONFLICT / VERSION_CONFLICT
</details>

---

## DRAFT-L4-043 （優先 · USB4負控）

- 層級：L4 / P0 / uncertainty_conflict
- 預期處理：棄權，不應回答
- 範圍：`USB4_SPEC`
- 本題應查閱的規格：無（棄權題不該引用 Phase 1 正式來源）

### 題目

Can a USB4 router requirement be answered from the Phase 1 USB Hub corpus, and what explicit Phase 2 abstention result should be returned?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 棄權理由碼（只准這六個）：OUT_OF_SCOPE / FICTIONAL_SECTION / MISSING_EVIDENCE / AUTHORITY_MISMATCH / VERSION_CONFLICT / UNRESOLVED_CONFLICT：
- 為何 Phase 1 corpus 不能答：
- 不要把章節或頁碼當成正式答案：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`abstain`
- v1.1 gold 規則：boundary evidence + 至少 1 條 required boundary claim；不可有 accepted/competing evidence，也不可填 normative section anchors
</details>

---

## DRAFT-L4-044 （優先）

- 層級：L4 / P0 / uncertainty_conflict
- 預期處理：棄權，不應回答
- 範圍：`FICTIONAL_CLAUSE`
- 本題應查閱的規格：無（棄權題不該引用 Phase 1 正式來源）

### 題目

What should the agent return when a requested USB Hub behavior cites fictional section 99.99 and cannot be resolved to a locked source section?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 棄權理由碼（只准這六個）：OUT_OF_SCOPE / FICTIONAL_SECTION / MISSING_EVIDENCE / AUTHORITY_MISMATCH / VERSION_CONFLICT / UNRESOLVED_CONFLICT：
- 為何 Phase 1 corpus 不能答：
- 不要把章節或頁碼當成正式答案：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`abstain`
- v1.1 gold 規則：boundary evidence + 至少 1 條 required boundary claim；不可有 accepted/competing evidence，也不可填 normative section anchors
</details>

---

## DRAFT-L4-045 （優先）

- 層級：L4 / P0 / uncertainty_conflict
- 預期處理：棄權，不應回答
- 範圍：`UNLISTED_AUTHORITY`
- 本題應查閱的規格：無（棄權題不該引用 Phase 1 正式來源）

### 題目

How should the agent respond when a proposed USB Hub answer relies on an authority or archive absent from the Phase 1 corpus lock?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 棄權理由碼（只准這六個）：OUT_OF_SCOPE / FICTIONAL_SECTION / MISSING_EVIDENCE / AUTHORITY_MISMATCH / VERSION_CONFLICT / UNRESOLVED_CONFLICT：
- 為何 Phase 1 corpus 不能答：
- 不要把章節或頁碼當成正式答案：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`abstain`
- v1.1 gold 規則：boundary evidence + 至少 1 條 required boundary claim；不可有 accepted/competing evidence，也不可填 normative section anchors
</details>

---

## DRAFT-L4-046 （優先）

- 層級：L4 / P0 / uncertainty_conflict
- 預期處理：棄權，不應回答
- 範圍：`USB_2_0`
- 本題應查閱的規格：無（棄權題不該引用 Phase 1 正式來源）

### 題目

What should the agent return when a requested USB 2.0 claim has no bound section, page, or stable citation anchor in the locked source?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 棄權理由碼（只准這六個）：OUT_OF_SCOPE / FICTIONAL_SECTION / MISSING_EVIDENCE / AUTHORITY_MISMATCH / VERSION_CONFLICT / UNRESOLVED_CONFLICT：
- 為何 Phase 1 corpus 不能答：
- 不要把章節或頁碼當成正式答案：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`abstain`
- v1.1 gold 規則：boundary evidence + 至少 1 條 required boundary claim；不可有 accepted/competing evidence，也不可填 normative section anchors
</details>

---

## DRAFT-L4-047 （優先）

- 層級：L4 / P0 / uncertainty_conflict
- 預期處理：棄權，不應回答
- 範圍：`VENDOR_FIRMWARE_SPECIFIC`
- 本題應查閱的規格：無（棄權題不該引用 Phase 1 正式來源）

### 題目

What is the correct response to a vendor-specific Hub firmware question outside the five locked Phase 1 source families?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 棄權理由碼（只准這六個）：OUT_OF_SCOPE / FICTIONAL_SECTION / MISSING_EVIDENCE / AUTHORITY_MISMATCH / VERSION_CONFLICT / UNRESOLVED_CONFLICT：
- 為何 Phase 1 corpus 不能答：
- 不要把章節或頁碼當成正式答案：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`abstain`
- v1.1 gold 規則：boundary evidence + 至少 1 條 required boundary claim；不可有 accepted/competing evidence，也不可填 normative section anchors
</details>

---

## DRAFT-L4-048 （優先 · USB4負控）

- 層級：L4 / P0 / uncertainty_conflict
- 預期處理：棄權，不應回答
- 範圍：`USB4_SPEC`
- 本題應查閱的規格：無（棄權題不該引用 Phase 1 正式來源）

### 題目

Is a USB4 tunneling requirement answerable from the Phase 1 USB Hub corpus, and which USB4 Phase 2 scope boundary must accompany the abstention?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 棄權理由碼（只准這六個）：OUT_OF_SCOPE / FICTIONAL_SECTION / MISSING_EVIDENCE / AUTHORITY_MISMATCH / VERSION_CONFLICT / UNRESOLVED_CONFLICT：
- 為何 Phase 1 corpus 不能答：
- 不要把章節或頁碼當成正式答案：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`abstain`
- v1.1 gold 規則：boundary evidence + 至少 1 條 required boundary claim；不可有 accepted/competing evidence，也不可填 normative section anchors
</details>

---

## DRAFT-L4-049 （優先）

- 層級：L4 / P0 / uncertainty_conflict
- 預期處理：回報衝突，不應自行裁決
- 範圍：`USB_2_0`
- 本題應查閱的規格：
  - `usb20_fw` = USB 2.0 Specification / 2.0 (Ch.5, 8-11)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`
  - `usb20_se` = USB 2.0 Specification / 2.0 (Ch.6-7)
    locator：`env://USB_SPEC_QA_RAW_ROOT/usb20/usb_20.pdf`
    content_sha256：`d39698a33486c399124af92bd02e4f978fd9a836b5cf4e52e6e4633eb1d89f61`

### 題目

How should a contradiction between USB 2.0 firmware-scope evidence and USB 2.0 signal/electrical-scope evidence be reported when the locked source pages do not reconcile it?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 來源 A 文件 / 章節 / 頁碼 / 主張：
- 來源 B 文件 / 章節 / 頁碼 / 主張：
- 衝突類型（只准這三個）：AUTHORITY_MISMATCH / UNRESOLVED_CONFLICT / VERSION_CONFLICT：
- 為何不能自行裁決：
- 判定：未判定 / PASS / REWORD / REJECT
- 備註：

<details>
<summary>機器規則（admission 用，審查時可略過）</summary>

- expected_status：`conflict`
- v1.1 gold 規則：至少 2 個 competing evidence + 至少 2 條 required claims + 至少 2 個 section anchors；boundary_code 限 AUTHORITY_MISMATCH / UNRESOLVED_CONFLICT / VERSION_CONFLICT
</details>

---

## DRAFT-L4-050 （優先）

- 層級：L4 / P0 / uncertainty_conflict
- 預期處理：棄權，不應回答
- 範圍：`AUTHORITY_VIOLATION_TRAP`
- 本題應查閱的規格：無（棄權題不該引用 Phase 1 正式來源）

### 題目

What should the agent do when a user asks it to promote an informative note into a normative USB Hub requirement without a supporting normative source?

### 請確認

- [ ] 可在鎖定來源中找到足以支持本題的依據
- [ ] 題目引用的規格與版本正確
- [ ] 預期處理類型（回答／衝突／棄權）分類正確
- [ ] 題幹沒有洩漏預期答案
- [ ] 題幹沒有暗示產品已通過認證

### 請填

- 棄權理由碼（只准這六個）：OUT_OF_SCOPE / FICTIONAL_SECTION / MISSING_EVIDENCE / AUTHORITY_MISMATCH / VERSION_CONFLICT / UNRESOLVED_CONFLICT：
- 為何 Phase 1 corpus 不能答：
- 不要把章節或頁碼當成正式答案：
- 判定：未判定 / PASS / REWORD / REJECT
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
