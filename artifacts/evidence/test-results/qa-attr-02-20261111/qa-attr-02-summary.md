> 公開審查副本：本機原始報告未改。此分支的 JSON 已去除原文；原報告所稱完整引文、Prompt／wire 與 PDF 核對指私人原始資料。公開版可審查方法與元資料，不能獨立重做原文語意驗證。原始 SHA 見 publication-provenance.json。

# QA-ATTR-02：歷史與目前 RAG 證據比較

已完成20個獨立問題的唯讀重放：16個歷史27B問題，另列4個retrieval-only控制。165筆完成紀錄中108筆完整Prompt只對應39種精確問句；本輪不把重複實驗當獨立樣本，也不計合併答題正確率。

**結論：選定16題的歷史主基準，只有Q005可確認缺必要證據；目前Evidence-first預覽已補齊。其餘15題主基準的必要來源角色原本就已具備，其中6題仍曾有品質／引用／契約失敗。這批失敗不能一概繼續歸咎於RAG找不到原文。**

**比較界線：目前正式Evidence-first服務只回傳證據預覽，沒有建立或送出LLM Prompt。以下IMPROVED／COMPLETE全部指來源角色與預覽證據；16題的正式新舊LLM Prompt比較均為NOT_COMPARABLE_NO_CURRENT_LLM_PROMPT。未證明目前27B答得更好，亦未證明純檢索演算法造成改善。**

| 摘要問題 | 實際結果 |
|---|---|
| A. 歷史主基準真正缺必要證據 | 1/16：Q005 early seven-live3；其當時拒答有依據 |
| B. 目前補齊幾題 | 預覽1/1補齊；實際新LLM Prompt補齊尚未驗證 |
| C. 新Critical回歸 | 20題範圍內0個來源角色回歸；不等於所有材料／格式完全保留 |
| D. 完整輸入仍失敗 | 6個主案例Q011、P03、P04、P05、SHORT、WAKE；另Q005 A1為同題完整輸入仍拒答控制 |
| E. 能否進入03 | 有足夠資料做這批已知案例的分層歸因；本輪沒有啟動03 |

## 每題來源角色比較

| 問題 | 舊必要來源缺口 | 新預覽缺口 | 證據變化 |
|---|---|---|---|
| Q005 | 1558, 1559 | 無 | EVIDENCE_IMPROVED |
| Q002 | 無 | 無 | EVIDENCE_UNCHANGED_COMPLETE |
| Q007 | 無 | 無 | EVIDENCE_UNCHANGED_COMPLETE |
| Q010 | 無 | 無 | EVIDENCE_UNCHANGED_COMPLETE |
| Q006 | 無 | 無 | EVIDENCE_UNCHANGED_COMPLETE |
| Q012 | 無 | 無 | EVIDENCE_UNCHANGED_COMPLETE |
| Q011 | 無 | 無 | EVIDENCE_UNCHANGED_COMPLETE |
| P01 | 無 | 無 | EVIDENCE_UNCHANGED_COMPLETE |
| P02 | 無 | 無 | EVIDENCE_UNCHANGED_COMPLETE |
| P03 | 無 | 無 | EVIDENCE_UNCHANGED_COMPLETE |
| P04 | 無 | 無 | EVIDENCE_UNCHANGED_COMPLETE |
| P05 | 無 | 無 | EVIDENCE_UNCHANGED_COMPLETE |
| SHORT | 無 | 無 | EVIDENCE_UNCHANGED_COMPLETE |
| ENUM | 無 | 無 | EVIDENCE_UNCHANGED_COMPLETE |
| WAKE | 無 | 無 | EVIDENCE_UNCHANGED_COMPLETE |
| SPEED | 無 | 無 | EVIDENCE_UNCHANGED_COMPLETE |
| AIQUAL01-U20-03 | 無 | 無 | EVIDENCE_UNCHANGED_COMPLETE |
| AIQUAL01-U20-04 | periodic_exclusion | 無 | EVIDENCE_IMPROVED |
| AIQUAL01-U32-04 | count_reset, format | format | EVIDENCE_IMPROVED |
| AIQUAL01-LVS-03 | both_enabled, tiered_deadline | both_enabled, tiered_deadline | EVIDENCE_UNCHANGED_INCOMPLETE |

## 判讀與未解決缺口

