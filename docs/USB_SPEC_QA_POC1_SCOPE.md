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

The current binding state is intentionally partial: Layer A's governed
reference is locked to commit `808f23c24bd8651da9cdcd63ea8669126917a379` and its
tracked-tree content hash, while the official raw USB 2.0, USB 3.2, and LVS
sources remain pending acquisition. Therefore a physical Layer A binding can
pass while the overall Phase 1 corpus remains `qualification_blocked`.

Lock metadata and runtime observation are separate states. A retriever without
`knowledge_repo_path` may use the embedded smoke baseline, but its
`runtime_binding_status` is `unverified` and a qualification claim remains
blocked. Qualification callers must pass `require_physical_binding=True` and a
checkout path; missing or failed physical verification fails closed. A
successful checkout verification sets `runtime_binding_status: verified` and
`physical_binding_verified: true`.

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

Each question must declare its expected status, scope, accepted evidence IDs,
required citation fields, and whether it is P0 or P1.

Golden questions and expected outcomes are evaluation-only artifacts. They must
be independently reviewed and must not be generated from retrieved chunks,
governed table rows, or model answers produced against the same corpus. Golden
questions may refer to corpus evidence IDs as expected answers, but the
benchmark itself is never eligible retrieval evidence.

## 7. Gate 1 Admission Signals

P0 admission signals are:

- `Recall@1` for the governing evidence, with the query-set hash recorded;
- grounded claim rate and citation validity/completeness;
- wrong-version and wrong-authority rates;
- unsupported/conflict abstention rate;
- fabricated citation count.

The existing retrieval target remains `Recall@1 >= 95%` and
`Wrong-Version Rate = 0%`. In addition, the POC-1 baseline must report zero
fabricated citations, zero unsupported claims on negative controls, and 100%
valid citations for accepted answer cases before a P0 pass can be claimed.

P1 admission signals are cross-document chain retrieval and chain explanation
accuracy. They are reported as their own score and target, rather than being
folded into single-spec retrieval accuracy.

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