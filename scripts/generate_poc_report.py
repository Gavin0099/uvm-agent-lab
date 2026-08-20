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
from gv100h.runtime.ssot import GV100H_BASELINE


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
            "model_id": None,
            "total_requests": 100,
            "corruption_count": 0,
            "vram_peak_per_gpu_gb": vram_per_gpu,
            "decode_tps": SYNTHETIC_DECODE_TPS,
            "hardware_observed": False,
            "gate_passed": False,
            "profile_identity": None,
            "model_provenance_ready": False,
            "model_provenance_independent": False,
            "context_fixture_bound": False,
            "launch_context_bound": False,
            "launch_profile_arm_consistent": False,
            "response_oracle": None,
            "budget": hw_budget,
        }

    gpu_tel = hw_live_data.get("gpu_telemetry") if isinstance(hw_live_data.get("gpu_telemetry"), dict) else {}
    vram = hw_live_data.get("vram_peak_per_gpu_gb")
    if vram is None:
        vram = gpu_tel.get("peak_vram_per_gpu_gb")
    decode = hw_live_data.get("decode_tps")
    if decode is None:
        decode = hw_live_data.get("est_decode_tps")

    candidate_value = hw_live_data.get("candidate", SYNTHETIC_CANDIDATE)
    if isinstance(candidate_value, dict):
        candidate_value = (
            hw_live_data.get("candidate_name")
            or candidate_value.get("name")
            or SYNTHETIC_CANDIDATE
        )

    return {
        "candidate": candidate_value,
        "model_id": hw_live_data.get("model_id"),
        "total_requests": hw_live_data.get("total_requests"),
        "corruption_count": hw_live_data.get("corruption_count"),
        "vram_peak_per_gpu_gb": vram,
        "decode_tps": decode,
        "hardware_observed": bool(hw_live_data.get("hardware_observed", False)),
        "gate_passed": hw_live_data.get("gate_passed"),
        "profile_identity": hw_live_data.get("profile_identity"),
        "model_provenance_ready": hw_live_data.get("model_provenance_ready"),
        "model_provenance_independent": hw_live_data.get("model_provenance_independent"),
        "context_fixture_bound": hw_live_data.get("context_fixture_bound"),
        "launch_context_bound": hw_live_data.get("launch_context_bound"),
        "launch_profile_arm_consistent": hw_live_data.get("launch_profile_arm_consistent"),
        "response_oracle": hw_live_data.get("response_oracle"),
        "nvlink": gpu_tel.get("initial", {}).get("nvlink"),
        "launch_profile": hw_live_data.get("launch_profile"),
        "budget": hw_budget,
    }


def _load_hardware_profile(hardware_profile_path: str | None) -> dict | None:
    """Load an explicitly selected profile; no path means synthetic input only."""

    if not hardware_profile_path:
        return None
    profile_path = Path(hardware_profile_path)
    if not profile_path.is_absolute():
        profile_path = PROJECT_ROOT / profile_path
    if not profile_path.is_file():
        raise FileNotFoundError(
            f"explicit hardware profile summary does not exist: {profile_path}"
        )
    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid explicit hardware profile summary: {profile_path}") from exc
    if not isinstance(profile, dict):
        raise ValueError("explicit hardware profile summary must be a JSON object")
    return profile


def generate_report(
    output_path: str = "results/GV100H_POC_REPORT.md",
    hardware_profile_path: str | None = None,
) -> str:
    candidate = GV100H_BASELINE
    model_reference = candidate.model_id if "/" in candidate.model_id else f"Qwen/{candidate.model_id}"
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

    hw_budget = DualGV100VRAMTracker.estimate_memory_budget(
        model_name=model_reference,
        quantization=candidate.quantization,
        context_length=candidate.baseline_context_length,
        tensor_parallel=candidate.tensor_parallel,
        kv_cache_type=candidate.kv_cache_type,
    )
    vram_per_gpu = (
        hw_budget.get("peak_vram_per_gpu_gb")
        if isinstance(hw_budget, dict)
        else getattr(hw_budget, "peak_vram_per_gpu_gb", None)
    )

    hw_live_data = _load_hardware_profile(hardware_profile_path)
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
> **目標硬體環境**: {candidate.target_hardware}
> **候選模型目標**: {model_reference} ({candidate.runtime_type}, {candidate.model_artifact}, {candidate.quantization}, {candidate.kv_cache_type_k} K/V, TP={candidate.tensor_parallel})
> **Context 測量順序**: primary {list(candidate.context_sweep)}; stretch {list(candidate.stretch_context_sweep)}
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
**現狀說明**: 目前 POC 測試台已完成 `GovernedSpecRetriever` (Embedded Registry) 與 10 個 canonical UVM benchmark cases 的 Schema/Fixture 定義。**尚未實際連線 {model_reference} 實體模型權重進行推論**；模型品質結論需待實機 Live Inference 執行並收集 Run Manifests 後方能判定。

