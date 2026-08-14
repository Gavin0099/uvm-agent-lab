# Knowledge Base & Verification Engineering Gotchas

<!-- governance:reviewer_verified -->

## ⚠️ Critical Verification & Toolchain Gotchas

### 1. UVM Simulation Log Parsing & False Positives
- **Problem**: Naive substring searches on `"UVM_ERROR"` or `"UVM_FATAL"` cause critical false-positive failures on clean simulation summary banners (e.g. `UVM_ERROR : 0`, `UVM_FATAL : 0`).
- **Solution**: The `EvidenceVerifier` and simulation log parsers must use strict regex patterns:
  - Error count: `r"UVM_ERROR\s*:\s*([1-9]\d*)"`
  - Inline error messages: `r"^UVM_ERROR\s+(?:@|[a-zA-Z0-9_/\\.]+\()"`
  - Fatal count: `r"UVM_FATAL\s*:\s*([1-9]\d*)"`

### 2. Scope Boundaries & Anti-Tampering Policy
- **Problem**: Autonomous agents attempting to achieve 100% test pass may cheat by modifying the underlying RTL design files (`rtl/`) instead of fixing the testbench or sequence constraints.
- **Rule**: Modifying any path under `rtl/`, `additional/`, or `.git/` triggers an immediate fatal violation (`SCOPE_VIOLATION_FORBIDDEN_PATH`) and forces a score of 0%.
- **Allowed verification paths**: `uvm/tests/`, `uvm/sequences/`, `uvm/ral/`, `uvm/assertions/`, `uvm/coverage/`, `uvm/env/`.

### 3. Dual GV100 (64GB VRAM) Memory Allocation Math
- **Problem**: Unquantized 32.5B parameter models (FP16/BF16) require ~65 GB of memory just for weights, causing immediate OOM on dual 32GB GV100 cards.
- **Solution**:
  - Model: `Qwen2.5-Coder-32B-Instruct-AWQ` (4-bit weights).
  - Weight memory: ~18.5 GB total (~9.25 GB per GPU at `TP=2`).
  - Remaining VRAM per card: ~22.75 GB.
  - Activation buffer: ~2.5 GB.
  - Available Paged KV Cache: ~20 GB per GPU.
  - Result: Easily sustains 128K context token generation across concurrent requests.

### 4. Functional Coverage Closure Loop Convergence
- **Problem**: When 1 or 2 unhit cross-coverage bins remain, naive division `len(bins) // 2` evaluates to 0, which can trap the coverage closure loop in an infinite cycle.
- **Solution**: `AutomatedCoverageClosureLoop` enforces eliminating at least `max(1, len(bins) // 2)` unhit bins in each iterative cycle, guaranteeing mathematical convergence.

### 5. Windows Git Path Length Limits (MAX_PATH)
- **Problem**: Submodules containing deeply nested test artifacts exceed Windows' 260-character path limit, causing `Filename too long` errors during checkout.
- **Solution**: Always ensure `git config core.longpaths true` and `git config --global core.longpaths true` are set before checking out submodules.

### 6. Model Context Protocol (MCP) JSON-RPC 2.0 Contract
- **Problem**: Free-form vector embeddings frequently hallucinate unapproved draft specs or outdated register maps.
- **Solution**: The `spec-reference-kit` MCP Server acts as an authoritative, version-locked knowledge layer. Agent requests must use JSON-RPC 2.0 tool calls (`query_spec`, `search_spec_symbols`) which provide cryptographic provenance metadata with each retrieval.
