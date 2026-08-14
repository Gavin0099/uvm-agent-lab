import json
import yaml
import pytest
from pathlib import Path
from jsonschema import validate, ValidationError


@pytest.fixture
def case_schema():
    schema_path = Path("benchmarks/schema/case_schema.json")
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_all_benchmark_cases_conform_to_schema(case_schema):
    cases_dir = Path("benchmarks/cases")
    case_files = list(cases_dir.glob("*.yaml"))
    assert len(case_files) >= 5, f"Expected at least 5 benchmark cases, found {len(case_files)}"

    for cf in case_files:
        with open(cf, "r", encoding="utf-8") as f:
            case_data = yaml.safe_load(f)
        try:
            validate(instance=case_data, schema=case_schema)
        except ValidationError as e:
            pytest.fail(f"Benchmark case {cf.name} failed schema validation: {e.message}")


def test_case_forbidden_paths_include_rtl():
    cases_dir = Path("benchmarks/cases")
    for cf in cases_dir.glob("*.yaml"):
        with open(cf, "r", encoding="utf-8") as f:
            case_data = yaml.safe_load(f)
        forbidden = [p.replace("\\", "/").strip("/") for p in case_data.get("forbidden_paths", [])]
        assert "rtl" in forbidden or any(f.startswith("rtl") for f in forbidden), f"Case {cf.name} must explicitly forbid rtl/ path"
