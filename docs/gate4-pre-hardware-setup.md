# Gate 4 Pre-GV100 Setup Runbook

## Baseline

The first measured baseline is a single-V100 control pair:

```text
Qwen3.8-27B-Q4_K_M.gguf
llama.cpp
Q8_0 KV cache for the first baseline
Flash Attention
parallel=1
MTP OFF vs draft-mtp n-max=2
```

The configuration source is [deploy/llama_cpp_gv100.yaml](../deploy/llama_cpp_gv100.yaml), projected from `gv100h.runtime.ssot.GV100H_BASELINE`.

The external MTP report is a hypothesis and reference only. It is not local hardware evidence and cannot grant Gate 4 admission. External llama.cpp issue #27109 reports a possible Qwen3.8 q4 KV prefill regression; PR #27140 is not assumed in every build, so q4 KV is not the first baseline.

## Before Hardware Arrives

1. Run the preflight:

   ```powershell
   python scripts/gate4_preflight.py --repo-root . --output artifacts/preflight/gate4-preflight.json
   ```

2. Obtain the exact GGUF artifact and record its SHA-256. Do not replace the model with a similarly named file.
3. Install or build `llama-server` with `draft-mtp` support and record the binary version/commit.
4. Keep the same model, KV type, Flash Attention setting, parallelism, prompt corpus, and sampling configuration between MTP OFF and n-max=2.
5. Prepare the context sweep: 128K first, then 192K and exploratory 256K.
6. Prepare the evidence output for every run:
   - model artifact hash
   - llama.cpp version/commit
   - runtime profile (`mtp_off` or `mtp_n2`)
   - context length
   - prompt/query hash
   - TTFT / prefill latency
   - decode tok/s
   - per-GPU VRAM peak
   - request success/corruption count
   - agent work-item success, wall-clock time, and human intervention count

## On Hardware Arrival

1. Verify GPU identity and count with `nvidia-smi`.
2. Verify NVLink topology and link state.
3. Run `mtp_off` first at 128K to establish the local control.
4. Run `mtp_n2` with identical input and sampling.
5. Repeat at 192K. Run 256K only after 128K stability is established.
6. Keep MTP OFF and n-max=2 as paired arms. Do not compare different quantization, KV type, model revision, or prompt sets in the same conclusion.
7. Re-run the agent work-item benchmark. Tok/s alone is not the qualification metric.
8. Test q4 KV only in a separately identified build that includes the relevant upstream fix and passes a prefill benchmark; never treat q4 KV as an unqualified optimization.

## Claim Boundary

The preflight can establish software/config readiness only. It cannot establish:

- physical hardware observation
- NVLink correctness
- stable inference
- EDA qualification
- model qualification
- `GO`

Gate 4 admission remains `NO_GO` until live telemetry and evidence satisfy the qualification policy.
