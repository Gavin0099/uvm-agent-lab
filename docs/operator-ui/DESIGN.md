# GV100H Spec QA Design Language

> Ask a USB Hub spec question, read the answer, then inspect the
> source. Medium technical density. One semantic accent per state.
> The first visual layer is never a QAResponse schema.

Status: **approved proposal language**, not yet implemented in
`gv100h/spec_qa/operator_ui/static/`. Current HTML/CSS is the PR #35
50/50 schema viewer. This file must not be treated as evidence that
the live page already looks like this. Do not restyle `static/` from
this document unless the user opens the implementation slice
`feat/spec-qa-operator-ui-redesign`.

Evidence:

- IA/UX proposal: [`docs/operator-ui-ia-ux-redesign.md`](../operator-ui-ia-ux-redesign.md)
- Current shell (as-is, not this language):
  `gv100h/spec_qa/operator_ui/static/{index.html,styles.css,app.js}`

Adapted from [nolly-studio design-md](https://github.com/nolly-studio/agent-skills/blob/main/skills/design-md/SKILL.md)
(MIT): cite evidence, name budgets, do not invent a live design system
from unimplemented CSS.

## Primary task

Ask → Answer → Source.

## Hierarchy

| Level | Surface | On first visual layer? |
| --- | --- | --- |
| 1 | Answer | yes |
| 2 | Source line (document · section · authority) | yes |
| 3 | Evidence details | no; collapsed |
| 4 | Governance / debug / fixture provenance | no; collapsed |

Ask is the entry control, not a competing hero.

## What must not appear on screen (first layer)

- `answer_scope`, `retrieval_mode`, `allowed_evidence_scopes`
- `boundary_code`, `claim_evidence_ids`, `evidence_ids`
- `synthetic-v1`, Frozen QAResponse schema dump
- 50/50 Question / Result dashboard
- fabricated PDF anchors
- decorative gradients / landing-page hero

Those fields stay under Advanced / Evidence / Governance.

## Temperament

Developer / ops workbench. Compact, precise, trustworthy. No marketing
hero. Fixture honesty stays (`FIXTURE — query not evaluated`) as a
chip, not a manifesto.

## Budgets (from the accepted proposal; not live tokens)

- One accent pairing per view (answer / abstain / conflict).
- At most one display-font moment (product name).
- Answer sits on a paper surface; chrome stays quiet.
- Sketch only (do not claim these exist in `styles.css` today):
  `paper #f4efe4`, `ink #1b1a17`, `bench #e7e1d4`, `rule #b7a990`,
  `fixture #8a5a12`, `conflict #8f2d2d`.

## Token reuse (when the redesign lands)

Adapted from n8n's design-system skill: after `styles.css` actually
defines named tokens, reuse them. Do not hardcode a second palette.
Until then, the sketch hex values above are proposal-only.

## Stack

HTML, CSS, vanilla JS, Python HTTP server. No React / Tailwind /
shadcn / Vite.

## Per-page checklist (next implementation PR)

- [ ] First screenshot is not a 50/50 schema viewer
- [ ] Answer is the largest text block
- [ ] Source is one line under the answer
- [ ] Advanced is closed by default
- [ ] Evidence is collapsed
- [ ] Desktop 1440×900, Laptop 1280×800, Mobile 390×844 captured
- [ ] Fixture copy still present for tests unless tests change in the same slice
