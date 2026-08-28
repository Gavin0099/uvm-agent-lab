# Operator UI — Information Architecture / UX Redesign Proposal

Status: frozen IA/UX proposal for a later implementation PR. This
document does not change `QAResponse`, retrieval, `GovernedQAService`,
`/api/qa`, or `gv100h/spec_qa/operator_ui/static/`.
Not POC-1 qualification, not Gate 4, not a complete Spec Bot.

This slice only establishes the design workflow and freezes the
proposal. Do not implement HTML/CSS/JS here. The next implementation
branch should be `feat/spec-qa-operator-ui-redesign`.

Skills used:

1. `.agents/skills/frontend-design/SKILL.md` (direction / IA)
2. `.agents/skills/ui-ux-review/SKILL.md` (second-pass UX review)

Baseline: merged Operator UI shell from PR #35
(`gv100h/spec_qa/operator_ui/static/{index.html,styles.css,app.js}`).

---

## 1. Subject

| Item | Choice |
| --- | --- |
| Product | USB Hub Spec QA Operator UI (Machine B development shell) |
| Audience | USB Hub FW / verification engineers |
| Single job | Ask a USB Hub spec question, read the answer, then inspect the source |
| Stack | HTML, CSS, vanilla JS, Python HTTP server |
| Signature | The **Answer** is a spec-reading surface; citations are folded instruments, not a schema dump |

## 2. Diagnosis of the current shell

The current page is a two-column schema viewer, not a Spec QA tool.

| Problem | Evidence in current files |
| --- | --- |
| 50/50 Question / Result split | `styles.css` `.layout { grid-template-columns: 1fr 1fr }` |
| Left pane is mostly empty in fixture mode | Query / `answer_scope` / `retrieval_mode` / `allowed_evidence_scopes` are disabled but still first-layer |
| Engineering fields outrank the question | `index.html` exposes schema identifiers as labels |
| Answer is not the hero | Result pane leads with `DATA SOURCE`, status pill, then `Answer` as an `h3` |
| Evidence always expanded | `app.js` `renderCitations` writes every excerpt/id/badge immediately |
| Governance occupies the first visual layer | Header kicker, claim sentence, `Frozen QAResponse` pill, fixture hint, DATA SOURCE banner, synthetic `document`/`revision` badges all compete |
| Generic AI-dashboard look | Near-black canvas (`#0b1020`), system UI font, rounded cards, blue Ask button — not USB-spec vernacular |

Fixture honesty is correct and must stay (`Fixture mode ignores query`,
`id="dataSource"`, text-node rendering, no fabricated PDF). The failure is
**priority**, not missing warnings.

## 3. Target flow

User path: **ask → read answer → open source**.

Not: **learn QAResponse → maybe ask**.

```text
┌──────────────────────────────────────────────────────────┐
│ USB Spec QA                                  DEV / Fixture │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Ask a USB specification question                        │
│ ┌──────────────────────────────────────────────────────┐ │
│ │ downstream port 可以在哪些 link state 發 Warm Reset? │ │
│ └──────────────────────────────────────────────────────┘ │
│                                                [ Ask ]    │
│                                                          │
│  Advanced settings ▸                                     │
│                                                          │
├──────────────────────────────────────────────────────────┤
│ ANSWER                                                   │
│                                                          │
│ Warm Reset may be initiated from ...                     │
│                                                          │
│ USB 3.2 Rev 1.1 · §6.9.3 · Authoritative                │
│                                                          │
│ Evidence                                              2 ▾ │
│ Governance / boundary                                ▸   │
└──────────────────────────────────────────────────────────┘
```

First visual layer keeps only three things: **what was asked → the
answer → where it came from.**

These fields do not disappear; they drop to Advanced / Evidence /
Governance:

- `answer_scope`
- `retrieval_mode`
- `allowed_evidence_scopes`
- `boundary_code`
- `claim_evidence_ids`
- `evidence_ids`
- `synthetic-v1`

## 4. Visual hierarchy

1. **Ask** — one question field + one primary Ask control.
2. **Answer** — largest type, longest measure, first result content.
3. **Source line** — document · section · authority on one line under the
   answer. No PDF link unless `has_pdf_anchor` and a safe `http(s)` href
   already exist.
4. **Evidence** — collapsed `<details>`; count in the summary.
5. **Boundary / governance** — collapsed. Includes claim ceiling,
   `boundary_code`, fixture provenance (`FIXTURE-*`, `synthetic-v1`).
6. **Advanced** — `answer_scope`, `retrieval_mode`,
   `allowed_evidence_scopes`, source=fixture|service.

Keep current honesty strings, move them down a layer:

- `Operator UI / development shell`
- `not POC-1 qualification`
- `Fixture mode ignores query`
- `DATA SOURCE` / `id="dataSource"`
- `Query is NOT evaluated.`

