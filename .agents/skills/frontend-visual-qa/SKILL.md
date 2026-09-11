---
name: frontend-visual-qa
description: "Use when: Operator UI implementation or redesign needs browser/screenshot verification. Source review is not enough. Do not use for QAResponse, retrieval, React, or Tailwind."
---

# Frontend Visual QA — Operator UI (GV100H)

Third role. Adapted from
[dachent/skills frontend-design-codex](https://github.com/dachent/skills/blob/main/frontend-design-codex/SKILL.md)
(rendered-UI / screenshot loop). This skill does **not** design the page.

`source review PASS` is not visual quality.

## When to use

After `frontend-design` + accepted proposal + implementation +
`ui-ux-review`. `AGENTS.md` requires this file before claiming a UI
change is done.

## Stack lock

Same as the other Operator UI skills. HTML / CSS / vanilla JS / Python
HTTP server only. No React, Tailwind, QAResponse, retrieval, or fake
PDF anchors.

## Loop

```text
Inspect current UI
        ↓
Before screenshot
        ↓
Implementation
        ↓
Launch browser (http://127.0.0.1:8091)
        ↓
Desktop 1440×900 / Laptop 1280×800 / Mobile 390×844
        ↓
Visual review (this skill)
        ↓
Fix
        ↓
Capture again
```

Do not complete without at least desktop and mobile screenshots of the
**running** page. CSS comments and pytest are not substitutes.

## What to inspect in the screenshot

Structure first, polish last:

1. Is the first visual layer only Ask → Answer → Source?
2. Are `answer_scope`, `retrieval_mode`, `allowed_evidence_scopes`,
   `claim_evidence_ids`, `synthetic-v1` off the first layer?
3. Is Evidence collapsed? Is Governance collapsed?
4. Does fixture mode still say the query is not evaluated?
5. Can the primary Ask control be used at 390×844?
6. Does the answer remain the largest readable block?

If structure fails, do not “fix” it with palette or radius changes.

## Output

```text
Rendered review: yes | no
Viewports captured: ...
Structure: PASS | FAIL
Findings: ...
Must recapture: yes | no
```

If `Rendered review: no`, the UI slice is incomplete.
