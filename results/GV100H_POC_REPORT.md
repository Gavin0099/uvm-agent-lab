# GV100H Local AI Agent POC 資格評審報告 (Qualification Report)

> **Evidence Class**: `synthetic_offline_scaffold`
> **Hardware Observed**: `False`
> **Claim Ceiling**: `scaffolding-and-guardrails-only`
> **專案代號**: GV100H
> **目標硬體環境**: Tesla V100 32GB (single-GPU baseline; dual-GV100 expansion)
> **候選模型目標**: Qwen/Qwen3.8-27B (llama.cpp, Qwen3.8-27B-Q4_K_M.gguf, Q4_K_M, q8_0 K/V, TP=1)
> **Context 測量順序**: primary [32768, 65536, 131072]; stretch [196608, 262144]
> **治理架構 Commit**: `3305b640d17ca253e632093d434ae029f920c3e3`  
> **知識權威庫 Commit**: `808f23c24bd8651da9cdcd63ea8669126917a379` (Embedded Registry Baseline)  
> **評審狀態**: Machine Evaluated by QualificationPolicyEvaluator  
> **最終決策判定**: **`NO_GO — synthetic/offline scaffold only`**  

---

## 🎯 1. 核心決策判定 (Final Decision Gate)

### 判定結果: **`NO_GO — synthetic/offline scaffold only`**
> **判定依據**: Offline testing scaffold, contracts, guardrails, and deterministic evaluation pipelines are operational. Physical Dual GV100 live execution manifests and real Qwen model endpoint inference receipts are currently pending.

### 政策閘門逐項檢驗表 (Policy Gate Evaluation Table)

> [!NOTE]
> 本次評審輸入為離線確定性腳手架與分析模型數據（Synthetic / Analytical Baseline），尚未載入實機推論收據。所有通過項目均標定為「腳手架邏輯驗證 (SYNTHETIC_PASS)」，嚴禁與實機 Qualification PASS 混淆。

| 政策門檻 (Policy Gate) | 說明 (Description) | 要求標準 (Required) | 輸入值 (Input Value - Synthetic / Analytical) | 判定 (Status) |
| :--- | :--- | :--- | :--- | :---: |
| **spec_qa.max_fabricated_citations** | Zero fabricated citation guarantee | Required: `0` | 0 | ⚠️ SYNTHETIC_PASS |
| **spec_qa.max_authority_violations** | Zero authority escalation violation | Required: `0` | 0 | ⚠️ SYNTHETIC_PASS |
| **spec_qa.min_grounded_accuracy** | Cat A grounded factual accuracy | Required: `90.0` | 100.0 | ⚠️ SYNTHETIC_PASS |
| **spec_qa.min_version_scope_accuracy** | Cat B cross-version scope isolation | Required: `100.0` | 100.0 | ⚠️ SYNTHETIC_PASS |
| **spec_qa.min_adversarial_pass_rate** | Cat D adversarial safety behavior | Required: `100.0` | 100.0 | ⚠️ SYNTHETIC_PASS |
| **spec_qa.min_unsupported_refusal_rate** | Cat C out-of-scope question refusal | Required: `95.0` | 100.0 | ⚠️ SYNTHETIC_PASS |
| **coding_agent.max_false_success_rate** | Deterministic elimination of false successes | Required: `0.0` | 0.0 | ⚠️ SYNTHETIC_PASS |
| **coding_agent.max_scope_violations** | Zero out-of-bounds scope tampering | Required: `0` | 0 | ⚠️ SYNTHETIC_PASS |
| **coding_agent.min_human_acceptance_a_b_rate** | Engineer acceptance rating (A/B) | Required: `70.0` | 80.0 | ⚠️ SYNTHETIC_PASS |
| **hardware_feasibility.max_corruption_count** | Zero corruption under sustained continuous requests | Required: `0` | 0 | ⚠️ SYNTHETIC_PASS |
| **coding_agent.min_task_success_rate** | Governed-sidecar task success rate | Required: `75.0` | 80.0 | ⚠️ SYNTHETIC_PASS |
| **hardware_feasibility.max_vram_usage_per_gpu_gb** | Peak VRAM per GPU within Dual GV100 budget | Required: `30.0` | 19.13 | ⚠️ SYNTHETIC_PASS |
| **hardware_feasibility.min_est_decode_tps** | Sustained decode throughput | Required: `15.0` | 20.0 | ⚠️ SYNTHETIC_PASS |

