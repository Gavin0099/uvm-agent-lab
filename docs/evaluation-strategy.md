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
| - Compare governed canonical retrieval, BM25, TF cosine, dense embedding,   |
|   and standard/governed dense hybrids. Dense arms are explicit opt-in.       |
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

Gate 1 v2 retrieval arms are explicitly separated by implementation and governance:

```text
A. spec-reference-kit / governed canonical retrieval
B. BM25 only
C. TF cosine lexical historical baseline
D. Dense embedding only (optional rag backend)
E. Governed lexical hybrid: canonical prefilter + BM25 + RRF
F. Standard dense hybrid: BM25 + dense + RRF, no governance prefilter
G. Governed dense hybrid: canonical prefilter + BM25 + dense + RRF
```

The canonical layer defines the eligible corpus before lexical or dense scoring.
Dense model revision, corpus hash, query-set hash, embedding dimension, and
normalization must be recorded with every dense evaluation. Retrieval metrics
alone do not establish production RAG, hardware qualification, or agent
qualification admission.

### Gate 2 & 3: Agent Performance Metrics
- **Task Success Rate ($S_{task}$)**: Fully compiled and simulated pass without human intervention.
- **Compile Success Rate ($S_{comp}$)**: Zero compiler errors on first try and final attempt.
- **Simulation Pass Rate ($S_{sim}$)**: UVM Test passed without scoreboard mismatches.
- **Scope Violation Rate ($R_{viol}$)**: Number of forbidden file touches per 100 tasks (Target: 0.0%).
- **Retry Count ($N_{retry}$)**: Average turns to convergence.
- **Token Efficiency**: (Tokens Consumed / Tasks Solved).
- **Evidence Integrity Rate**: Verified genuine evidence / Submitted evidence (Target: 100%).

### Gate 4: Hardware Profiling Metrics
- **VRAM Utilization**: Peak memory during 32K, 64K, 128K primary and exploratory 192K/256K context window KV cache.
- **Time to First Token (TTFT)**: Latency before first tool action.
- **Prefill Throughput**: Prompt tokens/sec and prefill latency, recorded separately from decode.
- **Generation Speed**: Decode tokens/sec under single-agent and multi-agent load.
- **Runtime Provenance**: Model SHA-256, llama.cpp commit/version, K/V cache types, and MTP arm.
- **Qualification Stability**: Corruption count, request success, wall-clock, agent work-item success, and human intervention count.
- **Tensor Parallelism Scaling Efficiency**: $Speedup(TP=2) / 2.0$.
