# Development & Verification Workflows

<!-- governance:reviewer_verified -->

## 🛠️ Routine Developer Commands

### 1. Test Suite & Validation
```bash
# Run all unit and governance integration tests
pytest -v tests/

# Run a specific test module
pytest -v tests/test_coverage_closure.py
pytest -v tests/test_ai_governance_framework_integration.py
```

### 2. Benchmark Execution
```bash
# Run all 10 benchmark cases with multi-turn self-healing runner
python scripts/run_case.py --all --runner multi_turn

# Run a single benchmark case
python scripts/run_case.py --case UVM-001 --runner multi_turn

# Run live evaluation harness with custom model
python scripts/run_live_eval.py --cases UVM-001 UVM-006 --runner multi_turn --mock
```

### 3. Interactive Web Dashboard
```bash
# Launch dashboard server (default port 8000)
python dashboard/server.py --port 8000

# Open browser to http://localhost:8000
```

### 4. Fine-Tuning Dataset Generation
```bash
# Export SFT and DPO datasets from benchmark runs
python dataset_gen/export_dataset.py --output-dir datasets/ --sft-count 50 --dpo-count 50
```

### 5. Dual GV100 vLLM Serving
```bash
# Launch vLLM server with AWQ 4-bit at TP=2
python scripts/serve_vllm.py --model Qwen/Qwen2.5-Coder-32B-Instruct-AWQ --tensor-parallel-size 2 --port 8000

# Or via Docker Compose
docker-compose -f deploy/docker-compose.vllm.yml up -d
```

---

## 🛡️ AI Governance & Quality Gates

### Drift Checks & Baseline Refresh:
```bash
# Run governance drift check
python additional/ai-governance-framework/governance_tools/governance_drift_checker.py --repo .

# Run quickstart smoke test
python additional/ai-governance-framework/governance_tools/quickstart_smoke.py --project-root . --plan PLAN.md --contract contract.yaml --format human

# Refresh governance baseline after modifying contracts or PLAN.md
python additional/ai-governance-framework/governance_tools/adopt_governance.py --target . --framework-root additional/ai-governance-framework --refresh
```

### Git Submodule Management on Windows:
```bash
# Ensure long paths are enabled on Windows to avoid MAX_PATH clone/checkout failures
git config core.longpaths true
git config --global core.longpaths true

# Update submodule pointer
git submodule update --init --recursive
```
