---
name: pr-review-merge-gate
description: "Use when reviewing a GitHub PR, Codex findings, P0/P1 comments, merge readiness, re-review after a fix, or deciding whether a finding blocks merge. Follows governance/REVIEW_CRITERIA.md. Converts PR review from 'fix every P1' into an engineering merge gate against a frozen claim ceiling."
---

# PR Review Merge Gate

Authority: `governance/REVIEW_CRITERIA.md` §2 is the single source of truth
for the engineering merge decision model. This skill is the operator
procedure. Do not invent a second policy, second severity scale, or extra
disposition codes.

Turn PR review into this question:

> Can this PR, at its frozen claim ceiling, be merged safely and honestly?

Do not turn it into:

> Has the whole subsystem been proven to have no remaining P1?

## When to Use

- GitHub PR review or merge-readiness check
- Codex / reviewer P0–P3 findings
- re-review after a correction push
- deciding whether a real finding blocks this PR

## Procedure

1. Freeze the current engineering merge decision using
   `REVIEW_CRITERIA.md` §2.5.
2. Treat every finding as evidence, not as a new task
   (`REVIEW_CRITERIA.md` §2.3).
3. Answer the four triage questions. Blocking disposition is `FIX_NOW`.
   Non-blocking P0/P1 must use exactly one allowed code from
   `REVIEW_CRITERIA.md` §2.3.1 plus a concrete reason.
4. Block merge only when `REVIEW_CRITERIA.md` §2.4 A–D is true. Use
   §2.4.1 as the six-scenario answer key. Do not restate a different
   blocker list here.
5. Report `MERGE READY` only when:
   - exact current HEAD has been reviewed;
   - PR-introduced or PR-worsened blocking P0/P1 = 0;
   - no unresolved finding invalidates frozen DONE, claim ceiling, merge
     safety, or relied-upon evidence;
   - required scope-matched checks are green;
   - remaining real findings have an allowed disposition and are not
     falsely represented as fixed or absent.
6. After a blocker fix, run delta-bounded re-review from
   `REVIEW_CRITERIA.md` §2.6. Ask only:
   - was X actually fixed?
   - did the correction create a direct regression?
   - did the frozen merge decision materially change?
   Do not restart unbounded adversarial review.
7. Apply the spec stop rule from `REVIEW_CRITERIA.md` §2.7 when there is
   no executable path yet.

## Re-Review Prompt

```text
Review the exact current HEAD for this PR's frozen merge decision.

Follow governance/REVIEW_CRITERIA.md §2.

Prioritize only:
1. was previously reported blocker X actually fixed?
2. did the correction create a direct regression?
3. did the frozen merge decision materially change?

Do not restart unbounded adversarial review of the whole PR.
Do not expand into unrelated subsystem qualification unless §2.6
re-expansion conditions are met.

Keep real finding severity. Decide merge blocking separately.
Use only FIX_NOW or an allowed non-blocking disposition from §2.3.1.
```

## Required Reviewer Summary

Copy the merge-ready summary shape from `REVIEW_CRITERIA.md` §6. Do not
invent a different disposition vocabulary.

```text
MERGE DECISION: READY | NOT READY

Blocking findings:
- none | <list>

Carried-forward findings:
- P1 — <title>
  Attribution: pre-existing | introduced | worsened | exposed
  Current merge impact: none | blocks merge
  Disposition: PRE_EXISTING | OUTSIDE_FROZEN_SCOPE | QUALIFICATION_ONLY | FUTURE_CAPABILITY | NO_PR_DELTA_IMPACT | FALSE_POSITIVE | FIX_NOW
  Reason: ...

Required checks:
- green | <failing check>

Reviewed HEAD:
- <sha>
```

A PR may have remaining real P1s and still be merge-ready when those P1s
do not materially block the frozen merge decision.

## Do Not Add

Do not create validators, schemas, ledgers, dashboards, or a second
severity scale to enforce this skill. The instruction is the change.
Do not duplicate the full A–D policy or disposition table here; cite
`REVIEW_CRITERIA.md`.

