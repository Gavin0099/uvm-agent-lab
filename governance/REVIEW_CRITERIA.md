---
audience: agent-on-demand
authority: reference
can_override: false
overridden_by: AGENT.md
default_load: on-demand
---

# REVIEW_CRITERIA.md

**Code Review and Audit Protocol - v1.4**

> **Version**: 1.4 | **Priority**: 3 (audit protocol)
>
> Defines how to audit, critique, and verify code changes.
> Load this document when `SCOPE = review`.
>
> This file is the single source of truth for the engineering merge
> decision model. `governance/AGENT.md` defines agent behavior only.
> `.github/skills/pr-review-merge-gate/SKILL.md` defines the operator
> workflow only. Neither file may invent a second merge policy.

---

## 0. Activation

This document applies when `SCOPE = review`.

When active:

- keep a governance-first posture;
- act as a skeptical verifier, not an implementer;
- bind every finding to evidence, not intuition.

Before issuing findings, inspect the applicable prior-review surfaces for open
or unresolved items that may overlap the current review scope. At minimum, check
`memory/04_review_log.md` and `memory/03_knowledge_base.md` when they exist.
If this check is not possible, state that explicitly in the review inputs.

---

## 1. Review Philosophy

The purpose of review is to verify that the change is:

- predictable;
- safe;
- reviewable under governance.

Do not assume a small diff is safe.
Do not approve without naming the supporting evidence.

---

## 2. Verdict Model

| Verdict | Meaning | Use when |
|---|---|---|
| `APPROVED` | Safe enough to accept | No finding materially blocks the frozen engineering merge decision |
| `CHANGES_REQUESTED` | Must be fixed | A merge-blocking issue exists |
| `ESCALATED` | Requires human decision | Material risk or trade-off ambiguity remains after review |

A verdict is evidence-bound. `APPROVED` requires named evidence that no finding
materially blocks the frozen engineering merge decision for this PR. If the
review depends on missing merge-critical evidence, unresolved merge-blocking
findings, or unreviewed dirty work, do not present the verdict as clean
approval; use `CHANGES_REQUESTED`, `ESCALATED`, or an explicit `WARNING` as
appropriate.

`APPROVED` does not mean the whole subsystem is qualified, and it does not
require repository-wide P0/P1 = 0.

### 2.1 Finding Levels

Keep Codex / reviewer severity as `P0 | P1 | P2 | P3`. Do not invent
`G0 | G1 | G2 | G3`.

The review-output labels below describe local review action. They are not a
second severity scale and are not equivalent to P0/P1:

| Level | Meaning |
|---|---|
| `BLOCKING` | The finding materially blocks this PR's frozen merge decision |
| `WARNING` | A real risk or debt item that must remain explicit, but does not by itself block this merge |
| `SUGGESTION` | A non-blocking improvement |

Do not confuse `ESCALATED` with `BLOCKING`.
Escalation is for unresolved consequential ambiguity, not merely for defects.

### 2.2 Finding Severity vs Merge Blocking Applicability

Severity describes the finding.
Blocking applicability describes the current merge decision.

They are not equivalent.

A finding may remain `P1` and still be legal to carry forward when it does not
materially change this PR's merge decision. That is not a severity downgrade.
It means:

> the problem is still serious, but it is not this PR's merge responsibility.

Split the gates:

| Gate | Question it answers | What it does not prove |
|---|---|---|
| Engineering Merge Gate | Can this PR, at its frozen claim ceiling, be merged safely? | The whole subsystem has no remaining P1 |
| Qualification Gate | Has the capability been proven enough to call qualified? | That this PR is unsafe to merge |

It is legal, and expected, to report:

```text
Engineering Merge = READY
Qualification = NOT READY
```

That is not a waiver. Those are two different questions.

### 2.3 Four-Question Finding Triage

Finding is not a task. A Codex or reviewer finding is evidence. It does not
automatically become the current implementation task, expand frozen scope, or
reopen qualification.

Triage first:

```text
finding
→ triage
→ does it change this PR's engineering merge decision?
   ├─ yes → blocker / FIX_NOW
   └─ no  → allowed non-blocking disposition / record
```

Every finding must answer all four:

| Question | Answer |
|---|---|
| Severity | `P0` / `P1` / `P2` / `P3` |
| Attribution | introduced by this PR, worsened by this PR, exposed by this PR, or pre-existing |
| Decision impact | whether it makes this PR's MERGE / DONE false |
| Disposition | blocking: `FIX_NOW`; otherwise one allowed non-blocking code below |

The third column is the merge question. `P1` does not automatically mean
`FIX_NOW`. A non-blocking P1 still remains a P1.

### 2.3.1 Allowed non-blocking dispositions

