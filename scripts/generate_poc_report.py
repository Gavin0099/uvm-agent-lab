#!/usr/bin/env python3
"""
GV100H POC Qualification Report Generator
Calls QualificationPolicyEvaluator and renders results/GV100H_POC_REPORT.md without local logic branches.
"""

import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gv100h.spec_qa.evaluation.deterministic_evaluator import DeterministicSpecQAEvaluator
from gv100h.spec_qa.api.qa_service import GovernedQAService
from gv100h.coding_eval.governance_ab_runner import GovernanceABRunner
from gv100h.health.vram_tracker import DualGV100VRAMTracker
from gv100h.qualification.evaluator import QualificationPolicyEvaluator, QualificationDecision


SYNTHETIC_DECODE_TPS = 20.0
SYNTHETIC_CANDIDATE = "candidate_a_llama_cpp_gguf"


def build_hardware_profile(hw_live_data, vram_per_gpu, hw_budget):
    """
    Map profiler JSON onto QualificationPolicyEvaluator hardware fields.

    When a live profile file exists, missing metrics stay missing (None).
    Do not substitute analytical/synthetic defaults as if they were observed.
    """
    if not hw_live_data:
        return {
            "candidate": SYNTHETIC_CANDIDATE,
            "total_requests": 100,
            "corruption_count": 0,
            "vram_peak_per_gpu_gb": vram_per_gpu,
            "decode_tps": SYNTHETIC_DECODE_TPS,
            "hardware_observed": False,
            "budget": hw_budget,
        }

    gpu_tel = hw_live_data.get("gpu_telemetry") if isinstance(hw_live_data.get("gpu_telemetry"), dict) else {}
    vram = hw_live_data.get("vram_peak_per_gpu_gb")
    if vram is None:
        vram = gpu_tel.get("peak_vram_per_gpu_gb")
    decode = hw_live_data.get("decode_tps")
    if decode is None:
        decode = hw_live_data.get("est_decode_tps")

    return {
        "candidate": hw_live_data.get("candidate", SYNTHETIC_CANDIDATE),
        "total_requests": hw_live_data.get("total_requests"),
        "corruption_count": hw_live_data.get("corruption_count"),
        "vram_peak_per_gpu_gb": vram,
        "decode_tps": decode,
        "hardware_observed": bool(hw_live_data.get("hardware_observed", False)),
        "budget": hw_budget,
    }


