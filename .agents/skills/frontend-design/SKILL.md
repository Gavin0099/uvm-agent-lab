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

1. Name subject, audience, and the page's single job.
2. Write a compact design plan: color (4–6 named hex), type (display + body
   + optional utility), layout (ASCII wireframe), signature (one memorable
   element).
3. Reject the three generic AI defaults unless the brief asks for them:
   cream+serif+terracotta; near-black+acid accent; broadsheet hairlines.
   Current Operator UI already reads as a generic dark schema viewer — do
   not polish that look.
4. Ground materials in USB spec work: binders, section numbers, lab
   instruments, governed citations — not dashboard chrome.
5. Copy uses the engineer's words (`Ask`, `Answer`, `Source`). Schema
   names (`answer_scope`, `retrieval_mode`, `Frozen QAResponse`) are
   secondary.
6. Do not write presentation code until the proposal is accepted.
7. Do not mix this workflow freeze with a large `static/` rewrite. The
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