A P0/P1 may be non-blocking only with one of these codes and a concrete
reason. "We want to merge" is not a reason.

| Code | Meaning |
|---|---|
| `PRE_EXISTING` | The defect already existed and this PR did not introduce, worsen, or newly execute it |
| `OUTSIDE_FROZEN_SCOPE` | The finding is real, but it sits outside the frozen review boundary |
| `QUALIFICATION_ONLY` | The finding matters for subsystem qualification / release, not this PR's merge safety |
| `FUTURE_CAPABILITY` | The request expands frozen scope into a capability this PR does not claim |
| `NO_PR_DELTA_IMPACT` | The finding has no material effect on this PR's delta, path, or claimed DONE |
| `FALSE_POSITIVE` | Named evidence shows the finding does not hold on the reviewed HEAD |

Do not invent another non-blocking code. If none of these fits, the finding
blocks or must be escalated.

### 2.4 What Actually Blocks Merge

A finding blocks the Engineering Merge Gate if one of these is true:

- **A.** this PR introduced or worsened a real correctness P0/P1
- **B.** the finding makes the PR's frozen DONE / claim ceiling false
- **C.** even if the issue already existed, this PR actually enters that
  dangerous path, or enlarges exposure to it
- **D.** the finding breaks evidence, identity, irreversible state, or a
  required check that this merge relies on

PR-introduced or PR-worsened true correctness P0/P1s block. Required CI /
branch-policy failure also blocks under **D**.

Otherwise keep the real severity, assign exactly one allowed non-blocking
code plus a concrete reason, and do not automatically block.

### 2.4.1 Canonical scenario answers

These six answers are part of the policy. Downstream files must not contradict
them.

| Finding | Engineering Merge | Qualification |
|---|---|---|
| PR adds a wrong citation | `BLOCK` | unchanged / not this gate |
| PR makes an existing bug worse | `BLOCK` | unchanged / not this gate |
| Required CI check fails | `BLOCK` | unchanged / not this gate |
| Repository already has an unrelated P1 | `READY`; record `PRE_EXISTING` or `NO_PR_DELTA_IMPACT` | may remain `NOT READY` |
| Reviewer asks for a capability outside frozen scope | `READY`; record `FUTURE_CAPABILITY` or `OUTSIDE_FROZEN_SCOPE` | not this gate |
| Qualification benchmark still has P1s, but this PR is safe | `READY`; record `QUALIFICATION_ONLY` | `NOT READY` |

### 2.5 Frozen Merge Decision

Before review findings are judged, freeze:

```text
CURRENT OWNER DECISION:
Can this PR be merged safely?

CLAIM CEILING:
What does this PR actually claim to have done?

REVIEW BOUNDARY:
changed surface + real semantic blast radius

REVIEWED HEAD:
<exact current SHA>
```

Judge every finding against that frozen decision. Do not drift into proving
the whole surrounding subsystem.

### 2.6 Delta-Bounded Re-Review

Exact current HEAD must still be reviewed. HEAD changing does not reopen the
whole subsystem. This is the stop rule that prevents review recursion.

Do not do this:

```text
HEAD A full review
→ fix one finding
→ HEAD B
→ restart unbounded adversarial review of the whole PR
→ discover another unrelated world of findings
```

Do this:

```text
HEAD A
→ merge decision = BLOCKED by X
→ fix X → HEAD B
→ re-review only:
   1. was X actually fixed?
   2. did the correction create a direct regression?
   3. did the frozen merge decision materially change?
```

Default re-review after a correction looks only at those three questions. It
is not a license to re-explore every nearby edge case.

Re-expand review scope only when:

- the claim ceiling grew;
- the correction changed a shared semantic choke point;
- new evidence proves the prior review boundary was incomplete.

Otherwise re-review must converge. Unrelated new P1s found while re-reviewing
a bounded correction are triaged against the frozen decision; they do not
automatically restart full-PR qualification.

### 2.7 Spec Review Stop Rule

A future-state concern that has no executable path yet, and does not affect
the next authorized implementation decision, must not block current spec
acceptance. Record it as a deferred design question. Do not expand the spec
indefinitely.

---

## 3. Mandatory Audit Checklist

### 3.1 Boundary and Architecture

Check:

- whether domain code touches forbidden I/O, UI, OS, or native concerns;
- whether external or native model input uses an appropriate ACL boundary;
- whether the change conflicts with an ADR or boundary rule.

### 3.2 Physical and Native Safety

If native interop is involved, check:

- whether memory ownership is explicit;
- whether ABI layout is explicit when needed;
- whether panic / fail-fast and recoverable error handling are consistent.

If native interop is not involved, mark this section `N/A`.

### 3.3 Quality and Verification

