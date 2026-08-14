# Gate 0: Benchmark Validation & Schema Conformance

## Objective
Validate that all benchmark definitions represent realistic digital verification tasks, conform strictly to `benchmarks/schema/case_schema.json`, and define explicit governance scopes (`allowed_paths`, `forbidden_paths`, `required_evidence`).

## Verification Command
```bash
pytest tests/test_benchmark_schema.py
```
