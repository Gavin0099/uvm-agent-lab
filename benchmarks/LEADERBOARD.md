# UVM Agent Lab — Industrial Verification Leaderboard

> **Last Updated**: 2026-08-15
> **Benchmark Cases**: UVM-001 through UVM-010 (10 Industrial Cases)
> **Governance Policy**: Zero-Trust Scope Isolation (`rtl/` Tampering = 0% Fatal)

| Rank | Configuration & Model | Retrieval Engine | Agent Paradigm | Compile % | Sim Pass % | Coverage % | Mean Turns | Scope Viol. | Composite Score |
| :---: | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| 🥇 | **SFT/DPO Fine-Tuned + Coverage Closure (UVM-Agent-Lab)**<br>`Qwen2.5-Coder-32B-UVM-DPO (Dual GV100)` | spec-reference-kit (Canonical MCP) | Multi-Turn + Automated Coverage Loop | 100.0% | 100.0% | 98.6% | 1.6 | ✅ 0% | **88.08 / 100** |
| 🥈 | **Governed MCP + Multi-Turn Self-Healing**<br>`Qwen2.5-Coder-32B-Instruct (AWQ 4-bit)` | spec-reference-kit (MCP JSON-RPC) | MultiTurnHealingAgentRunner | 100.0% | 90.0% | 88.5% | 2.4 | ✅ 0% | **79.05 / 100** |
| 🥉 | **Naive Vector RAG + Single-Turn**<br>`Qwen2.5-Coder-32B-Instruct` | Vector Similarity (Top-3 Chunk) | Single-Turn Augmented | 70.0% | 40.0% | 58.0% | 1.0 | ✅ 0% | **47.40 / 100** |
| #4 | **Zero-Shot Baseline (Generic LLM)**<br>`Qwen2.5-Coder-32B-Instruct` | None (Prompt-only) | Single-Turn Zero-Shot | 60.0% | 30.0% | 42.5% | 1.0 | ❌ 10.0% | **0.00 / 100** |

---

## 🔬 Evaluation Insights & Metrics Breakdown
- **Governed MCP Advantage**: Structured JSON-RPC 2.0 retrieval prevents draft specification pollution and improves first-turn accuracy by +50% over vector chunking.
- **Multi-Turn Healing Impact**: Multi-turn self-healing loops repair 100% of compile syntax errors and 88%+ of dynamic UVM phase timing mismatches.
- **Coverage Closure Loop**: Targeted constrained random sequence synthesis eliminates unhit cross-bins within 2 iterations, achieving >98% functional coverage.
- **Zero-Trust Scope Enforcement**: Scope violations (modifying `rtl/` to bypass bugs) are automatically detected and penalized with a 0.0 composite score.