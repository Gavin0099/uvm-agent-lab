# Validator Profiles

The benchmark contract separates the v1 validation path from the Phase 2 EDA
path. The profile is explicit in each case so a missing EDA installation cannot
silently become a v1 failure or a synthetic pass.

## LightweightValidator (v1)

Use `validator_profile: lightweight` for Local Coding Agent tasks. The profile
may validate:

- allowed and forbidden file paths;
- real git diff and worktree state;
- Python or other supported syntax checks;
- pytest or focused unit tests;
- lint and deterministic assertions;
- durable build/test/lint/validator evidence.

This is the default for new generic cases when no legacy compile/simulation
acceptance is declared. Legacy UVM cases infer `eda` from their existing
compile/simulation acceptance so their pinned content and evidence hashes stay
stable.

The canonical v1 Python benchmark universe is:

- `AGENT-CODE-001`: bug fix;
- `AGENT-CODE-002`: refactor;
- `AGENT-CODE-003`: add unit-test coverage;
- `AGENT-CODE-004`: configuration change;
- `AGENT-CODE-005`: bounded multi-file change.

The fixture tests are acceptance oracles for the agent. Bug-fix and
configuration cases may intentionally fail on the untouched baseline and are
expected to pass only after the agent change.

## EDAValidator (Phase 2)

Use `validator_profile: eda` for cases that intentionally require:

- Verilator, Icarus, VCS, or another EDA backend;
- SystemVerilog/UVM compile and simulation;
- coverage or simulator-specific logs.

The existing `scripts/eda/`, `EDARouter`, simulator stubs, and `UVM-001` to
`UVM-010` cases remain available under this profile. They are not a v1
GO/NO_GO dependency.

## Evidence Rule

Evidence must match the selected profile. EDA logs are required only for EDA
cases or an explicitly legacy contract; lightweight cases must prove their
static/test path instead.