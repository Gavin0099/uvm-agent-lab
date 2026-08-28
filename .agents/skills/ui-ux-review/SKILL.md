---
name: ui-ux-review
description: "Use when: second-pass Operator UI UX review after frontend-design. Check accessibility, forms, progressive disclosure, interaction, and hierarchy. Do not lead visual identity. Do not introduce React or Tailwind."
---

# UI/UX Review — Operator UI (GV100H)

Second-pass reviewer. Adapted from
[Hitbullets/codex-skills ui-ux-pro-max](https://github.com/Hitbullets/codex-skills)
and [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill)
(MIT).

Do **not** let this skill drive the first design. Upstream reports of
applying it as the sole designer can make UI worse. Sequence:

```text
frontend-design  →  direction / IA / tokens
IA/UX proposal   →  accepted
implementation   →  HTML/CSS/vanilla JS only
ui-ux-review     →  this skill
screenshot / rendered-UI review
PR
```

A skill file existing is not enough. After implementation, `AGENTS.md`
requires this file to be read, then a screenshot or rendered-UI review.
Do not approve from HTML/CSS/JS reading alone.

## When to use

- Second pass after `frontend-design` and an accepted proposal
- Reviewing a later implementation PR for Operator UI
- Checking forms, disclosure, accessibility, and empty/error states

## Stack lock (same as frontend-design)

ALLOW: IA, typography, spacing, hierarchy, responsive, accessibility, CSS,
HTML presentation, interaction.

DENY: QAResponse, GovernedQAService, retrieval, React, Tailwind, UI
frameworks, API contract changes, fake PDF anchors.

## Review order (fix CRITICAL first)

1. **Accessibility**: text contrast, visible focus, labels not placeholder-only,
   heading order, color not the only status signal, `prefers-reduced-motion`.
2. **Touch / interaction**: primary control ≥44px, Ask disabled while
   in-flight, errors next to the failing control.
3. **Forms / disclosure**: `answer_scope`, `retrieval_mode`,
   `allowed_evidence_scopes` must not occupy the first visual layer.
   Fixture vs service is a mode chip, not a schema lesson.
4. **Layout**: no 50/50 split that leaves the question pane empty and
   dumps the result pane. Answer is the hero. Evidence starts collapsed.
5. **Copy**: engineer language first; governance strings remain available
   but folded.
6. **Skip unless relevant**: charts, native-app navigation, icon-pack
   rewrites, dark/light dual-theme as a blocker.

## Anti-patterns for this shell

- Emoji as the only fixture warning (keep text: `FIXTURE — query not evaluated`)
- Expanding every citation like a debugger
- Putting ` Frozen QAResponse / synthetic-v1 / normative` in the first
  visual layer
- Recommending React/Tailwind/shadcn to “fix” hierarchy

## Output

A punch-list: severity, location (`index.html` / `styles.css` / `app.js`,
proposal section, or screenshot viewport), issue, required change. No
stack-change recommendations. State whether rendered-UI review happened.
