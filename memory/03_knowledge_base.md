# Knowledge Base

## Gotchas & Verification Lessons
- **UVM Log Regex**: Naive substring match `"UVM_ERROR"` causes false positives on clean summary lines (`UVM_ERROR : 0`). `EvidenceVerifier` must use boundary regex `r"UVM_ERROR\s*:\s*([1-9]\d*)"`.
- **GV100 Precision**: FP16 unquantized 32.5B parameter models trigger OOM on dual 32GB cards. Must use AWQ 4-bit quantization with `TP=2` to leave >14.5 GB / GPU for KV Cache scaling up to 128K context.
- **RTL Scope Protection**: Modifying `rtl/` is strictly forbidden and triggers `SCOPE_VIOLATION_FORBIDDEN_PATH` with immediate fatal 0% score override.
