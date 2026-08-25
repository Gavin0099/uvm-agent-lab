# POC-1 USB Hub Spec QA Scope and Acceptance Contract

> Status: Baseline definition for POC-1. This document defines what must be
> evaluated; it does not claim live model, GPU, or USB-IF corpus qualification.

## 1. Core Objective

POC-1 must let an engineer ask USB Hub FW, signal/electrical, and compliance
questions in natural language and receive an answer from a declared,
version-locked dual-layer corpus that is:

- retrieved from the specified authoritative USB-IF references;
- grounded only in the retrieved evidence;
- traceable to document, revision, chapter, section, and page or stable anchor;
- explicit about uncertainty, unsupported scope, version mismatch, and conflict;
- reproducible through a fixed Golden QA benchmark.

The target is a governed Spec QA Agent, not a generic USB chatbot and not only
a PDF-to-vector-database demonstration.

## 2. Phase 1 Authoritative Corpus

POC-1 uses two different evidence layers. They are complementary, not
interchangeable:

- **Layer A - governed reference**: `Gavin0099/usb-if-hub-spec-reference` is
  the first governed knowledge source. It provides structured, searchable
  entries, authority metadata, verification state, and claim boundaries. It is
  high-confidence reference material, not a substitute for the complete USB
  specifications.
- **Layer B - official raw corpus**: locked copies of the official USB 2.0,
  USB 3.2, and SuperSpeed Hub LVS source text provide coverage outside the
  structured reference. Raw text is eligible evidence only after its document
  revision and content hash are bound.

The source roles and binding state are recorded in
[`gv100h/spec_qa/contracts/corpus.lock.yaml`](../gv100h/spec_qa/contracts/corpus.lock.yaml).
Pending source bindings are an explicit incomplete state; they cannot support
a claim of complete Phase 1 corpus qualification. At runtime,
`GovernedSpecRetriever` validates the required layers, Phase 1 source IDs,
authority roles, revision/commit fields, scope binding fields, USB4 exclusion,
and evaluation-only boundary. Pending markers are reported as a qualification
block rather than silently treated as a complete binding.

The current binding state is source-identity complete but evaluation-incomplete:
Layer A's governed reference is locked to commit
`808f23c24bd8651da9cdcd63ea8669126917a379` and its tracked-tree content hash,
and the official raw USB 2.0, USB 3.2, and LVS artifacts are hash-verified in
operator-controlled private staging. The lock is `phase1_bound`, while the
final 50-100 question acceptance set and raw-document retrieval coverage remain
incomplete. Therefore physical corpus binding can pass without implying
complete POC-1 QA qualification.

Lock metadata and runtime observation are separate states. A retriever without
`knowledge_repo_path` may use the embedded smoke baseline, but its
`runtime_binding_status` is `unverified` and a qualification claim remains
blocked. Qualification callers must pass `require_physical_binding=True` and a
checkout path; missing or failed physical verification fails closed. A
successful checkout verification sets `runtime_binding_status: verified` and
`physical_binding_verified: true`.

For a qualification run, `source_paths` supplies one physical path per
required Phase 1 source: the governed reference path for `hub_reference` and
exact raw document files for `usb20_fw`, `usb20_se`, `usb32`, and
`superspeed_hub_lvs`. The runtime binding record keeps each source's status,
observed path, observed SHA-256, and observed Git commit where applicable.
Layer A and Layer B use different identity verifiers, but both must be
`verified` before a fully bound Phase 1 corpus can be admitted.

The first benchmark is intentionally limited to this USB Hub baseline:

| Source role | Authoritative scope | Included in Phase 1 |
| --- | --- | --- |
| USB 2.0 FW | Official raw text, Chapters 5 and 8-11 | Yes |
| USB 2.0 SE | Official raw text, Chapters 6-7 | Yes |
| USB 3.2 | Official raw text, Rev 1.1, Chapters 6, 7, 9, and 10 | Yes |
| SuperSpeed Hub LVS Test Specification | Official raw text, Rev 1.15 | Yes |
| USB4 | Router, tunneling, and USB 3 backward-compatibility extensions | No; Phase 2 |

The corpus lock, source revision, authority level, and file hashes are part of
the benchmark input. A source that is not in the lock cannot silently become
evidence for a Phase 1 answer. The governed reference's claim ceiling also
continues to apply: structured reference presence does not prove firmware,
electrical, interoperability, LVS, or certification compliance.

USB4 is therefore a deliberate negative-control scope in Phase 1: a USB4
question must be answered as unsupported or out of scope unless the question is
only asking whether USB4 is included in the current corpus.

## 3. Capabilities Under Test

