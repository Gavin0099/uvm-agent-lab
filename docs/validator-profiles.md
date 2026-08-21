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