### Q2 — Domain Reliability
**現狀說明**: 規格檢索管線已在 `usb-if-hub-spec-reference` 內嵌規則庫下驗證具備 **0 偽造引用結構防禦** 與 **100% 跨版本隔離** 規則。實體模型是否具備同等約束力，需待 M2 Live 評測。

### Q3 — Coding Productivity
**現狀說明**: 已建立 10 個 canonical UVM benchmark cases 與治理 A/B 評測框架（30 paired executions / 60 manifests 的聚合管線）。模擬數據展示了 Sidecar 在理論上能杜絕假成功；真實的人類時間節省與生產力效益，需待工程師盲測打分與實體 Manifest 聚合。

### Q4 — Hardware Feasibility
**現狀說明**: 依據參數量與 KV Cache 公式估算，{candidate.target_hardware} 的首輪 {candidate.runtime_type} baseline 使用 {candidate.kv_cache_type_k} K/V、{candidate.quantization}、context {candidate.baseline_context_length}、TP={candidate.tensor_parallel}，**預估佔用約 {vram_per_gpu} GB / GPU**。此為容量預算（Analytical Budget），並非實體 GPU Telemetry（NVML/nvidia-smi）監控數據。

### Q5 — Governance
**現狀說明**: AI Governance 護欄（Dynamic Contract Router、Canonical Path Guardrail、Strict Fail-Closed Runner、Run Manifest Schema）已建立測試案例。**測試通過數不是資格權威**；請重跑當前 pytest 取得即時數字，禁止沿用過期測試計數作為 admission 或 qualification 證據。

---

## ⚠️ 3. 嚴格非承諾宣告 (Explicit Non-Claims)
1. **本報告僅作為 Offline Scaffold Closeout 驗收**：不可作為模型已在硬體上線驗收之依據；當前所有數據均來自離線確定性腳手架與靜態分析模型。
2. **禁止宣稱「完美支撐」或「0% 假成功已在生產落地」**：此類宣稱必須依賴後續實機收集之真實 Run Manifests 與 GPU Telemetry 日誌。
3. **下一步行動 (Action Items to Achieve GO)**：
   - 部署本地推論伺服器（llama.cpp / vLLM）載入 Qwen 權重（端點設於 `http://localhost:8000/v1`）。
    - 在具備 NVIDIA 驅動與 GPU 的環境下，使用 approved model manifest、context fixture、resolved launch profile 與 expected response hash 執行 `scripts/profile_runtime.py`；每個 context/profile cell 必須輸出獨立 profile summary，不能以 metadata-only sweep 或預設檔案路徑取代實際 evidence。
    - 先以 32K、64K、128K 執行 primary context sweep，再將 192K、256K 作為 stretch；`python scripts/run_live_universe.py --full-universe` 才能執行 10×3×2 母體。`python scripts/run_live_eval.py` 已 deprecated，不可作為 producer。
   - 透過 `GovernanceABRunner` 聚合真實 Manifests 並重新執行評審以解除 `NO_GO — synthetic` 限制。
"""

    out_file = PROJECT_ROOT / output_path
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(report_content, encoding="utf-8")
    print(f"[REPORT] Final qualification report generated via Policy Evaluator at {out_file}")
    return report_content


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Render the Gate 4 qualification report")
    parser.add_argument("--output", default="results/GV100H_POC_REPORT.md")
    parser.add_argument(
        "--hardware-profile",
        default=None,
        help="Explicit profile summary JSON; missing paths fail closed.",
    )
    args = parser.parse_args()
    generate_report(output_path=args.output, hardware_profile_path=args.hardware_profile)

