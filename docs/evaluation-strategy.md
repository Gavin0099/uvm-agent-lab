# Evaluation Strategy: Gates 0 Through 4

This document defines the quantitative evaluation framework for the v1 Local AI Agent Qualification Harness across five gates. UVM/EDA execution remains a Phase 2 validator plugin, not a v1 admission dependency.

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
| - Evaluate the POC-1 capability contract before comparing retrieval arms.    |
| - Compare governed canonical retrieval, BM25, TF cosine, dense embedding,   |
|   and standard/governed dense hybrids. Dense arms are explicit opt-in.       |
| - Metrics: Recall@1, Recall@3, grounding, citation, abstention, and         |
|   Wrong-Version / Wrong-Authority %.                                        |
+─────────────────────────────────────────────────────────────────────────────+
                                       │
                                       ▼
+─────────────────────────────────────────────────────────────────────────────+
| Gate 2: Agent Harness & Governance Stress Test                              |
| - Deterministic testbed, worktree, static checks, tests, lint, and scope.   |
| - Zero-trust evidence verification.                                         |
+─────────────────────────────────────────────────────────────────────────────+
                                       │
                                       ▼
+─────────────────────────────────────────────────────────────────────────────+
| Gate 3: Model A/B Testing                                                   |
| - Apples-to-apples comparison across local coding agents with fixed budgets. |
| - Metrics: Task Success, Test Pass, Scope, False Success, Retries, Cost.     |
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

### Gate 1: POC-1 USB Hub Spec QA Capability Contract

The POC-1 scope and acceptance contract is defined in
[`docs/USB_SPEC_QA_POC1_SCOPE.md`](USB_SPEC_QA_POC1_SCOPE.md). Gate 1 must
report these capabilities separately from raw retrieval quality:

The corpus is a locked two-layer surface: Layer A is the governed structured
reference `Gavin0099/usb-if-hub-spec-reference`; Layer B is the official raw
USB 2.0/USB 3.2/LVS text bound by
`gv100h/spec_qa/contracts/corpus.lock.yaml`. The governed reference supplies
authority and claim boundaries but does not imply full specification coverage.
Unbound raw sources keep the result at manifest-only status.

- **P0 Retrieval**: correct authoritative document, revision, chapter, and section.
- **P0 Grounded Answer**: every material claim maps to retrieved evidence.
- **P0 Citation**: document, revision, chapter, section, page or stable anchor, and excerpt/evidence ID are present and valid.
- **P1 Cross-Spec Reasoning**: the requirement -> Hub behavior -> LVS test chain is retrieved and explained as a separate score.
- **P0 Unknown/Conflict Handling**: unsupported, out-of-scope, wrong-version, wrong-authority, and contradictory questions produce abstain/conflict results without fabricated evidence.

The first corpus includes USB 2.0 FW Ch.5 and Ch.8-11, USB 2.0 SE Ch.6-7,
USB 3.2 Rev.1.1 Ch.6/7/9/10, and SuperSpeed Hub LVS Rev.1.15. USB4 is Phase 2 and
must remain a Phase 1 negative control. The existing Golden 30 is a smoke
baseline; the final POC-1 benchmark is a fixed, versioned 50-100 question set
covering L1 single-spec facts, L2 engineering interpretation, L3 cross-document
QA, and L4 uncertainty/contradiction. Golden questions are evaluation-only and
must be independently reviewed rather than generated from retrieved corpus
chunks or same-corpus model answers.

P0 admission requires `Recall@1 >= 95%`, `Wrong-Version Rate = 0%`, zero
fabricated citations, zero unsupported claims on negative controls, and 100%
valid citations for accepted answer cases. P1 results are never collapsed into
the P0 retrieval score.

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
- **Task Success Rate ($S_{task}$)**: Required change passes the selected validator profile without untracked human repair.
- **Lightweight Validation Rate ($S_{light}$)**: Syntax, pytest, lint, and deterministic assertions pass for v1 cases.
- **EDA Validation Rate ($S_{eda}$)**: Compile/simulation/coverage pass only for explicit Phase 2 `eda` cases.
- **Scope Violation Rate ($R_{viol}$)**: Number of forbidden file touches per 100 tasks (Target: 0.0%).
- **Retry Count ($N_{retry}$)**: Average turns to convergence.
- **Token Efficiency**: (Tokens Consumed / Tasks Solved).
- **Evidence Integrity Rate**: Verified genuine evidence / Submitted evidence (Target: 100%).

The `validator_profile` is part of every case contract:

```text
lightweight: file scope, git diff, syntax, pytest, lint, deterministic assertions
eda:         Verilator/Icarus/VCS/UVM simulation/coverage and tool-specific logs
```

An unavailable EDA tool can fail an `eda` case, but it must not fail a v1
`lightweight` case or block the v1 qualification decision.

The CI benchmark signals are intentionally separated. The legacy EDA smoke
step selects only `UVM-*.yaml` and returns a non-zero exit code when a selected
case fails. The v1 Coding Agent readiness report selects the canonical
`AGENT-CODE-001` through `AGENT-CODE-005` cases and reports `READY` or
`NOT_READY` separately; its default report-only exit code does not imply model,
hardware, or qualification success. A future blocking v1 gate must opt in with
`--fail-on-not-ready` after the production path and all five cases are ready.

### Gate 4: Hardware Profiling Metrics
- **VRAM Utilization**: Peak memory during 32K, 64K, 128K primary and exploratory 192K/256K context window KV cache.
- **Time to First Token (TTFT)**: Latency before first tool action.
- **Prefill Throughput**: Prompt tokens/sec and prefill latency, recorded separately from decode.
- **Generation Speed**: Decode tokens/sec under single-agent and multi-agent load.
- **Runtime Provenance**: Model SHA-256, llama.cpp commit/version, K/V cache types, and MTP arm.
- **Qualification Stability**: Corruption count, request success, wall-clock, agent work-item success, and human intervention count.
- **Tensor Parallelism Scaling Efficiency**: $Speedup(TP=2) / 2.0$.
