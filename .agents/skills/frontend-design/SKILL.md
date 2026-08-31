---
name: frontend-design
description: "Use when: Operator UI visual direction, information architecture, typography, layout, or avoiding templated AI UI. First pass for gv100h/spec_qa/operator_ui presentation. Do not use for QAResponse, retrieval, React, or Tailwind."
---

# Frontend Design — Operator UI (GV100H)

Adapted from [anthropics/skills frontend-design](https://github.com/anthropics/skills/blob/main/skills/frontend-design/SKILL.md)
(Apache-2.0). This copy is **Operator UI scoped**. It does not authorize a
stack rewrite.

## When to use

- Reviewing or redesigning `gv100h/spec_qa/operator_ui/static/`
- Choosing layout, hierarchy, typography, or visual identity
- The first Codex/agent task on this surface is **IA/UX proposal**, not
  palette-only CSS

A skill file existing under `.agents/skills/` is not enough. When
modifying `gv100h/spec_qa/operator_ui/static/**`, `AGENTS.md` requires
this file to be read **before** proposing presentation changes.

## Subject (pin this before designing)

- **Product**: USB Hub Spec QA Operator UI (Machine B development shell)
- **Audience**: USB Hub FW / verification engineers
- **Single job**: ask a USB Hub spec question → read the answer → inspect
  the source
- **Not the job**: inspect a Pydantic/QAResponse schema

## Stack lock (DENY)

Keep PR #35 stack:

- HTML, CSS, vanilla JS, Python `http.server`

Do **not**:

- change `QAResponse`, `GovernedQAService`, retrieval, or `/api/qa` contract
- introduce React, Tailwind, shadcn, Vite, or any UI framework
- fabricate PDF anchors
- treat fixture mode as live Spec QA

## ALLOW

Information architecture, typography, spacing, hierarchy, responsive layout,
accessibility, CSS, HTML presentation, interaction (progressive disclosure).

## Process

This is a **rescue / existing-UI redesign**, not a greenfield app.
Adapted from [ag-kit frontend-design](https://github.com/vudovn/ag-kit/blob/main/.agents/skills/frontend-design/SKILL.md)
(audit-first) and [n8n design-system](https://github.com/n8n-io/n8n/blob/master/.agents/skills/design-system/SKILL.md)
(reuse existing tokens; keep the skill short).

1. Fill the Frontend Thinking Gate.
2. Audit the current rendered page before any CSS: first layer, hierarchy,
   what must not appear, Ask control, fixture honesty. Do not start with
   palette, radius, or shadow.
3. Name subject, audience, and the page's single job.
4. Write a compact design plan: color (4–6 named hex), type (display + body
   + optional utility), layout (ASCII wireframe), signature (one memorable
   element). Cite `docs/operator-ui/DESIGN.md` and the accepted proposal.
   Do not invent a live design system from unimplemented CSS.
5. Reject the three generic AI defaults unless the brief asks for them:
   cream+serif+terracotta; near-black+acid accent; broadsheet hairlines.
   Current Operator UI already reads as a generic dark schema viewer — do
   not polish that look.
6. Ground materials in USB spec work: binders, section numbers, lab
   instruments, governed citations — not dashboard chrome.
7. Copy uses the engineer's words (`Ask`, `Answer`, `Source`). Schema
   names (`answer_scope`, `retrieval_mode`, `Frozen QAResponse`) are
   secondary.
8. Prefer named tokens already in `docs/operator-ui/DESIGN.md` / `styles.css`
   once they exist. Do not hardcode a second palette beside them.
9. Do not write presentation code until the proposal is accepted.
10. Do not mix this workflow freeze with a large `static/` rewrite. The
    implementation PR is a later slice and must be reviewed from
    screenshot / rendered UI, not source only.

## Hierarchy for this product

Primary: Ask → Answer → Source.
Secondary: Evidence (collapsed).
Tertiary: Boundary / governance / fixture provenance.

Engineering fields stay under **Advanced**.

## Output for a review-only pass

Produce a proposal with diagnosis, wireframe, copy rules, token sketch,
and out-of-scope list. Do not edit `static/` in that pass.

## Frontend Thinking Gate (required before proposing)

Adapted from
[atuizz/codex-ui-ux-skill](https://github.com/atuizz/codex-ui-ux-skill/blob/main/ui-ux/SKILL.md).
Fill this before any presentation change. Keep it short.

```text
Project stage:       rescue (functional 50/50 schema viewer)
Surface type:        ops workbench / technical QA
Primary user task:   ask a USB Hub spec question and verify the source
Entry / journey:     open Operator UI → Ask → read Answer → open Source
First decision:      what to ask
Information priority: Answer > Source > Evidence > Governance
Friction / recovery: empty Ask, in-flight disable, fixture vs service
Mobile primary action: Ask at 390×844
What must not appear on screen (first layer):
  answer_scope, retrieval_mode, allowed_evidence_scopes,
  claim_evidence_ids, synthetic-v1, Frozen QAResponse dump
Verification plan:   frontend-visual-qa screenshots at
  1440×900 / 1280×800 / 390×844
```

If this gate is skipped, do not edit `static/`.

Persistent language lives in `docs/operator-ui/DESIGN.md` and
`docs/operator-ui-ia-ux-redesign.md`. Do not paste those docs into
`AGENTS.md`.