| Capability | Priority | Required behavior |
| --- | --- | --- |
| Retrieval | P0 | Find the governing document, revision, chapter, and section for the question. |
| Grounded answer | P0 | Every material claim is supported by retrieved evidence; no completion from model memory. |
| Citation | P0 | Cite the source document, revision, chapter, section, and page or stable anchor, plus a supporting excerpt or evidence ID. |
| Cross-spec reasoning | P1 | Connect a USB 2.0/3.2 requirement to the corresponding Hub behavior and, where applicable, the LVS test item or condition. |
| Unknown/conflict handling | P0 | Abstain when evidence is missing or out of scope; report the competing source versions or authority levels when evidence conflicts. |

P0 failures are admission-blocking. P1 cross-spec results must always be
reported separately and cannot be hidden by a strong single-document score.

## 4. Evaluation Layers

### L1: Single-spec factual QA

The agent identifies a normative fact from one source and returns the answer,
document, chapter, section, page or anchor, and supporting excerpt.

### L2: Engineering interpretation

The agent finds the applicable requirement, interprets normative language such
as `shall`, `may`, and `should`, and translates it into an engineering action
without adding an unsupported implementation rule.

### L3: Cross-document QA

The agent builds an evidence chain:

```text
Question -> source requirement -> Hub behavior -> LVS test item or condition
```

A plausible answer without both sides of the chain is incomplete. The
benchmark must distinguish retrieval of each link from the model's explanation
of the link.

### L4: Uncertainty and contradiction

The agent must distinguish at least these outcomes:

- no supporting evidence in the Phase 1 corpus;
- question outside the declared corpus, including USB4 content;
- source revision or authority mismatch;
- two retrieved sources that cannot be reconciled from the available evidence;
- a fictional section, fabricated evidence ID, or unsupported universal claim.

For these cases the correct behavior is an explicit abstention or conflict
report, not a plausible completion.

## 5. Answer and Evidence Contract

Each evaluated answer must expose a structured result, even when the user-facing
rendering is natural language:

- `status`: `answer`, `abstain`, or `conflict`;
- `claims`: material claims made by the answer;
- `citations`: document, revision, chapter, section, page or stable anchor,
  authority level, and evidence excerpt or registered evidence ID;
- `scope`: the corpus scope used for the answer;
- `boundary`: missing evidence, unsupported scope, or version/authority conflict;
- `evidence_ids`: IDs that can be resolved against the governed knowledge layer.

An `answer` without valid supporting citations fails the P0 citation and
grounding checks. An `abstain` or `conflict` result must not cite evidence that
does not support the stated boundary. Fabricated evidence IDs are a hard
failure.

The final evaluator consumes only a formal, independently reviewed v1.1
manifest through `FinalPOC1Evaluator`; the unreviewed authoring draft is not a
valid input. The agent response must be structured as `status`, `claims`,
`citations`, `scope`, and an optional `boundary_code`. The evaluator binds its
retrieval, grounding, citation, conflict, and abstention metrics to the
canonical acceptance-set hash and emits `admissible_for_model_qualification: false`
until a separate qualification admission layer verifies the review receipt,
corpus receipt, and runtime evidence.

## 6. Golden QA Benchmark

The final POC-1 benchmark is a fixed, versioned set of 50-100 questions. The
current `gv100h/spec_qa/golden/dataset_30.json` remains the deterministic smoke
baseline and is not sufficient evidence for full POC-1 acceptance.

The final set must contain all four evaluation layers and both positive and
negative controls. At minimum it must include:

- direct single-spec facts from every Phase 1 source family;
- FW/SE engineering interpretation questions with normative-language traps;
- USB 2.0 or USB 3.2 requirement-to-LVS correlation questions;
- unsupported, wrong-version, wrong-authority, fictional-section, and conflict
  questions;
- USB4 questions as explicit Phase 1 out-of-scope controls, not as retrieved
  Phase 1 evidence.

Each question must declare its expected status, scope, accepted source family,
required citation policy, Gold Oracle, grading weights, and whether it is P0 or
P1. The formal acceptance manifest uses schema version `1.1`.

Golden questions and expected outcomes are evaluation-only artifacts. They must
be independently reviewed and must not be generated from retrieved chunks,
governed table rows, or model answers produced against the same corpus. Golden
questions may refer to corpus evidence IDs as expected answers, but the
benchmark itself is never eligible retrieval evidence.

The final-set shape and oracle shape are enforced by
`gv100h/spec_qa/contracts/poc1_acceptance_contract.py`. Its loader requires a
50-100 question manifest, minimum coverage for L1-L4, the exact five Phase 1
source families, independent-review markers plus a durable review receipt path,
receipt hash, reviewer ID, and review timestamp. Each question's Gold Oracle
binds status-specific evidence and expected answer structure:

- `answer` requires accepted evidence IDs, required claims and facts, section
  anchors, and normative-source citation fields;
- `conflict` requires at least two competing evidence IDs and claims, two
  section anchors, a conflict boundary code, and competing-source citations;