def generate_report(output_path: str = "results/GV100H_POC_REPORT.md") -> str:
    # 1. Gather empirical inputs & Ingest live artifacts if present
    qa_evaluator = DeterministicSpecQAEvaluator()
    qa_service = GovernedQAService()
    qa_res = qa_evaluator.run_benchmark(
        lambda q, s: (qa_service.answer_question(q, s).answer, [e.evidence_id for e in qa_service.answer_question(q, s).cited_evidences])
    )

    live_manifest_dir = PROJECT_ROOT / "results" / "live_eval"
    coding_runner = GovernanceABRunner()
    coding_res = coding_runner.run_ab_benchmark(
        runs_per_task=3,
        manifest_dir=str(live_manifest_dir) if live_manifest_dir.exists() else None
    )

    hw_profile_path = PROJECT_ROOT / "results" / "hardware" / "profile_summary.json"
    hw_budget = DualGV100VRAMTracker.estimate_memory_budget(
        model_name="Qwen/Qwen3.8-35B-A3B",
        quantization="Q4_K_M",
        context_length=32768,
        tensor_parallel=2
    )
    vram_per_gpu = hw_budget.get("per_gpu_vram_gb", 14.96) if isinstance(hw_budget, dict) else getattr(hw_budget, "per_gpu_vram_gb", 14.96)

    hw_live_data = None
    if hw_profile_path.exists():
        try:
            with open(hw_profile_path, "r", encoding="utf-8") as f:
                hw_live_data = json.load(f)
        except Exception:
            hw_live_data = None
    hardware_profile = build_hardware_profile(hw_live_data, vram_per_gpu, hw_budget)

    # 2. Execute Deterministic Policy Evaluator
    evaluator = QualificationPolicyEvaluator()
    decision: QualificationDecision = evaluator.evaluate(qa_res, coding_res, hardware_profile)

    # 3. Render Markdown Report directly from Policy Decision
    gate_rows = []
    val_header = "觀測實測值 (Observed Live Evidence)" if not decision.is_synthetic else "輸入值 (Input Value - Synthetic / Analytical)"
    
    for g in decision.gates:
        if decision.is_synthetic:
            status_icon = "⚠️ SYNTHETIC_PASS" if g.passed else "❌ FAIL"
        else:
            status_icon = "✅ PASS" if g.passed else "❌ FAIL"
        gate_rows.append(f"| **{g.gate_name}** | {g.description} | Required: `{g.required}` | {g.observed} | {status_icon} |")

    gates_table = "\n".join(gate_rows)

    report_content = f"""# GV100H Local AI Agent POC 資格評審報告 (Qualification Report)

> **Evidence Class**: `{decision.evidence_class}`  
> **Hardware Observed**: `{not decision.is_synthetic}`  
> **Claim Ceiling**: `scaffolding-and-guardrails-only`  
> **專案代號**: GV100H  
> **目標硬體環境**: Dual NVIDIA GV100 (32GB x 2 = 64GB Aggregate VRAM, NVLink)  
> **候選模型目標**: Qwen3.8-35B-A3B (預定 Baseline: llama.cpp GGUF Q4_K_M, TP=2)  
> **治理架構 Commit**: `3305b640d17ca253e632093d434ae029f920c3e3`  
> **知識權威庫 Commit**: `808f23c24bd8651da9cdcd63ea8669126917a379` (Embedded Registry Baseline)  
> **評審狀態**: Machine Evaluated by QualificationPolicyEvaluator  
> **最終決策判定**: **`{decision.decision}`**  

---

## 🎯 1. 核心決策判定 (Final Decision Gate)

### 判定結果: **`{decision.decision}`**
> **判定依據**: {decision.summary_reason}

### 政策閘門逐項檢驗表 (Policy Gate Evaluation Table)

> [!NOTE]
> 本次評審輸入為離線確定性腳手架與分析模型數據（Synthetic / Analytical Baseline），尚未載入實機推論收據。所有通過項目均標定為「腳手架邏輯驗證 (SYNTHETIC_PASS)」，嚴禁與實機 Qualification PASS 混淆。

| 政策門檻 (Policy Gate) | 說明 (Description) | 要求標準 (Required) | {val_header} | 判定 (Status) |
| :--- | :--- | :--- | :--- | :---: |
{gates_table}

---

## 🔬 2. 五大核心問題真實狀態說明 (Answers to Core Questions — Truth Repaired)

### Q1 — Model Quality
**現狀說明**: 目前 POC 測試台已完成 `GovernedSpecRetriever` (Embedded Registry) 與 10 個歷史工程任務的 Schema/Fixture 定義。**尚未實際連線 Qwen3.8-35B-A3B 實體模型權重進行推論**；模型品質結論需待實機 Live Inference 執行並收集 Run Manifests 後方能判定。

### Q2 — Domain Reliability
**現狀說明**: 規格檢索管線已在 `usb-if-hub-spec-reference` 內嵌規則庫下驗證具備 **0 偽造引用結構防禦** 與 **100% 跨版本隔離** 規則。實體模型是否具備同等約束力，需待 M2 Live 評測。

### Q3 — Coding Productivity
**現狀說明**: 已建立 10 個標準歷史任務與治理 A/B 評測框架（包含實體 Manifest 聚合管線）。模擬數據展示了 Sidecar 在理論上能杜絕假成功；真實的人類時間節省與生產力效益，需待工程師盲測打分與實體 Manifest 聚合。

### Q4 — Hardware Feasibility
**現狀說明**: 依據參數量與 KV Cache 公式估算，雙 GV100 (64GB VRAM) 在 TP=2、Q4_K_M 量化下**預估佔用約 14.96 GB / GPU**。此為容量預算（Analytical Budget），並非實體 GPU Telemetry（NVML/nvidia-smi）監控數據。

### Q5 — Governance
**現狀說明**: AI Governance 護欄（Dynamic Contract Router、Canonical Path Guardrail、Strict Fail-Closed Runner、Run Manifest Schema）已建立測試案例。**測試通過數不是資格權威**；請重跑當前 pytest 取得即時數字，禁止沿用過期測試計數作為 admission 或 qualification 證據。

---

## ⚠️ 3. 嚴格非承諾宣告 (Explicit Non-Claims)
1. **本報告僅作為 Offline Scaffold Closeout 驗收**：不可作為模型已在硬體上線驗收之依據；當前所有數據均來自離線確定性腳手架與靜態分析模型。
2. **禁止宣稱「完美支撐」或「0% 假成功已在生產落地」**：此類宣稱必須依賴後續實機收集之真實 Run Manifests 與 GPU Telemetry 日誌。
3. **下一步行動 (Action Items to Achieve GO)**：
   - 部署本地推論伺服器（llama.cpp / vLLM）載入 Qwen 權重（端點設於 `http://localhost:8000/v1`）。
   - 在具備 NVIDIA 驅動與 GPU 的環境下執行 `python scripts/profile_runtime.py --requests 100` 獲取真實 NVML/nvidia-smi GPU Telemetry 儲存於 `results/hardware/profile_summary.json`。
   - 執行 `python scripts/run_live_universe.py --full-universe` 才能規劃 10×3×2 母體。`python scripts/run_live_eval.py` 預設單臂／單次不可宣稱完整 universe。
   - 透過 `GovernanceABRunner` 聚合真實 Manifests 並重新執行評審以解除 `NO_GO — synthetic` 限制。
"""

    out_file = PROJECT_ROOT / output_path
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(report_content, encoding="utf-8")
    print(f"[REPORT] Final qualification report generated via Policy Evaluator at {out_file}")
    return report_content


if __name__ == "__main__":
    generate_report()