## 5. Copy rules

| Now | Proposed label |
| --- | --- |
| Query | Question |
| Ask | Ask |
| answer_scope | Scope (inside Advanced) |
| retrieval_mode | Retrieval (inside Advanced) |
| allowed_evidence_scopes | Allowed evidence (inside Advanced) |
| Frozen QAResponse | fold into Boundary / governance |
| DATA SOURCE | Source (fixture chip + banner text retained for tests) |

Abstain copy stays:

> 系統不是不知道答案，而是目前證據不足以在治理規則下回答。

Empty result: “Ask a USB Hub question to see an answer here.”
Error: show the server `error` string next to Ask, not only in the
answer well.

## 6. Token sketch (do not implement in this slice)

Avoid the three generic AI palettes. Direction: **spec binder on a bench**
— a readable paper plane for the answer, quiet instrument chrome around
it.

| Token | Role | Sketch |
| --- | --- | --- |
| `paper` | Answer surface | `#f4efe4` |
| `ink` | Answer text | `#1b1a17` |
| `bench` | Page chrome | `#e7e1d4` |
| `rule` | Hairline / section rule | `#b7a990` |
| `fixture` | Fixture / abstain | `#8a5a12` |
| `conflict` | Conflict / error | `#8f2d2d` |

Type: a restrained display face for the product name only; a readable
serif or humanist body on the answer paper; tabular/mono for evidence
IDs. Do not keep the current system-ui-on-near-black as the identity.

Signature: the answer paper, not a gradient hero or numbered 01/02/03
dashboard.

## 7. UX review punch-list (ui-ux-review, no code)

| Sev | Location | Issue | Required change (later implementation) |
| --- | --- | --- | --- |
| P1 | `index.html` layout | Schema fields and DATA SOURCE precede Answer | Single column: Ask, then Answer hero |
| P1 | `index.html` labels | `answer_scope` / `retrieval_mode` / `allowed_evidence_scopes` first-layer | Move under Advanced; closed by default |
| P1 | `app.js` citations | All evidence expanded | Render summary + collapsed details |
| P2 | `index.html` headings | Multiple `h3` compete with Answer | Answer is the only first-layer result heading |
| P2 | `styles.css` | Ask is full-width but short; no focus ring token | Visible `:focus-visible`; Ask min height 44px |
| P2 | `app.js` Ask | No in-flight disabled state | Disable Ask until `/api/qa` returns |
| P2 | fixture banner | Emoji + long governance dump in first layer | Keep text warning; compact chip; full text in governance fold |
| P3 | contrast | Muted `#94a3b8` on `#141b2d` may fail body-size contrast | Recheck 4.5:1 on the implemented paper/chrome tokens |
| P3 | `#question` | Placeholder-as-example is fine if a visible label remains | Keep a visible `Question` label |

Out of scope for that later pass: icon libraries, dark/light dual theme
as a gate, chart rules, React/Tailwind.

## 8. Test and contract freeze

`tests/gv100h/test_operator_ui_presentation_workflow.py` only proves
that the workflow contract and this proposal still exist. It does
**not** prove UX quality.

Later implementation must keep these assertions from
`tests/gv100h/test_spec_qa_operator_ui.py` unless that test file is
updated in the same slice:

- `Operator UI / development shell`
- `not POC-1 qualification`
- `Fixture mode ignores query`
- `DATA SOURCE` and `id="dataSource"`
- `innerHTML` absent; `createElement` / `textContent` present
- `Query is NOT evaluated.`
- fixture evidence IDs stay `FIXTURE-*` and disjoint from production
- no fabricated `pdf_href`

Do not rename frozen QAResponse fields.

## 9. Not claimed

- Live Spec QA / RAG / PDF ingestion
- POC-1 or Gate 4
- Visual redesign implemented
- Accessibility audit of a new theme (tokens above are a sketch)
- UX quality (workflow tests are not a visual pass)

## 10. Next slice (separate implementation PR)

Do not mix this workflow/docs freeze with a large `static/` rewrite.

After this proposal is on `main`, open `feat/spec-qa-operator-ui-redesign`
and change only:

- `gv100h/spec_qa/operator_ui/static/index.html`
- `gv100h/spec_qa/operator_ui/static/styles.css`
- `gv100h/spec_qa/operator_ui/static/app.js`

Required evidence for that PR:

```text
before screenshot (current 50/50 schema viewer)
        ↓
implementation
        ↓
after screenshot
        ↓
ui-ux-review against rendered UI
```

Suggested viewports: Desktop 1440×900, Laptop 1280×800, Mobile 390×844.
Store the current ugly shell as the Before baseline review artifact.
Source-only “spacing good / hierarchy clear” is not acceptance.