- `abstain` requires boundary evidence IDs, a boundary claim, a boundary code,
  and scope/boundary citation fields while forbidding normative section
  citations when no source is claimed.

The contract also requires grading weights to sum to `1.0`. It rejects duplicate
IDs, unlisted sources, missing Gold Oracle elements, status/policy mismatches,
answer questions without supporting sources, abstention questions with
accepted sources, conflict questions without competing sources, layer/category
or priority mismatches, incomplete layer/source coverage, and USB4 controls
outside L4 `uncertainty_conflict` with `USB4_SPEC` scope. The loader checks the
manifest shape and declared oracle structure; it does not resolve evidence IDs
against private raw bytes, verify review receipt bytes, generate questions, or
prove semantic correctness. Those remain separate authoring, independent
review, and admission responsibilities. The current 30-question file and the
unreviewed PR #23 authoring draft remain outside this formal loader.

## 7. Gate 1 Admission Signals

P0 admission signals are:


The existing retrieval target remains `Recall@1 >= 95%` and
`Wrong-Version Rate = 0%`. In addition, the POC-1 baseline must report zero
fabricated citations, zero unsupported claims on negative controls, and 100%
valid citations for accepted answer cases before a P0 pass can be claimed.

### 7.1 Corpus Binding Receipt Admission

QA evaluation results are not admissible for qualification unless they carry a
verified `CorpusBindingReceipt`. The receipt must bind the corpus lock bytes
and Git identity, every required Phase 1 source ID and observed hash, the
runtime binding records, the physically verified state, and the governed
reference commit/content hash. A receipt hash is recorded for the exact
canonical receipt payload, excluding the self-referential `receipt_hash` field.

The evaluator propagates `corpus_receipt_status` and
`corpus_binding_receipt_hash` into `QAEvaluationResult`. The qualification
policy consumes `spec_qa.corpus_binding_verified` and re-verifies the on-disk
receipt against the bound retriever at decision time; the result fields alone
are not proof. `missing`, `mismatch`, and `unverified` statuses are admission
failures and force `NO_GO`. A verified receipt proves only that the current
lock and bound sources match the receipt at verification time; it does not
prove document correctness, model quality, or live qualification by itself.

Final POC-1 evaluation has a separate acceptance-admission boundary. When a
`FinalPOC1EvaluationResult` is supplied to qualification, the policy re-loads
the formal v1.1 manifest and verifies its canonical acceptance-set hash, the
raw review-receipt SHA-256, the receipt's reviewer metadata and source-revision
coverage, and the reviewed Git commit's copy of the manifest. The receipt must
report an approved review with every question passed. The manifest's
`review_receipt_hash` is deliberately excluded from the canonical acceptance
set hash so the manifest hash and receipt hash do not form a circular binding;
the receipt hash is still checked independently against the physical receipt
bytes. Missing or mismatched acceptance binding emits a failed
`spec_qa.final_acceptance_set_bound` gate and cannot support qualification.
The admission check also requires one result detail for every manifest question
and recomputes the reported counts, rates, fabricated-citation count,
authority-violation count, and overall pass flag from those details. A
summary-only or internally inconsistent `FinalPOC1EvaluationResult` is
rejected. This is provenance and consistency enforcement, not independent
proof that the private-source interpretation is semantically correct.

P1 admission signals are cross-document chain retrieval and chain explanation
accuracy. They are reported as their own score and target, rather than being
folded into single-spec retrieval accuracy.

### 7.2 Private Raw Source Locator

The official raw source files are retained outside this public repository under
an operator-controlled private staging root. `corpus.lock.yaml` records logical
`env://USB_SPEC_QA_RAW_ROOT/...` locators and content hashes; runtime callers
must resolve those locators to explicit `source_paths` on the executing host.
Machine-local absolute paths and raw specification bytes must not be committed
to this repository. The private staging authorization is an operator record,
not a claim that the USB-IF terms permit redistribution or external commercial
use.

A benchmark result is not a live qualification result. Real local-model
inference, dual-GV100 telemetry, latency, and hardware stability remain
separate evidence required by the wider project plan.

## 8. Implementation Order

1. Bind every Phase 1 source in `gv100h/spec_qa/contracts/corpus.lock.yaml` with immutable revision/commit and content hashes.
2. Extend the Golden QA schema and replace the smoke-only 30-question view with
   a 50-100 question versioned benchmark.
3. Add deterministic checks for claim grounding, citation completeness,
   cross-document links, abstention, and conflict handling.
4. Run offline retriever/evaluator baselines before comparing local models,
   embeddings, rerankers, or chunking strategies.
5. Treat USB4, Type-C/PD, and company-internal specifications as Phase 2 corpus
   extensions after the Phase 1 benchmark is stable.