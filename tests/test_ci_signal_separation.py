from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

from scripts import run_case
from scripts.report_coding_readiness import CANONICAL_CASE_IDS, _manifest_summary


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_case_pattern_selects_only_legacy_eda_cases():
    selected = run_case.select_case_paths("benchmarks/cases", "UVM-*.yaml")

    assert [path.stem for path in selected] == [
        f"UVM-{index:03d}" for index in range(1, 11)
    ]
    assert all(path.stem.startswith("UVM-") for path in selected)


def test_all_case_cli_returns_nonzero_for_selected_failure(tmp_path: Path, monkeypatch):
    case_path = tmp_path / "AGENT-CODE-FAIL.yaml"
    case_path.write_text(
        yaml.safe_dump(
            {
                "id": "AGENT-CODE-FAIL",
                "title": "intentional selected failure",
                "description": "The CLI must not report this as green.",
                "validator_profile": "lightweight",
                "task": {"type": "code_change", "goal": "fail closed"},
                "inputs": {"requirement_id": "AGENT-CODE-FAIL"},
                "allowed_paths": ["fixtures/coding_agent/"],
                "forbidden_paths": ["rtl/"],
                "acceptance": {"build": "pass", "test": "pass"},
                "required_evidence": ["requirement_id", "git_diff"],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        run_case,
        "run_benchmark",
        lambda *_args, **_kwargs: {
            "case_id": "AGENT-CODE-FAIL",
            "governance_status": {"passed": True},
            "metrics": {
                "task_success": False,
                "total_score": 0.0,
            },
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_case.py",
            "--all",
            "--cases-dir",
            str(tmp_path),
            "--case-pattern",
            "AGENT-CODE-*.yaml",
            "--output-dir",
            str(tmp_path / "results"),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        run_case.main()

    assert exc_info.value.code == 1


def test_readiness_summary_requires_two_lightweight_pass_manifests():
    class Manifest:
        class Outcome:
            status = "pass"

        class Evidence:
            validator_profile = "lightweight"

        outcome = Outcome()
        evidence = Evidence()

    result = _manifest_summary(
        {
            "manifests": [Manifest(), Manifest()],
            "evidence_class": "synthetic_offline_scaffold",
            "qualification_decision": "NO_GO",
        }
    )

    assert result["status"] == "READY"
    assert result["manifest_count"] == 2
    assert result["validator_profiles"] == ["lightweight", "lightweight"]


def test_readiness_summary_rejects_eda_or_incomplete_manifests():
    class Manifest:
        class Outcome:
            status = "pass"

        class Evidence:
            validator_profile = "eda"

        outcome = Outcome()
        evidence = Evidence()

    result = _manifest_summary({"manifests": [Manifest()]})

    assert result["status"] == "NOT_READY"
    assert CANONICAL_CASE_IDS == (
        "AGENT-CODE-001",
        "AGENT-CODE-002",
        "AGENT-CODE-003",
        "AGENT-CODE-004",
        "AGENT-CODE-005",
    )