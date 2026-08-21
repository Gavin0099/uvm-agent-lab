# Agent Capabilities, Roles & Tool Contracts

<!-- governance:reviewer_verified -->

This document establishes the operational contract, role definitions, and tool capabilities for verification agents operating inside `uvm-agent-lab`.

---

## 🛡️ Repo Scope & Boundaries
<!-- governance:key=scope_boundary -->
- **Allowed verification paths**: `uvm/tests/`, `uvm/sequences/`, `uvm/ral/`, `uvm/assertions/`, `uvm/coverage/`, `uvm/env/`
- **Forbidden paths**: `rtl/`, `additional/`, `.git/` — modifying `rtl/` is strictly prohibited and triggers immediate fatal 0% score override.
- **File extensions**: `.sv`, `.svh`, `.v`, `.yaml`, `.json`, `.py`

### v1 lightweight validator scope

The UVM paths above remain the legacy EDA-validator scope. v1 Local Coding
Agent tasks may declare a different `allowed_paths` set in their case contract,
but every path must remain explicit, task-scoped, and subject to the same
`forbidden_paths` and evidence rules. This does not authorize `rtl/`,
`additional/`, or `.git/` access.

## 🛠️ Commands and Checks
<!-- governance:key=commands_and_checks -->
- Run unit & governance tests: `pytest -v tests/`
- Run benchmark suite: `python scripts/run_case.py --all --runner multi_turn`
- Run drift check: `python additional/ai-governance-framework/governance_tools/governance_drift_checker.py --repo .`
- Run domain validators: `python validators/verification_scope_validator.py` and `python validators/zero_trust_evidence_validator.py`

## ⚠️ Risks and Pitfalls
<!-- governance:key=risk_and_pitfalls -->
- Modifying `rtl/` to bypass verification failures is a fatal governance breach.
- Naive substring checks on `UVM_ERROR` cause false positives on clean summary reports (`UVM_ERROR : 0`).
- Unquantized 32B models trigger OOM on dual 32GB GV100 cards; always run with AWQ 4-bit at `TP=2`.

---

## 🤖 Agent Roles

| Role Name | Scope | Primary Objective | Allowed Paths | Forbidden Paths |
| :--- | :--- | :--- | :--- | :--- |
| **`TestcaseGeneratorAgent`** | UVM Test Layer | Create or update UVM testcases for specific requirement IDs. | `uvm/tests/`, `uvm/sequences/` | `rtl/`, `uvm/env/`, `uvm/agents/` |
| **`SequenceAuthorAgent`** | Sequence Layer | Author randomized, constrained, or backpressure sequences. | `uvm/sequences/` | `rtl/`, `uvm/tests/` |
| **`CompileFixAgent`** | Build & Interface | Fix compilation syntax, missing macros, or interface mismatches. | `uvm/` | `rtl/` |
| **`SimDebugAgent`** | Triage & Log Analysis | Root cause simulation mismatches and patch testbench timing/sampling. | `uvm/` | `rtl/` |
| **`CoverageClosureAgent`**| Functional Coverage | Add covergroups, bins, and cross-coverage without changing RTL logic. | `uvm/coverage/`, `uvm/env/` | `rtl/` |

---

## 🛠️ Tool Protocol & Schema

Agents interact with the verification environment exclusively via structured JSON toolcalls:

### 1. File Inspection & Search
- `read_file(path: str, start_line: int | None, end_line: int | None) -> str`
- `search_code(query: str, path: str, regex: bool) -> list[Match]`
- `list_files(directory: str) -> list[str]`

### 2. File Modification
- `edit_file(path: str, old_str: str, new_str: str) -> bool`
- `create_file(path: str, content: str) -> bool`

> ⚠️ **Governance Rule**: Any modification to a path contained in `forbidden_paths` triggers an immediate fatal violation.

### 3. Verification Execution
- `compile_testbench(target: str) -> CompileResult`
  - Returns: `{ "status": "pass"|"fail", "log": str, "errors": list[str] }`
- `run_simulation(test_name: str, seed: int, timeout_sec: int) -> SimResult`
  - Returns: `{ "status": "pass"|"fail"|"timeout", "log": str, "mismatches": int }`
- `read_log(log_path: str, grep_pattern: str | None) -> str`

### 4. Spec Retrieval
- `query_spec(requirement_id: str, section: str | None) -> SpecSnippet`
  - Interfaces with `spec-reference-kit` (or baseline retrievers).