- Q005：舊主基準沒有p450續表標題與PORT_POWER/Port/8列，目前二者均選入。歷史主基準混入USB3.2，目前限定usb20；來源資格與選取條件已改，不能歸因為單一演算法提升。A1則原本就收到完整列／關聯，當時缺證據的拒答理由已被原Review反駁。B與Reconnect成功仍是另條件觀察。
- Q011：來源角色完整，不表示Frozen citation allowlist／Parser接受；原額外p485引用與顯示限定條件問題保留。P03則原coverage PASS、semantic FAIL，主要發現是個別claim引用沒有覆蓋其複合主張；未證明USB事實錯誤。SHORT原必要S-payload在輸入內，但沒有被答案選為引用。
- P04／P05與WAKE：保留原始quote、schema、規範限定／平台結果強度問題，不重跑或覆寫原評分。新版證據完整也不證明答案會改善。ENUM與SPEED是歷史成功控制。
- Enumeration：原9.1.2段落未入選，但9.2.1、9.1.1.4、9.4.3及GET_DESCRIPTOR表共同支持原核心，獨立來源Review排除字面比對造成的假回歸。額外端點描述符片段屬較低優先背景，不聲稱整包零無關資料。
- U20-03：舊GET_INTERFACE表列與currently selected alternate setting段落已有等價支持，為UNCHANGED_COMPLETE。Nov4的31/35→33/35只是候選scorer差異，未變成正式新分數。
- U20-04：目前選入原缺的periodic endpoint排除條件；原packed_fields scorer爭議另列。原AI Gold仍未完整涵蓋Table8-3 transfer-type mapping，因此四角色齊備不等於整題正式合格。
- U32-04：目前補回count/reset段，但Frozen Corpus request表仍缺欄位；官方PDF六欄完整，已驗證的PDF grid補充另列，不能當作Frozen Chunk或已送入LLM的內容。
- LVS-03：UFP兩種enabled條件的完整分支與tiered deadline仍未全部選入；必要原文存在Corpus，保留來源選取／字元預算線索，未確認新根因或修復。

## 重放與來源身份

本輪以目前工作樹的EvidenceService.query入口在隔離程序中重放，保留HEAD與程式SHA；未核實既有Tunnel程序載入的是同一份程式，也未向其發請求、重啟或變更。正式入口本身未修改；20個查詢沿用max20chunks／39,739 serialized-evidence字元預算。原始候選、baseline windows、保守packer bundle、PDF補充及額外all-rank診斷分開保存；all-rank在選取後執行，不回饋或放寬正式預算。舊版未保存的pre-packer候選池明標未知，不能從實際sent文字倒推全部retrieval候選。

目前Corpus為4330 chunks／8aef81aa…；Native六份歷史請求的120筆E1等alias逐題以sidecar、request SHA、messages wire SHA及原prepared綁定解回canonical來源，文字／位置完全相符。以原projection fingerprint算法獨立重算得4d8eec32…，確認不同hash namespace對應同一Corpus，而非以字串不同猜測換版。

3份本機官方PDF雜湊核對、32個完整頁面文字核對及4頁圖像檢視；Q006表格逐欄閱讀確認，未把文字抽取交錯誤當官方缺資料。所有來源、頁碼、ChunkID、SHA、角色引文／offset、原始評分與候選差異均在JSON。這是AI來源審核，未冒稱人工USB工程師核准。

歷史總Prompt tokens沿用保存紀錄，Evidence-only tokens多數未單獨保存，明標缺口；本輪不呼叫Tokenizer補算。新預覽只量測各來源／bundle字元與真實budget trace，沒有可供計算的新LLM Prompt。

## 驗證與交付邊界

artifact-integrity.json包含6組真實資料不變式與9種負向污染控制（含SHORT sidecar遺漏回歸）；另有來源雜湊與工作樹保存檢查。這些驗證報告可信度，不代表USB回答合格。Scoped Independent Review見qa-attr-02-review.md。

0 LLM／Apple／下載；未修改Frozen Corpus、Gold、Digest、Prompt、Parser、Evaluator、正式Retrieval／Packer或AI Governance。未Commit／Push／Deploy，未操作服務、Tunnel或Access Code。僅追加本Slice必要PLAN／canonical memory記錄。

建議下一步是對上述完整輸入仍失敗的已知案例做QA-ATTR-03分層歸因；目前資料不支持先擴張RAG或投入SAG2，也不支持立即重跑27B。此建議不構成下一Slice或模型呼叫授權。

獨立審查：APPROVED；見 qa-attr-02-review.md／review.json。必要 canonical writer 與 memory guard 已完成；guard允許本輪完成，但既存及未提交紀錄的unbound／provenance等警告仍保留，未宣稱全域記憶健康。
