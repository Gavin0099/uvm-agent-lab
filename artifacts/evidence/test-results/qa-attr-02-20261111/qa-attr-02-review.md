> 公開審查副本：本機原始報告未改。此分支的 JSON 已去除原文；原報告所稱完整引文、Prompt／wire 與 PDF 核對指私人原始資料。公開版可審查方法與元資料，不能獨立重做原文語意驗證。原始 SHA 見 publication-provenance.json。

# QA-ATTR-02 獨立 Scoped Review

結果：APPROVED。這是獨立 agent 審查；沒有人工 USB 工程師簽核，也不批准模型回答品質、正式三人試用或 QA-ATTR-03／04。

實際審讀五個 repo 外工具與完整差分、20 題選材／replay、歷史實際 sent／raw／原始評分、來源角色引文與等價證明、PDF 保存證據、摘要及必要 PLAN／記錄差分。獨立執行 `verify_artifacts.py`：exit 0，6 組資料不變式與 9 項真實資料污染負向控制通過；另核對五工具 compile、byte-exact 差分重建、375 baseline 與 463 歷史來源保存。這些是資料／來源比較驗證，沒有重跑 query、模型或歷史評分器。

- 16 個模型問題與 4 個 retrieval-only controls 分母分開。主案例為 Q005 一項歷史必要來源缺口在目前 preview 補齊，另 15 題原本已有核心來源；critical source-role regression 為 0。六個完整核心輸入仍有原品質／引用／契約失敗的案例保留原評分，Q005 A1 同題控制不多算樣本。
- ENUM 五個核心角色及 U20-03 舊 request_format 有獨立等價來源；literal 診斷保留。Q005 續表 caption、header、Port=8 row 與原順序／同表關聯已核對。U20-04 exclusion 改善仍保留 Gold mapping 限制；U32-04 count/reset 改善仍有 frozen format 缺口；LVS-03 仍不完整。
- 4330 chunks 的 corpus projection fingerprint 獨立重算吻合。六份 native 實際 request、canonical messages wire、original-prepared SHA 及 120 aliases 的內容／section／page 逐筆通過。SHORT 的 prepared-sidecar.json／hash-key 遺漏已修正，新增 null-binding 負向控制真正拒絕；先前暫時通過狀態已撤回並以本次修正覆審取代。
- 最大保存用量 20 chunks／39,722 serialized 字元，未超過 20／39,739。三份 PDF pins、32 頁保存文字 hash 及四張完整頁圖已核對；PDF supplement、packed preview 與選取後 diagnostic 沒有冒充實際 sent。§9.6.6 已更正為端點描述符，Reset 措辭保留原 §7.3／power-up 條件。
- 16 題目前正式 LLM Prompt 比較全部 NOT_COMPARABLE，實際 Prompt closure 為 0。只核目前工作樹入口，未核既有 Tunnel 程序載入版本、未操作服務。不宣稱答案／RAG 演算法改善、一般正確率或人工工程認證。

必要記錄差分亦通過：原 PLAN／KB prefix 保留，KB 僅 CANDIDATE／UNREVIEWED、commit UNCOMMITTED；既有 daily／review／active 在 canonical finalization 前未改寫。已核准的後續僅為 exact planned-memory-record payload 經 canonical writer 記錄、更新本輪 PLAN milestone 與真實 review 狀態／連結、執行 memory workflow／guard，以及 facts-only 保存 manifest。須保留警示及 reviewed／final 狀態差異；不得預先宣稱 guard 通過或全庫 clean，不啟動 03／04 或任何新 query／模型／下載／服務／commit／push／deploy。

精確檔案 hash、檢查證據與收尾條件見同目錄 review.json。canonical 記錄、最後 guard 及最後保存核對仍待執行。