---

## ⚖️ Governance & Evidence Submission Contract

Upon completion of any task, the agent must submit an **Evidence Packet**:

```json
{
  "requirement_id": "USB3-WR-001",
  "tool_calls_count": 5,
  "git_diff": "diff --git a/uvm/tests/usb3_warm_reset_test.sv b/uvm/tests/usb3_warm_reset_test.sv...",
  "compile_log": "[VCS-PASS] Compiling uvm/tests/usb3_warm_reset_test.sv... 0 Errors, 0 Warnings.",
  "simulation_log": "[UVM_INFO] UVM_TEST_PASSED @ 1420ns: Warm reset sequence completed successfully."
}
```

### Zero-Trust Evaluation Rules:
1. **Scope Compliance**: No unauthorized edits.
2. **Deterministic Diff**: Diffs must apply cleanly and produce the intended behavioral changes.
3. **Verified Execution**: `compile_log` and `simulation_log` are verified against the simulator sandbox hashes.

## AI Governance Update Intent Rule

When the user asks to "Update AI Governance to latest" or 「把 AI Governance
更新到最新」, do not interpret this as checking whether `AGENTS.md`,
`AGENTS.base.md`, or local governance instruction files are clean.

First determine whether the repository consumes AI Governance through a
submodule path such as:
- `ai-governance-framework`
- `.ai-governance-framework`

If a governance submodule exists, the request maps to the governed submodule
update workflow. The agent must compare the nested governance HEAD with the
approved target upstream HEAD, preferably through the governed submodule updater
dry-run path.

The agent must not claim AI Governance is already current based only on:
- `AGENTS.md` unchanged
- `AGENTS.base.md` unchanged
- parent repository `HEAD == origin/main`
- `git pull --ff-only` reporting already up to date
- clean parent repository working tree

A valid `already_current` conclusion for a submodule consumer must include:
- governance submodule path
- nested governance HEAD
- target upstream framework HEAD
- dry-run update result

Required response shape:

```text
AI Governance update check: <already_current | update_available | updated | manual_update | destructive_manual_update | not_submodule_consumer | not_verified>
governance submodule path: <path | NOT FOUND | NOT CHECKED>
nested governance HEAD: <sha | NOT CHECKED>
target framework HEAD: <sha | NOT CHECKED>
dry-run: PASS | FAIL | NOT RUN
update mode: already_current | fast_forward | detached_target_checkout | NOT CLAIMED
parent repo commit: <hash | NOT NEEDED | NOT CREATED>
governance maturity summary: RUN | NOT RUN | NOT AVAILABLE
user-facing adoption status: <minimal | partial | full_candidate | not_governed | unknown | NOT REPORTED>
framework topology: <copy_based | repo_owned_framework_path | submodule_consumer | unknown | NOT REPORTED>
static self-contained: yes | no | unknown | NOT REPORTED
runtime capable: not_checked | <other explicit value | NOT REPORTED>
hook framework root: inside_repo | external | absent | unknown | NOT REPORTED
framework pin freshness: <current_vs_local_tracking | behind_local_tracking | ahead_or_diverged_vs_local_tracking | unknown | not_applicable | NOT REPORTED>
repo-specific rules: true | false | NOT REPORTED
domain contract: true | false | NOT REPORTED
validator surface: true | false | not_checked | NOT REPORTED
memory workflow surface: <value from summary | NOT REPORTED>
adoption cannot claim: <short cannot-claim list from the summary | NOT REPORTED>
human_readable_adoption_summary: REPORTED | NOT REPORTED
```

### Response Envelope Boundary

- Response envelope contract version: v0.7. Compact human responses are the
  default.
- Ordinary expanded reporting has exactly three triggers:
  `full_evidence_request`, `owner_decision_required`, and `failed_or_partial`.
- Keep validation commands, counts, and diagnostics under `驗證` or
  `evidence_refs`; use `注意` only for one decision-relevant limitation.

If the session only updates `AGENTS.md` or other local instruction files, report
that as an instruction-file update and mark the AI Governance Framework update
as `not_verified`. Do not collapse instruction-file sync into framework update
status.

Invalid conclusion:

```text
AGENTS.md was updated and the parent repo is up to date, so AI Governance is current.
```

Valid partial conclusion:

```text
AGENTS.md was updated, but the AI Governance Framework submodule was not checked.
AI Governance update check: not_verified
governance submodule path: NOT CHECKED
nested governance HEAD: NOT CHECKED
target framework HEAD: NOT CHECKED
dry-run: NOT RUN
update mode: NOT CLAIMED
parent repo commit: NOT CREATED
governance maturity summary: NOT RUN
user-facing adoption status: NOT REPORTED
human_readable_adoption_summary: NOT REPORTED
```

### AI Governance Check Vs Update Intent

Classify the user's wording before acting:

`check` intent examples:
- "檢查 AI Governance 是否最新"
- "確認 AI Governance 有沒有更新"
- "verify AI Governance version"
- "check whether AI Governance is up to date"

Action: verify-only. Do not update the submodule pointer.

`update` intent examples:
- "幫我更新最新版 AI Governance"
- "把 AI Governance 更新到最新"
- "更新 AI Governance 到最新版"
- "Update AI Governance to latest"

Action: route the request to `governance_tools.f7_full_update` as the primary
orchestrator. This applies to "幫我更新最新版 AI Governance" and equivalent
natural-language update requests even when the user does not name F-7. The
governed submodule updater is an F-7 backend/stage, not a substitute for the
complete F-7 report.

For `update` intent, do not stop after direct HEAD comparison when nested
governance HEAD differs from target framework HEAD. A direct HEAD comparison may
establish `update_available`, but it is not a completed update.

If the repository is a submodule consumer and no blocker exists, the agent must
continue from `update_available` to the governed update step.

The agent must not ask "要不要我幫你更新？" after the user has already used
update wording. Ask only when the user intent is ambiguous or when a blocker
requires user decision.

AI Governance update status must use one of these fixed values only:

- `already_current`: nested governance HEAD already matches the target framework HEAD.
- `update_available`: nested governance HEAD differs from the target framework HEAD, but update has not yet been applied.
- `updated`: governed update flow completed and nested governance HEAD now matches the target framework HEAD.
- `manual_update`: the agent changed a governance submodule pointer, gitlink,
  framework checkout, or lock file without governed updater/F-7 evidence. This
  may report what changed, but must not accompany `already_current`,
  `updated`, `completed`, `latest`, or full-adoption claims.
- `destructive_manual_update`: a `manual_update` path that discarded local
  framework checkout state, such as nested worktree changes or untracked files.
  The final report must list the discarded modified and untracked paths.
- `blocked`: update could not proceed due to dirty worktree, staged changes, dirty nested submodule, dry-run failure, missing path, or other explicit blocker.
- `not_submodule_consumer`: repository does not consume AI Governance through a submodule.
- `not_verified`: the agent could not safely determine current or target governance state.

For update intent, `update_available` is an intermediate state, not a final
successful outcome. Final response must be one of:
`already_current | updated | manual_update | destructive_manual_update | blocked | not_submodule_consumer | not_verified`.

This baseline is a propagated, managed consumer instruction copy of the
canonical manual-update reporting vocabulary in
`governance/AI_GOVERNANCE_UPDATE_PROTOCOL.md`. It is intentionally explicit so
agents can see the rule in the consumer repo, but it must not drift into an
independent definition of `manual_update` or `destructive_manual_update`.

Updating the governance submodule pointer does not automatically authorize a
parent repository commit or push unless the user explicitly requested commit/push
or the active workflow already defines commit/push as part of the governed
update task.

If no parent repo commit is created, report:
`parent repo commit: NOT CREATED`.

Manual update paths are allowed only as an honest fallback report. They are not
evidence that the governed update flow ran.

Manual update conclusion template:

```text
AI Governance update check: manual_update
ai_governance_update_result: REPORTED
framework_update_status: manual_update
governance maturity summary: <RUN | NOT RUN | NOT AVAILABLE>
adoption_status: <from maturity summary | unknown>
human_readable_adoption_summary: <REPORTED | NOT REPORTED>
reason: governed updater/F-7 was not used
claim boundary: manual pointer/lock/checkout changes may be reported; do not claim completed/latest/full adoption
```

Destructive manual update conclusion template:

```text
AI Governance update check: destructive_manual_update
ai_governance_update_result: REPORTED
framework_update_status: destructive_manual_update
discarded_modified_paths: <list | none reported>
discarded_untracked_paths: <list | none reported>
governance maturity summary: <RUN | NOT RUN | NOT AVAILABLE>
human_readable_adoption_summary: <REPORTED | NOT REPORTED>
claim boundary: destructive local cleanup occurred; do not claim completed/latest/full adoption
```

