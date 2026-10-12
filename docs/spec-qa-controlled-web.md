# Controlled web infrastructure (opt-in)

This package extracts the durable job API, authentication relay and captured
transport from the local expert trial. It does **not** launch MLX, choose a
question profile, retrieve evidence or certify answer semantics. The deployed
website and its original launchers are unchanged. Native/preset adapter wiring
and removal of the old observer's executable-artifact import remain a separate
integration step; the complete runtime extraction is not claimed here.

The host supplies a reviewed executor, existing private ledger directory and
reviewed asset directory explicitly. There is no dated experiment path default,
dynamic import of experiment code, model warmup or automatic request. The asset
directory contains `index.html`, `styles.css`, `app.js` and `saved-cases.js`;
these are trusted UI code, not inspected by `WebPaths`. Keep source documents,
raw jobs, credentials and the ledger outside it. Existing download-only feedback
is handled by the supplied assets; this API adds no feedback upload or storage.

The existing `OperatorQAView` DTO transitively imports evaluator type/class
definitions through `qa_service`; this extraction executes no evaluator.
The direct-import audit does not assert that evaluator modules are absent from
the Python module graph. Benchmark/Gold helpers are not direct dependencies of
this new package, and semantic QA validation remains the host's responsibility.

```python
from gv100h.spec_qa.controlled_web.config import WebPaths
from gv100h.spec_qa.controlled_web.session import ControlledSession
from gv100h.spec_qa.controlled_web.server import create_backend

# reviewed_executor is provided by the hosting application, never by a request.
paths = WebPaths(ledger="/private/state/existing-trial", assets="/private/reviewed-ui")
session = ControlledSession(paths.ledger, reviewed_executor)
try:
    with create_backend(session, paths) as server:
        server.serve_forever()
finally:
    session.close()  # Wait for the owned job before releasing ledger ownership.
```

The executor receives `(question, job_directory, progress)` and retains the
existing retrieval/prompt/model, native ownership/cache, source-binding and
semantic obligations. Progress accepts `RESERVED`, `STARTING_MODEL`, `GENERATING`
and `VERIFYING`. A completed result carries `preview=False`,
`mode="controlled_live"`, the existing `OperatorQAView` and an inspection stage:
`SOURCE_SUPPORTED_ANSWER` or `CITATION_TEXT_VERIFIED` for answers;
`VALID_MODEL_ABSTENTION` for a valid refusal. These stages are assertions by the
reviewed host executor, not semantic proof produced by this package. Generic
quote/source matching still does not prove entailment or preserve modality.

A valid refusal is a completed response and consumes one attempt. An exception,
timeout or unaccepted answer stops the session. Reservation precedes executor
dispatch; six attempts are shared by all clients of that ledger. Duplicate
request IDs return the existing job, including after an uncertain browser POST;
refresh uses GET and does not execute a replacement request. A second process
cannot own the same ledger. Restart converts an interrupted job to failure,
retains its consumed attempt and stops. There is no reset/retry/recovery HTTP
route. The previous explicitly reviewed saved-response repair remains in the
old host integration; it has not been generalized or automatically enabled.

The HTTP job projection excludes raw model responses and private failure text.
The internal result/failure records retain them for local review. Both valid
refusals and answers remain distinct from runtime failure in the public status.

For external HTTPS, `gateway.GatewayPolicy` and `external_gateway` keep the
existing exact quick-tunnel origin, authentication, expiry and rate limit. Read
the secret with `config.read_secret`: an owned regular mode-0600 file; no secret
is stored in code. This extraction preserves the existing policy's minimum
20-character password. Supplying a different password policy, exposing a new
origin, or switching the live service is not part of this integration.

`transport.request_bytes` preserves the 27B model, temperature 0, max_tokens
2048, non-streaming and `enable_thinking=False`. `OneShotCapturedClient` requires
the host's owned-runtime/cache admission callback before connecting to
127.0.0.1:8080. It saves actual request bytes, reserves before POST and uses no
SDK retries, redirects or implicit socket reopen. Uncertain failures consume
the attempt and stop. The admission callback is an execution precondition; a
synthetic callback/HTTP fixture does not constitute native runtime evidence.

Tests use synthetic executors, assets and loopback responses only. They prove
the bounded web/lifecycle/transport behavior, not live answer quality, whole
website presentation parity, 120-second latency or Alpha readiness.
