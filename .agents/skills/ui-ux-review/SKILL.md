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

## Review order (structure first)

Adapted from
[pascalorg/skills web-design](https://github.com/pascalorg/skills/blob/main/web-design/SKILL.md)
tiering and ui-ux-pro-max. Do not start with palette.

1. **Structure / hierarchy**: first layer is Ask → Answer → Source.
   Fail if 50/50 schema viewer remains.
2. **Typography / density**: answer is the largest readable block.
3. **Color / contrast**: 4.5:1 body; one semantic accent per state.
4. **Components / disclosure**: Advanced, Evidence, Governance collapsed.
5. **Accessibility / interaction**: visible focus, Ask ≥44px, in-flight
   disabled, labels not placeholder-only.
6. **Motion / polish**: last, and only after structure passes.

This skill still does not approve from source. After the punch-list,
`frontend-visual-qa` must run against screenshots.

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