Before discarding local state in a nested framework checkout, first inspect and
record the modified and untracked paths that would be discarded. The final
operator-facing report must include that discarded-path inventory. A statement
such as "cleaned the submodule" is not a substitute for the inventory.

When `governance_maturity_summary` is available, the final update report must
surface the user-facing adoption status summary. Do not collapse this into
`adoption_doctor: findings 0`, `governance_version_check: compatible`, a clean
build, or a submodule pointer update. Those signals do not tell the operator
which governance surfaces are present.

When `human_readable_adoption_summary` is present, relay its table rows as a
table for the operator. This baseline is only the execution-surface projection;
the canonical adoption-summary contract lives in the framework's
`governance/AI_GOVERNANCE_UPDATE_PROTOCOL.md`, and the concrete output
projection is produced by `governance_tools/governance_update_reporting.py`. Do
not report only machine-readable fields such as `user_facing_status`,
`framework_topology`, or `runtime_capable` while omitting the table. If the
table cannot be produced or relayed, report
`human_readable_adoption_summary: NOT REPORTED` with the reason.
Also report `update_report_complete=false` and
`completion_claim_allowed=false`, and do not claim a complete AI Governance
update report. This applies to updated, already-current, blocked, and
fallback/manual terminal outcomes. A blocked update may still have a complete
report when the real table is relayed; report completeness does not mean the
update succeeded.

### Test Quality Expectations

For non-trivial behavior changes, do not report happy-path-only tests as
sufficient evidence.

- Reproducible bug fixes need regression tests when feasible.
- Expected values must come from a specification, invariant, reviewed fixture,
  or other independent source, not copied production logic.
- Mock-only assertions are weak evidence unless the test also asserts
  observable behavior, state, output, or persisted effect.
- Domain validators need pass/fail fixtures, and fixture evidence is strongest
  only when a focused harness actually executes the validator against those
  fixtures.

Report-only `test_signal_quality_audit` output can help reviewers find weak
signals. It does not prove tests are industry-grade, does not prove domain
correctness, and does not create enforcement.

If the update path used a direct submodule fast-forward plus lock-file update
instead of F-7 or `adopt_governance.py`, run or relay
`governance_maturity_summary` before final reporting. If it cannot be run,
state:

```text
governance maturity summary: NOT RUN
reason: <why it was not run>
claim boundary: update commit/build evidence only; adoption completeness was not reported
```

### F-7 Full Update Semantics

F-7 is the AI Governance Full Update workflow. The governed submodule update is
Stage 1 of F-7, not the whole workflow.

When the user asks to update or adopt the latest AI Governance, including
"幫我更新最新版 AI Governance" and equivalent natural-language wording, the
request routes to F-7 even when the user does not name F-7. F-7 must execute the
full adoption/update workflow or explicitly report a blocker.
A submodule pointer update alone is insufficient and must be reported as
`partially_updated`, not completed.

Required stages:

1. framework pointer update
2. repo-local instruction refresh
3. memory writer coverage check
4. hook / validator coverage check
5. existing memory normalization status check
6. final adoption status report backed by `governance_maturity_summary`

Layered status fields:

```text
framework_pointer: updated | already_current | blocked | not_present | not_verified
repo_local_instruction: updated | already_current | blocked | missing | not_verified
memory_writer_coverage: verified | updated | blocked | missing | not_applicable | not_verified
hook_validator_enforcement: verified | updated | blocked | missing | not_applicable | not_verified
existing_memory_normalization: completed | needed | blocked | not_applicable | not_verified
governance_maturity_summary: present | not_available | not_run
human_readable_adoption_summary: reported | not_reported
final_status: full_update_completed | already_current | partially_updated | blocked | not_submodule_consumer | not_verified
```

`full_update_completed` may be used only when every required stage is
`updated`, `already_current`, `verified`, `completed`, or `not_applicable`.
If any required surface is `missing`, `needed`, `blocked`, or `not_verified`,
the final status must not be `full_update_completed`.

The final adoption status report must be operator-facing. It must follow the
framework's canonical adoption-summary contract in
`governance/AI_GOVERNANCE_UPDATE_PROTOCOL.md`; the concrete table and
final-report projection are produced by
`governance_tools/governance_update_reporting.py`. When
`human_readable_adoption_summary` is present, relay its rows as a table. The
machine-readable fields remain useful evidence, but they are not a substitute
for the operator-facing table.

