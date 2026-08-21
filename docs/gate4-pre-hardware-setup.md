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

    The command above is a software-readiness check. Before hardware bring-up,
    run the strict form with the approved artifact manifest and exact file:

    ```powershell
    python scripts/gate4_preflight.py `
       --repo-root . `
       --model-manifest deploy/gate4_model_manifest.json `
       --model-path <absolute-path-to-Qwen3.8-27B-Q4_K_M.gguf> `
       --require-bringup `
       --output artifacts/preflight/gate4-bringup-preflight.json
    ```

    A zero exit code from the strict form means only that the runtime, model
    provenance, launch profiles, and observed hardware prerequisites are ready;
    it does not grant Gate 4 qualification or `GO`.

2. Obtain the exact GGUF artifact and create the operator-attested manifest:

    ```powershell
    python scripts/create_gate4_model_manifest.py `
       --model-path <absolute-path-to-Qwen3.8-27B-Q4_K_M.gguf> `
       --model-source <vendor-or-approved-registry-url> `
       --model-revision <vendor-revision-or-release-id> `
       --output deploy/gate4_model_manifest.json
    ```

    Compare the generated hash with an independent vendor/release checksum
    before treating the manifest as approved. Do not replace the model with a
    similarly named file. Until that external comparison is recorded, model
    provenance remains `operator_attested` and Gate 4 qualification is blocked.

   Record the independently approved model in the committed trust anchor
   `governance/gate4_approved_models.json`, then issue the verification receipt
   by approval ID. Do not pass a locally computed checksum as an approval value:

   ```powershell
   python scripts/verify_gate4_model_manifest.py `
      --repo-root . `
      --manifest deploy/gate4_model_manifest.json `
      --artifact <absolute-path-to-Qwen3.8-27B-Q4_K_M.gguf> `
      --approval-id <committed-approval-id> `
      --approval-registry governance/gate4_approved_models.json `
      --verifier-id <independent-verifier-id> `
      --verification-basis <vendor-release-checksum-or-equivalent> `
      --output deploy/gate4_model_verification_receipt.json
   ```

   The receipt binds the approval ID, registry bytes hash, registry Git blob
   OID, last registry-change commit, manifest bytes, and artifact bytes. An
   unrelated commit does not invalidate the receipt; a dirty, untracked,
   alternate-path, or changed registry fails closed. The registry in this
   repository remains empty until a real external checksum is reviewed and
   committed.
3. Install or build `llama-server` with `draft-mtp` support and record the binary version/commit.
4. Keep the same model, KV type, Flash Attention setting, parallelism, prompt corpus, and sampling configuration between MTP OFF and n-max=2.
5. Prepare the context sweep: 32K, 64K, and 128K primary; 192K and exploratory 256K stretch.
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

For each primary context cell, the profiler invocation must bind all execution
contracts explicitly. The following is illustrative for the MTP OFF 32K cell:

```powershell
python scripts/profile_runtime.py `
   --api-base http://127.0.0.1:8000/v1 `
   --candidate candidate_a_llama_cpp_gguf `
   --model-path <absolute-path-to-Qwen3.8-27B-Q4_K_M.gguf> `
   --model-manifest deploy/gate4_model_manifest.json `
   --model-verification-receipt deploy/gate4_model_verification_receipt.json `
   --model-approval-registry governance/gate4_approved_models.json `
   --context-fixture gate4/prompts/ctx_32k.json `
   --launch-profile-config deploy/llama_cpp_gv100.yaml `
   --launch-profile-id mtp_off `
   --expected-response-sha256 <fixture-expected-response-sha256> `
   --requests 100 `
   --output results/hardware/mtp_off_ctx32k.json
```

The MTP n=2 cell uses the same inputs, but must switch to
`--candidate candidate_a_llama_cpp_gguf_mtp_n2` and
`--launch-profile-id mtp_n2`.
Metadata-only `context_sweep` values, unbound launch profiles, missing model
manifests, and missing response oracles must remain non-admissible.

Each cell is a separate profile artifact. To evaluate one selected cell, pass
it explicitly to the report generator:

```powershell
python scripts/generate_poc_report.py `
   --hardware-profile results/hardware/mtp_off_ctx32k.json
```

The current software slice wires one explicit profile summary into
qualification; it does not yet aggregate the 32K/64K/128K cells into a single
campaign decision. A missing explicit profile path fails closed instead of
silently falling back to synthetic input.

## On Hardware Arrival

1. Verify GPU identity and count with `nvidia-smi`.
2. Verify NVLink topology and link state.
3. Run `mtp_off` first at 32K to establish the local control.
4. Run `mtp_n2` with identical input and sampling.
5. Repeat at 64K and 128K. Run 192K/256K only after 128K stability is established.
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