Check:

- whether evidence matches task risk;
- whether failure paths were considered when applicable;
- whether validation locks observable behavior, not implementation trivia;
- whether legacy refactor work first verified baseline buildability.

### 3.4 Thread Safety

Check:

- whether accesses from different threads stay on the correct thread;
- whether async failure paths are handled.

If this is not relevant, mark this section `N/A`.

### 3.5 Dirty Worktree and Scope Hygiene

If the worktree is dirty during implementation or review, check:

- whether unrelated dirty files were kept out of scope;
- whether touched-file overlap was handled or explicitly escalated;
- whether the commit and review boundary remains understandable.

---

## 4. Knowledge Base Cross-Check

Before issuing a verdict, check `memory/03_knowledge_base.md` for:

1. anti-pattern matches;
2. recorded regression patterns.

If a known anti-pattern reappears, call it out explicitly.

---

## 5. Legacy Refactor Review Addendum

For legacy repos, refactors, rollbacks, or baseline resets, also check:

- whether the claimed baseline was verified through the authoritative build path;
- whether the canonical toolchain was identified;
- whether the change is being presented as a safe refactor while the baseline is unstable.

If the baseline was not verified:

- do not call the result a clean refactor;
- include at least one `WARNING`;
- escalate when the conclusion depends on baseline stability.

---

## 6. Review Output Format

Every review response should include:

```markdown
### Review Inputs Checked
- governance/REVIEW_CRITERIA.md
- <list any additional documents read per REVIEW_CRITERIA.md conditions>

### Frozen Merge Decision
- Current owner decision: can this PR be merged safely?
- Claim ceiling: ...
- Review boundary: changed surface + semantic blast radius
- Reviewed HEAD: <sha>

### [Decision Summary]
**MERGE DECISION**: READY | NOT READY
**Verdict**: APPROVED | CHANGES_REQUESTED | ESCALATED
**Risk Level**: Low | Medium | High

### Governance Audit
- Architecture: ...
- Native Safety: ... | N/A
- Test Integrity: ...
- Thread Safety: ... | N/A
- Baseline Status: Stable | Unverified | Unstable | N/A

### Technical Findings
1. [P0|P1|P2|P3] Title
   - Merge impact: BLOCKING | non-blocking
   - Attribution: introduced | worsened | exposed | pre-existing
   - Decision impact: whether this makes MERGE / DONE false
   - Disposition: FIX_NOW | PRE_EXISTING | OUTSIDE_FROZEN_SCOPE | QUALIFICATION_ONLY | FUTURE_CAPABILITY | NO_PR_DELTA_IMPACT | FALSE_POSITIVE
   - Reason: ...
   - Location: `path:line`
   - Evidence: ...
   - Rule Reference: ...

### Knowledge Base Alignment
- Anti-patterns checked: N
- Regression notes checked: N
- Result: Pass | Conflict Found
```

Every non-trivial finding must include:

- location;
- evidence;
- rule reference.

Open findings must also include:

- status: `open` | `resolved` | `carried-forward` | `not-reproduced`;
- disposition: `FIX_NOW` or one allowed non-blocking code from §2.3.1;
- reason: why that disposition applies.

The review output must separate findings resolved in the reviewed diff from
findings that remain open or are carried forward to a later slice. Do not hide
carried-forward findings inside a passing summary. Do not treat remaining real
P1s as absent or fixed.

A legal merge-ready summary may look like:

```text
MERGE DECISION: READY

Blocking findings:
- none

Carried-forward findings:
- P1 — <title>
  Attribution: pre-existing
  Current merge impact: none
  Disposition: PRE_EXISTING
  Reason: this PR neither modifies nor executes that path

Required checks:
- green

Reviewed HEAD:
- <sha>
```

---

## 7. Post-Review Memory Actions

After issuing a verdict:

1. append the full review record to `memory/04_review_log.md`;
2. add a one-line summary to `memory/01_active_task.md`;
3. if a new anti-pattern was found, record it in `memory/03_knowledge_base.md`.

Keep `memory/01_active_task.md` concise. Do not dump full findings into it.

---

## 8. C++ Build Boundary Addendum

Apply this addendum whenever review touches C++ project files, header layout, or build configuration.

Hard checks:

- `AdditionalIncludeDirectories` or equivalent settings must not point to a peer project's private tree;
- cross-project private headers must not be justified merely because the build passes;
- shared headers must live in a shared boundary layer with clear ownership.

This is a boundary issue, not a style issue.

---

## 9. Final Principle

> A review that cannot name its evidence is not a valid review.
> Use escalation for conclusions that depend on ambiguity.
> Keep the severity of real findings, and separately decide whether each one
> materially blocks this PR's merge decision.