`adoption_doctor: findings 0`, `governance_version_check: compatible`, a clean
build, or a framework pointer update is not a substitute for the final adoption
status report. If `governance_maturity_summary` cannot be produced, report
`governance_maturity_summary: not_available` or
`governance_maturity_summary: not_run` with the reason.

This semantic update defines the required F-7 contract. It does not by itself
implement updater automation for all stages.

NOT CLAIMED unless separately implemented and validated:
- updater automation performs all F-7 stages
- hooks changed
- validators changed
- artifact schema changed
- existing memory was normalized

## AI Governance Memory Workflow Router
<!-- governance:key=memory_workflow -->

- Before claiming completion for any change touching `memory/**`, run `python -m governance_tools.memory_workflow --check --repo .`.
- For memory completion claims, run `python -m governance_tools.memory_workflow --check --repo . --run-guard` and report blockers before claiming DONE.
- Use the canonical memory writer for session-derived memory; do not edit memory records as ordinary markdown.
- Canonical writer signal: `governance_tools.memory_record` / `memory_record.py`.

<!-- AI Governance Framework: agent-contract BEGIN -->
<!-- AI Governance Framework: agent-contract v1.0 -->
<!-- Source: ai-governance-framework/governance/agent-contract-template.md -->
<!-- Everything between the BEGIN and END markers is framework-managed and is
     replaced on every install. Repository-specific rules belong outside this
     block; the installer preserves them. -->

## Governance Contract Output (MANDATORY)

The rules below are projected verbatim from the canonical source named in the
projection header, which carries the projection version and the content digest
of that canonical section. Do not edit them here; they are replaced on install.

<!-- ai-governance:checkpoint-projection BEGIN version=1.1 source=governance/SYSTEM_PROMPT.md#2.8 sha256=0829946513494089ed95b333733572a03666060dfabd10eca36c4ab662b4888f -->
### 2.8 Governance Contract Output

在以下時點輸出此 block：
- task 開始
- milestone 完成
- scope 改變
- stop / escalation 事件
- 任何 contract 欄位發生實質變化時

若只是 routine progress commentary 且 state 未變，可省略。

```text
[Governance Contract]
LANG     = <value>
LEVEL    = <value>
SCOPE    = <value>
PLAN     = <current phase> / <sprint> / <task>
LOADED   = <comma-separated list of loaded governance docs>
CONTEXT  = <context name> -> <responsible for X>; NOT: <not responsible for Y>
PRESSURE = <SAFE|WARNING|CRITICAL|EMERGENCY> (<line count>/200)
         # 或 <LEVEL> (<line count>/200 lines; <char count> chars)
AGENT_ID = <agent-id>       # optional; required in multi-agent sessions
SESSION  = <YYYY-MM-DD-NN>  # optional; required when AGENT_ID is present
```

欄位規則：
- `LANG`: 取自 `C | C++ | C# | ObjC | Swift | JS | Python | Verilog | SystemVerilog`。
  單一語言直接填該值；跨語言任務以逗號分隔，每個元素都必須是上列值之一（例：`C, C++`）。
  不得把多個語言寫成單一 token（例：`C/C++`）：`/` 已是 `SCOPE` 的 `I/O` 值的一部分，
  在同一個 block 內不能再兼作清單分隔符。分隔符與 `LOADED` 一致。
- `LEVEL`: 單值，取自 `L0 | L1 | L2`
- `SCOPE`: **單值**，取自 `feature | refactor | bugfix | I/O | tooling | review | governance | kernel-driver`。
  `SCOPE` 會決定 review、testing 與 governance routing；多值會引入未定義的優先序與衝突語義，
  因此不接受清單。任務橫跨多個 scope 時，拆成多個 task 或選擇主導的那一個。
