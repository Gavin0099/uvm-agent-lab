# QA-ATTR-02：供其他 agent 審查

這個分支交付已完成的 QA-ATTR-02 分析與公開審查材料。原測試工作樹為 `873c2061836fb39059e5d8289a4ecda4c820a2ee` 加當時未提交來源；本發布分支以 `71aeb028f95d814505f66be262ae404f22d9ed96` 為基準，沒有把其他工作樹變更混入正式程式。

## 從這裡開始

1. [原分析摘要](qa-attr-02-summary.md)：16 個歷史模型問題＋4 個 retrieval-only 控制；Q005 舊主基準缺口目前預覽補齊，6 個主案例在完整輸入時仍有品質／引用／契約失敗。
2. [案例選擇](qa-attr-02-case-selection.json)、[證據差異](qa-attr-02-evidence-diff.json)：公開 JSON 的 `.data` 才是原報告投影；外層保留原始檔案 SHA 與投影限制。
3. [既有獨立審查](qa-attr-02-review.md)、[機器記錄](review.json)：核准的是本機原分析，並非對這份公開投影的新語意認證。
4. `analysis-tools/` 為當時五份分析工具的原樣副本；`source-snapshots/` 為當時入口的靜態程式快照。它們不取代本分支正式程式，也不要直接執行其中的本機重放工具。

## 公開資料邊界

Repo 的 PLAN 明訂官方 Spec 原始資料保留於 private staging。因此本分支沒有官方 PDF、頁面圖片、Corpus 原文、完整 Prompt／wire／completion 或憑證。證據文字以 `withheld`、SHA256 及字元長度表示；長捕獲字串同樣遮蔽。`corpus-index.json` 只含原 4,330 chunks 的位置與雜湊元資料。

公開資料可以支援程式、分母、來源身分一致性、既有預算／執行記錄，以及結論是否過度宣稱的審查。**不能僅靠這個分支重新確認 USB 原文語意、完整 request／wire 綁定或模型答案改善。** 這些需要 Owner 提供原私人證據；不能把其缺失補成 PASS。

原 Markdown 報告中的絕對路徑、舊 `UNCOMMITTED`、未 Commit／Push 等敘述，是原分析完成時的狀態。此次 Owner 另行授權 Commit／Push；本次只發布審查材料，沒有啟動 QA-ATTR-03、模型測試、Merge 或 Deploy。原檔 SHA 與本次轉換記錄見 [publication-provenance.json](publication-provenance.json)。

## 唯讀離線核對

在 Repo 根目錄執行，使用 Python 3.9 以上，僅標準函式庫：

```bash
python3 -B artifacts/evidence/test-results/qa-attr-02-20261111/verify_published.py
```

核對 manifest、165/108/39 分組、16＋4 分母、120 aliases 的元資料、20 份零生成記錄及預算，並跑十一個負向污染案例（含五類短原文字段／表格的遮蔽回歸）。這是公開投影的一致性檢查，不是重跑原本的六組／九項私人證據驗證，也不是 USB 回答資格測試。

## 審查重點

- 同題重試與 Q005 A1/B/Reconnect 控制不能增加獨立樣本權重。
- 舊 actual-sent、目前候選／bundle、PDF 補充與 post-selection rank 診斷必須分開。
- 目前 Evidence-first 不建 LLM Prompt；預覽補齊不能宣稱新答案改善或純演算法因果。
- ENUM 與 U20-03 的等價支持判定，以及 SHORT sidecar 檔名修正，保留原發現與修正記錄。
- U20-04 Gold mapping 邊界、U32-04 Corpus 表格缺漏、LVS-03 選取缺口仍未消失。
- 有原文語意審查需求時，請標示「需私人原始證據」，不要啟動新的模型或翻譯呼叫。
