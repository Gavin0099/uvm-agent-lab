# Evaluation Strategy: Gates 0 Through 4

This document defines the quantitative evaluation framework for assessing UVM AI Verification Agents across 5 progressive gates.

---

## 🚦 Gate Breakdown & Criteria

```
+─────────────────────────────────────────────────────────────────────────────+
| Gate 0: Benchmark Definition                                                |
| - Validate schemas, verify test cases represent real engineering tasks.     |
+─────────────────────────────────────────────────────────────────────────────+
                                       │
                                       ▼
+─────────────────────────────────────────────────────────────────────────────+
| Gate 1: Spec / Retrieval Accuracy                                           |
| - Compare spec-reference-kit vs BM25 vs Vector RAG vs Hybrid.               |
| - Metrics: Recall@1, Recall@3, Wrong-Version %, Wrong-Authority %.          |
+─────────────────────────────────────────────────────────────────────────────+
                                       │
                                       ▼
+─────────────────────────────────────────────────────────────────────────────+
| Gate 2: Agent Harness & Governance Stress Test                              |
| - Deterministic testbed, tool correctness, sandbox & scope protection.      |
| - Zero-trust evidence verification.                                         |
+─────────────────────────────────────────────────────────────────────────────+
                                       │
                                       ▼
+─────────────────────────────────────────────────────────────────────────────+
| Gate 3: Model A/B Testing                                                   |
| - Apples-to-apples comparison across LLMs with fixed tools and budgets.     |
| - Metrics: Task Success, Compile Pass, Simulation Pass, Retries, Token Cost.|
+─────────────────────────────────────────────────────────────────────────────+
                                       │
                                       ▼
+─────────────────────────────────────────────────────────────────────────────+
| Gate 4: GV100 Hardware Characterization                                     |
| - Local execution profiling: VRAM, TTFT, tok/s, 32K-128K context, TP=1 vs 2.|
+─────────────────────────────────────────────────────────────────────────────+
```

---

## 📈 Quantitative Metrics per Gate

### Gate 1: Retrieval Metrics
- **Recall@K (K=1, 3)**: Did the top $K$ results contain the exact governing clause?
- **Wrong-Version Rate**: Percentage of queries returning deprecated or mismatching spec version clauses.
- **Wrong-Authority Rate**: Percentage of queries returning non-authoritative discussion notes instead of certified spec text.
- **Wrong-Customer Leak Rate**: Percentage of queries returning clauses restricted to different customer tiers.

### Gate 2 & 3: Agent Performance Metrics
- **Task Success Rate ($S_{task}$)**: Fully compiled and simulated pass without human intervention.
- **Compile Success Rate ($S_{comp}$)**: Zero compiler errors on first try and final attempt.
- **Simulation Pass Rate ($S_{sim}$)**: UVM Test passed without scoreboard mismatches.
- **Scope Violation Rate ($R_{viol}$)**: Number of forbidden file touches per 100 tasks (Target: 0.0%).
- **Retry Count ($N_{retry}$)**: Average turns to convergence.
- **Token Efficiency**: (Tokens Consumed / Tasks Solved).
- **Evidence Integrity Rate**: Verified genuine evidence / Submitted evidence (Target: 100%).

### Gate 4: Hardware Profiling Metrics
- **VRAM Utilization**: Peak memory during 32K, 64K, 128K context window KV cache.
- **Time to First Token (TTFT)**: Latency before first tool action.
- **Generation Speed**: Tokens per second (tok/s) under single-agent and multi-agent load.
- **Tensor Parallelism Scaling Efficiency**: $Speedup(TP=2) / 2.0$.