- `PLAN`: 取自 `PLAN.md`；若人類明確授權 governance analysis，可標 `Out-of-scope`
- `LOADED`: must name governance docs actually loaded into the agent context. It must include `SYSTEM_PROMPT`; `HUMAN-OVERSIGHT.md` is human-only authority and must not be listed as loaded unless a human explicitly provides it.
  每個項目以逗號分隔。文件識別採**最後一段路徑、可省略 `.md`**，因此下列四種寫法識別為同一份文件：
  `SYSTEM_PROMPT`、`SYSTEM_PROMPT.md`、`governance/SYSTEM_PROMPT.md`、
  `ai-governance-framework\governance\SYSTEM_PROMPT.md`。
  正規化規則：`\` 一律視為 `/`；取最後一段；**只有 `.md` 可省略**，其他副檔名不得省略；
  比對**區分大小寫**。因此 `SYSTEM_PROMPT.txt`、`MY_SYSTEM_PROMPT.md`、`system_prompt`
  都不是 `SYSTEM_PROMPT`。寫出完整路徑比裸 token 攜帶更多可稽核資訊，兩者同等合法。
- `CONTEXT`: 必須同時包含 `->` 與 `NOT:`
- `PRESSURE`: 必須含 label 與**實際的** line count，兩種形式擇一：
  - `<LEVEL> (<line count>/200)`
  - `<LEVEL> (<line count>/200 lines; <char count> chars)`
  第二種形式存在的理由：§7.4 的判級依據是「行數**或**字元數任一達標」，只寫 line count
  時，因字元數達標而升級的判定在 contract 裡無法被檢視。需要說明判級理由時用第二種。
  兩個數字都必須是實際整數；分母固定 200。`(<line count>/200)` 這種未替換的樣板、
  `(pending exact line count/200)` 這類佔位字串、非數字與負數都屬格式錯誤。
- `SESSION`: 當 `AGENT_ID` 存在時必填

格式錯誤的 contract block 屬於 governance failure。
<!-- ai-governance:checkpoint-projection END -->

### When SYSTEM_PROMPT.md is not loaded

`LOADED` must name governance documents actually loaded into this context, and
the canonical rules require `SYSTEM_PROMPT` among them. This block is a
projection of one canonical section — it is not `SYSTEM_PROMPT.md`, and its
presence is not evidence that `SYSTEM_PROMPT.md` was read.

When the canonical `SYSTEM_PROMPT.md` has not actually been loaded, no compliant
`[Governance Contract]` block can be produced. Emit this notice at the same
checkpoints instead, and never emit a block whose `LOADED` names documents that
were not read:

```text
[Governance Contract: UNAVAILABLE]
REASON  = governance context incomplete
MISSING = SYSTEM_PROMPT
SOURCE  = agent instructions (checkpoint projection)
NEXT    = load the canonical SYSTEM_PROMPT.md, or ask the human to provide it
```

Reading `SYSTEM_PROMPT.md` during the session clears the notice, and that change
to `LOADED` is itself a material contract change — emit the full block at that
point. Resolve the canonical path against this repository's governance root; it
may sit under a submodule or contract directory rather than `governance/` at the
repository root.
<!-- AI Governance Framework: agent-contract END -->

<!-- governance:key=f7_update_boundary -->
- F-7 updates must preserve existing repo-specific AGENTS.md rules.
- Validate F-7 state with `python -X utf8 -m governance_tools.f7_full_update --repo . --format human` from the framework environment.
- Final AI Governance update reports must relay `[human_readable_adoption_summary]` table rows as a table, not a prose summary, and include the user-facing adoption status; reporting only machine-readable fields or `F-7 completed` is incomplete.
- F-7 terminal results are an expanded-report exception to the compact three-line default: relay the complete adoption table and preserve its machine status, claim boundary, evidence references, and next action.
- Response envelope contract version: v0.7. Compact human responses are the default.
- Ordinary expanded reporting has exactly three triggers: `full_evidence_request`, `owner_decision_required`, and `failed_or_partial`.
- Keep validation commands, counts, and diagnostics under `驗證` or `evidence_refs`; use `注意` only for one decision-relevant limitation.
- If the adoption table is unavailable or cannot be relayed, report `human_readable_adoption_summary: NOT REPORTED`, `update_report_complete=false`, and `completion_claim_allowed=false` with the reason; do not fabricate rows or claim a complete update report.
- When a `mode` is used, keep `mode` event-derived with its `mode_source`; the human projection must not create trust claims or replace the canonical machine envelope.
- Non-trivial feature or bugfix work must not be reported with happy-path-only tests: reproducible bugs need regression tests when feasible, expected values must come from a spec/invariant/fixture rather than copied production logic, mock-only assertions are weak evidence unless observable behavior is asserted, and domain validators need pass/fail fixtures plus an execution harness before fixture evidence is treated as strong.
- `test_signal_quality_audit` output is report-only reviewer evidence; it helps surface weak signals but does not prove industry-grade tests, domain correctness, or enforcement.
- Required external contract surfaces: contract.yaml, governance/framework.lock.json, .git/hooks/pre-commit, .git/hooks/pre-push, .github/copilot-instructions.md.