---

## 🔬 2. 五大核心問題真實狀態說明 (Answers to Core Questions — Truth Repaired)

### Q1 — Model Quality
**現狀說明**: 目前 POC 測試台已完成 `GovernedSpecRetriever` (Embedded Registry) 與 10 個 canonical UVM benchmark cases 的 Schema/Fixture 定義。**尚未實際連線 Qwen/Qwen3.8-27B 實體模型權重進行推論**；模型品質結論需待實機 Live Inference 執行並收集 Run Manifests 後方能判定。

### Q2 — Domain Reliability
**現狀說明**: 規格檢索管線已在 `usb-if-hub-spec-reference` 內嵌規則庫下驗證具備 **0 偽造引用結構防禦** 與 **100% 跨版本隔離** 規則。實體模型是否具備同等約束力，需待 M2 Live 評測。

### Q3 — Coding Productivity
**現狀說明**: 已建立 10 個 canonical UVM benchmark cases 與治理 A/B 評測框架（30 paired executions / 60 manifests 的聚合管線）。模擬數據展示了 Sidecar 在理論上能杜絕假成功；真實的人類時間節省與生產力效益，需待工程師盲測打分與實體 Manifest 聚合。

### Q4 — Hardware Feasibility
**現狀說明**: 依據參數量與 KV Cache 公式估算，Tesla V100 32GB (single-GPU baseline; dual-GV100 expansion) 的首輪 llama.cpp baseline 使用 q8_0 K/V、Q4_K_M、context 32768、TP=1，**預估佔用約 19.13 GB / GPU**。此為容量預算（Analytical Budget），並非實體 GPU Telemetry（NVML/nvidia-smi）監控數據。

### Q5 — Governance
**現狀說明**: AI Governance 護欄（Dynamic Contract Router、Canonical Path Guardrail、Strict Fail-Closed Runner、Run Manifest Schema）已建立測試案例。**測試通過數不是資格權威**；請重跑當前 pytest 取得即時數字，禁止沿用過期測試計數作為 admission 或 qualification 證據。

---

## ⚠️ 3. 嚴格非承諾宣告 (Explicit Non-Claims)
1. **本報告僅作為 Offline Scaffold Closeout 驗收**：不可作為模型已在硬體上線驗收之依據；當前所有數據均來自離線確定性腳手架與靜態分析模型。
2. **禁止宣稱「完美支撐」或「0% 假成功已在生產落地」**：此類宣稱必須依賴後續實機收集之真實 Run Manifests 與 GPU Telemetry 日誌。
3. **下一步行動 (Action Items to Achieve GO)**：
   - 部署本地推論伺服器（llama.cpp / vLLM）載入 Qwen 權重（端點設於 `http://localhost:8000/v1`）。
   - 在具備 NVIDIA 驅動與 GPU 的環境下執行 `python scripts/profile_runtime.py --requests 100` 獲取真實 NVML/nvidia-smi GPU Telemetry 儲存於 `results/hardware/profile_summary.json`。
    - 先以 32K、64K、128K 執行 primary context sweep，再將 192K、256K 作為 stretch；`python scripts/run_live_universe.py --full-universe` 才能執行 10×3×2 母體。`python scripts/run_live_eval.py` 已 deprecated，不可作為 producer。
   - 透過 `GovernanceABRunner` 聚合真實 Manifests 並重新執行評審以解除 `NO_GO — synthetic` 限制。
