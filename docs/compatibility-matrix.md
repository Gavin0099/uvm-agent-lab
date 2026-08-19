# Compatibility Matrix

This document tracks supported and tested configurations across EDA Simulators, Model Runtimes, and Knowledge Layer Adapters.

---

## 💻 EDA Tool & Simulator Matrix

| Simulator | Type | Status | Supported Verification Tasks | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **SimStub (Built-in)** | Deterministic Mock | ✅ Native | All (UVM-001 ~ UVM-005) | Zero external EDA dependencies required. |
| **Synopsys VCS** | Commercial EDA | 🔄 Planned | Full IEEE 1800.2 UVM | Standard industry reference. |
| **Cadence Xcelium** | Commercial EDA | 🔄 Planned | Full IEEE 1800.2 UVM | Commercial multi-core runner. |
| **Siemens Questa** | Commercial EDA | 🔄 Planned | Full IEEE 1800.2 UVM | Native SystemVerilog engine. |
| **Verilator** | Open-Source | 🔄 Planned | C++ translation / Lint | Good for fast linting & C++ co-sim. |
| **Icarus Verilog** | Open-Source | 🔄 Planned | Basic SV / Test | Lightweight smoke testing. |

---

## 🧠 Model Runtime & LLM Inference Matrix

| Runtime | Protocol | Supported Formats | Recommended Model Target |
| :--- | :--- | :--- | :--- |
| **Mock / Baseline** | Python In-Memory | N/A | Deterministic pipeline & harness testing |
| **llama.cpp** | CLI / HTTP | GGUF, Q4_K_M, Q8_0 K/V, draft MTP | Qwen3.8-27B GGUF; MTP OFF vs n-max=2 first at 128K |
| **vLLM** | OpenAI Compatible REST | FP16, AWQ, GPTQ | Secondary/experimental Qwen 2.5 Coder 32B TP=2 path |
| **SGLang** | OpenAI Compatible REST | FP16, FP8, AWQ | Ultra-low latency tool calling |
| **Ollama** | Local REST | GGUF (Q4_K_M, Q8_0) | Fast local iteration |

The active Qwen3.8-27B Gate 4 baseline uses `q8_0` for both K and V, with
128K as the first context point and 192K/256K as secondary points. q4/q5 KV
types are experimental only: the selected llama.cpp build must carry the
relevant fix reference and pass a local prefill benchmark before admission.

---

## 📚 Knowledge Layer Adapters

| Adapter Type | Protocol | Target System | Governance Status |
| :--- | :--- | :--- | :--- |
| **Canonical Spec** | Python / JSON | `spec-reference-kit` | Certified Authoritative |
| **BM25 Keyword** | Python In-Memory | Local text index | Baseline |
| **TF Cosine Baseline** | Term-frequency Cosine | Python In-Memory | Lexical baseline; not dense embeddings |
| **Governed Lexical Hybrid** | Canonical filter + BM25 + RRF | Python In-Memory | Governed lexical baseline; not dense hybrid |
| **Dense Vector RAG** | Model Embeddings + Vector Search | Optional `rag` extra | Gate 1 opt-in; model/revision must be pinned |
| **Standard Dense Hybrid** | BM25 + Dense Embeddings + RRF | Optional `rag` extra | No governance prefilter; comparison baseline |
| **Governed Dense Hybrid** | Canonical prefilter + BM25 + Dense + RRF | Optional `rag` extra | Governance-first retrieval baseline |
| **MCP Adapter** | JSON-RPC (Model Context Protocol) | External Knowledge Server | Standardized Interoperability |
